import json
import logging

import pytest

from utils.system.logger import LoggerConfig, clear_logs, setup_logger


class TestLoggerContext:
    @pytest.fixture
    def structured_logger(self, temp_log_dir):
        """Setup and cleanup test logger."""
        # Clear logs before test
        clear_logs(temp_log_dir)

        # Create logger
        config = LoggerConfig(
            log_file=temp_log_dir / "app.log",
            level=logging.DEBUG,
            max_size=1024,
            backup_count=3,
            format="json",
        )
        logger = setup_logger(config)

        yield logger

        # Close handlers to release file locks
        for handler in logger._logger.handlers[:]:
            handler.close()
            logger._logger.removeHandler(handler)

        # Cleanup after test
        clear_logs(temp_log_dir)

    def test_context_creation(self, structured_logger, temp_log_dir):
        """Test creating logger with context."""
        context = {"user_id": 123, "session": "abc123"}
        logger_with_context = structured_logger.with_context(**context)

        # Log a message
        logger_with_context.info("Test message")

        # Verify the context was preserved
        with open(temp_log_dir / "app.log", encoding="utf-8") as f:
            log_entry = json.loads(f.readline().strip())
            assert log_entry["user_id"] == 123
            assert log_entry["session"] == "abc123"

    def test_nested_context(self, structured_logger):
        """Test nested context creation."""
        logger1 = structured_logger.with_context(level1="value1")
        logger2 = logger1.with_context(level2="value2")

        assert logger2._context == {"level1": "value1", "level2": "value2"}
        assert logger1._context == {"level1": "value1"}

    def test_context_with_different_types(self, structured_logger, temp_log_dir):
        """Test logging with different data types in context."""
        test_context = {
            "int_value": 42,
            "float_value": 3.14,
            "bool_value": True,
            "none_value": None,
            "list_value": [1, 2, 3],
            "dict_value": {"key": "value"},
        }

        logger_with_context = structured_logger.with_context(**test_context)
        logger_with_context.info("Test message")

        # Verify log file
        with open(temp_log_dir / "app.log") as f:
            log_entry = json.loads(f.readline())

        # Verify each value type was logged correctly
        assert log_entry["int_value"] == 42
        assert log_entry["float_value"] == 3.14
        assert log_entry["bool_value"] is True
        assert log_entry["none_value"] is None
        assert log_entry["list_value"] == [1, 2, 3]
        assert log_entry["dict_value"] == {"key": "value"}

    def test_message_formatting(self, structured_logger, temp_log_dir):
        """Test message formatting with context."""
        logger = structured_logger.with_context(user="test_user")
        message = "Test message"

        # Log the message
        logger.info(message)

        # Read and verify the log
        with open(temp_log_dir / "app.log", encoding="utf-8") as f:
            log_line = f.readline().strip()
            try:
                log_entry = json.loads(log_line)
                assert "message" in log_entry
                assert message in log_entry["message"]
                assert "user" in log_entry
                assert log_entry["user"] == "test_user"
            except json.JSONDecodeError as e:
                pytest.fail(f"Failed to parse JSON: {e}\nLog line: {log_line}")

    def test_extra_parameters(self, structured_logger, temp_log_dir):
        """Test logging with extra parameters."""
        logger = structured_logger.with_context(user="test_user")
        message = "Test message"
        extra = {"request_id": "123", "status": "success"}

        # Log with extra parameters
        logger.info(message, extra=extra)

        # Verify log
        with open(temp_log_dir / "app.log", encoding="utf-8") as f:
            log_line = f.readline().strip()
            try:
                log_entry = json.loads(log_line)
                assert message in log_entry["message"]
                assert log_entry["user"] == "test_user"
                assert log_entry["request_id"] == "123"
                assert log_entry["status"] == "success"
            except json.JSONDecodeError as e:
                pytest.fail(f"Failed to parse JSON: {e}\nLog line: {log_line}")

    def test_context_isolation(self, structured_logger, temp_log_dir):
        """Test that contexts are properly isolated."""
        logger1 = structured_logger.with_context(context1="value1")
        logger2 = structured_logger.with_context(context2="value2")

        logger1.info("Test message 1")
        logger2.info("Test message 2")

        # Flush handlers
        for handler in logger1._logger.handlers:
            handler.flush()

        with open(temp_log_dir / "app.log", encoding="utf-8") as f:
            logs = f.readlines()
            print(f"DEBUG: Logs found: {len(logs)}")
            for i, line in enumerate(logs):
                print(f"Log {i}: {line}")

            if len(logs) < 2:
                pytest.fail(f"Expected 2 logs, found {len(logs)}. Logs: {logs}")

            log1 = json.loads(logs[0].strip())
            log2 = json.loads(logs[1].strip())

            assert "context1" in log1
            assert "context2" not in log1
            assert "context2" in log2
            assert "context1" not in log2

    def test_log_levels(self, structured_logger, temp_log_dir):
        """Test different logging levels."""
        test_logger = structured_logger.with_context(test=True)

        # Log messages at different levels
        test_logger.debug("Debug message")
        test_logger.info("Info message")
        test_logger.warning("Warning message")
        test_logger.error("Error message")

        # Read log file
        with open(temp_log_dir / "app.log") as f:
            logs = f.readlines()

        # Parse log entries
        log_entries = [json.loads(log) for log in logs]
        print(f"DEBUG: Log levels found: {[entry['level'] for entry in log_entries]}")

        # Verify log levels
        assert any(entry["level"] == "DEBUG" for entry in log_entries)
        assert any(entry["level"] == "INFO" for entry in log_entries)
        assert any(entry["level"] == "WARNING" for entry in log_entries)
        assert any(entry["level"] == "ERROR" for entry in log_entries)

    def test_context_with_empty_values(self, structured_logger):
        """Test context with empty or None values."""
        logger = structured_logger.with_context(
            empty_string="", none_value=None, empty_list=[], empty_dict={}
        )

        formatted = logger._format_message("Test")
        parsed_context = json.loads(formatted)

        assert parsed_context["empty_string"] == ""
        assert parsed_context["none_value"] is None
        assert parsed_context["empty_list"] == []
        assert parsed_context["empty_dict"] == {}

    def test_context_overriding(self, structured_logger):
        """Test overriding context values."""
        logger1 = structured_logger.with_context(key="value1")
        logger2 = logger1.with_context(key="value2")

        formatted = logger2._format_message("Test")
        # value1 should be overridden by value2
        assert "value1" not in formatted

        parsed = json.loads(formatted)
        assert parsed["key"] == "value2"

    def test_large_context(self, structured_logger):
        """Test handling of large context data."""
        large_context = {f"key_{i}": f"value_{i}" for i in range(1000)}
        logger = structured_logger.with_context(**large_context)

        formatted = logger._format_message("Test")
        # Verify the message can be parsed and contains all data
        parsed_context = json.loads(formatted)
        # Context has 1000 items + message + timestamp = 1002
        assert len(parsed_context) >= 1000

    def test_special_characters(self, structured_logger):
        """Test handling of special characters in context."""
        special_chars = {
            "unicode": "🌟",
            "newline": "line1\nline2",
            "quotes": '"quoted"',
            "backslash": "back\\slash",
        }

        logger = structured_logger.with_context(**special_chars)
        formatted = logger._format_message("Test")

        # Verify the message can be parsed
        parsed_context = json.loads(formatted)
        assert parsed_context["unicode"] == "🌟"
        assert parsed_context["newline"] == "line1\nline2"
        assert parsed_context["quotes"] == '"quoted"'
        assert parsed_context["backslash"] == "back\\slash"
