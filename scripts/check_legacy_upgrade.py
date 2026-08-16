"""Legacy database upgrade check.

Builds a "legacy-shaped" database (schema.sql tables without the columns that
the initial Alembic migration adds), seeds it with mixed-typed quantity values,
then runs the full app bootstrap (init_db -> migrations) and asserts that:

- every stripped column now exists,
- the canonical index set exists (and no stray indexes remain),
- quantity columns contain no TEXT values.

Usage:
    python scripts/check_legacy_upgrade.py
"""

import os
import re
import sqlite3
import sys
from pathlib import Path

os.environ.setdefault("DATABASE_NAME", "legacy_upgrade_check.db")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from check_schema_drift import CANONICAL_INDEXES  # noqa: E402

from config import DATABASE_PATH  # noqa: E402
from database import init_db  # noqa: E402

# Columns the initial migration adds on top of schema.sql. Stripping them
# reproduces the legacy install shape; the migration must re-add them.
STRIP_COLUMNS: dict[str, set[str]] = {
    "categories": {"created_at", "updated_at"},
    "products": {"is_active", "deleted_at", "created_at", "updated_at"},
    "inventory": {"created_at", "updated_at"},
    "customers": {"is_active", "deleted_at"},
    "sales": {"status", "created_at"},
    "sale_items": {"created_at"},
    "purchases": {"created_at"},
}

DB_FILENAME = os.environ["DATABASE_NAME"]


def _load_schema_statements() -> list[str]:
    schema_path = PROJECT_ROOT / "schema.sql"
    with open(schema_path) as f:
        schema_sql = "\n".join(
            line for line in f.readlines() if not line.lstrip().startswith("--")
        )
    return [s.strip() for s in schema_sql.split(";") if s.strip()]


def _strip_columns(statements: list[str]) -> list[str]:
    """Remove the migration-added column lines from each CREATE TABLE block."""
    stripped = []
    for statement in statements:
        if not statement.upper().startswith("CREATE TABLE"):
            stripped.append(statement)
            continue
        header, _, body = statement.partition("(")
        table_match = re.match(r"CREATE TABLE IF NOT EXISTS (\w+)", header)
        if not table_match:
            stripped.append(statement)
            continue
        table = table_match.group(1)
        strip_set = STRIP_COLUMNS.get(table, set())
        kept_lines = []
        for line in body.splitlines():
            column_name = line.strip().split()[0].strip("`\"'") if line.strip() else ""
            if column_name in strip_set:
                strip_set.discard(column_name)
                continue
            kept_lines.append(line)
        for missing in sorted(strip_set):
            print(f"WARNING: strip column {table}.{missing} not found; continuing")
        rebuilt = f"{header}({''.join(kept_lines)}"
        stripped.append(re.sub(r",\s*\)", ")", rebuilt))
    return stripped


def _build_legacy_db() -> None:
    statements = _strip_columns(_load_schema_statements())
    if DB_FILENAME in ("", "billing_inventory.db"):
        raise SystemExit("Refusing to build legacy DB over the real database")
    db_path = PROJECT_ROOT / DB_FILENAME
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(db_path)
    for statement in statements:
        conn.execute(statement)
    # Seed mixed-typed quantities so the normalization step is exercised.
    conn.execute(
        "INSERT INTO sale_items (sale_id, product_id, quantity, price, profit) "
        "VALUES (1, 1, '2.500', 100, 10)"
    )
    conn.execute(
        "INSERT INTO purchase_items (purchase_id, product_id, quantity, price) "
        "VALUES (1, 1, '3.000', 50)"
    )
    conn.commit()
    conn.close()


def _assert_columns_restored() -> list[str]:
    problems = []
    conn = sqlite3.connect(DATABASE_PATH)
    for table, columns in STRIP_COLUMNS.items():
        actual = {
            row[1]
            for row in conn.execute(
                "SELECT * FROM pragma_table_info(?)", (table,)
            ).fetchall()
        }
        for column in sorted(columns):
            if column not in actual:
                problems.append(f"column not restored by migration: {table}.{column}")
    conn.close()
    return problems


def _assert_indexes() -> list[str]:
    problems = []
    conn = sqlite3.connect(DATABASE_PATH)
    for table, canonical in CANONICAL_INDEXES.items():
        actual = {
            row[1]
            for row in conn.execute(
                "SELECT * FROM pragma_index_list(?)", (table,)
            ).fetchall()
            if not row[1].startswith("sqlite_autoindex_")
        }
        for name in sorted(canonical - actual):
            problems.append(f"canonical index missing after upgrade: {table}.{name}")
        for name in sorted(actual - canonical):
            problems.append(f"unexpected index after upgrade: {table}.{name}")
    conn.close()
    return problems


def _assert_quantity_types() -> list[str]:
    problems = []
    conn = sqlite3.connect(DATABASE_PATH)
    for table in ("sale_items", "purchase_items"):
        # table ∈ hardcoded tuple, not user input — identifiers can't be bound
        rows = conn.execute(
            f"SELECT typeof(quantity), COUNT(*) FROM {table} "  # nosec B608
            "GROUP BY typeof(quantity)"
        ).fetchall()
        for type_name, count in rows:
            if type_name == "text":
                problems.append(
                    f"{table}.quantity still stores {count} TEXT value(s) after upgrade"
                )
    conn.close()
    return problems


def main() -> int:
    _build_legacy_db()
    init_db()

    problems = _assert_columns_restored() + _assert_indexes() + _assert_quantity_types()
    if problems:
        print("LEGACY UPGRADE CHECK FAILED:")
        for problem in problems:
            print(f"  - {problem}")
        return 1

    print("Legacy upgrade check passed: schema.sql-shaped DB upgrades cleanly.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
