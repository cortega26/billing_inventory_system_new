import sqlite3
from contextlib import contextmanager
from decimal import Decimal
from typing import List, Dict, Any, Union, Optional, Tuple
from config import DATABASE_PATH
from utils.system.logger import logger
from utils.decorators import db_operation, handle_exceptions
from utils.exceptions import DatabaseException, ValidationException
import threading
import re


class DatabaseManager:
    """
    A class to manage database operations.
    
    This class provides methods for executing queries, fetching results,
    and managing database connections and transactions.
    
    Attributes:
        _connection (sqlite3.Connection): Shared database connection.
        _lock (threading.Lock): Lock for thread-safe operations.
    """

    _connection = None
    _lock = threading.Lock()

    @classmethod
    @contextmanager
    @handle_exceptions(DatabaseException)
    def get_db_connection(cls):
        """Get a database connection."""
        if cls._connection is None:
            try:
                cls._connection = sqlite3.connect(DATABASE_PATH, timeout=20, check_same_thread=False)
                cls._connection.row_factory = sqlite3.Row

                # Register adapters for Decimal type
                sqlite3.register_adapter(Decimal, lambda d: str(d))
                sqlite3.register_converter("DECIMAL", lambda b: Decimal(b.decode()))

                # Enable foreign key constraints
                cls._connection.execute("PRAGMA foreign_keys = ON")
                logger.debug("New database connection established")
            except sqlite3.Error as e:
                logger.error(f"Database connection error: {e}")
                raise DatabaseException(f"Database connection error: {e}")

        try:
            with cls._lock:
                yield cls._connection
        except sqlite3.Error as e:
            logger.error(f"Database operation error: {e}")
            raise DatabaseException(f"Database operation error: {e}")

    @classmethod
    @db_operation(show_dialog=True)
    def execute_query(cls, query: str, params: Optional[Union[Tuple, List, Dict]] = None) -> sqlite3.Cursor:
        """Execute a single SQL query."""
        logger.debug(f"Executing query: {query}")
        logger.debug(f"Query parameters: {params}")
        
        if params is not None:
            if not isinstance(params, (tuple, list, dict)):
                raise ValidationException(f"Invalid params type: {type(params)}")
            
            # Convert any Decimal values to strings
            if isinstance(params, (tuple, list)):
                params = tuple(str(p) if isinstance(p, Decimal) else p for p in params)
            elif isinstance(params, dict):
                params = {k: str(v) if isinstance(v, Decimal) else v for k, v in params.items()}
            
            logger.debug(f"Sanitized parameters: {params}")

        with cls.get_db_connection() as conn:
            cursor = conn.cursor()
            try:
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)
                conn.commit()
                logger.debug("Query executed successfully")
                return cursor
            except sqlite3.Error as e:
                conn.rollback()
                logger.error(f"Query execution error: {e}")
                raise DatabaseException(f"Query execution error: {e}")

    @classmethod
    @db_operation(show_dialog=True)
    def fetch_one(cls, query: str, params: Optional[Union[Tuple, List, Dict]] = None) -> Optional[Dict[str, Any]]:
        """
        Fetch a single row from the database.

        Args:
            query (str): The SQL query to execute.
            params (Optional[Union[Tuple, List, Dict]]): The parameters for the query.

        Returns:
            Optional[Dict[str, Any]]: A dictionary containing the row data, or None if no row was found.

        Raises:
            DatabaseException: If there's an error fetching the row.
        """
        logger.debug(f"Fetching one row with query: {query}")
        logger.debug(f"Query parameters: {params}")
        
        with cls.get_db_connection() as conn:
            cursor = conn.cursor()
            try:
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)
                row = cursor.fetchone()
                logger.debug(f"Fetched row: {row}")
                return dict(row) if row else None
            except sqlite3.Error as e:
                logger.error(f"Error fetching one row: {e}")
                raise DatabaseException(f"Error fetching one row: {e}")

    @classmethod
    @db_operation(show_dialog=True)
    def fetch_all(cls, query: str, params: Optional[Union[Tuple, List, Dict]] = None) -> List[Dict[str, Any]]:
        """
        Fetch all rows from the database.

        Args:
            query (str): The SQL query to execute.
            params (Optional[Union[Tuple, List, Dict]]): The parameters for the query.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries, each containing a row of data.

        Raises:
            DatabaseException: If there's an error fetching the rows.
        """
        logger.debug(f"Fetching all rows with query: {query}")
        logger.debug(f"Query parameters: {params}")
        
        with cls.get_db_connection() as conn:
            cursor = conn.cursor()
            try:
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)
                rows = cursor.fetchall()
                logger.debug(f"Fetched {len(rows)} rows")
                return [dict(row) for row in rows]
            except sqlite3.Error as e:
                logger.error(f"Error fetching all rows: {e}")
                raise DatabaseException(f"Error fetching all rows: {e}")

    @classmethod
    @db_operation(show_dialog=True)
    def execute_many(cls, query: str, params_list: List[Union[Tuple, List, Dict]]) -> None:
        """
        Execute multiple SQL queries.

        Args:
            query (str): The SQL query to execute.
            params_list (List[Union[Tuple, List, Dict]]): A list of parameter sets for the query.

        Raises:
            DatabaseException: If there's an error executing the queries.
        """
        logger.debug(f"Executing many queries: {query}")
        logger.debug(f"Number of parameter sets: {len(params_list)}")
        
        if not params_list:
            logger.warning("No parameters provided for execute_many")
            return

        with cls.get_db_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.executemany(query, params_list)
                conn.commit()
                logger.debug("Multiple queries executed successfully")
            except sqlite3.Error as e:
                conn.rollback()
                logger.error(f"Error executing many queries: {e}")
                raise DatabaseException(f"Error executing many queries: {e}")

    @classmethod
    def close_connection(cls) -> None:
        """
        Close the database connection.
        
        This method should be called when shutting down the application.
        """
        if cls._connection:
            try:
                cls._connection.close()
                cls._connection = None
                logger.debug("Database connection closed")
            except sqlite3.Error as e:
                logger.error(f"Error closing database connection: {e}")
                raise DatabaseException(f"Error closing database connection: {e}")

    @classmethod
    @db_operation(show_dialog=True)
    def begin_transaction(cls) -> None:
        """Begin a database transaction."""
        with cls.get_db_connection() as conn:
            try:
                conn.execute("BEGIN TRANSACTION")
                logger.debug("Transaction begun")
            except sqlite3.Error as e:
                logger.error(f"Error beginning transaction: {e}")
                raise DatabaseException(f"Error beginning transaction: {e}")

    @classmethod
    @db_operation(show_dialog=True)
    def commit_transaction(cls) -> None:
        """Commit the current database transaction."""
        with cls.get_db_connection() as conn:
            try:
                conn.commit()
                logger.debug("Transaction committed")
            except sqlite3.Error as e:
                logger.error(f"Error committing transaction: {e}")
                raise DatabaseException(f"Error committing transaction: {e}")

    @classmethod
    @db_operation(show_dialog=True)
    def rollback_transaction(cls) -> None:
        """Rollback the current database transaction."""
        with cls.get_db_connection() as conn:
            try:
                conn.rollback()
                logger.debug("Transaction rolled back")
            except sqlite3.Error as e:
                logger.error(f"Error rolling back transaction: {e}")
                raise DatabaseException(f"Error rolling back transaction: {e}")

    @classmethod
    @db_operation(show_dialog=True)
    def fetch_paginated(cls, 
                       query: str, 
                       params: Optional[Union[Tuple, List, Dict]] = None,
                       page: int = 1, 
                       page_size: int = 20) -> Tuple[List[Dict[str, Any]], int]:
        """
        Fetch paginated results for a query.

        Args:
            query (str): The SQL query to execute.
            params (Optional[Union[Tuple, List, Dict]]): The parameters for the query.
            page (int): The page number to fetch (1-indexed).
            page_size (int): The number of items per page.

        Returns:
            Tuple[List[Dict[str, Any]], int]: A tuple containing the list of results and the total count.

        Raises:
            DatabaseException: If there's an error fetching the paginated results.
        """
        count_query = f"SELECT COUNT(*) as total FROM ({query})"
        offset = (page - 1) * page_size
        paginated_query = f"{query} LIMIT {page_size} OFFSET {offset}"

        with cls.get_db_connection() as conn:
            cursor = conn.cursor()
            try:
                if params:
                    total = cursor.execute(count_query, params).fetchone()['total']
                    results = cursor.execute(paginated_query, params).fetchall()
                else:
                    total = cursor.execute(count_query).fetchone()['total']
                    results = cursor.execute(paginated_query).fetchall()
                return [dict(row) for row in results], total
            except sqlite3.Error as e:
                logger.error(f"Error fetching paginated results: {e}")
                raise DatabaseException(f"Error fetching paginated results: {e}")


