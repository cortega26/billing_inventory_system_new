import sqlite3
from config import DATABASE_PATH

def migrate_database():
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    try:
        # Add cost_price and sell_price columns to products table
        cursor.execute('ALTER TABLE products ADD COLUMN cost_price REAL')
        cursor.execute('ALTER TABLE products ADD COLUMN sell_price REAL')

        # Initialize cost_price with the average purchase price
        cursor.execute('''
        UPDATE products
        SET cost_price = (
            SELECT AVG(price)
            FROM purchase_items
            WHERE product_id = products.id
        )
        ''')

        # Initialize sell_price with a default markup (e.g., 20% above cost)
        cursor.execute('UPDATE products SET sell_price = COALESCE(cost_price * 1.2, 0)')

        conn.commit()
        print("Database migration completed successfully.")
    except sqlite3.Error as e:
        conn.rollback()
        print(f"An error occurred: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_database()