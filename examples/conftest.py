"""Pytest configuration for examples."""

import pytest

# Configure pytest-asyncio
pytest_plugins = ["pytest_asyncio"]

# The pymcpevals plugin is already automatically loaded from the installed package
# No need to explicitly load it here

# Configure asyncio mode and fixture scope
def pytest_configure(config):
    """Configure pytest for async tests."""
    config.option.asyncio_mode = "auto"


@pytest.fixture(scope="session")
def event_loop_policy():
    """Set the event loop policy for the test session."""
    import asyncio
    return asyncio.get_event_loop_policy()


@pytest.fixture
def mcp_server():
    """Configure the calculator MCP server for testing."""
    import os

    # Get the absolute path to the calculator server
    current_dir = os.path.dirname(os.path.abspath(__file__))
    server_path = os.path.join(current_dir, "calculator_server.py")

    # Return a dictionary that matches ServerConfig format
    return {"command": ["python", server_path], "env": {"DEBUG": "false"}}


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
