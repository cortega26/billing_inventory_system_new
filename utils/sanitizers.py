import html
import re


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
