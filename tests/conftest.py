import pytest
from pathlib import Path
import tempfile
import shutil

@pytest.fixture(autouse=True)
def setup_test_environment():
    """Setup test environment before each test."""
    # Create temp directory for test files
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    # Cleanup after test
    shutil.rmtree(temp_dir)

@pytest.fixture(autouse=True)
def mock_database(mocker):
    """Mock database connection for all tests."""
    mock_db = mocker.patch('database.database_manager.DatabaseManager')
    mock_db.begin_transaction = mocker.Mock()
    mock_db.commit_transaction = mocker.Mock()
    mock_db.rollback_transaction = mocker.Mock()
    return mock_db

@pytest.fixture
def db_manager(mock_database):
    """Provide mocked database manager."""
    return mock_database

@pytest.fixture(autouse=True)
def reset_mocks(mocker):
    """Reset all mocks after each test."""
    yield
    mocker.resetall()

@pytest.fixture(autouse=True)
def clear_test_data(db_manager):
    """Clear test data after each test."""
    yield
    try:
        db_manager.execute_query("DELETE FROM products")
        db_manager.execute_query("DELETE FROM inventory")
        db_manager.execute_query("DELETE FROM sales")
        db_manager.execute_query("DELETE FROM purchases")
    except Exception:
        pass  # Ignore cleanup errors

@pytest.fixture(autouse=True)
def mock_db_operations(mocker):
    """Mock all database operations."""
    # Mock database connection
    mock_conn = mocker.Mock()
    mock_cursor = mocker.Mock()
    mock_conn.cursor.return_value = mock_cursor
    
    # Mock common database operations
    mock_execute = mocker.patch('database.database_manager.DatabaseManager.execute_query')
    mock_execute.return_value.lastrowid = 1
    mock_execute.return_value.rowcount = 1
    
    mock_fetch_one = mocker.patch('database.database_manager.DatabaseManager.fetch_one')
    mock_fetch_one.return_value = None
    
    mock_fetch_all = mocker.patch('database.database_manager.DatabaseManager.fetch_all')
    mock_fetch_all.return_value = []
    
    return {
        'execute': mock_execute,
        'fetch_one': mock_fetch_one,
        'fetch_all': mock_fetch_all,
        'connection': mock_conn
    }

@pytest.fixture
def temp_log_dir(tmp_path):
    """Create a temporary directory for logs with proper permissions."""
    log_dir = tmp_path / "logs"
    log_dir.mkdir(exist_ok=True)
    return log_dir

@pytest.fixture(autouse=True)
def clean_logs(temp_log_dir):
    """Clean log files before each test."""
    for file in temp_log_dir.glob("*.log"):
        try:
            file.unlink()
        except (PermissionError, FileNotFoundError):
            pass
    yield