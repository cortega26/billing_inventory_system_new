"""Database initialization and management."""

from database.database_manager import DatabaseManager
from database.migrations import run_migrations
from utils.exceptions import DatabaseException

__all__ = ["init_db", "DatabaseManager"]


def init_db(db_path: str = "billing_inventory.db"):
    """Initialize the database connection and create tables."""
    try:
        DatabaseManager.initialize(db_path)

        # Initialize schema from SQL file
        import os

        schema_path = "schema.sql"
        if os.path.exists(schema_path):
            with open(schema_path, "r") as f:
                schema_sql = f.read()
                with DatabaseManager.get_db_connection() as conn:
                    conn.executescript(schema_sql)
        else:
            # Fallback or strict error?
            # If running from different CWD, might miss it.
            # Try absolute path relative to project root?
            # For now assume CWD is project root as per standard run.
            pass

        # Check if migration is needed
        with DatabaseManager.transaction():
            cursor = DatabaseManager._get_cursor()

            cursor.execute(
                """
                SELECT sql FROM sqlite_master 
                WHERE type='table' AND name='customers'
            """
            )

            result = cursor.fetchone()
            if result and "REGEXP" in result[0]:
                # Migration needed
                cursor.execute(
                    """
                    CREATE TEMPORARY TABLE customers_backup AS 
                    SELECT * FROM customers
                """
                )

                cursor.execute("DROP TABLE customers")

                cursor.execute(
                    """
                    CREATE TABLE customers (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        identifier_9 TEXT NOT NULL UNIQUE COLLATE NOCASE,
                        name TEXT,
                        CHECK (LENGTH(identifier_9) = 9),
                        CHECK (SUBSTR(identifier_9, 1, 1) = '9'),
                        CHECK (identifier_9 NOT GLOB '*[^0-9]*'),
                        CHECK (name IS NULL OR LENGTH(name) <= 50)
                    )
                """
                )

                cursor.execute(
                    """
                    INSERT INTO customers (id, identifier_9, name)
                    SELECT id, identifier_9, name 
                    FROM customers_backup
                    WHERE LENGTH(identifier_9) = 9 
                    AND SUBSTR(identifier_9, 1, 1) = '9'
                    AND identifier_9 NOT GLOB '*[^0-9]*'
                """
                )

                cursor.execute("DROP TABLE customers_backup")

        # Run migrations for indexes
        run_migrations()

    except Exception as e:
        raise DatabaseException(f"Failed to initialize database: {str(e)}")
