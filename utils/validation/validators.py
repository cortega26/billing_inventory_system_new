import re
from collections.abc import Callable
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from utils.exceptions import ValidationException


def validate_string(
    value: str, min_length: int = 0, max_length: int | None = 100
) -> str:
    """Validate a string value."""
    if not isinstance(value, str):
        raise ValidationException("Value must be a string")

    # Normalize whitespace
    value = " ".join(value.split())

    if len(value) < min_length:
        raise ValidationException(
            f"Value must be at least {min_length} characters long"
        )

    if max_length is not None and len(value) > max_length:
        raise ValidationException(f"Value cannot exceed {max_length} characters")

    # Allow alphanumeric (incl. Unicode/Spanish: ñ, á, é…), spaces, and common punctuation
    allowed_extra = set("-.,;:()'/&%#+")
    if not all(
        c.isalpha() or c.isdigit() or c.isspace() or c in allowed_extra for c in value
    ):
        raise ValidationException("Value contains invalid characters")

    return value


def validate_filepath(value: str, max_length: int | None = 255) -> str:
    """Validate a filesystem path (alphanumerics, spaces, and path punctuation)."""
    if not isinstance(value, str):
        raise ValidationException("Path must be a string")
    if max_length is not None and len(value) > max_length:
        raise ValidationException(f"Path cannot exceed {max_length} characters")

    allowed_extra = set("-.,;:()'/&%#+_\\")
    if not all(
        c.isalpha() or c.isdigit() or c.isspace() or c in allowed_extra for c in value
    ):
        raise ValidationException("Path contains invalid characters")
    return value


def validate_integer(
    value: Any, min_value: int | None = None, max_value: int | None = None
) -> int:
    """
    Validate and convert a value to integer.
    Specifically for money values in Chilean Pesos.

    Args:
        value: Value to validate
        min_value: Minimum allowed value (inclusive)
        max_value: Maximum allowed value (inclusive)

    Returns:
        int: Validated integer value

    Raises:
        ValidationException: If validation fails
    """
    try:
        if isinstance(value, float):
            raise ValidationException("Integer required, got float")
        int_value = int(value)
        if not isinstance(int_value, int):
            raise ValidationException("Value must be an integer")
        if min_value is not None and int_value < min_value:
            raise ValidationException(
                f"Value must be greater than or equal to {min_value}"
            )
        if max_value is not None and int_value > max_value:
            raise ValidationException(
                f"Value must be less than or equal to {max_value}"
            )
        return int_value
    except (ValueError, TypeError):
        raise ValidationException(f"Invalid integer value: {value}") from None


def validate_float(
    value: Any,
    min_value: float | None = None,
    max_value: float | None = None,
    max_decimals: int = 3,
) -> float:
    """
    Validate and convert a value to float.
    Used primarily for quantities with up to 3 decimal places.

    Args:
        value: Value to validate
        min_value: Minimum allowed value (inclusive)
        max_value: Maximum allowed value (inclusive)
        max_decimals: Maximum allowed decimal places

    Returns:
        float: Validated float value

    Raises:
        ValidationException: If validation fails
    """
    try:
        float_value = float(value)

        # Check decimal places
        str_value = str(float_value)
        if "." in str_value:
            decimals = len(str_value.split(".")[1])
            if decimals > max_decimals:
                raise ValidationException(
                    f"Value cannot have more than {max_decimals} decimal places"
                )

        if min_value is not None and float_value < min_value:
            raise ValidationException(
                f"Value must be greater than or equal to {min_value}"
            )
        if max_value is not None and float_value > max_value:
            raise ValidationException(
                f"Value must be less than or equal to {max_value}"
            )

        # Round to specified decimal places
        return round(float_value, max_decimals)
    except (ValueError, TypeError):
        raise ValidationException("Invalid float value") from None


def validate_float_non_negative(value: float) -> float:
    """Validate a non-negative float value with 3 decimal places max."""
    return validate_float(value, min_value=0, max_decimals=3)


def validate_money(
    value: Any, field_name: str = "Amount", max_value: int | None = 1_000_000
) -> int:
    """
    Validate a money value (Chilean Pesos).

    By default caps at 1.000.000 CLP (suitable for unit prices).
    Pass max_value=None to skip the upper-bound check (suitable for totals).

    Args:
        value: Value to validate
        field_name: Name of field for error messages
        max_value: Upper bound (inclusive). None = no upper bound.

    Returns:
        int: Validated money value

    Raises:
        ValidationException: If value is invalid
    """
    try:
        decimal_value = Decimal(str(value))
        if decimal_value != decimal_value.to_integral_value():
            raise ValidationException(f"{field_name} cannot have decimals")
        money_value = int(decimal_value)
        if money_value < 0:
            raise ValidationException(f"{field_name} cannot be negative")
        if max_value is not None and money_value > max_value:
            raise ValidationException(f"{field_name} cannot exceed {max_value:,} CLP")
        return money_value
    except (InvalidOperation, ValueError, TypeError):
        raise ValidationException(f"Invalid {field_name.lower()} value") from None


