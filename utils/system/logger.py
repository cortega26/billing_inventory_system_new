import logging
import logging.config
import os
from pathlib import Path
import yaml
import sys
from typing import Any
from config import DEBUG_LEVEL, APP_NAME
import json

class StructuredLogger:
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(DEBUG_LEVEL)

    def _log(self, level: int, message: str, **kwargs):
        extra = json.dumps(kwargs) if kwargs else ""
        self.logger.log(level, f"{message} {extra}")

    def debug(self, message: str, **kwargs):
        self._log(logging.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs):
        self._log(logging.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs):
        self._log(logging.WARNING, message, **kwargs)

    def error(self, message: str, **kwargs):
        self._log(logging.ERROR, message, **kwargs)

    def critical(self, message: str, **kwargs):
        self._log(logging.CRITICAL, message, **kwargs)

def setup_logger() -> StructuredLogger:
    """
    Set up and configure the logger for the application.

    Returns:
        StructuredLogger: Configured logger instance.
    """
    config_path = Path(__file__).resolve().parent / "logging_config.yaml"

    if os.path.exists(config_path):
        setup_logger_from_yaml(config_path)
    else:
        setup_default_logger()

    return StructuredLogger(APP_NAME)

def setup_logger_from_yaml(config_path: Path) -> None:
    """
    Set up logger configuration from a YAML file.

    Args:
        config_path (Path): Path to the YAML configuration file.
    """
    try:
        with open(config_path, "rt") as f:
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
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(f"{APP_NAME.lower()}.log"),
        ],
    )

def log_exception(exc_type: type, exc_value: Exception, exc_traceback: Any) -> None:
    """
    Log an exception with full traceback.

    Args:
        exc_type (type): The type of the exception.
        exc_value (Exception): The exception instance.
        exc_traceback (Any): The traceback object.
    """
    logger = StructuredLogger(APP_NAME)
    logger.error("Uncaught exception", 
                 exc_info={
                     "type": str(exc_type),
                     "value": str(exc_value),
                     "traceback": str(exc_traceback)
                 })

# Set up the logger
logger = setup_logger()

# Set the exception hook to use our custom logger
sys.excepthook = log_exception
