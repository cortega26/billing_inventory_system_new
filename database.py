# database.py

import sqlite3
from contextlib import contextmanager
from typing import List, Dict, Any, Union, Optional
from config import DATABASE_PATH

class DatabaseManager:
    @staticmethod
    @contextmanager
    def get_db_connection():
        conn = None
        try:
            conn = sqlite3.connect(DATABASE_PATH, timeout=20)
            conn.row_factory = sqlite3.Row
            yield conn
        except sqlite3.Error as e:
            print(f"Database connection error: {e}")
            raise
        finally:
            if conn:
                conn.close()

    @classmethod
    def execute_query(cls, query: str, params: Optional[Union[tuple, List, Dict]] = None) -> sqlite3.Cursor:
        with cls.get_db_connection() as conn:
            cursor = conn.cursor()
            try:
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)
                conn.commit()
            except sqlite3.Error as e:
                conn.rollback()
                print(f"Query execution error: {e}")
                raise
            return cursor

    @classmethod
    def fetch_one(cls, query: str, params: Optional[Union[tuple, List, Dict]] = None) -> Dict[str, Any]:
        with cls.get_db_connection() as conn:
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            return cursor.fetchone()

    @classmethod
    def fetch_all(cls, query: str, params: Optional[Union[tuple, List, Dict]] = None) -> List[Dict[str, Any]]:
        with cls.get_db_connection() as conn:
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            return cursor.fetchall()

def init_db():
    with DatabaseManager.get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                identifier_9 TEXT UNIQUE NOT NULL,
                identifier_4 TEXT
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
        except sqlite3.Error as e:
            conn.rollback()
            print(f"Database initialization error: {e}")
            raise
