"""Test configuration settings."""

import pytest

# Test database settings
TEST_DB_NAME = "test.db"
TEST_DB_PATH = "tests/data"

# Test data settings
SAMPLE_SIZE = 10
MAX_TEST_RUNS = 3

# Test timeouts
DEFAULT_TIMEOUT = 5
EXTENDED_TIMEOUT = 15

# Mock settings
MOCK_RESPONSES = {
    "products": [
        {"id": 1, "name": "Test Product 1", "price": 100},
        {"id": 2, "name": "Test Product 2", "price": 200},
    ],
    "customers": [
        {"id": 1, "name": "Test Customer 1"},
        {"id": 2, "name": "Test Customer 2"},
    ],
}


class TestBusinessRegistry:
    def test_no_registry_implies_implicit_default_business(self):
        from config import (
            DEFAULT_ACTIVE_BUSINESS,
            DEFAULT_BUSINESSES,
            Config,
            ConfigValidationError,
            DATABASE_PATH,
        )

        assert Config.get_businesses() == DEFAULT_BUSINESSES
        assert Config.get_active_business()["id"] == DEFAULT_ACTIVE_BUSINESS
        assert Config.get_active_database_path() == DATABASE_PATH
        with pytest.raises(ConfigValidationError):
            Config.get_business_db_path("does-not-exist")

    def test_registry_round_trip(self):
        from config import Config

        businesses = [
            {"id": "default", "name": "Principal", "db_filename": "billing_inventory.db"},
            {"id": "casabea", "name": "CasaBea", "db_filename": "casabea.db"},
        ]
        Config.set("businesses", businesses)
        assert Config.get_businesses() == businesses

    def test_set_active_business_persists_and_round_trips(self):
        from config import Config, ConfigValidationError

        Config.set(
            "businesses",
            [
                {"id": "default", "name": "Principal", "db_filename": "billing_inventory.db"},
                {"id": "casabea", "name": "CasaBea", "db_filename": "casabea.db"},
            ],
        )
        Config.set_active_business("casabea")
        assert Config.get("active_business") == "casabea"
        assert Config.get_active_business()["id"] == "casabea"
        assert Config.get_active_database_path().name == "casabea.db"
        with pytest.raises(ConfigValidationError):
            Config.set_active_business("unknown")

    def test_set_active_business_session_only_does_not_persist(self):
        from config import Config

        Config.set(
            "businesses",
            [
                {"id": "default", "name": "Principal", "db_filename": "billing_inventory.db"},
                {"id": "casabea", "name": "CasaBea", "db_filename": "casabea.db"},
            ],
        )
        Config.set("active_business", "default")
        Config.set_active_business("casabea", persist=False)
        assert Config.get_active_business()["id"] == "casabea"
        Config.reload()
        assert Config.get_active_business()["id"] == "default"
