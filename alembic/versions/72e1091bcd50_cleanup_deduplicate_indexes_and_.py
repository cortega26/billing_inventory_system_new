"""cleanup: deduplicate indexes and normalize quantity types

Revision ID: 72e1091bcd50
Revises: e318e5c02e34
Create Date: 2026-08-15 21:15:08.499167

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "72e1091bcd50"
down_revision: str | Sequence[str] | None = "e318e5c02e34"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Converge fresh and legacy databases onto the canonical index set.
    # Indexes are owned by Alembic revisions only (schema.sql is tables-only).
    # Kept indexes are created with IF NOT EXISTS so fresh installs (which
    # only get the initial migration's index set) end with the same set as
    # legacy databases; duplicate and stale indexes are dropped with IF EXISTS
    # so the revision is idempotent on both paths.

    # 1. Create kept indexes that the initial migration does not create.
    op.execute("CREATE INDEX IF NOT EXISTS idx_sales_customer ON sales(customer_id)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_sale_items_composite ON sale_items(sale_id, product_id)"
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_sale_items_sale ON sale_items(sale_id)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_sale_items_product ON sale_items(product_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_purchase_items_purchase ON purchase_items(purchase_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_purchase_items_product ON purchase_items(product_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_inventory_product ON inventory(product_id)"
    )

    # 2. Drop identical-definition duplicates (keep the first of each pair).
    op.execute("DROP INDEX IF EXISTS idx_sale_items_sale_product")
    op.execute("DROP INDEX IF EXISTS idx_sale_items_sale_id")
    op.execute("DROP INDEX IF EXISTS idx_sale_items_product_id")
    op.execute("DROP INDEX IF EXISTS idx_sales_customer_id")
    op.execute("DROP INDEX IF EXISTS idx_sales_date_customer")
    op.execute("DROP INDEX IF EXISTS idx_sales_receipt")
    op.execute("DROP INDEX IF EXISTS idx_inventory_product_id")
    op.execute("DROP INDEX IF EXISTS idx_products_category_id")
    op.execute("DROP INDEX IF EXISTS idx_purchase_items_purchase_id")
    op.execute("DROP INDEX IF EXISTS idx_purchase_items_product_id")

    # 3. Drop the stale index on a column that does not exist.
    op.execute("DROP INDEX IF EXISTS idx_categories_parent_id")

    # 4. Normalize mixed-typed quantity values (legacy writes stored TEXT).
    op.execute(
        "UPDATE sale_items SET quantity = CAST(quantity AS REAL) "
        "WHERE typeof(quantity) = 'text'"
    )
    op.execute(
        "UPDATE purchase_items SET quantity = CAST(quantity AS REAL) "
        "WHERE typeof(quantity) = 'text'"
    )


def downgrade() -> None:
    """Downgrade schema."""
    pass
