from PySide6.QtWidgets import QTableWidget, QHeaderView, QMessageBox
from typing import List

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
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
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

def format_currency(amount: int) -> str:
    """
    Format an integer amount as a string with thousands separators.

    Args:
        amount (int): The amount to be formatted.

    Returns:
        str: The formatted amount as a string with thousands separators.
    """
    return f"{amount:,}"

def validate_integer_input(value: str, field_name: str) -> int:
    """
    Validate and convert a string input to an integer.

    Args:
        value (str): The string value to be converted.
        field_name (str): The name of the field for error reporting.

    Returns:
        int: The converted integer value.

    Raises:
        ValueError: If the input cannot be converted to a valid integer.
    """
    try:
        return int(value)
    except ValueError:
        raise ValueError(f"{field_name} must be a valid integer.")