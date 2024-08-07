import logging
import logging.config
import os
from pathlib import Path
import yaml
import sys
from typing import Any, Dict

from config import DEBUG_LEVEL, APP_NAME

def setup_logger() -> logging.Logger:
    """
    Set up and configure the logger for the application.

    Returns:
        logging.Logger: Configured logger instance.
    """
    config_path = Path(__file__).resolve().parent / 'logging_config.yaml'
    
    if os.path.exists(config_path):
        setup_logger_from_yaml(config_path)
    else:
        setup_default_logger()

    logger = logging.getLogger(APP_NAME)
    
    return logger

def setup_logger_from_yaml(config_path: Path) -> None:
    """
    Set up logger configuration from a YAML file.

    Args:
        config_path (Path): Path to the YAML configuration file.
    """
    try:
        with open(config_path, 'rt') as f:
            config = yaml.safe_load(f.read())
        logging.config.dictConfig(config)
    except Exception as e:
        print(f"Error in loading logger configuration from YAML: {e}")
        print("Falling back to default configuration.")
        setup_default_logger()

def setup_default_logger() -> None:
    """Set up a default logger configuration."""
    logging.basicConfig(
        level=DEBUG_LEVEL,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(f"{APP_NAME.lower()}.log")
        ]
    )

def log_exception(exc_type: type, exc_value: Exception, exc_traceback: Any) -> None:
    """
    Log an exception with full traceback.

    Args:
        exc_type (type): The type of the exception.
        exc_value (Exception): The exception instance.
        exc_traceback (Any): The traceback object.
    """
    logger = logging.getLogger(APP_NAME)
    logger.error(
        "Uncaught exception", 
        exc_info=(exc_type, exc_value, exc_traceback)
    )

class LoggerAdapter(logging.LoggerAdapter):
    """
    A custom LoggerAdapter that adds contextual information to log records.
    """
    def __init__(self, logger: logging.Logger, extra: Dict[str, Any] | None = None):
        super().__init__(logger, extra or {})

    def process(self, msg: str, kwargs: Dict[str, Any]) -> tuple[str, Dict[str, Any]]:
        extra = kwargs.get('extra', {})
        if self.extra:
            extra.update(self.extra)
        kwargs['extra'] = extra
        return msg, kwargs

# Set up the logger
logger = setup_logger()

# Create a LoggerAdapter instance
logger_adapter = LoggerAdapter(logger, {'app_name': APP_NAME})

# Set the exception hook to use our custom logger
sys.excepthook = log_exception

# Export the LoggerAdapter instance as 'logger'
logger = logger_adapter