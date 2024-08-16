import html
import re
from typing import Any

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

def sanitize_integer(value: Any) -> int:
    """
    Ensure the given value is a valid integer.
    
    Args:
        value (Any): The value to sanitize.
    
    Returns:
        int: The sanitized integer.
    
    Raises:
        ValueError: If the value cannot be converted to an integer.
    """
    try:
        return int(value)
    except ValueError:
        raise ValueError(f"Cannot convert {value} to integer")

def sanitize_float(value: Any) -> float:
    """
    Ensure the given value is a valid float.
    
    Args:
        value (Any): The value to sanitize.
    
    Returns:
        float: The sanitized float.
    
    Raises:
        ValueError: If the value cannot be converted to a float.
    """
    try:
        return float(value)
    except ValueError:
        raise ValueError(f"Cannot convert {value} to float")

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

# You can add more sanitization functions as needed