"""Database manager implementation."""

import sqlite3
import threading
import time
from contextlib import contextmanager
from typing import Any, Dict, List, Tuple, Union

from utils.exceptions import DatabaseException
from utils.system.logger import logger

SLOW_QUERY_THRESHOLD_MS = 50
STARTUP_PRAGMAS = (
    ("PRAGMA foreign_keys = ON", True),
    ("PRAGMA journal_mode = WAL", False),
    ("PRAGMA synchronous = NORMAL", False),
    ("PRAGMA cache_size = 2000", False),
    ("PRAGMA temp_store = MEMORY", False),
    ("PRAGMA auto_vacuum = INCREMENTAL", False),
    ("PRAGMA mmap_size = 268435456", False),
)


class DatabaseManager:
    _connection = None
    _connection_lock = threading.RLock()
    _transaction_state = threading.local()

    @classmethod
    def initialize(cls, db_path: str = "billing_inventory.db"):
        """Initialize database connection"""
        # Register adapters if needed (e.g., for Decimal)
        import sqlite3
        from decimal import Decimal

        def adapt_decimal(d):
            return str(d)

        def convert_decimal(s):
            return Decimal(s.decode("utf-8"))

        sqlite3.register_adapter(Decimal, adapt_decimal)
        sqlite3.register_converter("DECIMAL", convert_decimal)

        with cls._connection_lock:
            if cls._connection is not None:
                try:
                    cls._connection.close()
                except sqlite3.Error:
                    pass

            cls._connection = sqlite3.connect(
                db_path,
                check_same_thread=False,
                detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
            )
            cls._connection.row_factory = sqlite3.Row
            cls._transaction_state.depth = 0
            cls.apply_startup_pragmas()

    @classmethod
    def _get_transaction_depth(cls) -> int:
        return getattr(cls._transaction_state, "depth", 0)

    @classmethod
    def _set_transaction_depth(cls, depth: int) -> None:
        cls._transaction_state.depth = max(depth, 0)

    @classmethod
    def is_in_transaction(cls) -> bool:
        """Return whether the current thread is inside a managed transaction."""
        return cls._get_transaction_depth() > 0

    @classmethod
    def _get_cursor(cls):
        if cls._connection is None:
            cls.initialize()
        if cls._connection is None:  # If still None after initialization
            raise DatabaseException("Could not establish database connection")
        return cls._connection.cursor()

    @classmethod
    def apply_startup_pragmas(cls) -> None:
        """Apply connection-level pragmas outside any active transaction."""
        if cls._connection is None:
            raise DatabaseException("No active database connection")
        if cls.is_in_transaction() or cls._connection.in_transaction:
            raise DatabaseException(
                "Startup pragmas must be applied outside a transaction"
            )

        for pragma, required in STARTUP_PRAGMAS:
            try:
                cls._connection.execute(pragma)
                logger.info(f"Applied database pragma: {pragma}")
            except Exception as e:
                message = f"Failed to apply pragma {pragma}: {str(e)}"
                if required:
                    raise DatabaseException(message) from e
                logger.warning(message)

    @classmethod
    @contextmanager
    def transaction(cls):
        """Context manager for database transactions"""
        cls.begin_transaction()
        try:
            yield
            cls.commit_transaction()
        except Exception as e:
            cls.rollback_transaction()
            if any(base.__name__ == "AppException" for base in type(e).__mro__):
                raise
            raise DatabaseException(f"Transaction failed: {str(e)}") from e

    @classmethod
    def fetch_one(cls, query: str, params: Union[tuple, Dict[str, Any]] = ()):
        try:
            with cls._connection_lock:
                cursor = cls._get_cursor()
                start_time = time.perf_counter()
                cursor.execute(query, params)
                duration_ms = (time.perf_counter() - start_time) * 1000
                if duration_ms > SLOW_QUERY_THRESHOLD_MS:
                    logger.warning(f"Slow query ({duration_ms:.2f}ms): {query}")

                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            if isinstance(e, DatabaseException):
                raise
            raise DatabaseException(f"Query failed: {str(e)}")

    @classmethod
    def fetch_all(cls, query: str, params: Union[tuple, Dict[str, Any]] = ()):
        try:
            with cls._connection_lock:
                cursor = cls._get_cursor()
                start_time = time.perf_counter()
                cursor.execute(query, params)
                duration_ms = (time.perf_counter() - start_time) * 1000
                if duration_ms > SLOW_QUERY_THRESHOLD_MS:
                    logger.warning(f"Slow query ({duration_ms:.2f}ms): {query}")

                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            if isinstance(e, DatabaseException):
                raise
            raise DatabaseException(f"Query failed: {str(e)}")

    @classmethod
    def execute_query(
        cls, query: str, params: Union[tuple, Dict[str, Any]] = ()
    ) -> sqlite3.Cursor:
        """Execute a query and return the cursor."""
        if cls._connection is None:
            cls.initialize()
        if cls._connection is None:
            raise DatabaseException("No active database connection")
        try:
            with cls._connection_lock:
                cursor = cls._get_cursor()
                start_time = time.perf_counter()
                cursor.execute(query, params)
                duration_ms = (time.perf_counter() - start_time) * 1000
                if duration_ms > SLOW_QUERY_THRESHOLD_MS:
                    logger.warning(f"Slow query ({duration_ms:.2f}ms): {query}")

                if not cls.is_in_transaction():
                    cls._connection.commit()
                return cursor
        except Exception as e:
            if isinstance(e, DatabaseException):
                raise
            raise DatabaseException(f"Query execution failed: {str(e)}")

    @classmethod
    def begin_transaction(cls):
        """Begin a database transaction."""
        if cls._connection is None:
            cls.initialize()
        if cls._connection is None:
            raise DatabaseException("No active database connection")

        depth = cls._get_transaction_depth()
        if depth == 0:
            cls._connection_lock.acquire()
            try:
                cls._connection.execute("BEGIN")
            except Exception:
                cls._connection_lock.release()
                raise
        cls._set_transaction_depth(depth + 1)

    @classmethod
    def commit_transaction(cls):
        """Commit the current transaction."""
        if cls._connection is None:
            raise DatabaseException("No active database connection")
        depth = cls._get_transaction_depth()
        if depth <= 0:
            cls._connection.commit()
            return

        try:
            if depth == 1:
                cls._connection.commit()
        finally:
            cls._set_transaction_depth(depth - 1)
            if depth == 1:
                cls._connection_lock.release()

    @classmethod
    def rollback_transaction(cls):
        """Rollback the current transaction."""
        if cls._connection is None:
            raise DatabaseException("No active database connection")
        depth = cls._get_transaction_depth()
        try:
            cls._connection.rollback()
        finally:
            if depth > 0:
                cls._set_transaction_depth(0)
                cls._connection_lock.release()

    @classmethod
    @contextmanager
    def get_db_connection(cls):
        """Get a database connection context manager."""
        if cls._connection is None:
            cls.initialize()
        if cls._connection is None:
            raise DatabaseException("No active database connection")
        try:
            with cls._connection_lock:
                yield cls._connection
        except Exception as e:
            raise DatabaseException(f"Database connection error: {str(e)}")

    @classmethod
    def executemany(cls, query: str, params: List[Tuple]) -> sqlite3.Cursor:
        """Execute a query with multiple parameter sets and commit."""
        if cls._connection is None:
            cls.initialize()
        if cls._connection is None:
            raise DatabaseException("No active database connection")
        try:
            with cls._connection_lock:
                cursor = cls._get_cursor()
                cursor.executemany(query, params)
                if not cls.is_in_transaction():
                    cls._connection.commit()
                return cursor
        except Exception as e:
            if isinstance(e, DatabaseException):
                raise
            raise DatabaseException(f"Batch execution failed: {str(e)}")