def validate_money_multiplication(
    amount: int, quantity: float, field_name: str = "Total"
) -> int:
    """
    Multiply a unit price by quantity and return the rounded integer result.

    The result is a line total (not a unit price) so no upper-bound cap is applied.

    Args:
        amount: Unit price in CLP
        quantity: Quantity multiplier
        field_name: Name of field for error messages

    Returns:
        int: Rounded integer result

    Raises:
        ValidationException: If calculation fails
    """
    try:
        if amount < 0:
            raise ValidationException(f"{field_name} amount cannot be negative")
        if quantity < 0:
            raise ValidationException(f"{field_name} quantity cannot be negative")
        return int(round(float(amount) * quantity))
    except ValidationException:
        raise
    except (ValueError, TypeError):
        raise ValidationException(f"Invalid {field_name.lower()} calculation") from None


def validate_quantity(value: Any) -> float:
    """
    Validate a quantity value.
    Must be a positive float with up to 3 decimal places.

    Args:
        value: Value to validate

    Returns:
        float: Validated quantity value

    Raises:
        ValidationException: If validation fails
    """
    return validate_float(value, min_value=0.001, max_decimals=3)


def validate_date(date_str: str, format: str = "%Y-%m-%d") -> str:
    try:
        datetime_obj = datetime.strptime(date_str, format)

        current_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        check_date = datetime_obj.replace(hour=0, minute=0, second=0, microsecond=0)
        if check_date > current_date:
            raise ValidationException("Date cannot be in the future")

        return datetime_obj.strftime(format)
    except ValueError:
        raise ValidationException(
            f"Invalid date format. Expected format: {format}"
        ) from None


def validate_with_pattern(
    value: str, pattern: str, error_message: str = "Invalid format"
) -> str:
    """Validate string with regex pattern."""
    if not re.match(pattern, value):
        raise ValidationException(error_message)
    return value


def validate_identifier(value: str, length: int | tuple[int, ...]) -> str:
    """Validate numeric identifier with specific length(s)."""
    value = validate_string(value)

    if isinstance(length, int):
        pattern = rf"^\d{{{length}}}$"
        error_message = f"Identifier must be exactly {length} digits"
    else:
        pattern = rf"^\d{{{','.join(map(str, length))}}}$"
        error_message = f"Identifier must be {' or '.join(map(str, length))} digits"

    return validate_with_pattern(value, pattern, error_message)


def validate_9digit_identifier(value: str) -> str:
    """Validate a 9-digit identifier."""
    value = validate_identifier(value, length=9)
    if not value.startswith("9"):
        raise ValidationException("Identifier must start with 9")
    return value


def validate_3or4digit_identifier(value: str) -> str:
    """Validate a 3 or 4-digit identifier."""
    value = validate_identifier(value, length=(3, 4))
    if value.startswith("0"):
        raise ValidationException("Identifier cannot start with 0")
    return value


def validate_barcode(barcode: str | None) -> str | None:
    """Validate a barcode (EAN-8, UPC-A, EAN-13, EAN-14) format."""
    if barcode is None:
        return None
    if not isinstance(barcode, str):
        raise ValidationException("Barcode must be a string")

    # Remove any whitespace
    barcode = barcode.strip()
    if len(barcode) == 0:
        return barcode

    if not barcode.isdigit():
        raise ValidationException("Barcode must contain only digits")

    valid_lengths = {8, 12, 13, 14}
    if len(barcode) not in valid_lengths:
        raise ValidationException(f"Barcode must be one of: {valid_lengths} digits")

    return barcode


def validate_list(
    value: Any,
    item_validator: Callable[[Any], Any],
    min_length: int = 0,
    max_length: int | None = None,
) -> list[Any]:
    if not isinstance(value, list):
        raise ValidationException("Value must be a list")
    if len(value) < min_length:
        raise ValidationException(f"List must have at least {min_length} items")
    if max_length is not None and len(value) > max_length:
        raise ValidationException(f"List can have at most {max_length} items")
    return [item_validator(item) for item in value]


def validate_dict(
    value: Any,
    key_validator: Callable[[Any], Any],
    value_validator: Callable[[Any], Any],
) -> dict:
    if not isinstance(value, dict):
        raise ValidationException("Value must be a dictionary")
    return {key_validator(k): value_validator(v) for k, v in value.items()}
