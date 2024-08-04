from PySide6.QtWidgets import QTableWidget, QHeaderView, QMessageBox
from typing import List, Any, Optional, Union
from decimal import Decimal
import datetime

def create_table(headers: List[str]) -> QTableWidget:
    """
    Create and return a QTableWidget with the specified headers.

    Args:
        headers (List[str]): A list of strings to be used as table headers.

    Returns:
        QTableWidget: A configured table widget with the specified headers.
    """
    table = QTableWidget()
    table.setColumnCount(len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
    table.horizontalHeader().setStretchLastSection(True)
    table.setSortingEnabled(True)
    table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    return table

def show_error_message(title: str, message: str) -> None:
    """
    Display an error message box with the specified title and message.

    Args:
        title (str): The title of the error message box.
        message (str): The detailed error message to be displayed.
    """
    error_box = QMessageBox()
    error_box.setIcon(QMessageBox.Icon.Critical)
    error_box.setWindowTitle(title)
    error_box.setText(message)
    error_box.exec()

def show_info_message(title: str, message: str) -> None:
    """
    Display an information message box with the specified title and message.

    Args:
        title (str): The title of the information message box.
        message (str): The detailed information message to be displayed.
    """
    info_box = QMessageBox()
    info_box.setIcon(QMessageBox.Icon.Information)
    info_box.setWindowTitle(title)
    info_box.setText(message)
    info_box.exec()

def format_currency(amount: Union[int, float, Decimal]) -> str:
    """
    Format a numeric amount as a string with thousands separators and two decimal places.

    Args:
        amount (Union[int, float, Decimal]): The amount to be formatted.

    Returns:
        str: The formatted amount as a string with thousands separators and two decimal places.
    """
    return f"{amount:,.2f}"

def validate_integer_input(value: str, field_name: str, min_value: Optional[int] = None, max_value: Optional[int] = None) -> int:
    """
    Validate and convert a string input to an integer within an optional range.

    Args:
        value (str): The string value to be converted.
        field_name (str): The name of the field for error reporting.
        min_value (Optional[int]): The minimum allowed value (inclusive).
        max_value (Optional[int]): The maximum allowed value (inclusive).

    Returns:
        int: The converted integer value.

    Raises:
        ValueError: If the input cannot be converted to a valid integer or is out of the specified range.
    """
    try:
        int_value = int(value)
        if min_value is not None and int_value < min_value:
            raise ValueError(f"{field_name} must be at least {min_value}.")
        if max_value is not None and int_value > max_value:
            raise ValueError(f"{field_name} must not exceed {max_value}.")
        return int_value
    except ValueError:
        raise ValueError(f"{field_name} must be a valid integer.")

def safe_convert(value: Any, target_type: type, default: Any = None) -> Any:
    """
    Safely convert a value to a target type, returning a default value if conversion fails.

    Args:
        value (Any): The value to be converted.
        target_type (type): The type to convert the value to.
        default (Any, optional): The default value to return if conversion fails. Defaults to None.

    Returns:
        Any: The converted value or the default value if conversion fails.
    """
    try:
        return target_type(value)
    except (ValueError, TypeError):
        return default

def format_date(date: datetime.date, format_str: str = "%Y-%m-%d") -> str:
    """
    Format a date object as a string.

    Args:
        date (datetime.date): The date to be formatted.
        format_str (str, optional): The format string to use. Defaults to "%Y-%m-%d".

    Returns:
        str: The formatted date string.
    """
    return date.strftime(format_str)

def truncate_string(text: str, max_length: int, ellipsis: str = "...") -> str:
    """
    Truncate a string to a maximum length, appending an ellipsis if truncated.

    Args:
        text (str): The string to truncate.
        max_length (int): The maximum length of the resulting string, including the ellipsis.
        ellipsis (str, optional): The ellipsis to append if truncated. Defaults to "...".

    Returns:
        str: The truncated string.
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - len(ellipsis)] + ellipsis