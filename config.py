import logging
import os
import re
import json
import time
from enum import IntEnum
from pathlib import Path
from typing import Dict, Any, Optional, Union
from json.decoder import JSONDecodeError
import threading

# Custom exceptions
class ConfigError(Exception):
    """Base exception for configuration errors."""
    pass

class ConfigLoadError(ConfigError):
    """Error loading configuration file."""
    pass

class ConfigValidationError(ConfigError):
    """Error validating configuration."""
    pass

# Application settings
APP_NAME: str = "Inventory and Billing System"
APP_VERSION: str = "2.0"
COMPANY_NAME: str = "El Rincón de Ébano"
CONFIG_VERSION: str = "1.0"

# Database configuration
def get_safe_db_path(db_name: str) -> Path:
    """
    Safely construct database path preventing directory traversal.
    
    Args:
        db_name: The name of the database file
        
    Returns:
        Path: Safe path to database file
    """
    sanitized_name = re.sub(r'[^a-zA-Z0-9_.-]', '', db_name)
    return Path(__file__).parent / sanitized_name

DATABASE_NAME = os.environ.get("DATABASE_NAME", "billing_inventory.db")
DATABASE_PATH = get_safe_db_path(DATABASE_NAME)

# Debug Level configuration
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
DEBUG_LEVEL = logging.INFO  # This should control the global level

class Config:
    """Thread-safe singleton class for managing application configuration."""

    _instance: Optional['Config'] = None
    _config: Optional[Dict[str, Any]] = None
    _lock = threading.Lock()
    _cache_ttl: int = 300  # 5 minutes
    _last_load_time: float = 0
    _config_file: Optional[Path] = None

    def __new__(cls) -> 'Config':
        """Ensure singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(Config, cls).__new__(cls)
        return cls._instance

    @classmethod
    def _is_cache_valid(cls) -> bool:
        """Check if cached configuration is still valid."""
        return cls._config is not None and time.time() - cls._last_load_time < cls._cache_ttl

    @classmethod
    def _load_config(cls) -> None:
        """Load configuration from file or create default if not exists."""
        if not cls._is_cache_valid():
            with cls._lock:
                if not cls._is_cache_valid():
                    config_file = Path(__file__).parent / 'app_config.json'
                    if config_file.exists():
                        try:
                            with open(config_file, 'r') as f:
                                loaded_config = json.load(f)
                            cls._validate_config(loaded_config)
                            cls._config = loaded_config
                            cls._last_load_time = time.time()
                        except (IOError, JSONDecodeError) as e:
                            logging.error(f"Error loading configuration: {e}")
                            raise ConfigLoadError(f"Failed to load config: {e}")
                        except (ValueError, TypeError) as e:
                            logging.error(f"Invalid configuration: {e}")
                            raise ConfigValidationError(f"Invalid config: {e}")
                    else:
                        cls._config = cls._get_default_config()
                        cls._save_config()
                        cls._last_load_time = time.time()

    @classmethod
    def _get_default_config(cls) -> Dict[str, Union[str, int]]:
        """Return the default configuration."""
        return {
            "version": CONFIG_VERSION,
            "theme": "default",
            "language": "en",
            "backup_interval": 24,
        }

    @classmethod
    def _save_config(cls) -> None:
        """Save current configuration to file."""
        if cls._config is None:
            cls._config = cls._get_default_config()
        
        config_file = Path(__file__).parent / 'app_config.json'
        try:
            with open(config_file, 'w') as f:
                json.dump(cls._config, f, indent=4)
        except IOError as e:
            logging.error(f"Error saving configuration: {e}")
            raise ConfigLoadError(f"Failed to save config: {e}")

    @classmethod
    def _validate_config(cls, config: Dict[str, Any]) -> None:
        """
        Validate the configuration structure and types.
        
        Args:
            config: Configuration dictionary to validate
            
        Raises:
            ConfigValidationError: If validation fails
        """
        required_keys = {
            "version": (str, [CONFIG_VERSION]),
            "theme": (str, ["default", "dark", "light"]),
            "language": (str, ["en", "es"]), 
            "backup_interval": (int, (1, 168))  # 1 hour to 1 week
        }
        
        for key, (expected_type, valid_values) in required_keys.items():
            if key not in config:
                raise ConfigValidationError(f"Missing required key: {key}")
                
            value = config[key]
            if not isinstance(value, expected_type):
                raise ConfigValidationError(
                    f"Invalid type for {key}. Expected {expected_type}, got {type(value)}"
                )
                
            if isinstance(valid_values, (list, tuple)):
                if value not in valid_values and not (
                    isinstance(valid_values, tuple) and 
                    valid_values[0] <= value <= valid_values[1]
                ):
                    raise ConfigValidationError(
                        f"Invalid value for {key}. Must be one of {valid_values}"
                    )

    @classmethod
    def get(cls, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.

        Args:
            key: The configuration key
            default: Default value if key is not found

        Returns:
            The configuration value or default
        """
        cls._load_config()
        with cls._lock:
            return cls._config.get(key, default) if cls._config is not None else default

    @classmethod
    def set(cls, key: str, value: Any) -> None:
        """
        Set a configuration value.

        Args:
            key: The configuration key
            value: The value to set
        """
        cls._load_config()
        with cls._lock:
            if cls._config is None:
                cls._config = cls._get_default_config()
            cls._config[key] = value
            cls._save_config()

    @classmethod
    def reload(cls) -> None:
        """Force reload of the configuration from file."""
        with cls._lock:
            cls._config = None
            cls._last_load_time = 0
        cls._load_config()

    @classmethod
    def _reset_for_testing(cls, config_file=None):
        """Reset singleton state for testing."""
        cls._instance = None
        cls._config = None
        cls._config_file = config_file

# Global instance of Config
config = Config()
