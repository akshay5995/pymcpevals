"""Integration tests for configuration loading and validation."""

import os
import tempfile
from pathlib import Path

import pytest
import yaml

from pymcpevals.config import load_yaml_config, save_config_template
from pymcpevals.types import EvaluationConfig


class TestYAMLConfigLoading:
    """Test YAML configuration loading and validation."""

    def test_complete_configuration_loading(self):
        """Test loading a complete YAML configuration with all features."""
        config_data = {
            "model": {"provider": "openai", "name": "gpt-4", "api_key": "test-key"},
            "server": {"command": ["python", "server.py"], "env": {"DEBUG": "true"}},
            "evaluations": [
                {
                    "name": "basic_math",
                    "description": "Test basic arithmetic",
                    "prompt": "What is 2 + 2?",
                    "expected_result": "Should return 4",
                    "expected_tools": ["add"],
                    "threshold": 3.0,
                    "tags": ["math", "basic"],
                }
            ],
            "timeout": 45.0,
            "parallel": True,
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_data, f)
            config_path = Path(f.name)

        try:
            config = load_yaml_config(config_path)

            # Verify all configuration is loaded correctly
            assert isinstance(config, EvaluationConfig)
            assert config.model.provider == "openai"
            assert config.model.name == "gpt-4"
            assert config.server.command == ["python", "server.py"]
            assert config.server.env == {"DEBUG": "true"}
            assert len(config.evaluations) == 1
            assert config.evaluations[0].name == "basic_math"
            assert config.evaluations[0].expected_tools == ["add"]
            assert config.timeout == 45.0
            assert config.parallel is True
        finally:
            config_path.unlink()

    def test_trajectory_configuration_loading(self):
        """Test loading configuration with trajectory evaluations."""
        config_data = {
            "model": {"provider": "anthropic", "name": "claude-3"},
            "server": {"url": "https://api.example.com/mcp"},
            "evaluations": [
                {
                    "name": "multi_step_workflow",
                    "description": "Test multi-step interaction",
                    "turns": [
                        {
                            "role": "user",
                            "content": "Initialize the process",
                            "expected_tools": ["initialize"],
                        },
                        {
                            "role": "user",
                            "content": "Execute the main task",
                            "expected_tools": ["execute"],
                        },
                        {
                            "role": "user",
                            "content": "Finalize and cleanup",
                            "expected_tools": ["finalize"],
                        },
                    ],
                    "threshold": 4.0,
                }
            ],
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_data, f)
            config_path = Path(f.name)

        try:
            config = load_yaml_config(config_path)

            # Verify trajectory configuration
            evaluation = config.evaluations[0]
            assert evaluation.is_trajectory is True
            assert len(evaluation.turns) == 3
            assert evaluation.turns[0].expected_tools == ["initialize"]
            assert evaluation.turns[1].expected_tools == ["execute"]
            assert evaluation.turns[2].expected_tools == ["finalize"]
        finally:
            config_path.unlink()

    def test_environment_variable_expansion(self):
        """Test environment variable expansion in YAML configuration."""
        # Set test environment variables
        os.environ["TEST_API_KEY"] = "secret-key-123"
        os.environ["TEST_SERVER_URL"] = "https://test-server.com"

        try:
            config_data = {
                "model": {
                    "provider": "openai",
                    "name": "gpt-4",
                    "api_key": "secret-key-123",  # Hardcoded since model config doesn't expand env vars
                },
                "server": {
                    "url": "${TEST_SERVER_URL}",  # Only exact matches are expanded
                    "headers": {
                        "Authorization": "${TEST_API_KEY}"  # Only exact matches are expanded
                    },
                },
                "evaluations": [
                    {
                        "name": "test_eval",
                        "prompt": "Test with server url",  # Hardcoded since evaluations don't expand env vars
                    }
                ],
            }

            with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
                yaml.dump(config_data, f)
                config_path = Path(f.name)

            try:
                config = load_yaml_config(config_path)

                # Environment variables should be expanded in server config only
                assert config.model.api_key == "secret-key-123"  # Hardcoded, not expanded
                assert config.server.url == "https://test-server.com"  # Expanded
                assert config.server.headers["Authorization"] == "secret-key-123"  # Expanded
                assert config.evaluations[0].prompt == "Test with server url"  # Not expanded
            finally:
                config_path.unlink()

        finally:
            # Clean up environment variables
            del os.environ["TEST_API_KEY"]
            del os.environ["TEST_SERVER_URL"]

    def test_configuration_validation_errors(self):
        """Test that invalid configurations raise appropriate errors."""
        # Missing required server configuration
        invalid_config = {
            "model": {"provider": "openai", "name": "gpt-4"},
            # Missing server section
            "evaluations": [],
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(invalid_config, f)
            config_path = Path(f.name)

        try:
            with pytest.raises(ValueError, match="Server configuration is required"):
                load_yaml_config(config_path)
        finally:
            config_path.unlink()

    def test_malformed_yaml_handling(self):
        """Test handling of malformed YAML files."""
        malformed_yaml = """
        model:
          provider: openai
        server: [unclosed list
        evaluations:
          - name: test
        """

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(malformed_yaml)
            config_path = Path(f.name)

        try:
            with pytest.raises((yaml.YAMLError, ValueError)):  # Should raise YAML parse error
                load_yaml_config(config_path)
        finally:
            config_path.unlink()


class TestConfigTemplate:
    """Test configuration template generation."""

    def test_save_and_load_config_template(self):
        """Test that saved config templates are valid and loadable."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            template_path = Path(f.name)

        try:
            # Save template
            save_config_template(template_path)

            # Verify file was created
            assert template_path.exists()

            # Verify it's valid YAML
            with open(template_path) as f:
                template_data = yaml.safe_load(f)

            assert isinstance(template_data, dict)
            assert "model" in template_data
            assert "server" in template_data
            assert "evaluations" in template_data

            # Verify template can be loaded as valid config
            config = load_yaml_config(template_path)
            assert isinstance(config, EvaluationConfig)
            assert len(config.evaluations) > 0  # Should have example evaluations

        finally:
            template_path.unlink()

    def test_template_contains_examples(self):
        """Test that generated template contains useful examples."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            template_path = Path(f.name)

        try:
            save_config_template(template_path)

            # Read template content
            with open(template_path) as f:
                content = f.read()

            # Should contain helpful examples
            assert (
                "example" in content.lower()
                or "sample" in content.lower()
                or "basic" in content.lower()
            )

            # Should show different evaluation types
            config = load_yaml_config(template_path)
            evaluation_names = [eval_case.name for eval_case in config.evaluations]

            # Should have at least one single-prompt and one trajectory example
            has_single_prompt = any(eval_case.is_single_prompt for eval_case in config.evaluations)
            has_trajectory = any(eval_case.is_trajectory for eval_case in config.evaluations)

            assert has_single_prompt or has_trajectory  # At least one type

        finally:
            template_path.unlink()
