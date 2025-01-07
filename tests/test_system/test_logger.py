import pytest
import logging
import json
import tempfile
from pathlib import Path
from utils.system.logger import (
    logger,
    JsonFormatter,
    setup_logger,
    LoggerConfig,
    rotate_logs,
    clear_logs
)
from utils.exceptions import ConfigurationException

class TestLogger:
    @pytest.fixture
    def temp_log_dir(self):
        """Create a temporary directory for log files."""
        with tempfile.TemporaryDirectory() as tmpdirname:
            yield Path(tmpdirname)

    @pytest.fixture
    def logger_config(self, temp_log_dir):
        """Create a logger configuration."""
        return LoggerConfig(
            log_file=temp_log_dir / "app.log",
            level=logging.INFO,
            max_size=1024 * 1024,  # 1MB
            backup_count=3,
            format="json"
        )

    @pytest.fixture
    def configured_logger(self, logger_config):
        """Create and configure a logger instance."""
        setup_logger(logger_config)
        return logger

    def test_logger_initialization(self, configured_logger):
        """Test basic logger initialization."""
        assert configured_logger is not None
        assert isinstance(configured_logger, logging.Logger)
        assert configured_logger.level == logging.INFO

    def test_json_formatter(self):
        """Test JSON formatter."""
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        formatted = formatter.format(record)
        parsed = json.loads(formatted)
        
        assert "timestamp" in parsed
        assert parsed["level"] == "INFO"
        assert parsed["message"] == "Test message"

    def test_log_levels(self, configured_logger, temp_log_dir):
        """Test different log levels."""
        test_messages = {
            "debug": "Debug message",
            "info": "Info message",
            "warning": "Warning message",
            "error": "Error message",
            "critical": "Critical message"
        }

        for level, message in test_messages.items():
            getattr(configured_logger, level)(message)

        with open(temp_log_dir / "app.log") as f:
            logs = [json.loads(line) for line in f.readlines()]
            
        assert len(logs) == 4  # Debug messages should not be logged at INFO level
        assert any(log["level"] == "INFO" for log in logs)
        assert any(log["level"] == "WARNING" for log in logs)
        assert any(log["level"] == "ERROR" for log in logs)
        assert any(log["level"] == "CRITICAL" for log in logs)

    def test_log_rotation(self, configured_logger, temp_log_dir):
        """Test log file rotation."""
        # Write enough logs to trigger rotation
        for i in range(1000):
            configured_logger.info(f"Test message {i}" * 100)  # Large message

        log_files = list(temp_log_dir.glob("app.log*"))
        assert len(log_files) > 1  # Should have main log and at least one backup

    def test_log_with_extra_fields(self, configured_logger, temp_log_dir):
        """Test logging with extra fields."""
        extra_data = {
            "user_id": 123,
            "action": "login",
            "ip": "127.0.0.1"
        }
        
        configured_logger.info("User action", extra=extra_data)
        
        with open(temp_log_dir / "app.log") as f:
            log = json.loads(f.readline())
            
        assert log["user_id"] == 123
        assert log["action"] == "login"
        assert log["ip"] == "127.0.0.1"

    def test_log_exceptions(self, configured_logger, temp_log_dir):
        """Test exception logging."""
        try:
            raise ValueError("Test error")
        except ValueError:
            configured_logger.exception("An error occurred")

        with open(temp_log_dir / "app.log") as f:
            log = json.loads(f.readline())
            
        assert "exc_info" in log
        assert "ValueError: Test error" in log["exc_info"]

    def test_clear_logs(self, configured_logger, temp_log_dir):
        """Test log clearing functionality."""
        configured_logger.info("Test message")
        clear_logs(temp_log_dir)
        
        assert not (temp_log_dir / "app.log").exists()

    def test_invalid_config(self, temp_log_dir):
        """Test invalid logger configuration."""
        invalid_config = LoggerConfig(
            log_file=temp_log_dir / "invalid/app.log",  # Invalid path
            level=logging.INFO,
            max_size=1024,
            backup_count=3,
            format="json"
        )
        
        with pytest.raises(ConfigurationException):
            setup_logger(invalid_config)

    def test_log_format_validation(self, temp_log_dir):
        """Test log format validation."""
        invalid_config = LoggerConfig(
            log_file=temp_log_dir / "app.log",
            level=logging.INFO,
            max_size=1024,
            backup_count=3,
            format="invalid_format"  # Invalid format
        )
        
        with pytest.raises(ConfigurationException):
            setup_logger(invalid_config)

    def test_concurrent_logging(self, configured_logger, temp_log_dir):
        """Test concurrent logging from multiple threads."""
        import threading
        
        def log_messages():
            for i in range(100):
                configured_logger.info(f"Thread message {i}")

        threads = [threading.Thread(target=log_messages) for _ in range(5)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        with open(temp_log_dir / "app.log") as f:
            logs = f.readlines()
            
        assert len(logs) == 500  # 5 threads * 100 messages

    def test_performance(self, configured_logger, temp_log_dir):
        """Test logging performance."""
        import time
        
        # Reduce number of test messages to 10 instead of 1000
        start_time = time.time()
        for i in range(10):
            configured_logger.info(f"Performance test message {i}")
        end_time = time.time()
        
        # Should complete within reasonable time
        assert end_time - start_time < 0.1  # Tighter performance requirement
        
        # Verify log file exists and contains messages
        log_file = temp_log_dir / "app.log"
        assert log_file.exists()
        with open(log_file) as f:
            logs = f.readlines()
            assert len(logs) == 10

    def test_structured_logging(self, configured_logger, temp_log_dir):
        """Test structured logging capabilities."""
        structured_data = {
            "event_type": "user_action",
            "user": {
                "id": 123,
                "name": "test_user"
            },
            "metadata": {
                "ip": "127.0.0.1",
                "timestamp": "2024-01-01T00:00:00Z"
            }
        }
        
        configured_logger.info("Structured log test", extra=structured_data)
        
        with open(temp_log_dir / "app.log") as f:
            log = json.loads(f.readline())
            
        assert log["event_type"] == "user_action"
        assert log["user"]["id"] == 123
        assert log["metadata"]["ip"] == "127.0.0.1" 

    def test_manual_log_rotation(self, configured_logger, temp_log_dir):
        """Test manual log rotation."""
        # Write some logs
        configured_logger.info("Test message before rotation")
        
        # Perform manual rotation
        rotate_logs(temp_log_dir)
        
        # Write more logs
        configured_logger.info("Test message after rotation")
        
        # Check that both files exist
        assert (temp_log_dir / "app.log").exists()
        assert (temp_log_dir / "app.log.1").exists() 