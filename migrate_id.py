import sqlite3
from config import DATABASE_PATH

def add_receipt_id_column():
    try:
        # Connect to the database
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        # Execute the ALTER TABLE command
        cursor.execute("ALTER TABLE sales ADD COLUMN receipt_id TEXT;")

        # Commit the changes
        conn.commit()
        print("Successfully added 'receipt_id' column to the sales table.")

    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print("The 'receipt_id' column already exists in the sales table.")
        else:
            print(f"An error occurred: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    finally:
        # Close the connection
        if conn:
            conn.close()

if __name__ == "__main__":
    add_receipt_id_column()