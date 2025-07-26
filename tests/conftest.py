"""Minimal pytest configuration and essential fixtures."""

import asyncio

import pytest

from pymcpevals.types import (
    ConversationTurn,
    EvaluationCase,
    EvaluationResult,
)


@pytest.fixture
def sample_evaluation_case():
    """Sample single-prompt evaluation case."""
    return EvaluationCase(
        name="basic_test", prompt="What is 2 + 2?", expected_tools=["add"], threshold=3.0
    )


@pytest.fixture
def sample_trajectory_case():
    """Sample trajectory evaluation case."""
    return EvaluationCase(
        name="multi_step",
        turns=[
            ConversationTurn(role="user", content="What is 10 + 5?", expected_tools=["add"]),
            ConversationTurn(role="user", content="Now multiply by 2", expected_tools=["multiply"]),
        ],
        threshold=3.5,
    )


@pytest.fixture
def sample_evaluation_result():
    """Sample evaluation result."""
    return EvaluationResult(
        accuracy=4.0,
        completeness=4.0,
        relevance=4.0,
        clarity=4.0,
        reasoning=4.0,
        average_score=4.0,
        overall_comments="Good performance",
        model_used="gpt-4",
        server_source="test_server",
        passed=True,
    )


# Pytest configuration
def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "behavior: Behavior-focused tests")


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
