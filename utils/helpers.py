import datetime
from decimal import Decimal
from typing import Any, Callable, List, Optional, TypeVar, Union

from PySide6.QtWidgets import QHeaderView, QMessageBox, QTableWidget, QWidget

from utils.exceptions import ValidationException
from utils.system.logger import logger

T = TypeVar("T")


def create_table(headers: List[str]) -> QTableWidget:
    """
    Create and return a QTableWidget with the specified headers.

    Args:
        headers (List[str]): A list of strings to be used as table headers.

    Returns:
        QTableWidget: A configured table widget with the specified headers.
    """
    try:
        table = QTableWidget()
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive
        )
        table.horizontalHeader().setStretchLastSection(True)
        table.setSortingEnabled(True)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        logger.debug(f"Created table with {len(headers)} columns")
        return table
    except Exception as e:
        logger.error(f"Error creating table: {str(e)}")
        raise


def show_message(
    title: str, message: str, icon: QMessageBox.Icon = QMessageBox.Icon.Information
) -> None:
    """
    Display a message box with the specified title, message, and icon.

    Args:
        title (str): The title of the message box.
        message (str): The message to be displayed.
        icon (QMessageBox.Icon): The icon to be displayed in the message box.
    """
    try:
        msg_box = QMessageBox()
        msg_box.setIcon(icon)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.exec()
        logger.debug(f"Showed message: {title} - {message}")
    except Exception as e:
        logger.error(f"Error showing message: {str(e)}")
        raise


def show_error_message(title: str, message: str) -> None:
    """
    Display an error message box with the specified title and message.

    Args:
        title (str): The title of the error message box.
        message (str): The detailed error message to be displayed.
    """
    show_message(title, message, QMessageBox.Icon.Critical)
    logger.error(f"Error message shown: {title} - {message}")


def show_info_message(title: str, message: str) -> None:
    """
    Display an information message box with the specified title and message.

    Args:
        title (str): The title of the information message box.
        message (str): The detailed information message to be displayed.
    """
    show_message(title, message, QMessageBox.Icon.Information)
    logger.info(f"Info message shown: {title} - {message}")


def validate_integer_input(
    value: str,
    field_name: str,
    min_value: Optional[int] = None,
    max_value: Optional[int] = None,
) -> int:
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
        ValidationException: If the input cannot be converted to a valid integer or is out of the specified range.
    """
    try:
        int_value = int(value)
        if min_value is not None and int_value < min_value:
            raise ValidationException(f"{field_name} must be at least {min_value}.")
        if max_value is not None and int_value > max_value:
            raise ValidationException(f"{field_name} must not exceed {max_value}.")
        return int_value
    except ValueError:
        raise ValidationException(f"{field_name} must be a valid integer.")


def safe_convert(value: Any, target_type: Callable[[Any], T], default: T) -> T:
    """
    Safely convert a value to a target type, returning a default value if conversion fails.

    Args:
        value (Any): The value to be converted.
        target_type (Callable[[Any], T]): The type to convert the value to.
        default (T): The default value to return if conversion fails.

    Returns:
        T: The converted value or the default value if conversion fails.
    """
    try:
        return target_type(value)
    except (ValueError, TypeError):
        logger.warning(
            f"Conversion failed for value: {value}. Using default: {default}"
        )
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
    return text[: max_length - len(ellipsis)] + ellipsis


def format_price(amount: Union[int, float, Decimal]) -> str:
    """
    Format a price with dot as thousand separator and no decimals.

    Args:
        amount (Union[int, float, Decimal]): The price amount to format.

    Returns:
        str: The formatted price string.
    """
    return f"{int(amount):,}".replace(",", ".")


def confirm_action(parent: Optional[QWidget], title: str, message: str) -> bool:
    """
    Display a confirmation dialog and return the user's choice.

    Args:
        parent (Optional[QWidget]): The parent widget for the dialog.
        title (str): The title of the confirmation dialog.
        message (str): The message to display in the confirmation dialog.

    Returns:
        bool: True if the user confirms, False otherwise.
    """
    try:
        msg_box = QMessageBox(parent) if parent else QMessageBox()
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        msg_box.setDefaultButton(QMessageBox.StandardButton.No)

        result = msg_box.exec()

        confirmed = result == QMessageBox.StandardButton.Yes
        logger.debug(
            f"Action confirmation: {title} - {'Confirmed' if confirmed else 'Cancelled'}"
        )
        return confirmed
    except Exception as e:
        logger.error(f"Error in confirm_action: {str(e)}")
        raise
