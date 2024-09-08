import sqlite3
from config import DATABASE_PATH
from utils.system.logger import logger

def migrate_profits():
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    try:
        # Step 1: Add new columns if they don't exist
        cursor.execute("PRAGMA table_info(sales)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'total_profit' not in columns:
            cursor.execute("ALTER TABLE sales ADD COLUMN total_profit REAL DEFAULT 0")

        cursor.execute("PRAGMA table_info(sale_items)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'profit' not in columns:
            cursor.execute("ALTER TABLE sale_items ADD COLUMN profit REAL DEFAULT 0")

        # Step 2: Calculate and update profits for each sale item
        cursor.execute("""
            UPDATE sale_items
            SET profit = (price - (SELECT cost_price FROM products WHERE products.id = sale_items.product_id)) * quantity
            WHERE profit = 0
        """)

        # Step 3: Calculate and update total profits for each sale
        cursor.execute("""
            UPDATE sales
            SET total_profit = (
                SELECT COALESCE(SUM(profit), 0)
                FROM sale_items
                WHERE sale_items.sale_id = sales.id
            )
            WHERE total_profit = 0
        """)

        conn.commit()
        logger.info("Profit migration completed successfully")

    except sqlite3.Error as e:
        conn.rollback()
        logger.error(f"An error occurred during profit migration: {str(e)}")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_profits()
