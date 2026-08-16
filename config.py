import json
import logging
import os
import re
import threading
import time
from enum import IntEnum
from json.decoder import JSONDecodeError
from pathlib import Path
from typing import Any, Optional

from models.business import BUSINESS_ID_PATTERN


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
    sanitized_name = re.sub(r"[^a-zA-Z0-9_.-]", "", db_name)
    return Path(__file__).parent / sanitized_name


DATABASE_NAME = os.environ.get("DATABASE_NAME", "billing_inventory.db")
DATABASE_PATH = get_safe_db_path(DATABASE_NAME)

# Business registry (backward compatible: absent from config ⇒ single
# implicit "default" business using DATABASE_PATH semantics).
DEFAULT_BUSINESSES = [
    {"id": "default", "name": "Principal", "db_filename": "billing_inventory.db"},
]
DEFAULT_ACTIVE_BUSINESS = "default"


# Debug Level configuration
class DebugLevel(IntEnum):
    """Enum representing different debug levels for the application."""

    CRITICAL = 1
    ERROR = 2
    WARNING = 3
    INFO = 4
    DEBUG = 5


DEBUG_LEVEL_MAP: dict[DebugLevel, int] = {
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

    _instance: Optional["Config"] = None
    _config: dict[str, Any] | None = None
    _lock = threading.Lock()
    _cache_ttl: int = 300  # 5 minutes
    _last_load_time: float = 0
    _config_file: Path | None = None

    def __new__(cls) -> "Config":
        """Ensure singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def _is_cache_valid(cls) -> bool:
        """Check if cached configuration is still valid."""
        return (
            cls._config is not None
            and time.time() - cls._last_load_time < cls._cache_ttl
        )

    @classmethod
    def _get_config_file(cls) -> Path:
        """Resolve the config file to read from.

        Prefers a user-local path outside the repo; falls back to the repo
        copy for backward compatibility with existing installs.
        """
        if cls._config_file is not None:
            return cls._config_file
        primary = Path.home() / ".config" / "billing-inventory" / "app_config.json"
        if primary.exists():
            return primary
        repo_copy = Path(__file__).parent / "app_config.json"
        if repo_copy.exists():
            return repo_copy
        return primary

    @classmethod
    def _get_save_target(cls) -> Path:
        """Resolve where config writes land (user-local, migrated on save)."""
        if cls._config_file is not None:
            return cls._config_file
        return Path.home() / ".config" / "billing-inventory" / "app_config.json"

    @classmethod
    def _load_config(cls) -> None:
        """Load configuration from file or create default if not exists."""
        if not cls._is_cache_valid():
            with cls._lock:
                if not cls._is_cache_valid():
                    config_file = cls._get_config_file()
                    if config_file.exists():
                        try:
                            with open(config_file) as f:
                                loaded_config = json.load(f)
                            merged_config = cls._get_default_config()
                            merged_config.update(loaded_config)
                            cls._validate_config(merged_config)
                            cls._config = merged_config
                            cls._last_load_time = time.time()
                        except (OSError, JSONDecodeError) as e:
                            logging.error(f"Error loading configuration: {e}")
                            raise ConfigLoadError(f"Failed to load config: {e}") from e
                        except (ValueError, TypeError) as e:
                            logging.error(f"Invalid configuration: {e}")
                            raise ConfigValidationError(f"Invalid config: {e}") from e
                    else:
                        cls._config = cls._get_default_config()
                        cls._save_config()
                        cls._last_load_time = time.time()

    @classmethod
    def _get_default_config(cls) -> dict[str, str | int]:
        """Return the default configuration."""
        return {
            "version": CONFIG_VERSION,
            "theme": "default",
            "language": "en",
            "backup_interval": 24,
            "backup_dir": "backups",
            "backup_retention_days": 7,
            "pin_hash": "",
            "pin_failed_attempts": 0,
            "pin_locked_until": "",
            "last_backup_success": "",
            "last_backup_skipped_time": "",
            "last_backup_skipped_reason": "",
        }

    @classmethod
    def _restrict_permissions(cls, path: Path) -> None:
        """Restrict a file to owner-only read/write (0600)."""
        try:
            os.chmod(path, 0o600)
        except OSError as e:
            logging.error(f"Failed to restrict permissions on {path}: {e}")

    @classmethod
    def _save_config(cls) -> None:
        """Save current configuration to file."""
        if cls._config is None:
            cls._config = cls._get_default_config()

        config_file = cls._get_save_target()
        config_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(config_file, "w") as f:
                json.dump(cls._config, f, indent=4)
            cls._restrict_permissions(config_file)
        except OSError as e:
            logging.error(f"Error saving configuration: {e}")
            raise ConfigLoadError(f"Failed to save config: {e}") from e

    @classmethod
    def _validate_businesses(cls, businesses: Any) -> None:
        """Validate the optional business registry structure.

        Business ids must be safe for file/dir names (``^[a-z0-9_]+$``) and
        ``db_filename`` must be a bare filename (no separators).
        """
        if not isinstance(businesses, list) or not businesses:
            raise ConfigValidationError("'businesses' must be a non-empty list")

        seen_ids = set()
        for business in businesses:
            if not isinstance(business, dict):
                raise ConfigValidationError("Each business entry must be an object")
            business_id = business.get("id")
            name = business.get("name")
            filename = business.get("db_filename")
            if not isinstance(business_id, str) or not BUSINESS_ID_PATTERN.fullmatch(
                business_id
            ):
                raise ConfigValidationError(
                    f"Invalid business id: {business_id!r}. "
                    f"Must match {BUSINESS_ID_PATTERN.pattern}"
                )
            if business_id in seen_ids:
                raise ConfigValidationError(f"Duplicate business id: {business_id!r}")
            seen_ids.add(business_id)
            if not isinstance(name, str) or not name:
                raise ConfigValidationError(
                    f"Business {business_id!r} must have a non-empty name"
                )
            if not isinstance(filename, str) or not filename:
                raise ConfigValidationError(
                    f"Business {business_id!r} must have a non-empty db_filename"
                )
            if get_safe_db_path(filename).name != filename:
                raise ConfigValidationError(
                    f"Invalid db_filename for business {business_id!r}: {filename!r}"
                )

    @classmethod
    def _validate_config(cls, config: dict[str, Any]) -> None:
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
            "backup_interval": (int, (1, 168)),  # 1 hour to 1 week
            "backup_dir": (str, None),
            "backup_retention_days": (int, (1, 365)),
            "pin_hash": (str, None),
            "pin_failed_attempts": (int, None),
            "pin_locked_until": (str, None),
            "last_backup_success": (str, None),
            "last_backup_skipped_time": (str, None),
            "last_backup_skipped_reason": (str, None),
        }

        for key, (expected_type, valid_values) in required_keys.items():
            if key not in config:
                raise ConfigValidationError(f"Missing required key: {key}")

            value = config[key]

            # Auto-cast strings to integers if expected
            if expected_type is int and isinstance(value, str):
                try:
                    value = int(value)
                    config[key] = value
                except ValueError:
                    pass  # Let validation fail below

            if not isinstance(value, expected_type):
                raise ConfigValidationError(
                    f"Invalid type for {key}. Expected {expected_type}, got {type(value)}"
                )

            if (
                isinstance(valid_values, (list, tuple))
                and value not in valid_values
                and not (
                    isinstance(valid_values, tuple)
                    and valid_values[0] <= value <= valid_values[1]
                )
            ):
                raise ConfigValidationError(
                    f"Invalid value for {key}. Must be one of {valid_values}"
                )

        # Optional keys (backward compatible: absent ⇒ single-business default)
        if "businesses" in config:
            cls._validate_businesses(config["businesses"])
        if "active_business" in config and not isinstance(
            config["active_business"], str
        ):
            raise ConfigValidationError("'active_business' must be a string")

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
            # Create copy to validate
            temp_config = cls._config.copy()
            temp_config[key] = value
            cls._validate_config(temp_config)

            # Use the validated (and potentially cast) value
            cls._config[key] = temp_config[key]
            cls._save_config()

    @classmethod
    def reload(cls) -> None:
        """Force reload of the configuration from file."""
        with cls._lock:
            cls._config = None
            cls._last_load_time = 0
        cls._load_config()

    @classmethod
    def save(cls) -> None:
        """Public alias for _save_config."""
        cls._save_config()

    @classmethod
    def reset_to_defaults(cls) -> None:
        """Reset configuration to defaults."""
        cls._config = cls._get_default_config()
        cls._save_config()

    @classmethod
    def get_businesses(cls) -> list[dict]:
        """Return the configured businesses.

        With no ``businesses`` key in config, the implicit single-business
        default (business id ``default``) is returned.
        """
        businesses = cls.get("businesses")
        if not businesses:
            return [dict(business) for business in DEFAULT_BUSINESSES]
        return [dict(business) for business in businesses]

    @classmethod
    def get_active_business(cls) -> dict:
        """Return the active business entry.

        Falls back to the first configured business (with a log) when the
        stored ``active_business`` id does not match any configured business.
        """
        active_id = cls.get("active_business", DEFAULT_ACTIVE_BUSINESS)
        businesses = cls.get_businesses()
        for business in businesses:
            if business["id"] == active_id:
                return dict(business)
        logging.warning(
            f"active_business {active_id!r} not found in configured businesses; "
            f"falling back to {businesses[0]['id']!r}"
        )
        return dict(businesses[0])

    @classmethod
    def set_active_business(cls, business_id: str, persist: bool = True) -> None:
        """Set (and optionally persist) the active business id.

        Args:
            business_id: An id from the configured businesses registry.
            persist: When False the choice applies to this session only and is
                not written to disk.
        """
        if not isinstance(business_id, str) or not BUSINESS_ID_PATTERN.fullmatch(
            business_id
        ):
            raise ConfigValidationError(
                f"Invalid business id: {business_id!r}. "
                f"Must match {BUSINESS_ID_PATTERN.pattern}"
            )
        known_ids = {business["id"] for business in cls.get_businesses()}
        if business_id not in known_ids:
            raise ConfigValidationError(f"Unknown business id: {business_id!r}")

        cls._load_config()
        with cls._lock:
            if cls._config is None:
                cls._config = cls._get_default_config()
            cls._config["active_business"] = business_id
            if persist:
                cls._save_config()

    @classmethod
    def get_business_db_path(cls, business_id: str) -> Path:
        """Resolve a business's database file path (mirrors ``DATABASE_PATH``)."""
        for business in cls.get_businesses():
            if business["id"] == business_id:
                return get_safe_db_path(business["db_filename"])
        raise ConfigValidationError(f"Unknown business id: {business_id!r}")

    @classmethod
    def get_active_database_path(cls) -> Path:
        """Path to the active business's database file.

        For the implicit single-business install this equals ``DATABASE_PATH``.
        """
        return cls.get_business_db_path(cls.get_active_business()["id"])

    @classmethod
    def _reset_for_testing(cls, config_file=None):
        """Reset singleton state for testing."""
        cls._instance = None
        cls._config = None
        cls._config_file = config_file


# Global instance of Config
config = Config()
