import pytest

from services.customer_service import CustomerService
from utils.exceptions import DatabaseException, ValidationException


@pytest.fixture
def customer_service(db_manager):
    return CustomerService()


@pytest.fixture
def sample_customer_data():
    return {
        "identifier_9": "123456789",  # 9-digit identifier
        "name": "Test Customer",
        "identifier_3or4": "123",  # 3-digit identifier
    }


@pytest.mark.customer
class TestCustomerService:
    """Customer service tests."""

    def test_create_customer(self, customer_service, sample_customer_data, mocker):
        # Mock database operations
        mock_execute = mocker.patch(
            "database.database_manager.DatabaseManager.execute_query"
        )
        mock_execute.return_value.lastrowid = 1

        mock_fetch = mocker.patch("database.database_manager.DatabaseManager.fetch_one")
        mock_fetch.return_value = {
            "id": 1,
            "name": sample_customer_data["name"],
            "identifier_9": sample_customer_data["identifier_9"],
            "identifier_3or4": sample_customer_data["identifier_3or4"],
        }

        customer_id = customer_service.create_customer(
            identifier_9=sample_customer_data["identifier_9"],
            name=sample_customer_data["name"],
            identifier_3or4=sample_customer_data["identifier_3or4"],
        )
        assert customer_id == 1

        # Verify customer was created
        customer = customer_service.get_customer(customer_id)
        assert customer.identifier_9 == sample_customer_data["identifier_9"]
        assert customer.name == sample_customer_data["name"]

    def test_create_customer_invalid_identifier(self, customer_service):
        with pytest.raises(ValidationException):
            customer_service.create_customer(
                identifier_9="12345", name="Test Customer"  # Invalid length
            )

    def test_create_customer_duplicate_identifier(
        self, customer_service, sample_customer_data, mocker
    ):
        # Mock first customer creation success
        mock_execute_success = mocker.patch(
            "database.database_manager.DatabaseManager.execute_query"
        )
        mock_execute_success.return_value.lastrowid = 1

        # Create first customer
        customer_service.create_customer(
            identifier_9=sample_customer_data["identifier_9"],
            name=sample_customer_data["name"],
        )

        # Mock database error for duplicate
        mocker.patch(
            "database.database_manager.DatabaseManager.execute_query",
            side_effect=DatabaseException("Duplicate identifier"),
        )

        # Try to create duplicate
        with pytest.raises(DatabaseException):
            customer_service.create_customer(
                identifier_9=sample_customer_data["identifier_9"],
                name="Another Customer",
            )

    def test_update_customer(self, customer_service, sample_customer_data):
        # First create a customer
        customer_id = customer_service.create_customer(
            identifier_9=sample_customer_data["identifier_9"],
            name=sample_customer_data["name"],
        )

        # Update the customer
        new_name = "Updated Customer Name"
        customer_service.update_customer(customer_id, name=new_name)

        # Verify update
        customer = customer_service.get_customer(customer_id)
        assert customer.name == new_name

    def test_delete_customer(self, customer_service, sample_customer_data, mocker):
        # Mock customer creation
        mock_customer = mocker.Mock()
        mock_customer.id = 1
        mocker.patch.object(customer_service, "get_customer", side_effect=[None])

        # Mock database execution
        mock_execute = mocker.patch(
            "database.database_manager.DatabaseManager.execute_query"
        )
        mock_execute.return_value.rowcount = 1

        # Execute test
        customer_service.delete_customer(1)

        # Verify
        mock_execute.assert_called()
        # get_customer returns None if not found, does NOT raise
        assert customer_service.get_customer(1) is None

    def test_search_customers(self, customer_service, sample_customer_data, mocker):
        # Mock database results
        mock_rows = [
            {
                "id": 1,
                "name": "John Doe",
                "identifier_9": "111222333",
                "identifier_3or4": "123",
            },
            {
                "id": 2,
                "name": "Jane Doe",
                "identifier_9": "444555666",
                "identifier_3or4": "456",
            },
        ]

        # Mock database fetch
        mock_fetch = mocker.patch("database.database_manager.DatabaseManager.fetch_all")
        mock_fetch.return_value = mock_rows

        # Test search by name
        results = customer_service.search_customers("Doe")
        assert len(results) == 2
        assert results[0].name == "John Doe"
        assert results[1].name == "Jane Doe"

        # Test search by identifier
        mock_fetch.return_value = [mock_rows[0]]
        results = customer_service.search_customers("111")
        assert len(results) == 1
        assert results[0].identifier_9 == "111222333"

    def test_get_customer_purchase_history(
        self, customer_service, sample_customer_data
    ):
        customer_id = customer_service.create_customer(
            identifier_9=sample_customer_data["identifier_9"],
            name=sample_customer_data["name"],
        )

        # Get purchase history (should be empty for new customer)
        history = customer_service.get_customer_purchase_history(customer_id)
        assert len(history) == 0

    def test_validate_identifiers(self, customer_service):
        """Test identifier validation."""
        # Valid identifiers
        assert (
            customer_service.validate_identifier("123456789", "identifier_9")
            == "123456789"
        )
        assert customer_service.validate_identifier("123", "identifier_3or4") == "123"
        assert customer_service.validate_identifier("1234", "identifier_3or4") == "1234"

        # Invalid identifiers
        with pytest.raises(ValidationException):
            customer_service.validate_identifier(
                "12345678", "identifier_9"
            )  # Too short
        with pytest.raises(ValidationException):
            customer_service.validate_identifier("12", "identifier_3or4")  # Too short

    def test_delete_customer_mock(self, mocker):
        # Using pytest-mock instead of unittest.mock
        mock_execute = mocker.patch(
            "database.database_manager.DatabaseManager.execute_query"
        )
        mock_execute.return_value.rowcount = 1  # Simulate successful deletion
        CustomerService().delete_customer(1)
        mock_execute.assert_called()
