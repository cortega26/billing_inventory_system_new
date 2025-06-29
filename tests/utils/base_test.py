import pytest
from typing import Any, Dict, Optional
from unittest.mock import Mock

class BaseTest:
    """Base class for all tests."""
    
    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Setup common mocks for all tests."""
        # Reset any existing mocks
        mocker.resetall()
        
        # Create fresh mock
        self.mock_db = mocker.patch('database.database_manager.DatabaseManager')
        self.mock_db.execute_query.return_value.lastrowid = 1
        self.mock_db.execute_query.return_value.rowcount = 1
        self.mock_db.fetch_one.return_value = None
        self.mock_db.fetch_all.return_value = []
        
        # Setup transaction mocks
        self.mock_db.begin_transaction = mocker.Mock()
        self.mock_db.commit_transaction = mocker.Mock()
        self.mock_db.rollback_transaction = mocker.Mock()
        
        # Don't mock date validation - let it use real implementation
        return self.mock_db

    def setup_mock_db_response(
        self, 
        mock_db: Mock, 
        fetch_one_return: Optional[Dict[str, Any]] = None,
        fetch_all_return: Optional[list] = None,
        execute_return: Any = None
    ):
        """Setup mock database responses with validation."""
        try:
            if fetch_one_return is not None:
                if not isinstance(fetch_one_return, dict):
                    raise ValueError("fetch_one_return must be a dictionary")
                mock_db.fetch_one.return_value = fetch_one_return

            if fetch_all_return is not None:
                if not isinstance(fetch_all_return, list):
                    raise ValueError("fetch_all_return must be a list")
                mock_db.fetch_all.return_value = fetch_all_return

            if execute_return is not None:
                mock_db.execute_query.return_value = execute_return

        except Exception as e:
            pytest.fail(f"Failed to setup mock DB response: {str(e)}") 