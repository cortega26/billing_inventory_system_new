import sqlite3
from contextlib import contextmanager
from utils.exceptions import DatabaseException
from typing import Union, Dict, Any, List, Tuple

class DatabaseManager:
    _connection = None

    @classmethod
    def initialize(cls, db_path: str = "billing_inventory.db"):
        """Initialize database connection"""
        cls._connection = sqlite3.connect(db_path)
        cls._connection.row_factory = sqlite3.Row

    @classmethod
    def _get_cursor(cls):
        if cls._connection is None:
            cls.initialize()
        if cls._connection is None:  # If still None after initialization
            raise DatabaseException("Could not establish database connection")
        return cls._connection.cursor()

    @classmethod
    @contextmanager
    def transaction(cls):
        """Context manager for database transactions"""
        if cls._connection is None:
            cls.initialize()
        if cls._connection is None:
            raise DatabaseException("No active database connection")
        try:
            yield
            cls._connection.commit()
        except Exception as e:
            cls._connection.rollback()
            raise DatabaseException(f"Transaction failed: {str(e)}")

    @classmethod
    def fetch_one(cls, query: str, params: Union[tuple, Dict[str, Any]] = ()):
        cursor = cls._get_cursor()
        cursor.execute(query, params)
        row = cursor.fetchone()
        return dict(row) if row else None

    @classmethod
    def fetch_all(cls, query: str, params: Union[tuple, Dict[str, Any]] = ()):
        cursor = cls._get_cursor()
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    @classmethod
    def execute_query(cls, query: str, params: Union[tuple, Dict[str, Any]] = ()) -> sqlite3.Cursor:
        """Execute a query and return the cursor."""
        if cls._connection is None:
            cls.initialize()
        if cls._connection is None:
            raise DatabaseException("No active database connection")
        cursor = cls._get_cursor()
        cursor.execute(query, params)
        cls._connection.commit()
        return cursor 

    @classmethod
    def begin_transaction(cls):
        """Begin a database transaction."""
        cls._get_cursor().execute("BEGIN TRANSACTION")

    @classmethod
    def commit_transaction(cls):
        """Commit the current transaction."""
        if cls._connection is None:
            raise DatabaseException("No active database connection")
        cls._connection.commit()

    @classmethod
    def rollback_transaction(cls):
        """Rollback the current transaction."""
        if cls._connection is None:
            raise DatabaseException("No active database connection")
        cls._connection.rollback() 

    @classmethod
    @contextmanager
    def get_db_connection(cls):
        """Get a database connection context manager."""
        if cls._connection is None:
            cls.initialize()
        if cls._connection is None:
            raise DatabaseException("No active database connection")
        try:
            yield cls._connection
        except Exception as e:
            raise DatabaseException(f"Database connection error: {str(e)}")

    @classmethod
    def executemany(cls, query: str, params: List[Tuple]) -> sqlite3.Cursor:
        """Execute a query with multiple parameter sets."""
        cursor = cls._get_cursor()
        cursor.executemany(query, params)
        return cursor
