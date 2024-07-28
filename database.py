import sqlite3
from contextlib import contextmanager
from typing import List, Dict, Any, Union, Optional
from config import DATABASE_PATH
from utils.logger import logger

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
    def execute_query(cls, query: str, params: Optional[Union[tuple, List, Dict]] = None) -> sqlite3.Cursor:
        logger.debug(f"Executing query: {query}")
        logger.debug(f"Query parameters: {params}")
        with cls.get_db_connection() as conn:
            cursor = conn.cursor()
            try:
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)
                conn.commit()
                logger.debug("Query executed successfully")
            except sqlite3.Error as e:
                conn.rollback()
                logger.error(f"Query execution error: {e}")
                raise
            return cursor

    @classmethod
    def fetch_one(cls, query: str, params: Optional[Union[tuple, List, Dict]] = None) -> Dict[str, Any]:
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
            return row

    @classmethod
    def fetch_all(cls, query: str, params: Optional[Union[tuple, List, Dict]] = None) -> List[Dict[str, Any]]:
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
            return rows

def init_db():
    with DatabaseManager.get_db_connection() as conn:
        cursor = conn.cursor()
        try:
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
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT
            )
            ''')
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS sales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER,
                date TEXT NOT NULL,
                total_amount INTEGER NOT NULL,
                FOREIGN KEY (customer_id) REFERENCES customers (id)
            )
            ''')
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS sale_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sale_id INTEGER,
                product_id INTEGER,
                quantity INTEGER NOT NULL,
                price INTEGER NOT NULL,
                FOREIGN KEY (sale_id) REFERENCES sales (id),
                FOREIGN KEY (product_id) REFERENCES products (id)
            )
            ''')
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                supplier TEXT NOT NULL,
                date TEXT NOT NULL,
                total_amount INTEGER NOT NULL
            )
            ''')
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS purchase_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                purchase_id INTEGER,
                product_id INTEGER,
                quantity INTEGER NOT NULL,
                price INTEGER NOT NULL,
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
            conn.commit()
            logger.info("Database initialized successfully")
        except sqlite3.Error as e:
            conn.rollback()
            logger.error(f"Database initialization error: {e}")
            raise