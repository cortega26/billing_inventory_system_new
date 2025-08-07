"""Database migrations for performance optimization."""

from database_manager import DatabaseManager
from utils.system.logger import logger


def add_performance_indexes():
    """Add indexes for query optimization."""
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_products_barcode ON products(barcode)",
        "CREATE INDEX IF NOT EXISTS idx_products_category ON products(category_id)",
        "CREATE INDEX IF NOT EXISTS idx_customers_identifier_9 ON customers(identifier_9)",
        "CREATE INDEX IF NOT EXISTS idx_customer_identifiers_3or4 ON customer_identifiers(identifier_3or4)",
        "CREATE INDEX IF NOT EXISTS idx_customer_identifiers_customer ON customer_identifiers(customer_id)",
        "CREATE INDEX IF NOT EXISTS idx_sales_date ON sales(date)",
        "CREATE INDEX IF NOT EXISTS idx_sales_customer ON sales(customer_id)",
        "CREATE INDEX IF NOT EXISTS idx_sales_receipt ON sales(receipt_id)",
        "CREATE INDEX IF NOT EXISTS idx_sale_items_sale ON sale_items(sale_id)",
        "CREATE INDEX IF NOT EXISTS idx_sale_items_product ON sale_items(product_id)",
        "CREATE INDEX IF NOT EXISTS idx_purchases_date ON purchases(date)",
        "CREATE INDEX IF NOT EXISTS idx_purchase_items_purchase ON purchase_items(purchase_id)",
        "CREATE INDEX IF NOT EXISTS idx_purchase_items_product ON purchase_items(product_id)",
        "CREATE INDEX IF NOT EXISTS idx_inventory_product ON inventory(product_id)",
    ]

    try:
        with DatabaseManager.transaction():
            for index_sql in indexes:
                DatabaseManager.execute_query(index_sql)
                logger.info(
                    f"Created index: {index_sql.split('idx_')[1].split(' ')[0]}")

        # Enable WAL mode for better concurrency
        DatabaseManager.execute_query("PRAGMA journal_mode=WAL")
        DatabaseManager.execute_query("PRAGMA synchronous=NORMAL")

        logger.info("All performance indexes created successfully")

    except Exception as e:
        logger.error(f"Failed to create indexes: {str(e)}")
        raise


def run_migrations():
    """Run all database migrations."""
    add_performance_indexes()
    logger.info("Database migrations completed successfully")
    return True
