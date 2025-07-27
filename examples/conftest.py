"""Pytest configuration for examples."""

import pytest

# Note: pymcpevals plugin is automatically loaded via entry point in pyproject.toml


@pytest.fixture
def mcp_server():
    """Configure the calculator MCP server for testing."""
    import os
    # Get the absolute path to the calculator server
    current_dir = os.path.dirname(os.path.abspath(__file__))
    server_path = os.path.join(current_dir, "calculator_server.py")
    
    # Return a dictionary that matches ServerConfig format
    return {
        "command": ["python", server_path],
        "env": {"DEBUG": "false"}
    }


@pytest.fixture  
def mcp_model():
    """Configure the LLM model for evaluations."""
    # Use claude-3-5-sonnet-20241022 for faster/cheaper tests
    return "claude-3-5-sonnet-20241022"

@pytest.fixture
def mcp_model_provider():
    """Configure the LLM model provider for evaluations."""
    # Use claude-3.5 for faster/cheaper tests
    return "anthropic"