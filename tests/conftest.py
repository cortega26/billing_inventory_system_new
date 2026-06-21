import shutil
import tempfile
from pathlib import Path

import pytest

from database.database_manager import DatabaseManager


@pytest.fixture(autouse=True)
def setup_test_environment():
    """Setup test environment before each test."""
    # Create temp directory for test files
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    # Cleanup after test
    shutil.rmtree(temp_dir)


@pytest.fixture
def db_manager():
    """Provide REAL in-memory database manager for all tests."""
    # Initialize in-memory database
    DatabaseManager.initialize(":memory:")
    DatabaseManager.execute_query("PRAGMA foreign_keys = ON")

    # Create tables via SQLModel
    from sqlmodel import SQLModel
    from models.category import Category  # noqa: F401
    from models.product import Product  # noqa: F401
    from models.customer import Customer  # noqa: F401
    from models.inventory import Inventory, InventoryAdjustment  # noqa: F401
    from models.sale import Sale, SaleItem  # noqa: F401
    from models.purchase import Purchase, PurchaseItem  # noqa: F401
    from models.audit_log import AuditLog  # noqa: F401

    SQLModel.metadata.create_all(DatabaseManager._engine)

    yield DatabaseManager

    # Cleanup connection
    if DatabaseManager._connection:
        try:
            DatabaseManager._connection.close()
        except Exception:
            pass
        DatabaseManager._connection = None


@pytest.fixture(autouse=True)
def isolate_config(tmp_path):
    """Isolate configuration for each test to prevent global state pollution."""
    from config import Config

    # Create temp config file
    config_file = tmp_path / "test_app_config.json"

    # Inject temp config file
    Config._reset_for_testing(config_file)
    Config.reset_to_defaults()

    yield

    # Reset to defaults / cleanup
    Config.reset_to_defaults()
    Config._config_file = None


@pytest.fixture(autouse=True)
def clear_test_data(db_manager):
    """Clear test data after each test."""
    yield
    try:
        # Check if connection is open first
        if db_manager._connection:
            # Truncate tables. We temporarily disable FKs to avoid constraint errors.
            tables = [
                "sale_items",
                "purchase_items",
                "inventory_adjustments",
                "products",
                "inventory",
                "sales",
                "purchases",
                "customers",
                "categories",
            ]
            db_manager.execute_query("PRAGMA foreign_keys = OFF")
            for table in tables:
                try:
                    db_manager.execute_query(f"DELETE FROM {table}")
                except Exception:
                    # Table might not exist or error
                    pass
            db_manager.execute_query("PRAGMA foreign_keys = ON")
    except Exception:
        pass


@pytest.fixture
def mock_database(mocker):
    """Mock database connection for all tests."""
    mock_db = mocker.patch("database.database_manager.DatabaseManager")
    mock_db.begin_transaction = mocker.Mock()
    mock_db.commit_transaction = mocker.Mock()
    mock_db.rollback_transaction = mocker.Mock()

    # Patch DatabaseManager where it is imported in services
    mocker.patch("services.product_service.DatabaseManager", mock_db, create=True)
    mocker.patch("services.inventory_service.DatabaseManager", mock_db, create=True)
    mocker.patch("services.sale_service.DatabaseManager", mock_db, create=True)
    mocker.patch("services.purchase_service.DatabaseManager", mock_db, create=True)
    mocker.patch("services.analytics_service.DatabaseManager", mock_db, create=True)

    return mock_db


@pytest.fixture
def mock_db_operations(mocker):
    """Mock all database operations."""
    # Mock database connection
    mock_conn = mocker.Mock()
    mock_cursor = mocker.Mock()
    mock_conn.cursor.return_value = mock_cursor

    # Mock common database operations
    mock_execute = mocker.patch(
        "database.database_manager.DatabaseManager.execute_query"
    )
    mock_execute.return_value.lastrowid = 1
    mock_execute.return_value.rowcount = 1

    mock_fetch_one = mocker.patch("database.database_manager.DatabaseManager.fetch_one")
    mock_fetch_one.return_value = None

    mock_fetch_all = mocker.patch("database.database_manager.DatabaseManager.fetch_all")
    mock_fetch_all.return_value = []

    return {
        "execute": mock_execute,
        "fetch_one": mock_fetch_one,
        "fetch_all": mock_fetch_all,
        "connection": mock_conn,
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
    import logging

    # Close all handlers to release file locks
    logging.shutdown()

    # Force close any dangling handlers on the root logger AND all other loggers
    loggers = [logging.getLogger()] + [
        logging.getLogger(name) for name in logging.root.manager.loggerDict
    ]
    for logger in loggers:
        if not isinstance(logger, logging.Logger):
            continue
        for handler in logger.handlers[:]:
            handler.close()
            logger.removeHandler(handler)

    for file in temp_log_dir.glob("*.log"):
        try:
            file.unlink()
        except (PermissionError, FileNotFoundError):
            pass
    yield
