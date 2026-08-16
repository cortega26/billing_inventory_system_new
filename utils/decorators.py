import functools
from collections.abc import Callable
from typing import Any, ParamSpec, TypeVar

from utils.system.logger import logger

from .exceptions import (
    DatabaseException,
    NotFoundException,
    UIException,
)

T = TypeVar("T")
P = ParamSpec("P")


def log_exception(exc: Exception, func_name: str, error_message: str) -> None:
    """Helper function to log exceptions."""
    logger.error(
        f"{error_message} in {func_name}",
        extra={"error": str(exc), "function": func_name},
    )


def show_error_dialog(title: str, message: str, parent: Any = None) -> None:
    """Helper function to show error dialog to the user."""
    import sys

    if "pytest" in sys.modules:
        logger.warning(f"Suppressing error dialog in test: {title} - {message}")
        return

    try:
        from PySide6.QtWidgets import QApplication, QMessageBox
    except ImportError:
        logger.warning("PySide6 not found, cannot show error dialog")
        return

    if parent is None:
        parent = QApplication.activeWindow()
    QMessageBox.critical(parent, title, message)


def _get_dialog_parent(args: tuple[Any, ...]) -> Any:
    """Return a QWidget parent only for UI-bound calls."""
    try:
        from PySide6.QtWidgets import QWidget
    except ImportError:
        return None

    if args and isinstance(args[0], QWidget):
        return args[0]

    return None


def handle_exceptions(
    *exception_types: type[Exception], show_dialog: bool = False
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """
    A decorator to handle specified exception types.

    Args:
    - *exception_types: Exception types to be caught
    - show_dialog: Whether to show an error dialog to the user
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            try:
                return func(*args, **kwargs)
            except exception_types as e:
                error_message = f"Error in {func.__name__}: {str(e)}"
                log_exception(e, func.__name__, error_message)
                parent = _get_dialog_parent(args)
                if show_dialog and parent is not None:
                    show_error_dialog("Operation Failed", str(e), parent)
                raise

        return wrapper

    return decorator


def db_operation(
    show_dialog: bool = False,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorator for database operations."""
    return handle_exceptions(
        DatabaseException, NotFoundException, show_dialog=show_dialog
    )


def ui_operation(
    show_dialog: bool = True,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorator for UI operations."""
    return handle_exceptions(UIException, show_dialog=show_dialog)
