"""Tests for logging configuration module."""

import logging
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from local_deepwiki.logging import (
    LOG_FORMAT,
    LOG_FORMAT_DETAILED,
    PACKAGE_NAME,
    get_logger,
    setup_logging,
)


class TestSetupLogging:
    """Tests for setup_logging function."""

    def test_setup_logging_default_level(self):
        """Test setup_logging uses INFO as default level."""
        logger = setup_logging()

        assert logger.name == PACKAGE_NAME
        assert logger.level == logging.INFO
        assert len(logger.handlers) == 1
        assert isinstance(logger.handlers[0], logging.StreamHandler)

    def test_setup_logging_with_string_level(self):
        """Test setup_logging accepts string level."""
        logger = setup_logging(level="DEBUG")

        assert logger.level == logging.DEBUG

    def test_setup_logging_with_uppercase_string_level(self):
        """Test setup_logging handles uppercase string level."""
        logger = setup_logging(level="WARNING")

        assert logger.level == logging.WARNING

    def test_setup_logging_with_lowercase_string_level(self):
        """Test setup_logging handles lowercase string level."""
        logger = setup_logging(level="error")

        assert logger.level == logging.ERROR

    def test_setup_logging_with_int_level(self):
        """Test setup_logging accepts integer level."""
        logger = setup_logging(level=logging.CRITICAL)

        assert logger.level == logging.CRITICAL

    def test_setup_logging_with_invalid_string_level(self):
        """Test setup_logging defaults to INFO for invalid string level."""
        logger = setup_logging(level="INVALID_LEVEL")

        assert logger.level == logging.INFO

    def test_setup_logging_from_env_var(self):
        """Test setup_logging reads level from environment variable."""
        with patch.dict(os.environ, {"DEEPWIKI_LOG_LEVEL": "DEBUG"}):
            logger = setup_logging(level=None)

        assert logger.level == logging.DEBUG

    def test_setup_logging_env_var_case_insensitive(self):
        """Test setup_logging handles env var case insensitively."""
        with patch.dict(os.environ, {"DEEPWIKI_LOG_LEVEL": "warning"}):
            logger = setup_logging(level=None)

        assert logger.level == logging.WARNING

    def test_setup_logging_detailed_format(self):
        """Test setup_logging with detailed format style."""
        logger = setup_logging(format_style="detailed")

        assert len(logger.handlers) == 1
        handler = logger.handlers[0]
        assert handler.formatter._fmt == LOG_FORMAT_DETAILED

    def test_setup_logging_simple_format(self):
        """Test setup_logging with simple format style (default)."""
        logger = setup_logging(format_style="simple")

        assert len(logger.handlers) == 1
        handler = logger.handlers[0]
        assert handler.formatter._fmt == LOG_FORMAT

    def test_setup_logging_no_stream(self):
        """Test setup_logging with stream=False."""
        logger = setup_logging(stream=False)

        # No handlers should be added when stream=False and no log_file
        assert len(logger.handlers) == 0

    def test_setup_logging_with_file(self, tmp_path):
        """Test setup_logging with log file."""
        log_file = tmp_path / "test.log"

        logger = setup_logging(log_file=str(log_file))

        # Should have both stream and file handler
        assert len(logger.handlers) == 2
        handler_types = [type(h) for h in logger.handlers]
        assert logging.StreamHandler in handler_types
        assert logging.FileHandler in handler_types

        # Log a message and verify it's written to file
        logger.info("Test message")

        # Close the file handler to flush
        for handler in logger.handlers:
            if isinstance(handler, logging.FileHandler):
                handler.close()

        assert log_file.exists()
        content = log_file.read_text()
        assert "Test message" in content

    def test_setup_logging_file_only(self, tmp_path):
        """Test setup_logging with file but no stream."""
        log_file = tmp_path / "test.log"

        logger = setup_logging(stream=False, log_file=str(log_file))

        assert len(logger.handlers) == 1
        assert isinstance(logger.handlers[0], logging.FileHandler)

        # Close handler
        logger.handlers[0].close()

    def test_setup_logging_clears_existing_handlers(self):
        """Test setup_logging clears existing handlers."""
        # First setup
        logger = setup_logging(level="INFO")
        initial_handler_count = len(logger.handlers)

        # Second setup should not duplicate handlers
        logger = setup_logging(level="DEBUG")

        assert len(logger.handlers) == initial_handler_count

    def test_setup_logging_no_propagation(self):
        """Test setup_logging disables propagation."""
        logger = setup_logging()

        assert logger.propagate is False

    def test_setup_logging_returns_logger(self):
        """Test setup_logging returns the logger instance."""
        result = setup_logging()

        assert isinstance(result, logging.Logger)
        assert result.name == PACKAGE_NAME


