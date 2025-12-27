"""Database migrations for performance optimization."""

from database.database_manager import DatabaseManager
from utils.exceptions import DatabaseException
from utils.system.logger import logger


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
        "CREATE INDEX IF NOT EXISTS idx_sales_date ON sales(date DESC)",
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

            # Enable WAL mode and optimize performance
            pragmas = [
                "PRAGMA journal_mode=WAL",
                "PRAGMA synchronous=NORMAL",
                "PRAGMA cache_size=2000",
                "PRAGMA temp_store=MEMORY",
                "PRAGMA foreign_keys=ON",
                "PRAGMA auto_vacuum=INCREMENTAL",
                "PRAGMA mmap_size=268435456",  # 256MB memory mapping
            ]

            for pragma in pragmas:
                try:
                    DatabaseManager.execute_query(pragma)
                    logger.info(f"Applied optimization: {pragma}")
                except Exception as pragma_error:
                    logger.warning(
                        f"Failed to apply pragma {pragma}: {str(pragma_error)}"
                    )

        logger.info("All performance indexes and optimizations completed successfully")

    except Exception as e:
        logger.error(f"Failed to create indexes: {str(e)}")
        raise DatabaseException(f"Failed to create indexes: {str(e)}")


def run_migrations():
    """Run all database migrations."""
    try:
        add_performance_indexes()
        logger.info("Database migrations completed successfully")
        return True
    except Exception as e:
        logger.error(f"Migration failed: {str(e)}")
        raise DatabaseException(f"Migration failed: {str(e)}") from e
