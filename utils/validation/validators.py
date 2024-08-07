import re
from typing import Union, Optional, TypeVar, Any, Type, Tuple, List
from datetime import datetime

T = TypeVar("T")


def validate_9digit_identifier(identifier: str) -> str:
    """
    Validate a 9-digit identifier.

    Args:
        identifier (str): The identifier to validate.

    Returns:
        str: The validated identifier.

    Raises:
        ValueError: If the identifier is not exactly 9 digits.
    """
    if not re.match(r"^\d{9}$", identifier):
        raise ValueError("Identifier must be exactly 9 digits")
    return identifier


def validate_3or4digit_identifier(identifier: str) -> str:
    """
    Validate a 3 or 4-digit identifier.

    Args:
        identifier (str): The identifier to validate.

    Returns:
        str: The validated identifier.

    Raises:
        ValueError: If the identifier is not 3 or 4 digits.
    """
    if not re.match(r"^\d{3,4}$", identifier):
        raise ValueError("Identifier must be either 3 or 4 digits")
    return identifier


def validate_numeric(
    value: Union[int, float, str],
    field_name: str,
    min_value: Optional[Union[int, float]] = None,
    max_value: Optional[Union[int, float]] = None,
) -> Union[int, float]:
    """
    Validate and convert a value to a numeric type within an optional range.

    Args:
        value (Union[int, float, str]): The value to be validated and converted.
        field_name (str): The name of the field for error reporting.
        min_value (Optional[Union[int, float]]): The minimum allowed value (inclusive).
        max_value (Optional[Union[int, float]]): The maximum allowed value (inclusive).

    Returns:
        Union[int, float]: The validated numeric value.

    Raises:
        ValueError: If the input cannot be converted to a valid number or is out of the specified range.
    """
    try:
        numeric_value = float(value)
        if isinstance(value, str) and value.isdigit():
            numeric_value = int(value)
        if min_value is not None and numeric_value < min_value:
            raise ValueError(f"{field_name} must be at least {min_value}.")
        if max_value is not None and numeric_value > max_value:
            raise ValueError(f"{field_name} must not exceed {max_value}.")
        return numeric_value
    except ValueError:
        raise ValueError(f"{field_name} must be a valid number.")


def validate_string(
    value: str,
    field_name: str,
    max_length: Optional[int] = None,
    min_length: Optional[int] = None,
    pattern: Optional[str] = None,
) -> str:
    """
    Validate a string.

    Args:
        value (str): The string to validate.
        field_name (str): The name of the field for error reporting.
        max_length (Optional[int]): The maximum allowed length of the string.
        min_length (Optional[int]): The minimum allowed length of the string.
        pattern (Optional[str]): A regex pattern the string must match.

    Returns:
        str: The validated string.

    Raises:
        ValueError: If the string is empty, too short, too long, or doesn't match the pattern.
    """
    stripped_value = value.strip()
    if not stripped_value:
        raise ValueError(f"{field_name} cannot be empty")
    if min_length and len(stripped_value) < min_length:
        raise ValueError(f"{field_name} must be at least {min_length} characters long")
    if max_length and len(stripped_value) > max_length:
        raise ValueError(f"{field_name} must be {max_length} characters or less")
    if pattern and not re.match(pattern, stripped_value):
        raise ValueError(f"{field_name} does not match the required pattern")
    return stripped_value


def validate_email(email: str) -> str:
    """
    Validate an email address.

    Args:
        email (str): The email address to validate.

    Returns:
        str: The validated email address.

    Raises:
        ValueError: If the email address is invalid.
    """
    email_regex = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    if not re.match(email_regex, email):
        raise ValueError("Invalid email address")
    return email


def validate_date(date_str: str, format: str = "%Y-%m-%d") -> datetime:
    """
    Validate a date string and convert it to a datetime object.

    Args:
        date_str (str): The date string to validate.
        format (str): The expected format of the date string.

    Returns:
        datetime: The validated date as a datetime object.

    Raises:
        ValueError: If the date string is invalid or doesn't match the specified format.
    """
    try:
        return datetime.strptime(date_str, format)
    except ValueError:
        raise ValueError(f"Invalid date format. Expected format: {format}")


def validate_phone_number(phone: str) -> str:
    """
    Validate a phone number.

    Args:
        phone (str): The phone number to validate.

    Returns:
        str: The validated phone number.

    Raises:
        ValueError: If the phone number is invalid.
    """
    phone_regex = r"^\+?1?\d{9,15}$"
    if not re.match(phone_regex, phone):
        raise ValueError("Invalid phone number")
    return phone


def validate_url(url: str) -> str:
    """
    Validate a URL.

    Args:
        url (str): The URL to validate.

    Returns:
        str: The validated URL.

    Raises:
        ValueError: If the URL is invalid.
    """
    url_regex = r"^(http:\/\/www\.|https:\/\/www\.|http:\/\/|https:\/\/)?[a-z0-9]+([\-\.]{1}[a-z0-9]+)*\.[a-z]{2,5}(:[0-9]{1,5})?(\/.*)?$"
    if not re.match(url_regex, url):
        raise ValueError("Invalid URL")
    return url


def validate_type(
    value: Any, expected_type: Union[Type[T], Tuple[Type[T], ...]], field_name: str
) -> T:
    """
    Validate that a value is of the expected type(s).

    Args:
        value (Any): The value to validate.
        expected_type (Union[Type[T], Tuple[Type[T], ...]]): The expected type or tuple of types.
        field_name (str): The name of the field for error reporting.

    Returns:
        T: The validated value.

    Raises:
        TypeError: If the value is not of the expected type(s).
    """
    if not isinstance(value, expected_type):
        type_names = (
            expected_type.__name__
            if isinstance(expected_type, type)
            else " or ".join(t.__name__ for t in expected_type)
        )
        raise TypeError(f"{field_name} must be of type {type_names}")
    return value


def validate_in_range(
    value: Union[int, float],
    min_value: Union[int, float],
    max_value: Union[int, float],
    field_name: str,
) -> Union[int, float]:
    """
    Validate that a numeric value is within a specified range.

    Args:
        value (Union[int, float]): The value to validate.
        min_value (Union[int, float]): The minimum allowed value (inclusive).
        max_value (Union[int, float]): The maximum allowed value (inclusive).
        field_name (str): The name of the field for error reporting.

    Returns:
        Union[int, float]: The validated value.

    Raises:
        ValueError: If the value is not within the specified range.
    """
    if not min_value <= value <= max_value:
        raise ValueError(f"{field_name} must be between {min_value} and {max_value}")
    return value


def validate_non_empty_list(value: List[Any], field_name: str) -> List[Any]:
    """
    Validate that a list is not empty.

    Args:
        value (List[Any]): The list to validate.
        field_name (str): The name of the field for error reporting.

    Returns:
        List[Any]: The validated list.

    Raises:
        ValueError: If the list is empty.
    """
    if not value:
        raise ValueError(f"{field_name} cannot be empty")
    return value


def validate_boolean(value: Any, field_name: str) -> bool:
    """
    Validate and convert a value to a boolean.

    Args:
        value (Any): The value to validate and convert.
        field_name (str): The name of the field for error reporting.

    Returns:
        bool: The validated boolean value.

    Raises:
        ValueError: If the value cannot be converted to a boolean.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.lower()
        if lowered in ("true", "1", "yes", "on"):
            return True
        if lowered in ("false", "0", "no", "off"):
            return False
    raise ValueError(f"{field_name} must be a valid boolean value")
