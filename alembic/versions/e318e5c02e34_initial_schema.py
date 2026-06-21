"""Initial schema

Revision ID: e318e5c02e34
Revises:
Create Date: 2026-06-21 16:57:42.140787

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e318e5c02e34"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # SQLite-compatible upgrade logic using safe, idempotent alter statements.
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = insp.get_table_names()

    def add_column_if_not_exists(table_name: str, column: sa.Column):
        columns = [c["name"] for c in insp.get_columns(table_name)]
        if column.name not in columns:
            op.add_column(table_name, column)

    # 1. Ensure audit_log table exists
    if "audit_log" not in tables:
        op.create_table(
            "audit_log",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("operation", sa.String(), nullable=False),
            sa.Column("entity_type", sa.String(), nullable=False),
            sa.Column("entity_id", sa.Integer(), nullable=True),
            sa.Column("actor", sa.String(), nullable=True),
            sa.Column("payload", sa.String(), nullable=True),
            sa.Column(
                "timestamp", sa.DateTime(), nullable=True, server_default=sa.func.now()
            ),
        )

    # 2. Add missing columns to categories
    if "categories" in tables:
        add_column_if_not_exists(
            "categories", sa.Column("created_at", sa.DateTime(), nullable=True)
        )
        add_column_if_not_exists(
            "categories", sa.Column("updated_at", sa.DateTime(), nullable=True)
        )

    # 3. Add missing columns to products
    if "products" in tables:
        add_column_if_not_exists(
            "products",
            sa.Column(
                "is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")
            ),
        )
        add_column_if_not_exists(
            "products", sa.Column("deleted_at", sa.String(), nullable=True)
        )
        add_column_if_not_exists(
            "products", sa.Column("created_at", sa.DateTime(), nullable=True)
        )
        add_column_if_not_exists(
            "products", sa.Column("updated_at", sa.DateTime(), nullable=True)
        )

    # 4. Add missing columns to inventory
    if "inventory" in tables:
        add_column_if_not_exists(
            "inventory", sa.Column("created_at", sa.DateTime(), nullable=True)
        )
        add_column_if_not_exists(
            "inventory", sa.Column("updated_at", sa.DateTime(), nullable=True)
        )

    # 5. Add missing columns to customers
    if "customers" in tables:
        add_column_if_not_exists(
            "customers",
            sa.Column(
                "is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")
            ),
        )
        add_column_if_not_exists(
            "customers", sa.Column("deleted_at", sa.String(), nullable=True)
        )

    # 6. Add missing columns to sales
    if "sales" in tables:
        add_column_if_not_exists(
            "sales",
            sa.Column(
                "status",
                sa.String(),
                nullable=False,
                server_default=sa.text("'confirmed'"),
            ),
        )
        add_column_if_not_exists(
            "sales", sa.Column("created_at", sa.DateTime(), nullable=True)
        )

    # 7. Add missing columns to sale_items
    if "sale_items" in tables:
        add_column_if_not_exists(
            "sale_items", sa.Column("created_at", sa.DateTime(), nullable=True)
        )

    # 8. Add missing columns to purchases
    if "purchases" in tables:
        add_column_if_not_exists(
            "purchases", sa.Column("created_at", sa.DateTime(), nullable=True)
        )

    # 9. Create indexes safely using IF NOT EXISTS
    op.execute("CREATE INDEX IF NOT EXISTS idx_products_barcode ON products(barcode)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_products_category ON products(category_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_customers_identifier_9 ON customers(identifier_9)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_sales_customer_date ON sales(customer_id, date)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_sale_items_sale_product ON sale_items(sale_id, product_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_purchase_items_purchase_product ON purchase_items(purchase_id, product_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_sales_covering ON sales(date, customer_id, total_amount, total_profit)"
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_products_name ON products(name)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_products_is_active ON products(is_active)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_customers_is_active ON customers(is_active)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_audit_log_entity ON audit_log(entity_type, entity_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log(timestamp)"
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_sales_date ON sales(date DESC)")
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_sales_receipt_id ON sales(receipt_id) WHERE receipt_id IS NOT NULL"
    )


def downgrade() -> None:
    """Downgrade schema."""
    pass
