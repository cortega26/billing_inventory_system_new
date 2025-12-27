"""Test configuration settings."""

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
