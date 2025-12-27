from datetime import date

import pytest

from utils.exceptions import ValidationException
from utils.validation.validators import (
    validate_3or4digit_identifier,
    validate_9digit_identifier,
    validate_and_sanitize,
    validate_date,
    validate_dict,
    validate_float,
    validate_float_non_negative,
    validate_integer,
    validate_list,
    validate_money,
    validate_money_multiplication,
    validate_string,
    validate_with_pattern,
)


class TestValidators:
    def test_string_validation(self):
        """Test string validation."""
        # Valid cases
        assert validate_string("test") == "test"
        assert validate_string("test", min_length=1) == "test"
        assert validate_string("test", max_length=10) == "test"

        # Remove pattern tests since we now use validate_with_pattern separately
        with pytest.raises(ValidationException):
            validate_string("", min_length=1)  # Empty string
        with pytest.raises(ValidationException):
            validate_string("a", min_length=2)  # Too short
        with pytest.raises(ValidationException):
            validate_string("test", max_length=3)  # Too long

    def test_integer_validation(self):
        """Test integer validation."""
        # Valid cases
        assert validate_integer(42) == 42
        assert validate_integer("42") == 42
        assert validate_integer(42, min_value=0) == 42
        assert validate_integer(42, max_value=100) == 42

        # Invalid cases
        with pytest.raises(ValidationException):
            validate_integer("not_a_number")
        with pytest.raises(ValidationException):
            validate_integer(-1, min_value=0)
        with pytest.raises(ValidationException):
            validate_integer(101, max_value=100)
        with pytest.raises(ValidationException):
            validate_integer(3.14)  # Float not allowed
        with pytest.raises(ValidationException):
            validate_integer(101, max_value=100)
        with pytest.raises(ValidationException):
            validate_integer(3.14)  # Float not allowed

    def test_float_validation(self):
        """Test float validation."""
        # Valid cases
        assert validate_float(3.14) == 3.14
        assert validate_float("3.14") == 3.14
        assert validate_float(3) == 3.0

        # Invalid cases
        with pytest.raises(ValidationException):
            validate_float("not_a_number")
        with pytest.raises(ValidationException):
            validate_float("abc")  # Invalid format

    def test_float_non_negative_validation(self):
        """Test non-negative float validation."""
        # Valid cases
        assert validate_float_non_negative(0.0) == 0.0
        assert validate_float_non_negative(3.14) == 3.14

        # Invalid cases
        with pytest.raises(ValidationException):
            validate_float_non_negative(-1.0)

    def test_money_validation(self):
        """Test money validation for Chilean Pesos."""
        # Valid cases
        assert validate_money(1000) == 1000
        assert validate_money("1000") == 1000
        assert validate_money(999999) == 999999

        # Invalid cases
        with pytest.raises(ValidationException):
            validate_money(-1000)  # Negative amount
        with pytest.raises(ValidationException):
            validate_money(1000.50)  # Decimal not allowed
        with pytest.raises(ValidationException):
            validate_money(1_000_001)  # Exceeds maximum

    def test_money_multiplication_validation(self):
        """Test money multiplication validation."""
        # Valid cases
        assert validate_money_multiplication(1000, 2) == 2000
        assert validate_money_multiplication(1000, 0.5) == 500

        # Invalid cases
        with pytest.raises(ValidationException):
            validate_money_multiplication(1000, -1)  # Negative multiplier
        with pytest.raises(ValidationException):
            validate_money_multiplication(-1000, 1)  # Negative amount

    def test_date_validation(self):
        """Test date validation."""
        today = date.today()

        # Valid cases
        assert validate_date(today.isoformat()) == today.isoformat()
        assert validate_date(str(today)) == str(today)
        assert validate_date(today.strftime("%Y-%m-%d")) == today.strftime("%Y-%m-%d")

        # Invalid cases
        with pytest.raises(ValidationException):
            validate_date("not_a_date")
        with pytest.raises(ValidationException):
            validate_date("2024-13-01")  # Invalid month
        with pytest.raises(ValidationException):
            validate_date("2024-02-30")  # Invalid day

    def test_identifier_validation(self):
        """Test identifier validation."""
        # 9-digit identifier
        assert validate_9digit_identifier("123456789") == "123456789"
        with pytest.raises(ValidationException):
            validate_9digit_identifier("12345678")  # Too short
        with pytest.raises(ValidationException):
            validate_9digit_identifier("1234567890")  # Too long

        # 3or4-digit identifier
        assert validate_3or4digit_identifier("123") == "123"
        assert validate_3or4digit_identifier("1234") == "1234"
        with pytest.raises(ValidationException):
            validate_3or4digit_identifier("12")  # Too short
        with pytest.raises(ValidationException):
            validate_3or4digit_identifier("12345")  # Too long

    def test_validate_and_sanitize(self):
        """Test combined validation and sanitization."""

        def sample_validator(value):
            return len(value) >= 3

        def sample_sanitizer(value):
            return value.strip().lower()

        # Valid cases
        assert (
            validate_and_sanitize(
                "  Test  ", [sample_validator], sample_sanitizer, "Invalid value"
            )
            == "test"
        )

        # Invalid cases
        with pytest.raises(ValidationException):
            validate_and_sanitize(
                "ab", [sample_validator], sample_sanitizer, "Invalid value"
            )

    def test_list_validation(self):
        """Test list validation."""

        def item_validator(item):
            if not isinstance(item, int):
                raise ValidationException("Must be integer")
            return item

        # Valid cases
        assert validate_list([1, 2, 3], item_validator) == [1, 2, 3]
        assert validate_list([1], item_validator, min_length=1) == [1]
        assert validate_list([1, 2], item_validator, max_length=3) == [1, 2]

        # Invalid cases
        with pytest.raises(ValidationException):
            validate_list(["not", "integers"], item_validator)
        with pytest.raises(ValidationException):
            validate_list([1], item_validator, min_length=2)
        with pytest.raises(ValidationException):
            validate_list([1, 2, 3], item_validator, max_length=2)

    def test_dict_validation(self):
        """Test dictionary validation."""

        def key_validator(k):
            if not isinstance(k, str):
                raise ValidationException("Key must be string")
            return k

        def value_validator(v):
            if not isinstance(v, int):
                raise ValidationException("Value must be integer")
            return v

        # Valid cases
        test_dict = {"a": 1, "b": 2}
        assert validate_dict(test_dict, key_validator, value_validator) == test_dict

        # Invalid cases
        with pytest.raises(ValidationException):
            validate_dict({1: 1}, key_validator, value_validator)  # Invalid key
        with pytest.raises(ValidationException):
            validate_dict({"a": "1"}, key_validator, value_validator)  # Invalid value

    def test_pattern_validation(self):
        """Test pattern validation."""
        # Add new test for validate_with_pattern
        assert validate_with_pattern("test", r"^[a-z]+$") == "test"
        with pytest.raises(ValidationException):
            validate_with_pattern("test123", r"^[a-z]+$")
