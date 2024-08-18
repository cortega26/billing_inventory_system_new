import html
import re
from typing import Union
from decimal import Decimal

def sanitize_html(value: str) -> str:
    """
    Escape HTML special characters in the given string.
    
    Args:
        value (str): The string to sanitize.
    
    Returns:
        str: The sanitized string.
    """
    return html.escape(value)

def sanitize_sql(value: str) -> str:
    """
    Remove SQL injection vulnerable characters from the given string.
    
    Args:
        value (str): The string to sanitize.
    
    Returns:
        str: The sanitized string.
    """
    return re.sub(r"['\";]", "", value)

def sanitize_filename(value: str) -> str:
    """
    Remove characters that are not allowed in filenames.
    
    Args:
        value (str): The filename to sanitize.
    
    Returns:
        str: The sanitized filename.
    """
    return re.sub(r'[<>:"/\\|?*]', '', value)

def strip_tags(value: str) -> str:
    """
    Remove all HTML tags from the given string.
    
    Args:
        value (str): The string to sanitize.
    
    Returns:
        str: The sanitized string.
    """
    return re.sub(r'<[^>]*>', '', value)

def sanitize_number(value: Union[int, float, Decimal, str]) -> Union[int, float, Decimal]:
    """
    Ensure the given value is a valid number.
    
    Args:
        value (Union[int, float, Decimal, str]): The value to sanitize.
    
    Returns:
        Union[int, float, Decimal]: The sanitized number.
    
    Raises:
        ValueError: If the value cannot be converted to a number.
    """
    if isinstance(value, (int, float, Decimal)):
        return value
    try:
        return int(value)
    except ValueError:
        try:
            return float(value)
        except ValueError:
            try:
                return Decimal(value)
            except:
                raise ValueError(f"Cannot convert {value} to a number")

def truncate_string(value: str, max_length: int) -> str:
    """
    Truncate the given string to the specified maximum length.
    
    Args:
        value (str): The string to truncate.
        max_length (int): The maximum allowed length.
    
    Returns:
        str: The truncated string.
    """
    return value[:max_length]

def sanitize_email(value: str) -> str:
    """
    Sanitize and validate an email address.
    
    Args:
        value (str): The email address to sanitize.
    
    Returns:
        str: The sanitized email address.
    
    Raises:
        ValueError: If the email address is invalid.
    """
    email = value.strip().lower()
    if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
        raise ValueError("Invalid email address")
    return email

def sanitize_phone(value: str) -> str:
    """
    Sanitize and validate a phone number.
    
    Args:
        value (str): The phone number to sanitize.
    
    Returns:
        str: The sanitized phone number.
    
    Raises:
        ValueError: If the phone number is invalid.
    """
    phone = re.sub(r'\D', '', value)
    if not 7 <= len(phone) <= 15:
        raise ValueError("Invalid phone number")
    return phone

def sanitize_url(value: str) -> str:
    """
    Sanitize and validate a URL.
    
    Args:
        value (str): The URL to sanitize.
    
    Returns:
        str: The sanitized URL.
    
    Raises:
        ValueError: If the URL is invalid.
    """
    url = value.strip()
    if not re.match(r'^(http:\/\/www\.|https:\/\/www\.|http:\/\/|https:\/\/)?[a-z0-9]+([\-\.]{1}[a-z0-9]+)*\.[a-z]{2,5}(:[0-9]{1,5})?(\/.*)?$', url):
        raise ValueError("Invalid URL")
    return url