class TestGetLogger:
    """Tests for get_logger function."""

    def test_get_logger_with_package_prefix(self):
        """Test get_logger with name starting with package name."""
        module_name = f"{PACKAGE_NAME}.some_module"
        logger = get_logger(module_name)

        assert logger.name == module_name

    def test_get_logger_without_package_prefix(self):
        """Test get_logger with name not starting with package name."""
        module_name = "external_module"
        logger = get_logger(module_name)

        assert logger.name == f"{PACKAGE_NAME}.{module_name}"

    def test_get_logger_nested_module(self):
        """Test get_logger with nested module name."""
        module_name = f"{PACKAGE_NAME}.core.parser"
        logger = get_logger(module_name)

        assert logger.name == module_name

    def test_get_logger_external_nested_module(self):
        """Test get_logger with external nested module name."""
        module_name = "some.external.module"
        logger = get_logger(module_name)

        assert logger.name == f"{PACKAGE_NAME}.{module_name}"

    def test_get_logger_returns_child_of_package_logger(self):
        """Test get_logger returns a child of the package logger."""
        logger = get_logger("test_module")
        parent_logger = logging.getLogger(PACKAGE_NAME)

        # The logger should be a child (starts with parent name)
        assert logger.name.startswith(PACKAGE_NAME)

    def test_get_logger_with_dunder_name(self):
        """Test get_logger with __name__ style input."""
        # Simulate a module calling get_logger(__name__)
        logger = get_logger("local_deepwiki.generators.wiki")

        assert logger.name == "local_deepwiki.generators.wiki"


class TestModuleLevelInit:
    """Tests for module-level initialization."""

    def test_default_logger_exists(self):
        """Test that the default logger is configured."""
        logger = logging.getLogger(PACKAGE_NAME)

        # Should have at least one handler from module init
        assert len(logger.handlers) >= 1

    def test_default_logger_has_handler(self):
        """Test that the default logger has a stream handler."""
        logger = logging.getLogger(PACKAGE_NAME)

        # Check there's at least one StreamHandler
        stream_handlers = [h for h in logger.handlers if isinstance(h, logging.StreamHandler)]
        assert len(stream_handlers) >= 1

    def test_default_logger_no_propagation(self):
        """Test that the default logger doesn't propagate."""
        logger = logging.getLogger(PACKAGE_NAME)

        assert logger.propagate is False


class TestLoggingConstants:
    """Tests for logging constants."""

    def test_package_name_constant(self):
        """Test PACKAGE_NAME constant."""
        assert PACKAGE_NAME == "local_deepwiki"

    def test_log_format_constant(self):
        """Test LOG_FORMAT constant contains expected parts."""
        assert "%(asctime)s" in LOG_FORMAT
        assert "%(name)s" in LOG_FORMAT
        assert "%(levelname)s" in LOG_FORMAT
        assert "%(message)s" in LOG_FORMAT

    def test_log_format_detailed_constant(self):
        """Test LOG_FORMAT_DETAILED constant contains file/line info."""
        assert "%(filename)s" in LOG_FORMAT_DETAILED
        assert "%(lineno)d" in LOG_FORMAT_DETAILED
        assert "%(asctime)s" in LOG_FORMAT_DETAILED
        assert "%(message)s" in LOG_FORMAT_DETAILED


class TestLoggingIntegration:
    """Integration tests for logging functionality."""

    def test_logging_hierarchy(self):
        """Test that loggers follow proper hierarchy."""
        parent = setup_logging(level="DEBUG")
        child = get_logger("test_child")

        # Child should inherit from parent when parent is configured
        assert child.name.startswith(parent.name)

    def test_log_message_propagates_format(self, tmp_path, capfd):
        """Test that log messages use the configured format."""
        # Setup with known format
        logger = setup_logging(level="INFO", format_style="simple")

        # Log a message
        logger.info("Test log message")

        # Capture stderr output
        captured = capfd.readouterr()

        # Verify format elements are present
        assert "local_deepwiki" in captured.err
        assert "INFO" in captured.err
        assert "Test log message" in captured.err

    def test_detailed_format_includes_file_info(self, tmp_path, capfd):
        """Test that detailed format includes file and line info."""
        logger = setup_logging(level="INFO", format_style="detailed")

        # Log a message
        logger.info("Detailed test message")

        # Capture stderr output
        captured = capfd.readouterr()

        # Detailed format should include filename
        assert "Detailed test message" in captured.err
        # The format includes [filename:lineno]
        assert "[" in captured.err
