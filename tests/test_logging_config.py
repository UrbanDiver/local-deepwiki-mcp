"""Tests for the logging configuration module."""

import logging
import os
from unittest.mock import patch

import pytest

from local_deepwiki.logging import (
    LOG_FORMAT,
    LOG_FORMAT_DETAILED,
    PACKAGE_NAME,
    get_logger,
    setup_logging,
)


class TestGetLogger:
    """Test suite for get_logger."""

    def test_returns_logger_instance(self):
        """Should return a logging.Logger instance."""
        result = get_logger("test_module")
        assert isinstance(result, logging.Logger)

    def test_prefixes_with_package_name(self):
        """Should prefix non-package names with the package name."""
        result = get_logger("mymodule")
        assert result.name == f"{PACKAGE_NAME}.mymodule"

    def test_preserves_name_starting_with_package(self):
        """Should not double-prefix names that already start with the package name."""
        full_name = f"{PACKAGE_NAME}.core.parser"
        result = get_logger(full_name)
        assert result.name == full_name

    def test_returns_same_logger_for_same_name(self):
        """Should return the same logger instance for the same module name."""
        logger_a = get_logger("same_module")
        logger_b = get_logger("same_module")
        assert logger_a is logger_b

    def test_returns_different_loggers_for_different_names(self):
        """Should return different loggers for different module names."""
        logger_a = get_logger("module_a")
        logger_b = get_logger("module_b")
        assert logger_a is not logger_b

    def test_empty_name_gets_prefixed(self):
        """Should prefix an empty string with the package name."""
        result = get_logger("")
        assert result.name == f"{PACKAGE_NAME}."

    def test_nested_module_name(self):
        """Should handle deeply nested module names correctly."""
        result = get_logger("core.deep.nested")
        assert result.name == f"{PACKAGE_NAME}.core.deep.nested"


class TestSetupLogging:
    """Test suite for setup_logging."""

    def test_returns_logger_instance(self):
        """Should return a logging.Logger instance."""
        result = setup_logging(level="WARNING", stream=False)
        assert isinstance(result, logging.Logger)

    def test_logger_has_package_name(self):
        """Should return a logger named after the package."""
        result = setup_logging(level="WARNING", stream=False)
        assert result.name == PACKAGE_NAME

    def test_sets_debug_level(self):
        """Should set log level to DEBUG when specified."""
        logger = setup_logging(level="DEBUG", stream=False)
        assert logger.level == logging.DEBUG

    def test_sets_info_level(self):
        """Should set log level to INFO when specified."""
        logger = setup_logging(level="INFO", stream=False)
        assert logger.level == logging.INFO

    def test_sets_warning_level(self):
        """Should set log level to WARNING when specified."""
        logger = setup_logging(level="WARNING", stream=False)
        assert logger.level == logging.WARNING

    def test_sets_error_level(self):
        """Should set log level to ERROR when specified."""
        logger = setup_logging(level="ERROR", stream=False)
        assert logger.level == logging.ERROR

    def test_accepts_integer_level(self):
        """Should accept an integer log level directly."""
        logger = setup_logging(level=logging.CRITICAL, stream=False)
        assert logger.level == logging.CRITICAL

    def test_defaults_to_info_when_level_is_none(self):
        """Should default to INFO when no level is specified and env var is unset."""
        with patch.dict(os.environ, {}, clear=True):
            # Remove the env var if it exists
            os.environ.pop("DEEPWIKI_LOG_LEVEL", None)
            logger = setup_logging(level=None, stream=False)
            assert logger.level == logging.INFO

    def test_reads_level_from_env_var(self):
        """Should read log level from DEEPWIKI_LOG_LEVEL when level is None."""
        with patch.dict(os.environ, {"DEEPWIKI_LOG_LEVEL": "DEBUG"}):
            logger = setup_logging(level=None, stream=False)
            assert logger.level == logging.DEBUG

    def test_simple_format_uses_log_format(self):
        """Should use the simple LOG_FORMAT when format_style is 'simple'."""
        logger = setup_logging(level="WARNING", format_style="simple", stream=True)
        handler = logger.handlers[0]
        assert handler.formatter._fmt == LOG_FORMAT

    def test_detailed_format_uses_log_format_detailed(self):
        """Should use LOG_FORMAT_DETAILED when format_style is 'detailed'."""
        logger = setup_logging(level="WARNING", format_style="detailed", stream=True)
        handler = logger.handlers[0]
        assert handler.formatter._fmt == LOG_FORMAT_DETAILED

    def test_stream_handler_added_when_stream_true(self):
        """Should add a StreamHandler when stream is True."""
        logger = setup_logging(level="WARNING", stream=True)
        stream_handlers = [
            h
            for h in logger.handlers
            if isinstance(h, logging.StreamHandler)
            and not isinstance(h, logging.FileHandler)
        ]
        assert len(stream_handlers) >= 1

    def test_no_stream_handler_when_stream_false(self):
        """Should not add a StreamHandler when stream is False."""
        logger = setup_logging(level="WARNING", stream=False, log_file=None)
        stream_handlers = [
            h
            for h in logger.handlers
            if isinstance(h, logging.StreamHandler)
            and not isinstance(h, logging.FileHandler)
        ]
        assert len(stream_handlers) == 0

    def test_file_handler_added_when_log_file_specified(self, tmp_path):
        """Should add a FileHandler when log_file path is provided."""
        log_file = str(tmp_path / "test.log")
        logger = setup_logging(level="WARNING", stream=False, log_file=log_file)
        file_handlers = [
            h for h in logger.handlers if isinstance(h, logging.FileHandler)
        ]
        assert len(file_handlers) == 1
        # Clean up handler to release file
        for h in file_handlers:
            h.close()

    def test_clears_existing_handlers(self):
        """Should clear previous handlers to avoid duplicates."""
        logger = setup_logging(level="WARNING", stream=True)
        initial_count = len(logger.handlers)

        # Call again -- should not accumulate handlers
        logger = setup_logging(level="WARNING", stream=True)
        assert len(logger.handlers) == initial_count

    def test_propagate_set_to_false(self):
        """Should set propagate to False to prevent double logging."""
        logger = setup_logging(level="WARNING", stream=False)
        assert logger.propagate is False

    def test_case_insensitive_level_string(self):
        """Should accept lowercase level strings."""
        logger = setup_logging(level="debug", stream=False)
        assert logger.level == logging.DEBUG

    def test_invalid_string_level_defaults_to_info(self):
        """Should default to INFO for an unrecognized level string."""
        logger = setup_logging(level="NONEXISTENT", stream=False)
        assert logger.level == logging.INFO


class TestModuleConstants:
    """Test suite for module-level constants."""

    def test_package_name_value(self):
        """Should define the correct package name."""
        assert PACKAGE_NAME == "local_deepwiki"

    def test_log_format_contains_expected_fields(self):
        """Should include asctime, name, levelname, and message in the format."""
        assert "%(asctime)s" in LOG_FORMAT
        assert "%(name)s" in LOG_FORMAT
        assert "%(levelname)s" in LOG_FORMAT
        assert "%(message)s" in LOG_FORMAT

    def test_detailed_format_contains_file_info(self):
        """Should include filename and lineno in the detailed format."""
        assert "%(filename)s" in LOG_FORMAT_DETAILED
        assert "%(lineno)d" in LOG_FORMAT_DETAILED
