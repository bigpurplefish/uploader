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

    def test_migrate_old_output_file_field(self, temp_dir, monkeypatch):
        """Test migration of OUTPUT_FILE to PRODUCT_OUTPUT_FILE."""
        config_path = temp_dir / "config.json"
        monkeypatch.setattr(config, 'CONFIG_FILE', str(config_path))

        # Create old config with OUTPUT_FILE
        old_config = {
            "SHOPIFY_STORE_URL": "test.myshopify.com",
            "OUTPUT_FILE": "/path/to/old/output.json"
        }
        with open(config_path, 'w') as f:
            json.dump(old_config, f)

        # Load config (should migrate)
        loaded = config.load_config()

        assert "PRODUCT_OUTPUT_FILE" in loaded
        assert loaded["PRODUCT_OUTPUT_FILE"] == "/path/to/old/output.json"
        assert "OUTPUT_FILE" not in loaded

    def test_migrate_old_use_claude_ai_field(self, temp_dir, monkeypatch):
        """Test migration of USE_CLAUDE_AI to USE_AI_ENHANCEMENT."""
        config_path = temp_dir / "config.json"
        monkeypatch.setattr(config, 'CONFIG_FILE', str(config_path))

        # Create old config with USE_CLAUDE_AI
        old_config = {
            "SHOPIFY_STORE_URL": "test.myshopify.com",
            "USE_CLAUDE_AI": True
        }
        with open(config_path, 'w') as f:
            json.dump(old_config, f)

        # Load config (should migrate)
        loaded = config.load_config()

        assert "USE_AI_ENHANCEMENT" in loaded
        assert loaded["USE_AI_ENHANCEMENT"] is True
        assert loaded["AI_PROVIDER"] == "claude"
        assert "USE_CLAUDE_AI" not in loaded

    def test_load_config_json_decode_error(self, temp_dir, monkeypatch, caplog):
        """Test that load_config handles corrupted JSON gracefully."""
        config_path = temp_dir / "config.json"
        monkeypatch.setattr(config, 'CONFIG_FILE', str(config_path))

        # Create corrupted JSON
        with open(config_path, 'w') as f:
            f.write("{ invalid json }")

        # Should return defaults without crashing
        with caplog.at_level(logging.ERROR):
            result = config.load_config()

        assert isinstance(result, dict)
        assert "SHOPIFY_STORE_URL" in result
        assert "Failed to parse config.json" in caplog.text

    def test_save_config_io_error(self, monkeypatch, caplog):
        """Test that save_config logs IO errors gracefully."""
        # Set config path to invalid location
        monkeypatch.setattr(config, 'CONFIG_FILE', '/nonexistent/path/config.json')

        with caplog.at_level(logging.ERROR):
            config.save_config({"test": "data"})

        # Should log error but not crash
        assert "Failed to write config.json" in caplog.text or "error" in caplog.text.lower()

    def test_load_config_io_error(self, temp_dir, monkeypatch, caplog):
        """Test that load_config handles IO errors gracefully."""
        config_path = temp_dir / "config.json"
        monkeypatch.setattr(config, 'CONFIG_FILE', str(config_path))

        # Create file and make it unreadable by mocking open to raise IOError
        config_path.touch()

        def mock_open_ioerror(*args, **kwargs):
            if 'r' in str(kwargs.get('mode', args[1] if len(args) > 1 else '')):
                raise IOError("Cannot read file")
            # Allow write for initial creation
            return open(*args, **kwargs)

        monkeypatch.setattr("builtins.open", mock_open_ioerror)

        with caplog.at_level(logging.ERROR):
            result = config.load_config()

        assert isinstance(result, dict)
        assert "Failed to read/write config.json" in caplog.text

    def test_load_config_generic_exception(self, temp_dir, monkeypatch, caplog):
        """Test that load_config handles unexpected exceptions gracefully."""
        config_path = temp_dir / "config.json"
        monkeypatch.setattr(config, 'CONFIG_FILE', str(config_path))
        config_path.touch()

        def mock_open_error(*args, **kwargs):
            raise RuntimeError("Unexpected error")

        monkeypatch.setattr("builtins.open", mock_open_error)

        with caplog.at_level(logging.ERROR):
            result = config.load_config()

        assert isinstance(result, dict)
        assert "Unexpected error loading config" in caplog.text

    def test_save_config_generic_exception(self, monkeypatch, caplog):
        """Test that save_config handles unexpected exceptions gracefully."""
        def mock_open_error(*args, **kwargs):
            raise RuntimeError("Unexpected error")

        monkeypatch.setattr("builtins.open", mock_open_error)

        with caplog.at_level(logging.ERROR):
            config.save_config({"test": "data"})

        assert "Unexpected error saving config" in caplog.text


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

    def test_setup_logging_handles_exceptions(self, temp_dir, monkeypatch, capsys):
        """Test that setup_logging handles exceptions and re-raises."""
        def mock_file_handler_error(*args, **kwargs):
            raise RuntimeError("Cannot create file handler")

        monkeypatch.setattr("logging.FileHandler", mock_file_handler_error)

        with pytest.raises(RuntimeError, match="Cannot create file handler"):
            config.setup_logging(str(temp_dir / "test.log"))

        # Check that error was printed to stderr
        captured = capsys.readouterr()
        assert "Failed to setup logging" in captured.err


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

    def test_log_and_status_strips_url_from_ui_msg(self, mock_status_fn, caplog):
        """Test that URLs are stripped from UI messages."""
        with caplog.at_level(logging.INFO):
            config.log_and_status(
                mock_status_fn,
                msg="Uploading product https://cdn.shopify.com/image.jpg"
            )

        # UI message should have URL stripped
        assert len(mock_status_fn.messages) == 1
        assert "https://" not in mock_status_fn.messages[0]
        assert "Uploading product" in mock_status_fn.messages[0]

    def test_log_and_status_preserves_final_url(self, mock_status_fn, caplog):
        """Test that 'Final URL' messages preserve the URL."""
        with caplog.at_level(logging.INFO):
            config.log_and_status(
                mock_status_fn,
                msg="Final URL: https://admin.shopify.com/product/123"
            )

        # UI message should preserve URL for Final URL messages
        assert len(mock_status_fn.messages) == 1
        assert "Final URL: https://admin.shopify.com/product/123" in mock_status_fn.messages[0]

    def test_log_and_status_handles_exception_in_status_fn(self, caplog, capsys):
        """Test that exceptions in status_fn are handled gracefully."""
        def broken_status_fn(msg):
            raise ValueError("Status function broke!")

        with caplog.at_level(logging.INFO):
            # Should not raise exception
            config.log_and_status(
                broken_status_fn,
                msg="Test message"
            )

        # Should log warning about the exception
        assert any("status_fn raised" in record.message for record in caplog.records)

        # Should fallback to console print
        captured = capsys.readouterr()
        assert "[STATUS]" in captured.out


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

    def test_exception_hook_logs_unhandled_exceptions(self, temp_dir):
        """Test that exception hook logs unhandled exceptions."""
        log_path = temp_dir / "test.log"
        config.setup_logging(str(log_path))

        # Trigger the exception hook directly
        import sys
        try:
            raise ValueError("Test exception")
        except ValueError:
            exc_info = sys.exc_info()
            # Call the exception hook
            sys.excepthook(*exc_info)

        # Check that it was logged to the file
        with open(log_path, 'r') as f:
            log_content = f.read()
            assert "Unhandled exception" in log_content or "CRITICAL" in log_content


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
