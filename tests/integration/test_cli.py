"""Integration tests for CLI commands and error handling."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from pymcpevals.cli import main


class TestCLIBasicCommands:
    """Test basic CLI command functionality."""

    def test_help_command_succeeds(self):
        """Test that help command provides useful information."""
        with patch("sys.argv", ["pymcpevals", "--help"]):
            with pytest.raises(SystemExit) as exc_info:
                main()

            # Help should exit cleanly
            assert exc_info.value.code == 0

    def test_init_command_creates_config(self):
        """Test that init command creates a valid configuration file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "test_config.yaml"

            with patch("sys.argv", ["pymcpevals", "init", str(config_path)]):
                with pytest.raises(SystemExit) as exc_info:
                    main()

                # Init should succeed
                assert exc_info.value.code == 0

                # File should be created
                assert config_path.exists()

                # File should contain valid YAML
                with open(config_path) as f:
                    config_data = yaml.safe_load(f)

                assert isinstance(config_data, dict)
                assert "model" in config_data
                assert "server" in config_data
                assert "evaluations" in config_data

                # Should be loadable by our config loader
                from pymcpevals.config import load_yaml_config

                config = load_yaml_config(config_path)
                assert config is not None


class TestCLIErrorHandling:
    """Test CLI error handling and user feedback."""

    def test_missing_config_file_error(self):
        """Test clear error message for missing configuration file."""
        nonexistent_file = "/nonexistent/config.yaml"

        with patch("sys.argv", ["pymcpevals", "run", nonexistent_file]):
            with pytest.raises(SystemExit) as exc_info:
                main()

            # Should exit with error code
            assert exc_info.value.code != 0

    def test_invalid_yaml_config_error(self):
        """Test error handling for malformed YAML configuration."""
        invalid_yaml = """
        model:
          provider: openai
        server: [invalid yaml structure
        evaluations:
        """

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(invalid_yaml)
            config_path = f.name

        try:
            with patch("sys.argv", ["pymcpevals", "run", config_path]):
                with pytest.raises(SystemExit) as exc_info:
                    main()

                # Should exit with error code for invalid YAML
                assert exc_info.value.code != 0
        finally:
            os.unlink(config_path)

    def test_invalid_configuration_error(self):
        """Test error handling for valid YAML but invalid configuration."""
        invalid_config = {
            "model": {"provider": "openai", "name": "gpt-4"},
            # Missing required server configuration
            "evaluations": [],  # Empty evaluations also invalid
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(invalid_config, f)
            config_path = f.name

        try:
            with patch("sys.argv", ["pymcpevals", "run", config_path]):
                with pytest.raises(SystemExit) as exc_info:
                    main()

                # Should exit with error code for invalid config
                assert exc_info.value.code != 0
        finally:
            os.unlink(config_path)
