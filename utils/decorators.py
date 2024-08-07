import functools
import logging
from typing import Callable, Type, Optional, TypeVar, ParamSpec
from PySide6.QtWidgets import QMessageBox, QWidget, QApplication
from .exceptions import *
import time

logger = logging.getLogger(__name__)

T = TypeVar('T')
P = ParamSpec('P')

def log_exception(exc: Exception, func_name: str, error_message: str) -> None:
    """Helper function to log exceptions."""
    logger.exception(f"{error_message} in {func_name}: {str(exc)}")

def show_error_dialog(title: str, message: str, parent: Optional[QWidget] = None) -> None:
    """Helper function to show error dialog to the user."""
    if parent is None:
        parent = QApplication.activeWindow()
    QMessageBox.critical(parent, title, message)

def handle_exceptions(*exception_types: Type[Exception], show_dialog: bool = False) -> Callable[[Callable[P, T]], Callable[P, T]]:
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
                error_message = f"Error in {func.__name__}"
                log_exception(e, func.__name__, error_message)
                if show_dialog:
                    # Assuming the first argument might be self or cls in a class method
                    parent = args[0] if args and isinstance(args[0], QWidget) else None
                    show_error_dialog("Operation Failed", str(e), parent)
                raise
        return wrapper
    return decorator

def db_operation(show_dialog: bool = False) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorator for database operations."""
    return handle_exceptions(DatabaseException, NotFoundException, show_dialog=show_dialog)

def validate_input(show_dialog: bool = False) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorator for input validation."""
    return handle_exceptions(ValidationException, show_dialog=show_dialog)

def require_authorization(show_dialog: bool = True) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorator for operations requiring authorization."""
    return handle_exceptions(AuthorizationException, show_dialog=show_dialog)

def handle_external_service(show_dialog: bool = False) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorator for external service interactions."""
    return handle_exceptions(ExternalServiceException, show_dialog=show_dialog)

def handle_concurrency(show_dialog: bool = False) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorator for concurrency-sensitive operations."""
    return handle_exceptions(ConcurrencyException, show_dialog=show_dialog)

def enforce_business_logic(show_dialog: bool = False) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorator for enforcing business logic rules."""
    return handle_exceptions(BusinessLogicException, show_dialog=show_dialog)

def ui_operation(show_dialog: bool = True) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorator for UI operations."""
    return handle_exceptions(UIException, show_dialog=show_dialog)

def retry(max_attempts: int = 3, delay: float = 1.0) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """
    A decorator that retries the function execution on failure.
    
    Args:
    - max_attempts: Maximum number of retry attempts
    - delay: Delay between retries in seconds
    """
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            attempts = 0
            last_exception: Optional[Exception] = None
            while attempts < max_attempts:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    attempts += 1
                    last_exception = e
                    if attempts < max_attempts:
                        time.sleep(delay)
                    else:
                        log_exception(e, func.__name__, f"Failed after {max_attempts} attempts")
            
            if last_exception:
                raise last_exception
            else:
                raise RuntimeError(f"Failed to execute {func.__name__} after {max_attempts} attempts")
        
        return wrapper
    return decorator

def measure_performance(threshold: Optional[float] = None) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """
    A decorator that measures the execution time of a function.
    
    Args:
    - threshold: If set, log a warning if execution time exceeds this value (in seconds)
    """
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            start_time = time.time()
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            logger.debug(f"{func.__name__} executed in {execution_time:.2f} seconds")
            if threshold and execution_time > threshold:
                logger.warning(f"{func.__name__} exceeded threshold of {threshold} seconds")
            return result
        return wrapper
    return decorator

def cache_result(ttl: int = 300) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """
    A decorator that caches the result of a function for a specified time.
    
    Args:
    - ttl: Time to live for the cached result in seconds
    """
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        cache: dict = {}
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            key = str(args) + str(kwargs)
            if key in cache and time.time() - cache[key]['time'] < ttl:
                return cache[key]['result']
            result = func(*args, **kwargs)
            cache[key] = {'result': result, 'time': time.time()}
            return result
        return wrapper
    return decorator
