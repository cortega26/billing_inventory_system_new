import pytest
import os
import json
import tempfile
from pathlib import Path
from config import Config
from utils.exceptions import ConfigurationException

class TestConfig:
    @pytest.fixture
    def temp_config_file(self):
        """Create a temporary config file for testing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({
                "version": "1.0",
                "theme": "default",
                "language": "en",
                "backup_interval": 24,
                "database": {
                    "path": "test.db",
                    "backup_path": "backups/"
                },
                "logging": {
                    "level": "INFO",
                    "file": "app.log"
                }
            }, f)
        yield Path(f.name)
        os.unlink(f.name)

    @pytest.fixture
    def config(self, temp_config_file):
        """Create a Config instance with the temporary config file."""
        Config._reset_for_testing(temp_config_file)
        return Config()

    def test_singleton_pattern(self, config):
        """Test that Config follows the singleton pattern."""
        config2 = Config()
        assert config is config2
        assert Config() is config

    def test_load_config(self, config, temp_config_file):
        """Test loading configuration from file."""
        assert config._config is not None
        assert config._config["version"] == "1.0"
        assert config._config["theme"] == "default"

    def test_get_config_value(self, config):
        """Test getting configuration values."""
        assert config.get("theme") == "default"
        assert config.get("language") == "en"
        assert config.get("backup_interval") == 24

    def test_get_nested_config_value(self, config):
        """Test getting nested configuration values."""
        assert config.get("database.path") == "test.db"
        assert config.get("logging.level") == "INFO"

    def test_get_default_value(self, config):
        """Test getting default value for non-existent keys."""
        assert config.get("nonexistent", default="default") == "default"
        assert config.get("nonexistent.nested", default=123) == 123

    def test_set_config_value(self, config):
        """Test setting configuration values."""
        config.set("theme", "dark")
        assert config.get("theme") == "dark"

        config.set("database.path", "new.db")
        assert config.get("database.path") == "new.db"

    def test_invalid_config_file(self):
        """Test handling of invalid config file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("invalid json")
        Config._reset_for_testing(Path(f.name))
        with pytest.raises(ConfigurationException):
            Config()
        os.unlink(f.name)

    def test_missing_config_file(self):
        """Test handling of missing config file."""
        Config._reset_for_testing(Path("nonexistent.json"))
        with pytest.raises(ConfigurationException):
            Config()

    def test_save_config(self, config, temp_config_file):
        """Test saving configuration changes."""
        config.set("theme", "dark")
        config.save()

        # Read the file directly to verify changes were saved
        with open(temp_config_file) as f:
            saved_config = json.load(f)
            assert saved_config["theme"] == "dark"

    def test_config_validation(self, config):
        """Test configuration validation."""
        # Test invalid theme
        with pytest.raises(ConfigurationException):
            config.set("theme", "invalid_theme")

        # Test invalid backup interval
        with pytest.raises(ConfigurationException):
            config.set("backup_interval", -1)

        # Test invalid logging level
        with pytest.raises(ConfigurationException):
            config.set("logging.level", "INVALID")

    def test_config_type_conversion(self, config):
        """Test type conversion of configuration values."""
        # Integer conversion
        config.set("backup_interval", "48")
        assert isinstance(config.get("backup_interval"), int)
        assert config.get("backup_interval") == 48

        # Boolean conversion
        config.set("debug", "true")
        assert isinstance(config.get("debug"), bool)
        assert config.get("debug") is True

    def test_config_reset(self, config):
        """Test resetting configuration to defaults."""
        original_theme = config.get("theme")
        config.set("theme", "dark")
        
        config.reset_to_defaults()
        
        assert config.get("theme") == original_theme

    def test_config_environment_override(self, config):
        """Test environment variable override of config values."""
        os.environ["APP_THEME"] = "dark"
        
        # Reload config
        Config._load_config()
        
        assert config.get("theme") == "dark"
        
        # Cleanup
        del os.environ["APP_THEME"]

    def test_config_merge(self, config):
        """Test merging configuration dictionaries."""
        new_config = {
            "new_setting": "value",
            "database": {
                "new_option": "value"
            }
        }
        
        config.merge(new_config)
        
        assert config.get("new_setting") == "value"
        assert config.get("database.new_option") == "value"
        assert config.get("database.path") == "test.db"  # Original value preserved 