"""Schema drift check: verifies that a fresh init_db() database matches SQLModel.metadata.

Runs the exact app bootstrap (schema.sql + Alembic migrations) on a scratch database
and compares table/column names in BOTH directions and index sets against the model
metadata. Fails with a diff report if they diverge, so CI catches model changes
without a matching migration or schema.sql update.

Indexes are owned by Alembic migrations only (schema.sql is tables-only). The
canonical set below is the post-cleanup set from the index deduplication revision.

Usage:
    python scripts/check_schema_drift.py
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("DATABASE_NAME", "ci_drift_check.db")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from sqlmodel import SQLModel  # noqa: E402

import models.audit_log  # noqa: F401, E402
import models.category  # noqa: F401, E402
import models.customer  # noqa: F401, E402
import models.inventory  # noqa: F401, E402
import models.product  # noqa: F401, E402
import models.purchase  # noqa: F401, E402
import models.sale  # noqa: F401, E402
from database import init_db  # noqa: E402
from database.database_manager import DatabaseManager  # noqa: E402

EXCLUDED_TABLES = {
    "sqlite_sequence",
    "alembic_version",
    "test_table",
    "customer_payments",
}

# Canonical index set per table (post deduplication). Indexes are migration-owned.
# Revisit when models add/remove index=True or unique=True.
CANONICAL_INDEXES: dict[str, set[str]] = {
    "audit_log": {"idx_audit_log_entity", "idx_audit_log_timestamp"},
    "customers": {"idx_customers_identifier_9", "idx_customers_is_active"},
    "products": {
        "idx_products_barcode",
        "idx_products_category",
        "idx_products_is_active",
        "idx_products_name",
    },
    "purchase_items": {
        "idx_purchase_items_purchase_product",
        "idx_purchase_items_purchase",
        "idx_purchase_items_product",
    },
    "sale_items": {
        "idx_sale_items_composite",
        "idx_sale_items_product",
        "idx_sale_items_sale",
    },
    "sales": {
        "idx_sales_covering",
        "idx_sales_customer",
        "idx_sales_customer_date",
        "idx_sales_date",
        "idx_sales_receipt_id",
    },
    "inventory": {"idx_inventory_product"},
    "categories": set(),
}

# SQLModel-generated indexes (Field(index=True)); never part of the canonical set.
EXCLUDED_INDEXES = {
    "ix_categories_name",
    "ix_customers_identifier_9",
    "ix_inventory_product_id",
}


def _index_names(conn, table: str) -> set[str]:
    rows = conn.execute(
        "SELECT * FROM pragma_index_list(?)", (table,)
    ).fetchall()
    return {
        row["name"]
        for row in rows
        if not row["name"].startswith("sqlite_autoindex_")
        and row["name"] not in EXCLUDED_INDEXES
    }


def main() -> int:
    init_db()

    metadata_tables = {
        name for name in SQLModel.metadata.tables if name not in EXCLUDED_TABLES
    }
    problems = []

    with DatabaseManager.get_db_connection() as conn:
        db_tables = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
            if row["name"] not in EXCLUDED_TABLES
        }

        for table in sorted(metadata_tables - db_tables):
            problems.append(f"table in metadata but missing from database: {table}")
        for table in sorted(db_tables - metadata_tables):
            problems.append(f"table in database but missing from metadata: {table}")

        for table in sorted(metadata_tables & db_tables):
            db_columns = {
                row["name"]
                for row in conn.execute(
                    "SELECT * FROM pragma_table_info(?)", (table,)
                )
            }
            metadata_columns = {
                column.key for column in SQLModel.metadata.tables[table].columns
            }
            for name in sorted(metadata_columns - db_columns):
                problems.append(
                    f"column in metadata but missing from database: {table}.{name}"
                )
            for name in sorted(db_columns - metadata_columns):
                problems.append(
                    f"column in database but missing from metadata: {table}.{name}"
                )

            canonical = CANONICAL_INDEXES.get(table)
            if canonical is None:
                continue
            db_indexes = _index_names(conn, table)
            for name in sorted(canonical - db_indexes):
                problems.append(f"index missing from database: {table}.{name}")
            for name in sorted(db_indexes - canonical):
                problems.append(f"unexpected index in database: {table}.{name}")

    if problems:
        print("SCHEMA DRIFT DETECTED:")
        for problem in problems:
            print(f"  - {problem}")
        print("Update schema.sql and/or add an Alembic migration to match models/.")
        return 1

    print("Schema drift check passed: metadata matches a fresh init_db() database.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
