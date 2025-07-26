"""YAML configuration support for pymcpevals."""

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class YamlModelConfig(BaseModel):
    """Model configuration in YAML."""

    provider: str = Field(description="LLM provider (e.g., 'openai', 'anthropic')")
    name: str = Field(description="Model name (e.g., 'gpt-4', 'claude-3-opus-20240229')")
    api_key: str | None = Field(default=None, description="API key (uses env var if not set)")


class YamlEval(BaseModel):
    """Single evaluation definition in YAML."""

    name: str = Field(description="Name of the evaluation")
    description: str = Field(description="Description of what the evaluation tests")
    prompt: str = Field(description="The prompt to send to the MCP server")
    expected_result: str | None = Field(
        default=None,
        description="Optional description of expected behavior",
    )
    tags: list[str] | None = Field(default=None, description="Optional tags for categorization")
    threshold: float | None = Field(
        default=None,
        description="Optional score threshold override for this test",
    )


class YamlEvalConfig(BaseModel):
    """Complete YAML evaluation configuration."""

    model: YamlModelConfig = Field(description="Model configuration")
    evals: list[YamlEval] = Field(description="List of evaluations to run")
    defaults: dict[str, Any] | None = Field(
        default=None,
        description="Default values for evaluations",
    )


def load_yaml_config(path: str | Path) -> YamlEvalConfig:
    """
    Load evaluation configuration from a YAML file.

    Args:
        path: Path to YAML configuration file

    Returns:
        YamlEvalConfig object

    Raises:
        FileNotFoundError: If the file doesn't exist
        yaml.YAMLError: If the YAML is invalid
        ValueError: If the configuration is invalid
    """
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")

    with open(path) as f:
        data = yaml.safe_load(f)

    return YamlEvalConfig(**data)


def yaml_eval_to_dict(eval_config: YamlEval) -> dict[str, Any]:
    """Convert a YamlEval to a dictionary suitable for test generation."""
    return {
        "query": eval_config.prompt,
        "expected_result": eval_config.expected_result,
        "threshold": eval_config.threshold,
        "tags": eval_config.tags,
        "name": eval_config.name,
        "description": eval_config.description,
    }
