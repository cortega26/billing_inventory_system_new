import pytest

from utils.exceptions import (
    AppException,
    ConfigurationException,
    DatabaseException,
    UIException,
    ValidationException,
)


class TestExceptions:
    @pytest.fixture
    def sample_error_data(self):
        return {"code": "ERR001", "details": {"field": "username", "value": "invalid"}}

    def test_base_exception(self):
        """Test the base AppException."""
        message = "Test error message"
        error = AppException(message)

        assert str(error) == message
        assert isinstance(error, Exception)
        assert error.message == message
        assert error.error_code is None
        assert error.details == {}

    def test_exception_with_code(self):
        """Test exception with error code."""
        error = AppException("Test message", error_code="ERR001")
        assert error.error_code == "ERR001"

    def test_exception_with_details(self, sample_error_data):
        """Test exception with detailed information."""
        error = AppException(
            "Test message",
            error_code=sample_error_data["code"],
            details=sample_error_data["details"],
        )

        assert error.details == sample_error_data["details"]
        assert "field" in error.details
        assert error.details["field"] == "username"

    def test_database_exception(self):
        """Test database-specific exceptions."""
        error = DatabaseException(
            "Database connection failed",
            error_code="DB001",
            details={"connection": "localhost:5432"},
        )

        assert isinstance(error, AppException)
        assert "connection failed" in str(error)
        assert error.error_code == "DB001"

    def test_validation_exception(self):
        """Test validation-specific exceptions."""
        error = ValidationException(
            "Invalid input",
            error_code="VAL001",
            details={"field": "email", "reason": "invalid format"},
        )

        assert isinstance(error, AppException)
        assert "Invalid input" in str(error)
        assert "email" in error.details["field"]

    def test_configuration_exception(self):
        """Test configuration-specific exceptions."""
        error = ConfigurationException(
            "Missing required config",
            error_code="CFG001",
            details={"missing_key": "database_url"},
        )

        assert isinstance(error, AppException)
        assert "Missing required config" in str(error)
        assert "database_url" in error.details["missing_key"]

    def test_ui_exception(self):
        """Test UI-specific exceptions."""
        error = UIException(
            "Widget initialization failed",
            error_code="UI001",
            details={"widget_type": "TableView", "reason": "invalid data model"},
        )

        assert isinstance(error, AppException)
        assert "Widget initialization failed" in str(error)
        assert "TableView" in error.details["widget_type"]

    def test_exception_inheritance(self):
        """Test exception inheritance hierarchy."""
        exceptions = [
            DatabaseException,
            ValidationException,
            ConfigurationException,
            UIException,
        ]

        for exception_class in exceptions:
            assert issubclass(exception_class, AppException)

    def test_exception_chaining(self):
        """Test exception chaining."""
        try:
            try:
                raise ValueError("Original error")
            except ValueError as e:
                raise DatabaseException("Database error") from e
        except DatabaseException as e:
            assert isinstance(e.__cause__, ValueError)
            assert str(e.__cause__) == "Original error"

    def test_exception_formatting(self):
        """Test string formatting of exceptions."""
        error = AppException(
            "Error occurred", error_code="ERR001", details={"key": "value"}
        )

        error_str = str(error)
        assert "Error occurred" in error_str
        assert "ERR001" in repr(error)

    def test_exception_comparison(self):
        """Test exception comparison."""
        error1 = AppException("Error", error_code="ERR001")
        error2 = AppException("Error", error_code="ERR001")
        error3 = AppException("Different", error_code="ERR002")

        assert error1.error_code == error2.error_code
        assert error1.error_code != error3.error_code

    def test_exception_with_empty_details(self):
        """Test exception with empty details."""
        error = AppException("Message", details={})
        assert error.details == {}
        assert str(error) == "Message"
