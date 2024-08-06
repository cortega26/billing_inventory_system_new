import functools
import logging
from typing import Callable, Any, Type, Union, Optional
from PySide6.QtWidgets import QMessageBox, QWidget,QApplication
from .exceptions import *

logger = logging.getLogger(__name__)

def log_exception(exc: Exception, func_name: str, error_message: str):
    """Helper function to log exceptions."""
    logger.exception(f"{error_message} in {func_name}: {str(exc)}")

def show_error_dialog(title: str, message: str, parent: Optional[QWidget] = None):
    """Helper function to show error dialog to the user."""
    if parent is None:
        parent = QApplication.activeWindow()
    else:
        QMessageBox.critical(parent, title, message)


def handle_exceptions(*exception_types: Type[Exception], show_dialog: bool = False):
    """
    A decorator to handle specified exception types.
    
    Args:
    - *exception_types: Exception types to be caught
    - show_dialog: Whether to show an error dialog to the user
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            try:
                return func(*args, **kwargs)
            except exception_types as e:
                error_message = f"Error in {func.__name__}"
                log_exception(e, func.__name__, error_message)
                if show_dialog:
                    # Assuming the first argument might be self or cls in a class method
                    parent = args[0] if args and isinstance(args[0], QWidget) else None
                    show_error_dialog("Operation Failed", str(e), parent)
                raise
        return wrapper
    return decorator

def db_operation(show_dialog: bool = False):
    """Decorator for database operations."""
    return handle_exceptions(DatabaseException, NotFoundException, show_dialog=show_dialog)

def validate_input(show_dialog: bool = False):
    """Decorator for input validation."""
    return handle_exceptions(ValidationException, show_dialog=show_dialog)

def require_authorization(show_dialog: bool = True):
    """Decorator for operations requiring authorization."""
    return handle_exceptions(AuthorizationException, show_dialog=show_dialog)

def handle_external_service(show_dialog: bool = False):
    """Decorator for external service interactions."""
    return handle_exceptions(ExternalServiceException, show_dialog=show_dialog)

def handle_concurrency(show_dialog: bool = False):
    """Decorator for concurrency-sensitive operations."""
    return handle_exceptions(ConcurrencyException, show_dialog=show_dialog)

def enforce_business_logic(show_dialog: bool = False):
    """Decorator for enforcing business logic rules."""
    return handle_exceptions(BusinessLogicException, show_dialog=show_dialog)

def ui_operation(show_dialog: bool = True):
    """Decorator for UI operations."""
    return handle_exceptions(UIException, show_dialog=show_dialog)

def retry(max_attempts: int = 3, delay: float = 1.0):
    """
    A decorator that retries the function execution on failure.
    
    Args:
    - max_attempts: Maximum number of retry attempts
    - delay: Delay between retries in seconds
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            import time
            attempts = 0
            while attempts < max_attempts:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    attempts += 1
                    if attempts == max_attempts:
                        log_exception(e, func.__name__, f"Failed after {max_attempts} attempts")
                        raise
                    time.sleep(delay)
        return wrapper
    return decorator

def measure_performance(threshold: Optional[float] = None):
    """
    A decorator that measures the execution time of a function.
    
    Args:
    - threshold: If set, log a warning if execution time exceeds this value (in seconds)
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            import time
            start_time = time.time()
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            logger.debug(f"{func.__name__} executed in {execution_time:.2f} seconds")
            if threshold and execution_time > threshold:
                logger.warning(f"{func.__name__} exceeded threshold of {threshold} seconds")
            return result
        return wrapper
    return decorator

def cache_result(ttl: int = 300):
    """
    A decorator that caches the result of a function for a specified time.
    
    Args:
    - ttl: Time to live for the cached result in seconds
    """
    def decorator(func: Callable) -> Callable:
        cache = {}
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            import time
            key = str(args) + str(kwargs)
            if key in cache and time.time() - cache[key]['time'] < ttl:
                return cache[key]['result']
            result = func(*args, **kwargs)
            cache[key] = {'result': result, 'time': time.time()}
            return result
        return wrapper
    return decorator
