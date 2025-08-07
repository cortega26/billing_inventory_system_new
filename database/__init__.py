from utils.exceptions import DatabaseException
from database.database_manager import DatabaseManager

__all__ = ['init_db', 'DatabaseManager']


def init_db(db_path: str = "billing_inventory.db"):
    """Initialize the database connection and create tables."""
    try:
        DatabaseManager.initialize(db_path)

        # First, backup existing data
        backup_query = """
        CREATE TEMPORARY TABLE customers_backup AS 
        SELECT id, identifier_9, name 
        FROM customers;
        """

        # Drop old table
        drop_query = "DROP TABLE IF EXISTS customers;"

        # Create new table without REGEXP
        create_query = """
        CREATE TABLE customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            identifier_9 TEXT NOT NULL UNIQUE COLLATE NOCASE,
            name TEXT,
            CHECK (LENGTH(identifier_9) = 9),
            CHECK (identifier_9 GLOB '9[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]'),
            CHECK (SUBSTR(identifier_9, 1, 1) = '9'),
            CHECK (name IS NULL OR LENGTH(name) <= 50)
        );
        """

        migration_query = """
        -- Backup existing data
        CREATE TABLE customers_backup AS SELECT * FROM customers;

        -- Drop old table
        DROP TABLE customers;

        -- Create new table with correct validation
        CREATE TABLE customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            identifier_9 TEXT NOT NULL UNIQUE COLLATE NOCASE,
            name TEXT,
            CHECK (LENGTH(identifier_9) = 9),
            CHECK (SUBSTR(identifier_9, 1, 1) = '9'),
            CHECK (identifier_9 NOT GLOB '*[^0-9]*'),
            CHECK (name IS NULL OR LENGTH(name) <= 50)
        );

        -- Restore valid data
        INSERT INTO customers (id, identifier_9, name)
        SELECT id, identifier_9, name 
        FROM customers_backup
        WHERE LENGTH(identifier_9) = 9 
        AND SUBSTR(identifier_9, 1, 1) = '9'
        AND identifier_9 NOT GLOB '*[^0-9]*';

        -- Drop backup
        DROP TABLE customers_backup;
        """

        # Restore data
        restore_query = """
        INSERT INTO customers (id, identifier_9, name)
        SELECT id, identifier_9, name FROM customers_backup;
        """

        with DatabaseManager.transaction():
            cursor = DatabaseManager._get_cursor()
            cursor.executescript(backup_query)
            cursor.executescript(drop_query)
            cursor.executescript(create_query)
            cursor.executescript(restore_query)

    except Exception as e:
        raise DatabaseException(f"Failed to initialize database: {str(e)}")
