from pathlib import Path
import logging
import os
from enum import IntEnum
from typing import Dict, Any, Optional
import json
from json.decoder import JSONDecodeError

# Application settings
APP_NAME: str = "Inventory and Billing System"
APP_VERSION: str = "2.0"
COMPANY_NAME: str = "El Rincón de Ébano"

# Database
DATABASE_NAME = os.environ.get("DATABASE_NAME", "billing_inventory.db")
DATABASE_PATH = Path(__file__).parent / DATABASE_NAME

# Analytics settings
LOYALTY_THRESHOLD: int = 5  # Number of purchases to be considered a loyal customer

# Debug Level
class DebugLevel(IntEnum):
    """Enum representing different debug levels for the application."""
    CRITICAL = 1
    ERROR = 2
    WARNING = 3
    INFO = 4
    DEBUG = 5

DEBUG_LEVEL_MAP: Dict[DebugLevel, int] = {
    DebugLevel.CRITICAL: logging.CRITICAL,
    DebugLevel.ERROR: logging.ERROR,
    DebugLevel.WARNING: logging.WARNING,
    DebugLevel.INFO: logging.INFO,
    DebugLevel.DEBUG: logging.DEBUG,
}

# Set the desired debug level
DEBUG_LEVEL: int = DEBUG_LEVEL_MAP[DebugLevel.INFO]

class Config:
    """Singleton class for managing application configuration."""

    _instance = None
    _config: Optional[Dict[str, Any]] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
        return cls._instance

    @classmethod
    def _load_config(cls):
        """Load configuration from file or create default if not exists."""
        if cls._config is None:
            config_file = Path(__file__).parent / 'app_config.json'
            if config_file.exists():
                try:
                    with open(config_file, 'r') as f:
                        cls._config = json.load(f)
                except (IOError, JSONDecodeError) as e:
                    print(f"Error loading configuration: {e}")
                    cls._config = cls._get_default_config()
            else:
                cls._config = cls._get_default_config()
                cls._save_config()

    @classmethod
    def _get_default_config(cls) -> Dict[str, Any]:
        """Return the default configuration."""
        return {
            "theme": "default",
            "language": "en",
            "backup_interval": 24,
        }

    @classmethod
    def _save_config(cls):
        """Save current configuration to file."""
        if cls._config is None:
            cls._config = cls._get_default_config()
        
        config_file = Path(__file__).parent / 'app_config.json'
        try:
            with open(config_file, 'w') as f:
                json.dump(cls._config, f, indent=4)
        except IOError as e:
            print(f"Error saving configuration: {e}")

    @classmethod
    def get(cls, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.

        Args:
            key (str): The configuration key.
            default (Any, optional): Default value if key is not found.

        Returns:
            Any: The configuration value or default.
        """
        cls._load_config()
        if cls._config is not None:
            return cls._config.get(key, default)
        return default

    @classmethod
    def set(cls, key: str, value: Any):
        """
        Set a configuration value.

        Args:
            key (str): The configuration key.
            value (Any): The value to set.
        """
        cls._load_config()
        if cls._config is None:
            cls._config = cls._get_default_config()
        cls._config[key] = value
        cls._save_config()

# Global instance of Config
config = Config()

# Usage example:
# from config import config, APP_NAME, DATABASE_PATH
# theme = config.get('theme', 'default')
# config.set('language', 'es')
