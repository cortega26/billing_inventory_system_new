"""add customer balance and credit limit columns

Revision ID: 652b05c0c11e
Revises: 72e1091bcd50
Create Date: 2026-08-16 00:00:00.000000

The live El Rincón DB already carries `current_balance` and `credit_limit`
columns on `customers` that no repo schema source defined. This revision adds
them to the repo's migration chain. The inspector guard makes the revision a
no-op on databases that already have the columns (the live DB) and additive on
fresh/pre-024 databases.

2026-08-18 fix: the SQLite batch recreate used to DROP the old `customers`
table while the connection had `PRAGMA foreign_keys = ON`, which cascade-
deleted every `customer_identifiers` row (ON DELETE CASCADE). FK enforcement
is now disabled around the recreation (regression test:
test_pre_024_migration_preserves_customer_identifiers).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "652b05c0c11e"
down_revision: str | Sequence[str] | None = "72e1091bcd50"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add customer credit columns; no-op when they already exist (live DB)."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {c["name"] for c in inspector.get_columns("customers")}

    if "current_balance" in existing and "credit_limit" in existing:
        return

    # SQLite batch mode recreates the table via DROP + CREATE. With
    # PRAGMA foreign_keys = ON (DatabaseManager startup pragma), the DROP
    # fires ON DELETE CASCADE on child tables (customer_identifiers),
    # silently wiping their rows. Disable FK enforcement around the
    # recreation — the standard Alembic recipe for SQLite batch mode.
    bind.exec_driver_sql("PRAGMA foreign_keys = OFF")
    try:
        with op.batch_alter_table("customers") as batch_op:
            if "current_balance" not in existing:
                batch_op.add_column(
                    sa.Column(
                        "current_balance",
                        sa.Integer(),
                        nullable=False,
                        server_default=sa.text("0"),
                    )
                )
            if "credit_limit" not in existing:
                batch_op.add_column(
                    sa.Column(
                        "credit_limit",
                        sa.Integer(),
                        nullable=False,
                        server_default=sa.text("50000"),
                    )
                )
                batch_op.create_check_constraint(
                    "check_customer_credit_limit", "credit_limit >= 0"
                )
    finally:
        bind.exec_driver_sql("PRAGMA foreign_keys = ON")


def downgrade() -> None:
    """Drop the columns if present."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {c["name"] for c in inspector.get_columns("customers")}

    if "credit_limit" not in existing and "current_balance" not in existing:
        return

    bind.exec_driver_sql("PRAGMA foreign_keys = OFF")
    try:
        with op.batch_alter_table("customers") as batch_op:
            if "credit_limit" in existing:
                batch_op.drop_constraint("check_customer_credit_limit", type_="check")
                batch_op.drop_column("credit_limit")
            if "current_balance" in existing:
                batch_op.drop_column("current_balance")
    finally:
        bind.exec_driver_sql("PRAGMA foreign_keys = ON")
