"""Configuration loading for pymcpevals."""

import os
from pathlib import Path
from typing import Any

import yaml

from .types import EvaluationCase, EvaluationConfig, ModelConfig, ServerConfig


def load_yaml_config(config_path: str | Path) -> EvaluationConfig:
    """
    Load evaluation configuration from YAML file.

    Args:
        config_path: Path to YAML configuration file

    Returns:
        EvaluationConfig object

    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If config is invalid
    """
    config_path = Path(config_path)

    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(config_path) as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError("Configuration must be a YAML object")

    # Parse model configuration
    model_data = data.get("model", {})
    model_config = ModelConfig(**model_data)

    # Parse server configuration
    server_data = data.get("server", {})
    if not server_data:
        raise ValueError("Server configuration is required")

    # Handle environment variable substitution in server config
    server_data = _substitute_env_vars(server_data)
    server_config = ServerConfig(**server_data)

    # Parse evaluations
    evaluations_data = data.get("evaluations", [])
    if not evaluations_data:
        raise ValueError("At least one evaluation is required")

    evaluations = []
    for eval_data in evaluations_data:
        if not isinstance(eval_data, dict):
            raise ValueError("Each evaluation must be an object")

        evaluation = EvaluationCase(**eval_data)
        evaluations.append(evaluation)

    # Parse global settings
    timeout = data.get("timeout", 30.0)
    parallel = data.get("parallel", False)

    return EvaluationConfig(
        model=model_config,
        server=server_config,
        evaluations=evaluations,
        timeout=timeout,
        parallel=parallel,
    )


def _substitute_env_vars(data: Any) -> Any:
    """
    Recursively substitute environment variables in configuration data.

    Supports ${VAR_NAME} syntax.
    """
    if isinstance(data, dict):
        return {key: _substitute_env_vars(value) for key, value in data.items()}
    if isinstance(data, list):
        return [_substitute_env_vars(item) for item in data]
    if isinstance(data, str):
        # Simple environment variable substitution
        if data.startswith("${") and data.endswith("}"):
            var_name = data[2:-1]
            return os.getenv(var_name, data)  # Return original if env var not found
        return data
    return data


def create_simple_config(
    server_command: list[str],
    evaluations: list[dict[str, Any]],
    model: str = "gpt-4",
    provider: str = "openai",
) -> EvaluationConfig:
    """
    Create a simple evaluation configuration programmatically.

    Args:
        server_command: Command to run the MCP server
        evaluations: List of evaluation dictionaries
        model: LLM model to use
        provider: LLM provider

    Returns:
        EvaluationConfig object
    """
    model_config = ModelConfig(name=model, provider=provider)
    server_config = ServerConfig(command=server_command)

    eval_cases = []
    for eval_data in evaluations:
        eval_case = EvaluationCase(**eval_data)
        eval_cases.append(eval_case)

    return EvaluationConfig(model=model_config, server=server_config, evaluations=eval_cases)


def save_config_template(output_path: str | Path) -> None:
    """
    Save a template configuration file.

    Args:
        output_path: Where to save the template
    """
    template = {
        "model": {
            "provider": "openai",  # Options: openai, anthropic, gemini, vertex_ai
            "name": "gpt-4",  # e.g., gpt-4, claude-3-sonnet, gemini-pro, gemini-1.5-pro
            # "api_key": "${OPENAI_API_KEY}"  # Optional, uses env var by default
        },
        "server": {
            "command": ["python", "my_mcp_server.py"],
            # "env": {"DEBUG": "true"}  # Optional environment variables
        },
        "evaluations": [
            # Single-prompt evaluation
            {
                "name": "basic_functionality",
                "description": "Test basic server functionality",
                "prompt": "What can you help me with?",
                "expected_result": "Should describe available capabilities",
                "threshold": 3.0,
            },
            # Single-prompt evaluation with expected tools
            {
                "name": "tool_usage_test",
                "description": "Test if specific tools are called",
                "prompt": "What's the weather like today?",
                "expected_tools": ["get_weather"],
                "expected_result": "Should call get_weather tool and provide weather information",
                "threshold": 4.0,
            },
            # Trajectory-based evaluation
            {
                "name": "multi_step_task",
                "description": "Test multi-step problem solving",
                "turns": [
                    {
                        "role": "user",
                        "content": "I need help with my weather data analysis",
                        "expected_tools": ["get_weather"],
                    },
                    {
                        "role": "user",
                        "content": "Can you compare today's weather with last week?",
                        "expected_tools": ["get_weather", "compare_data"],
                    },
                ],
                "expected_result": "Should gather weather data and perform comparison",
                "threshold": 4.0,
                "tags": ["trajectory", "multi-step"],
            },
        ],
        "timeout": 30.0,
        "parallel": False,
    }

    output_path = Path(output_path)
    with open(output_path, "w") as f:
        yaml.dump(template, f, default_flow_style=False, indent=2)

    print(f"Configuration template saved to: {output_path}")


# For backward compatibility with original interface
def load_yaml_evals(config_path: str | Path) -> list[EvaluationCase]:
    """
    Load just the evaluation cases from a YAML file.

    Args:
        config_path: Path to YAML configuration file

    Returns:
        List of EvaluationCase objects
    """
    config = load_yaml_config(config_path)
    return config.evaluations
