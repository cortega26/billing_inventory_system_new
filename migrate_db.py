import sqlite3
from config import DATABASE_PATH

def migrate_database():
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    try:
        # Create categories table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        )
        ''')

        # Create a new products table with the category_id column
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS new_products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            category_id INTEGER,
            FOREIGN KEY (category_id) REFERENCES categories (id)
        )
        ''')

        # Copy data from the old products table to the new one
        cursor.execute('''
        INSERT INTO new_products (id, name, description)
        SELECT id, name, description FROM products
        ''')

        # Drop the old products table
        cursor.execute('DROP TABLE products')

        # Rename the new products table to products
        cursor.execute('ALTER TABLE new_products RENAME TO products')

        # Create index on category_id
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_products_category_id ON products (category_id)')

        conn.commit()
        print("Database migration completed successfully.")
    except sqlite3.Error as e:
        conn.rollback()
        print(f"An error occurred: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_database()