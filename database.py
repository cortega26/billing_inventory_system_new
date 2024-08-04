import sqlite3
from contextlib import contextmanager
from typing import List, Dict, Any, Union, Optional, Tuple
from config import DATABASE_PATH
from utils.logger import logger

def validate_query_params(params: Any) -> None:
    if params is None:
        return
    if isinstance(params, (tuple, list)):
        for param in params:
            if not isinstance(param, (str, int, float, type(None))):
                raise ValueError(f"Invalid parameter type: {type(param)}")
    elif isinstance(params, dict):
        for value in params.values():
            if not isinstance(value, (str, int, float, type(None))):
                raise ValueError(f"Invalid parameter type: {type(value)}")
    else:
        raise ValueError(f"Invalid params type: {type(params)}")

class DatabaseManager:
    @staticmethod
    @contextmanager
    def get_db_connection():
        conn = None
        try:
            conn = sqlite3.connect(DATABASE_PATH, timeout=20)
            conn.row_factory = sqlite3.Row
            logger.debug("Database connection established")
            yield conn
        except sqlite3.Error as e:
            logger.error(f"Database connection error: {e}")
            raise
        finally:
            if conn:
                conn.close()
                logger.debug("Database connection closed")

    @classmethod
    def execute_query(cls, query: str, params: Optional[Union[Tuple, List, Dict]] = None) -> sqlite3.Cursor:
        logger.debug(f"Executing query: {query}")
        logger.debug(f"Query parameters: {params}")
        validate_query_params(params)
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
                raise

    @classmethod
    def fetch_one(cls, query: str, params: Optional[Union[Tuple, List, Dict]] = None) -> Optional[Dict[str, Any]]:
        logger.debug(f"Fetching one row with query: {query}")
        logger.debug(f"Query parameters: {params}")
        with cls.get_db_connection() as conn:
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            row = cursor.fetchone()
            logger.debug(f"Fetched row: {row}")
            return dict(row) if row else None

    @classmethod
    def fetch_all(cls, query: str, params: Optional[Union[Tuple, List, Dict]] = None) -> List[Dict[str, Any]]:
        logger.debug(f"Fetching all rows with query: {query}")
        logger.debug(f"Query parameters: {params}")
        with cls.get_db_connection() as conn:
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            rows = cursor.fetchall()
            logger.debug(f"Fetched {len(rows)} rows")
            return [dict(row) for row in rows]

def init_db():
    with DatabaseManager.get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            # Create categories table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            )
            ''')

            # Create products table with category_id
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                category_id INTEGER,
                cost_price REAL,
                sell_price REAL,
                FOREIGN KEY (category_id) REFERENCES categories (id)
            )
            ''')

            cursor.execute('''
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                identifier_9 TEXT NOT NULL UNIQUE
            )
            ''')
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS customer_identifiers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER,
                identifier_3or4 TEXT NOT NULL,
                FOREIGN KEY (customer_id) REFERENCES customers (id),
                UNIQUE (customer_id, identifier_3or4)
            )
            ''')
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS sales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER,
                date TEXT NOT NULL,
                total_amount REAL NOT NULL,
                FOREIGN KEY (customer_id) REFERENCES customers (id)
            )
            ''')
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS sale_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sale_id INTEGER,
                product_id INTEGER,
                quantity INTEGER NOT NULL,
                price REAL NOT NULL,
                FOREIGN KEY (sale_id) REFERENCES sales (id),
                FOREIGN KEY (product_id) REFERENCES products (id)
            )
            ''')
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                supplier TEXT NOT NULL,
                date TEXT NOT NULL,
                total_amount REAL NOT NULL
            )
            ''')
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS purchase_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                purchase_id INTEGER,
                product_id INTEGER,
                quantity INTEGER NOT NULL,
                price REAL NOT NULL,
                FOREIGN KEY (purchase_id) REFERENCES purchases (id),
                FOREIGN KEY (product_id) REFERENCES products (id)
            )
            ''')
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER UNIQUE,
                quantity INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (product_id) REFERENCES products (id)
            )
            ''')

            # Add indexes
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_products_category_id ON products (category_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_customers_identifier_9 ON customers (identifier_9)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_sales_customer_id ON sales (customer_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_sale_items_sale_id ON sale_items (sale_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_sale_items_product_id ON sale_items (product_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_purchase_items_purchase_id ON purchase_items (purchase_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_purchase_items_product_id ON purchase_items (product_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_inventory_product_id ON inventory (product_id)')

            conn.commit()
            logger.info("Database initialized successfully")
        except sqlite3.Error as e:
            conn.rollback()
            logger.error(f"Database initialization error: {e}")
            raise