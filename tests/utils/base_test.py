from typing import Any, Dict, Optional
from unittest.mock import Mock

import pytest


class BaseTest:
    """Base class for all tests."""

    @pytest.fixture(autouse=True)
    def mock_db(self, db_manager, mocker):
        """Setup common mocks for all tests using shared db_manager."""
        self.mock_db = db_manager

        # Only configure if it is a Mock object
        if hasattr(self.mock_db, "execute_query") and hasattr(
            self.mock_db.execute_query, "return_value"
        ):
            # Ensure return values are standard for BaseTest expectations
            self.mock_db.execute_query.return_value.lastrowid = 1
            self.mock_db.execute_query.return_value.rowcount = 1
            self.mock_db.fetch_one.return_value = None
            self.mock_db.fetch_all.return_value = []

            # Setup transaction mocks if not present
            if not hasattr(self.mock_db, "begin_transaction"):
                self.mock_db.begin_transaction = mocker.Mock()
            if not hasattr(self.mock_db, "commit_transaction"):
                self.mock_db.commit_transaction = mocker.Mock()
            if not hasattr(self.mock_db, "rollback_transaction"):
                self.mock_db.rollback_transaction = mocker.Mock()

        return self.mock_db

        return self.mock_db

    def setup_mock_db_response(
        self,
        mock_db: Mock,
        fetch_one_return: Optional[Dict[str, Any]] = None,
        fetch_all_return: Optional[list] = None,
        execute_return: Any = None,
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
