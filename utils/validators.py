import re
from typing import Union, Optional
from datetime import datetime

def validate_9digit_identifier(identifier: str) -> None:
    """
    Validate a 9-digit identifier.

    Args:
        identifier (str): The identifier to validate.

    Raises:
        ValueError: If the identifier is not exactly 9 digits.
    """
    if not re.match(r'^\d{9}$', identifier):
        raise ValueError("Identifier must be exactly 9 digits")

def validate_3or4digit_identifier(identifier: str) -> None:
    """
    Validate a 3 or 4-digit identifier.

    Args:
        identifier (str): The identifier to validate.

    Raises:
        ValueError: If the identifier is not 3 or 4 digits.
    """
    if not re.match(r'^\d{3,4}$', identifier):
        raise ValueError("Identifier must be either 3 or 4 digits")

def validate_positive_integer(value: Union[int, str], field_name: str) -> int:
    """
    Validate and convert a value to a positive integer.

    Args:
        value (Union[int, str]): The value to validate and convert.
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
    Validate and convert a value to a positive float.

    Args:
        value (Union[float, str]): The value to validate and convert.
        field_name (str): The name of the field for error reporting.

    Returns:
        float: The validated positive float.

    Raises:
        ValueError: If the value is not a positive number.
    """
    try:
        float_value = float(value)
        if float_value <= 0:
            raise ValueError
        return float_value
    except ValueError:
        raise ValueError(f"{field_name} must be a positive number")

def validate_string(value: str, field_name: str, max_length: Optional[int] = None, min_length: Optional[int] = None) -> str:
    """
    Validate a string.

    Args:
        value (str): The string to validate.
        field_name (str): The name of the field for error reporting.
        max_length (Optional[int]): The maximum allowed length of the string.
        min_length (Optional[int]): The minimum allowed length of the string.

    Returns:
        str: The validated string.

    Raises:
        ValueError: If the string is empty, too short, or too long.
    """
    stripped_value = value.strip()
    if not stripped_value:
        raise ValueError(f"{field_name} cannot be empty")
    if min_length and len(stripped_value) < min_length:
        raise ValueError(f"{field_name} must be at least {min_length} characters long")
    if max_length and len(stripped_value) > max_length:
        raise ValueError(f"{field_name} must be {max_length} characters or less")
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
    email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
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
    phone_regex = r'^\+?1?\d{9,15}$'
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
    url_regex = r'^(http:\/\/www\.|https:\/\/www\.|http:\/\/|https:\/\/)?[a-z0-9]+([\-\.]{1}[a-z0-9]+)*\.[a-z]{2,5}(:[0-9]{1,5})?(\/.*)?$'
    if not re.match(url_regex, url):
        raise ValueError("Invalid URL")
    return url