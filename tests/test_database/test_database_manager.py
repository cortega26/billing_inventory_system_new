import threading
from decimal import Decimal

import pytest

from database.database_manager import DatabaseManager
from utils.exceptions import DatabaseException


@pytest.fixture
def test_table_schema():
    return """
    CREATE TABLE IF NOT EXISTS test_table (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        value INTEGER,
        decimal_value DECIMAL(10,2)
    )
    """


@pytest.fixture
def mock_database():
    """Override global mock_database to do nothing for this test file."""
    return None


@pytest.fixture
def mock_db_operations():
    """Override global mock_db_operations to do nothing for this test file."""
    return None


@pytest.fixture
def db_manager():
    """Provide REAL database manager for tests."""
    from database.database_manager import DatabaseManager

    # Use in-memory DB or temp file. In-memory is safer for speed and isolation.
    # But some threading tests might fail with :memory: if not shared properly?
    # DatabaseManager singleton uses one connection.
    DatabaseManager.initialize(":memory:")
    yield DatabaseManager
    # Cleanup
    if DatabaseManager._connection:
        try:
            DatabaseManager._connection.close()
        except Exception:
            pass
        DatabaseManager._connection = None


class TestDatabaseManager:
    def test_connection_initialization(self, db_manager):
        """Test that database connection is properly initialized."""
        assert db_manager is not None
        # db_manager is the Class itself, not an instance
        assert db_manager == DatabaseManager

    def test_create_table(self, db_manager, test_table_schema):
        """Test table creation."""
        # Use execute_query to ensure commit
        DatabaseManager.execute_query(test_table_schema)

        # Verify table exists
        cursor = db_manager._get_cursor()
        cursor.execute(
            """
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='test_table'
        """
        )
        assert cursor.fetchone() is not None

    def test_insert_and_fetch(self, db_manager, test_table_schema):
        """Test basic insert and fetch operations."""
        # Create table
        DatabaseManager.execute_query(test_table_schema)

        cursor = db_manager._get_cursor()

        # Insert test data
        test_data = {"name": "test", "value": 42}
        cursor.execute(
            "INSERT INTO test_table (name, value) VALUES (?, ?)",
            (test_data["name"], test_data["value"]),
        )
        last_id = cursor.lastrowid

        # Fetch and verify
        result = DatabaseManager.fetch_one(
            "SELECT * FROM test_table WHERE id = ?", (last_id,)
        )
        assert result is not None, "Expected a result but got None"
        assert result["name"] == test_data["name"]
        assert result["value"] == test_data["value"]

    def test_fetch_all(self, db_manager, test_table_schema):
        """Test fetching multiple rows."""
        # Create table and insert test data
        DatabaseManager.execute_query(test_table_schema)

        cursor = db_manager._get_cursor()
        test_data = [{"name": f"test{i}", "value": i} for i in range(3)]

        for data in test_data:
            cursor.execute(
                "INSERT INTO test_table (name, value) VALUES (?, ?)",
                (data["name"], data["value"]),
            )

        # Fetch all and verify
        results = DatabaseManager.fetch_all("SELECT * FROM test_table")
        assert len(results) == len(test_data)
        assert all(isinstance(r, dict) for r in results)

    def test_transaction_commit(self, db_manager, test_table_schema):
        """Test successful transaction commit."""
        DatabaseManager.execute_query(test_table_schema)

        with DatabaseManager.transaction():
            cursor = db_manager._get_cursor()
            cursor.execute(
                "INSERT INTO test_table (name, value) VALUES (?, ?)",
                ("test_transaction", 100),
            )

        # Verify data was committed
        result = DatabaseManager.fetch_one(
            "SELECT * FROM test_table WHERE name = ?", ("test_transaction",)
        )
        assert result is not None
        assert result["value"] == 100

    def test_transaction_rollback(self, db_manager, test_table_schema):
        """Test transaction rollback on error."""
        DatabaseManager.execute_query(test_table_schema)

        cursor = db_manager._get_cursor()

        try:
            with DatabaseManager.transaction():
                cursor.execute(
                    "INSERT INTO test_table (name, value) VALUES (?, ?)",
                    ("test_rollback", 100),
                )
                # Force an error
                raise Exception("Test error")
        except Exception:
            pass

        # Verify data was rolled back
        result = DatabaseManager.fetch_one(
            "SELECT * FROM test_table WHERE name = ?", ("test_rollback",)
        )
        assert result is None

    def test_decimal_handling(self, db_manager, test_table_schema):
        """Test handling of decimal values."""
        DatabaseManager.execute_query(test_table_schema)

        cursor = db_manager._get_cursor()
        test_value = Decimal("123.45")
        cursor.execute(
            "INSERT INTO test_table (name, decimal_value) VALUES (?, ?)",
            ("test_decimal", test_value),
        )

        result = DatabaseManager.fetch_one(
            "SELECT * FROM test_table WHERE name = ?", ("test_decimal",)
        )
        assert result is not None, "Expected a result but got None"
        assert isinstance(result["decimal_value"], Decimal)
        assert result["decimal_value"] == test_value

    def test_concurrent_access(self, db_manager, test_table_schema):
        """Test concurrent database access."""
        DatabaseManager.execute_query(test_table_schema)

        db_manager._get_cursor()

        def worker(name: str):
            try:
                with DatabaseManager.transaction():
                    cursor = db_manager._get_cursor()
                    cursor.execute(
                        "INSERT INTO test_table (name, value) VALUES (?, ?)", (name, 1)
                    )
            except Exception as e:
                pytest.fail(f"Worker {name} failed: {str(e)}")

        threads = [
            threading.Thread(target=worker, args=(f"thread_{i}",)) for i in range(5)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        results = DatabaseManager.fetch_all("SELECT * FROM test_table")
        assert len(results) == 5

    def test_error_handling(self, db_manager):
        """Test database error handling."""
        with pytest.raises(DatabaseException):
            DatabaseManager.fetch_one("SELECT * FROM nonexistent_table")

    def test_parameter_validation(self, db_manager, test_table_schema):
        """Test SQL parameter validation."""
        DatabaseManager.execute_query(test_table_schema)

        with pytest.raises(DatabaseException):
            # Test with wrong number of parameters
            DatabaseManager.fetch_one(
                "SELECT * FROM test_table WHERE name = ? AND value = ?",
                ("test",),  # Missing one parameter
            )

    def test_connection_cleanup(self, db_manager):
        """Test connection cleanup on errors."""
        try:
            with DatabaseManager.transaction():
                raise Exception("Test error")
        except Exception:
            pass

        # Verify connection is still valid
        cursor = db_manager._get_cursor()
        cursor.execute("SELECT 1")
        assert cursor.fetchone() is not None

    def test_large_dataset(self, db_manager, test_table_schema):
        """Test handling of large datasets."""
        DatabaseManager.execute_query(test_table_schema)

        cursor = db_manager._get_cursor()

        # Insert 1000 rows
        test_data = [{"name": f"test{i}", "value": i} for i in range(1000)]

        with DatabaseManager.transaction():
            for data in test_data:
                cursor.execute(
                    "INSERT INTO test_table (name, value) VALUES (?, ?)",
                    (data["name"], data["value"]),
                )

        # Fetch all and verify
        results = DatabaseManager.fetch_all("SELECT * FROM test_table")
        assert len(results) == 1000
