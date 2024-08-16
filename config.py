"""Configuration settings for the Inventory and Billing System."""

from pathlib import Path
import logging
import os
from enum import IntEnum
from typing import Dict, Any
import json

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

DEBUG_LEVELS: Dict[DebugLevel, int] = {
    DebugLevel.CRITICAL: logging.CRITICAL,
    DebugLevel.ERROR: logging.ERROR,
    DebugLevel.WARNING: logging.WARNING,
    DebugLevel.INFO: logging.INFO,
    DebugLevel.DEBUG: logging.DEBUG,
}

# Set the desired debug level
DEBUG_LEVEL: int = DEBUG_LEVELS[DebugLevel.INFO]

class Config:
    """Class to manage configuration settings."""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
            cls._instance._config = {}
            cls._instance._load_config()
        return cls._instance
    
    def _load_config(self):
        config_file = Path(__file__).parent / 'app_config.json'
        if config_file.exists():
            with open(config_file, 'r') as f:
                self._config = json.load(f)
        else:
            self._config = {
                "theme": "default",
                "language": "en",
                "backup_interval": 24,  # hours
            }
            self._save_config()
    
    def _save_config(self):
        config_file = Path(__file__).parent / 'app_config.json'
        with open(config_file, 'w') as f:
            json.dump(self._config, f, indent=4)
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value."""
        return self._config.get(key, default)
    
    def set(self, key: str, value: Any):
        """Set a configuration value."""
        self._config[key] = value
        self._save_config()

# Global instance of Config
config = Config()

# Usage example:
# from config import config, APP_NAME, DATABASE_PATH
# theme = config.get('theme', 'default')
# config.set('language', 'es')
