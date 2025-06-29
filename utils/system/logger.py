import logging
import logging.config
import logging.handlers
from pathlib import Path
import yaml
from typing import Any, Optional, Dict
import json
from functools import wraps
from config import DEBUG_LEVEL, APP_NAME
from datetime import datetime

class LogLevel:
    """Enum-like class for log levels with clear hierarchy."""
    DEBUG = logging.DEBUG       # Detailed information for debugging
    INFO = logging.INFO        # General operational events
    WARNING = logging.WARNING  # Warning messages for potential issues
    ERROR = logging.ERROR      # Error events that might still allow the app to run
    CRITICAL = logging.CRITICAL  # Critical errors that prevent proper functioning

class StructuredLogger:
    """Enhanced logger with structured logging capabilities and context management."""
    
    def __init__(self, name: str, log_file: Optional[Path] = None):
        self.name = name
        self._context = {}
        self._log_file = log_file
        self._logger = logging.getLogger(name)
        self._logger.setLevel(DEBUG_LEVEL)  # Set level immediately
        
        if log_file is not None:
            handler = logging.FileHandler(log_file, encoding='utf-8')
            handler.setLevel(DEBUG_LEVEL)  # Set handler level
            formatter = JsonFormatter()
            handler.setFormatter(formatter)
            self._logger.addHandler(handler)

        self._logger.propagate = False  # Prevent double logging

    def with_context(self, **kwargs) -> 'StructuredLogger':
        """Create a new logger instance with added context."""
        new_logger = StructuredLogger(self.name, self._log_file)
        new_logger._context = {**self._context, **kwargs}
        return new_logger

    def _format_message(self, message: str, extra: Optional[Dict[str, Any]] = None) -> str:
        """Format message with context and extra data."""
        log_data = {
            "message": message,
            "timestamp": datetime.now().isoformat(),
            **self._context,
            **(extra or {})  # Use empty dict if extra is None
        }
        return json.dumps(log_data)

    def info(self, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        self._logger.info(self._format_message(message, extra))

    def debug(self, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        self._logger.debug(self._format_message(message, extra))

    def warning(self, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        self._logger.warning(self._format_message(message, extra))

    def error(self, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        self._logger.error(self._format_message(message, extra))

    def critical(self, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        self._logger.critical(self._format_message(message, extra))

    def _log(self, level: int, message: str, **kwargs) -> None:
        """Internal method for logging with level."""
        self._logger.log(level, self._format_message(message, kwargs))

class JsonFormatter(logging.Formatter):
    """Format log records as JSON."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format the log record as JSON."""
        data = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name
        }
        
        # Parse the message if it's JSON
        try:
            message_data = json.loads(record.msg)
            data.update(message_data)
        except (json.JSONDecodeError, TypeError):
            data["message"] = record.msg
            
        return json.dumps(data)

class LoggerConfig:
    """Configuration class for logger settings."""
    def __init__(self, log_file: Path, level: int, max_size: int, backup_count: int, format: str):
        self.log_file = log_file
        self.level = level
        self.max_size = max_size
        self.backup_count = backup_count
        self.format = format

def setup_logger(config: LoggerConfig) -> StructuredLogger:
    """Set up the logger with the given configuration."""
    logger = StructuredLogger("app", config.log_file)
    
    handler = logging.handlers.RotatingFileHandler(
        config.log_file,
        maxBytes=config.max_size,
        backupCount=config.backup_count,
        encoding='utf-8'
    )
    
    handler.setFormatter(
        JsonFormatter() if config.format == "json" 
        else logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    )
    
    logger._logger.addHandler(handler)
    logger._logger.setLevel(config.level)
    return logger

def rotate_logs(log_dir: Path) -> None:
    """Rotate log files in the given directory."""
    for handler in logger._logger.handlers:
        if isinstance(handler, logging.handlers.RotatingFileHandler):
            handler.doRollover()

def clear_logs(log_dir: Path) -> None:
    """Clear all log files in the given directory."""
    for log_file in log_dir.glob("*.log*"):
        log_file.unlink(missing_ok=True)

def setup_structured_logger() -> StructuredLogger:
    """Configure and set up the application logger."""
    # Set root logger level first
    logging.getLogger().setLevel(DEBUG_LEVEL)
    
    config_path = Path("login_config.yaml")
    
    if config_path.exists():
        with open(config_path) as f:
            config = yaml.safe_load(f)
            logging.config.dictConfig(config)
    else:
        # Fallback configuration if YAML doesn't exist
        logging.basicConfig(
            level=DEBUG_LEVEL,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler(f"{APP_NAME.lower()}.log"),
            ],
        )

    logger = StructuredLogger(APP_NAME)
    logger._logger.setLevel(DEBUG_LEVEL)  # Ensure logger level is set
    return logger

def log_method(level: int = LogLevel.DEBUG):
    """Decorator for logging method calls with their arguments and results."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            func_logger = logger.with_context(
                function=func.__name__,
                module=func.__module__
            )
            
            # Log method entry
            func_logger._log(level, f"Entering {func.__name__}", 
                           args=str(args[1:]), kwargs=str(kwargs))
            
            try:
                result = func(*args, **kwargs)
                # Log successful completion
                func_logger._log(level, f"Completed {func.__name__}")
                return result
            except Exception as e:
                # Log exception with full context
                func_logger.error(
                    f"Exception in {func.__name__}",
                    extra={
                        "exc_info": True,
                        "exception_type": type(e).__name__,
                        "exception_message": str(e)
                    }
                )
                raise
            
        return wrapper
    return decorator

# Initialize global logger instance
logger = setup_structured_logger()
