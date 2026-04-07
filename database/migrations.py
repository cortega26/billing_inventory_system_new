"""Database migrations for performance optimization."""

from database.database_manager import DatabaseManager
from utils.exceptions import DatabaseException
from utils.system.logger import logger


SCHEMA_ALTERATIONS = [
    # [M-1] Sales status (cancel without deleting)
    "ALTER TABLE sales ADD COLUMN status TEXT NOT NULL DEFAULT 'confirmed'",
    # [M-2] Record insertion timestamps (separate from the business date)
    "ALTER TABLE sales ADD COLUMN created_at TEXT NOT NULL DEFAULT '1970-01-01 00:00:00'",
    "ALTER TABLE sale_items ADD COLUMN created_at TEXT NOT NULL DEFAULT '1970-01-01 00:00:00'",
    "ALTER TABLE purchases ADD COLUMN created_at TEXT NOT NULL DEFAULT '1970-01-01 00:00:00'",
    # [M-3] Soft-delete support for business entities
    "ALTER TABLE customers ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1",
    "ALTER TABLE customers ADD COLUMN deleted_at TEXT",
    "ALTER TABLE products ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1",
    "ALTER TABLE products ADD COLUMN deleted_at TEXT",
    """
    CREATE TRIGGER IF NOT EXISTS trg_sales_created_at
    AFTER INSERT ON sales
    WHEN NEW.created_at = '1970-01-01 00:00:00'
    BEGIN
        UPDATE sales SET created_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END;
    """,
    """
    CREATE TRIGGER IF NOT EXISTS trg_sale_items_created_at
    AFTER INSERT ON sale_items
    WHEN NEW.created_at = '1970-01-01 00:00:00'
    BEGIN
        UPDATE sale_items SET created_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END;
    """,
    """
    CREATE TRIGGER IF NOT EXISTS trg_purchases_created_at
    AFTER INSERT ON purchases
    WHEN NEW.created_at = '1970-01-01 00:00:00'
    BEGIN
        UPDATE purchases SET created_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END;
    """,
]


def _log_schema_migration(sql: str) -> None:
    if "ADD COLUMN" in sql:
        col = sql.split("ADD COLUMN")[1].split()[0]
        table = sql.split("ALTER TABLE")[1].split()[0]
        logger.info(f"Added column '{col}' to '{table}'")
        return
    logger.info("Executed supplementary migration step")


def _execute_schema_migration(sql: str) -> None:
    try:
        DatabaseManager.execute_query(sql)
        _log_schema_migration(sql)
    except Exception as e:
        if "duplicate column name" in str(e).lower():
            return
        raise DatabaseException(f"Column migration failed: {str(e)}") from e


def add_performance_indexes():
    """Add indexes for query optimization."""
    indexes = [
        # Existing indexes
        "CREATE INDEX IF NOT EXISTS idx_products_barcode ON products(barcode)",
        "CREATE INDEX IF NOT EXISTS idx_products_category ON products(category_id)",
        "CREATE INDEX IF NOT EXISTS idx_customers_identifier_9 ON customers(identifier_9)",
        "CREATE INDEX IF NOT EXISTS idx_customer_identifiers_3or4 ON customer_identifiers(identifier_3or4)",
        "CREATE INDEX IF NOT EXISTS idx_customer_identifiers_customer ON customer_identifiers(customer_id)",
        # New composite indexes for performance
        "CREATE INDEX IF NOT EXISTS idx_sales_customer_date ON sales(customer_id, date)",
        "CREATE INDEX IF NOT EXISTS idx_sale_items_sale_product ON sale_items(sale_id, product_id)",
        "CREATE INDEX IF NOT EXISTS idx_purchase_items_purchase_product ON purchase_items(purchase_id, product_id)",
        # Covering index for common queries
        "CREATE INDEX IF NOT EXISTS idx_sales_covering ON sales(date, customer_id, total_amount, total_profit)",
        # Additional indexes for foreign key optimization
        # New indexes for performance
        "CREATE INDEX IF NOT EXISTS idx_products_name ON products(name COLLATE NOCASE)",
        "CREATE INDEX IF NOT EXISTS idx_products_is_active ON products(is_active)",
        "CREATE INDEX IF NOT EXISTS idx_customers_is_active ON customers(is_active)",
        "CREATE INDEX IF NOT EXISTS idx_audit_log_entity ON audit_log(entity_type, entity_id)",
        "CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log(timestamp)",
        "CREATE INDEX IF NOT EXISTS idx_sales_date ON sales(date DESC)",
        # Unique constraint on receipt_id (NULL values excluded — each non-null must be unique)
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_sales_receipt_id ON sales(receipt_id) WHERE receipt_id IS NOT NULL",
    ]

    try:
        with DatabaseManager.transaction():
            for index_sql in indexes:
                try:
                    DatabaseManager.execute_query(index_sql)
                    logger.info(
                        f"Created index: {index_sql.split('idx_')[1].split(' ')[0]}"
                    )
                except Exception as index_error:
                    logger.error(f"Failed to create index: {str(index_error)}")
                    raise DatabaseException(
                        f"Index creation failed: {str(index_error)}"
                    )
        logger.info("All performance indexes completed successfully")

    except Exception as e:
        logger.error(f"Failed to create indexes: {str(e)}")
        raise DatabaseException(f"Failed to create indexes: {str(e)}")


def add_schema_columns():
    """Add new columns to existing databases (idempotent — safe to run repeatedly)."""
    try:
        with DatabaseManager.transaction():
            for sql in SCHEMA_ALTERATIONS:
                _execute_schema_migration(sql)
        logger.info("Schema column migrations completed successfully")
    except DatabaseException:
        raise
    except Exception as e:
        logger.error(f"Failed to add schema columns: {str(e)}")
        raise DatabaseException(f"Failed to add schema columns: {str(e)}") from e


def create_audit_log_table():
    """Create audit log table for persistent mutation tracing."""
    statements = [
        """
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            operation TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id INTEGER,
            actor TEXT,
            payload TEXT,
            timestamp TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_audit_log_entity ON audit_log(entity_type, entity_id)",
        "CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log(timestamp)",
    ]

    try:
        with DatabaseManager.transaction():
            for sql in statements:
                DatabaseManager.execute_query(sql)
        logger.info("Audit log migrations completed successfully")
    except Exception as e:
        logger.error(f"Failed to create audit log table: {str(e)}")
        raise DatabaseException(f"Failed to create audit log table: {str(e)}") from e


def run_migrations():
    """Run all database migrations."""
    try:
        create_audit_log_table()
        add_schema_columns()
        add_performance_indexes()
        logger.info("Database migrations completed successfully")
        return True
    except Exception as e:
        logger.error(f"Migration failed: {str(e)}")
        raise DatabaseException(f"Migration failed: {str(e)}") from e