@db_operation(show_dialog=True)
@handle_exceptions(DatabaseException, show_dialog=True)
def init_db() -> None:
    """
    Initialize the database by creating necessary tables if they don't exist.

    This function creates all required tables with appropriate constraints and indexes.
    It also adds support for custom SQLite functions needed for validation.

    Raises:
        DatabaseException: If there's an error initializing the database.
    """
    with DatabaseManager.get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            # Add REGEXP support for name validation
            conn.create_function('REGEXP', 2, lambda pattern, value: bool(re.match(pattern, value)) if value else True)

            # Create categories table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE
                )
                """
            )

            # Create products table with category_id and barcode
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    category_id INTEGER,
                    cost_price INTEGER NOT NULL,
                    sell_price INTEGER NOT NULL,
                    barcode TEXT UNIQUE,
                    FOREIGN KEY (category_id) REFERENCES categories (id)
                )
                """
            )

            # Create customers table with name field
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS customers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    identifier_9 TEXT NOT NULL UNIQUE,
                    name TEXT,
                    CHECK (name IS NULL OR name REGEXP '^[A-Za-zÁÉÍÓÚÑáéíóúñ ]+$'),
                    CHECK (LENGTH(name) <= 50)
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS customer_identifiers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    customer_id INTEGER,
                    identifier_3or4 TEXT NOT NULL,
                    FOREIGN KEY (customer_id) REFERENCES customers (id) ON DELETE CASCADE,
                    UNIQUE (customer_id, identifier_3or4)
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS sales (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    customer_id INTEGER,
                    date TEXT NOT NULL,
                    total_amount INTEGER NOT NULL,
                    total_profit INTEGER NOT NULL,
                    receipt_id TEXT,
                    FOREIGN KEY (customer_id) REFERENCES customers (id)
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS sale_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sale_id INTEGER,
                    product_id INTEGER,
                    quantity REAL NOT NULL,
                    price INTEGER NOT NULL,
                    profit INTEGER NOT NULL,
                    FOREIGN KEY (sale_id) REFERENCES sales (id) ON DELETE CASCADE,
                    FOREIGN KEY (product_id) REFERENCES products (id)
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS purchases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    supplier TEXT NOT NULL,
                    date TEXT NOT NULL,
                    total_amount INTEGER NOT NULL
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS purchase_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    purchase_id INTEGER,
                    product_id INTEGER,
                    quantity REAL NOT NULL,
                    price INTEGER NOT NULL,
                    FOREIGN KEY (purchase_id) REFERENCES purchases (id) ON DELETE CASCADE,
                    FOREIGN KEY (product_id) REFERENCES products (id)
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS inventory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id INTEGER UNIQUE,
                    quantity REAL NOT NULL DEFAULT 0,
                    FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE CASCADE
                )
                """
            )

            # Add indexes for performance optimization
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_category_id ON products (category_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_barcode ON products (barcode)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_name ON products (name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_customers_identifier_9 ON customers (identifier_9)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_customers_name ON customers (name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sales_customer_id ON sales (customer_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sales_date ON sales (date)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sale_items_sale_id ON sale_items (sale_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sale_items_product_id ON sale_items (product_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_purchase_items_purchase_id ON purchase_items (purchase_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_purchase_items_product_id ON purchase_items (product_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_inventory_product_id ON inventory (product_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sales_receipt_id ON sales (receipt_id)")

            # Enable WAL mode for better concurrent access
            cursor.execute("PRAGMA journal_mode=WAL")
            
            # Enable foreign key constraints
            cursor.execute("PRAGMA foreign_keys=ON")

            conn.commit()
            logger.info("Database initialized successfully")

        except sqlite3.Error as e:
            conn.rollback()
            logger.error(f"Database initialization error: {e}")
            raise DatabaseException(f"Database initialization error: {e}")
