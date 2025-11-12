"""
Tests for uploader_modules/config.py

Tests configuration management and logging functions.
"""

import pytest
import json
import logging
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from uploader_modules import config


# ============================================================================
# CONFIG LOAD/SAVE TESTS
# ============================================================================

class TestConfigManagement:
    """Tests for configuration file management."""

    def test_load_config_nonexistent(self, temp_dir, monkeypatch):
        """Test loading config when file doesn't exist returns default config."""
        monkeypatch.setattr(config, 'CONFIG_FILE', str(temp_dir / 'config.json'))
        result = config.load_config()
        # Should return a dictionary with default values
        assert isinstance(result, dict)

    def test_save_and_load_config(self, temp_config_file, monkeypatch):
        """Test saving and loading configuration."""
        monkeypatch.setattr(config, 'CONFIG_FILE', str(temp_config_file))

        # Load existing config
        loaded_config = config.load_config()
        assert loaded_config["SHOPIFY_STORE_URL"] == "test-store.myshopify.com"

        # Modify and save
        loaded_config["USE_AI_ENHANCEMENT"] = True
        config.save_config(loaded_config)

        # Load again to verify
        reloaded = config.load_config()
        assert reloaded["USE_AI_ENHANCEMENT"] is True

    def test_config_has_required_fields(self, temp_config_file, monkeypatch):
        """Test that config contains all required fields."""
        monkeypatch.setattr(config, 'CONFIG_FILE', str(temp_config_file))
        loaded_config = config.load_config()

        required_fields = [
            "SHOPIFY_STORE_URL",
            "SHOPIFY_ACCESS_TOKEN",
            "USE_AI_ENHANCEMENT"
        ]

        for field in required_fields:
            assert field in loaded_config


# ============================================================================
# LOGGING SETUP TESTS
# ============================================================================

class TestLoggingSetup:
    """Tests for logging configuration."""

    def test_setup_logging_creates_log_file(self, temp_dir):
        """Test that setup_logging creates a log file."""
        log_path = temp_dir / "test.log"
        config.setup_logging(str(log_path))

        # Log a test message
        logging.info("Test message")

        # Verify log file was created
        assert log_path.exists()

    def test_setup_logging_with_debug_level(self, temp_dir):
        """Test setup_logging with DEBUG level."""
        log_path = temp_dir / "debug.log"
        config.setup_logging(str(log_path), level=logging.DEBUG)

        # Log debug message
        logging.debug("Debug message")

        # Verify it was logged
        with open(log_path, 'r') as f:
            content = f.read()
            assert "Debug message" in content

    def test_setup_logging_console_output(self, temp_dir):
        """Test that logging outputs to console."""
        log_path = temp_dir / "test.log"
        config.setup_logging(str(log_path))

        # Log a message
        logging.info("Console test message")

        # Verify it was logged to file (console logging tested manually)
        with open(log_path, 'r') as f:
            content = f.read()
            assert "Console test message" in content


# ============================================================================
# LOG_AND_STATUS TESTS
# ============================================================================

class TestLogAndStatus:
    """Tests for log_and_status() dual logging function."""

    def test_log_and_status_with_status_fn(self, mock_status_fn, caplog):
        """Test log_and_status sends message to status function."""
        with caplog.at_level(logging.INFO):
            config.log_and_status(
                mock_status_fn,
                msg="Detailed technical message",
                ui_msg="Simple user message"
            )

        # Check status function received UI message
        assert len(mock_status_fn.messages) == 1
        assert mock_status_fn.messages[0] == "Simple user message"

        # Check log received detailed message
        assert "Detailed technical message" in caplog.text

    def test_log_and_status_without_ui_msg(self, mock_status_fn, caplog):
        """Test log_and_status uses main message if no ui_msg provided."""
        with caplog.at_level(logging.INFO):
            config.log_and_status(
                mock_status_fn,
                msg="Main message"
            )

        assert mock_status_fn.messages[0] == "Main message"
        assert "Main message" in caplog.text

    def test_log_and_status_none_status_fn(self, caplog):
        """Test log_and_status works with None status_fn (CLI mode)."""
        with caplog.at_level(logging.INFO):
            config.log_and_status(
                None,
                msg="CLI only message"
            )

        # Should log but not crash
        assert "CLI only message" in caplog.text

    def test_log_and_status_warning_level(self, mock_status_fn, caplog):
        """Test log_and_status with warning level."""
        with caplog.at_level(logging.WARNING):
            config.log_and_status(
                mock_status_fn,
                msg="Warning message",
                level="warning"
            )

        assert "Warning message" in caplog.text
        # Check it was logged at WARNING level
        assert any(record.levelname == "WARNING" for record in caplog.records)

    def test_log_and_status_error_level(self, mock_status_fn, caplog):
        """Test log_and_status with error level."""
        with caplog.at_level(logging.ERROR):
            config.log_and_status(
                mock_status_fn,
                msg="Error message",
                level="error"
            )

        assert "Error message" in caplog.text
        assert any(record.levelname == "ERROR" for record in caplog.records)

    def test_log_and_status_info_level_default(self, mock_status_fn, caplog):
        """Test that log_and_status defaults to INFO level."""
        with caplog.at_level(logging.INFO):
            config.log_and_status(
                mock_status_fn,
                msg="Info message"
            )

        assert any(record.levelname == "INFO" for record in caplog.records)


# ============================================================================
# GLOBAL EXCEPTION LOGGING TESTS
# ============================================================================

class TestGlobalExceptionLogging:
    """Tests for global exception logging."""

    def test_install_global_exception_logging(self, caplog):
        """Test that global exception logging captures unhandled exceptions."""
        # Install the hook
        config.install_global_exception_logging()

        # The actual exception hook is hard to test without crashing the test
        # but we can verify it was installed
        import sys
        assert sys.excepthook != sys.__excepthook__


# ============================================================================
# CONFIG FILE FORMAT TESTS
# ============================================================================

class TestConfigFileFormat:
    """Tests for config file format and structure."""

    def test_config_saved_as_valid_json(self, temp_dir, monkeypatch):
        """Test that config is saved as valid JSON."""
        config_path = temp_dir / "config.json"
        monkeypatch.setattr(config, 'CONFIG_FILE', str(config_path))

        test_config = {
            "SHOPIFY_STORE_URL": "test.myshopify.com",
            "SHOPIFY_ACCESS_TOKEN": "token123"
        }

        config.save_config(test_config)

        # Read and parse
        with open(config_path, 'r') as f:
            parsed = json.load(f)

        assert parsed["SHOPIFY_STORE_URL"] == "test.myshopify.com"

    def test_config_has_proper_indentation(self, temp_dir, monkeypatch):
        """Test that config file has readable indentation."""
        config_path = temp_dir / "config.json"
        monkeypatch.setattr(config, 'CONFIG_FILE', str(config_path))

        test_config = {"key1": "value1", "key2": {"nested": "value"}}
        config.save_config(test_config)

        with open(config_path, 'r') as f:
            content = f.read()

        # Should have newlines and indentation
        assert '\n' in content
        assert ('    ' in content or '\t' in content)
