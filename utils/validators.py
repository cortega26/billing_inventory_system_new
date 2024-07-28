import re
from typing import Union

def validate_9digit_identifier(identifier: str) -> None:
    """
    Validate that the given identifier is exactly 9 digits.

    Args:
        identifier (str): The identifier to validate.

    Raises:
        ValueError: If the identifier is not exactly 9 digits.
    """
    if not re.match(r'^\d{9}$', identifier):
        raise ValueError("9-digit identifier must be exactly 9 digits")

def validate_4digit_identifier(identifier: Union[str, None]) -> None:
    """
    Validate that the given identifier is either None or exactly 4 digits.

    Args:
        identifier (Union[str, None]): The identifier to validate.

    Raises:
        ValueError: If the identifier is not None and not exactly 4 digits.
    """
    if identifier and not re.match(r'^\d{4}$', identifier):
        raise ValueError("4-digit identifier must be exactly 4 digits or empty")

def validate_positive_integer(value: Union[int, str], field_name: str) -> int:
    """
    Validate that the given value is a positive integer.

    Args:
        value (Union[int, str]): The value to validate.
        field_name (str): The name of the field for error reporting.

    Returns:
        int: The validated positive integer.

    Raises:
        ValueError: If the value is not a positive integer.
    """
    try:
        int_value = int(value)
        if int_value <= 0:
            raise ValueError
        return int_value
    except ValueError:
        raise ValueError(f"{field_name} must be a positive integer")

def validate_positive_float(value: Union[float, str], field_name: str) -> float:
    """
    Validate that the given value is a positive float.

    Args:
        value (Union[float, str]): The value to validate.
        field_name (str): The name of the field for error reporting.

    Returns:
        float: The validated positive float.

    Raises:
        ValueError: If the value is not a positive float.
    """
    try:
        float_value = float(value)
        if float_value <= 0:
            raise ValueError
        return float_value
    except ValueError:
        raise ValueError(f"{field_name} must be a positive number")

def validate_string(value: str, field_name: str, max_length: Union[int, None] = None) -> str:
    """
    Validate that the given value is a non-empty string and optionally check its length.

    Args:
        value (str): The string to validate.
        field_name (str): The name of the field for error reporting.
        max_length (Union[int, None], optional): The maximum allowed length of the string. Defaults to None.

    Returns:
        str: The validated string.

    Raises:
        ValueError: If the string is empty or exceeds the maximum length.
    """
    if not value.strip():
        raise ValueError(f"{field_name} cannot be empty")
    if max_length and len(value) > max_length:
        raise ValueError(f"{field_name} must be {max_length} characters or less")
    return value.strip()