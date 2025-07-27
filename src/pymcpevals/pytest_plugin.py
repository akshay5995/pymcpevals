"""Pytest plugin for pymcpevals - easy MCP server testing."""

from typing import Any

import pytest
from _pytest.config import Config

from .core import evaluate_case, evaluate_mcp_server, evaluate_mcp_server_trajectory
from .types import ConversationTurn, EvaluationCase, EvaluationResult


def pytest_configure(config: Config) -> None:
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "mcp_eval: Mark test as MCP evaluation (args: prompt, expected_tools, expected_result, min_score)",
    )
    config.addinivalue_line(
        "markers",
        "mcp_trajectory: Mark test as MCP trajectory evaluation",
    )


class MCPEvaluator:
    """Helper class for MCP evaluations in tests."""

    def __init__(self, server_source: Any, model: str = "gpt-4"):
        self.server_source = server_source
        self.model = model

    async def evaluate_prompt(
        self,
        prompt: str,
        expected_tools: list[str] | None = None,
        expected_result: str | None = None,
        min_score: float = 3.0,
    ) -> EvaluationResult:
        """Evaluate a single prompt."""
        result = await evaluate_mcp_server(
            self.server_source,
            prompt,
            self.model,
            expected_result,
            expected_tools,
        )
        # Update passed status based on min_score
        result.passed = result.average_score >= min_score
        return result

    async def evaluate_trajectory(
        self,
        turns: list[ConversationTurn],
        expected_result: str | None = None,
        min_score: float = 3.0,
    ) -> EvaluationResult:
        """Evaluate a multi-turn trajectory."""
        result = await evaluate_mcp_server_trajectory(
            self.server_source,
            turns,
            self.model,
            expected_result,
        )
        # Update passed status based on min_score
        result.passed = result.average_score >= min_score
        return result

    async def evaluate_case(
        self,
        case: EvaluationCase,
        min_score: float | None = None,
    ) -> EvaluationResult:
        """Evaluate an EvaluationCase."""
        result = await evaluate_case(self.server_source, case, self.model)
        # Use case threshold or provided min_score
        threshold = min_score or case.threshold or 3.0
        result.passed = result.average_score >= threshold
        return result


@pytest.fixture
def mcp_evaluator(mcp_server: str | list[str] | dict[str, Any], mcp_model: str) -> MCPEvaluator:
    """Create an MCP evaluator for testing."""
    return MCPEvaluator(mcp_server, mcp_model)


@pytest.fixture
def mcp_server() -> str | list[str] | dict[str, Any]:
    """
    MCP server configuration.
    Override this fixture in your conftest.py:

    @pytest.fixture
    def mcp_server():
        return ["python", "my_server.py"]
        # or return "http://localhost:8080/mcp"
        # or return {"command": ["python", "server.py"], "env": {"DEBUG": "true"}}
    """
    raise NotImplementedError(
        "You must define the 'mcp_server' fixture in your conftest.py. "
        "It should return either a command list, URL string, or config dict."
    )


@pytest.fixture
def mcp_model() -> str:
    """LLM model to use for evaluations. Override to change."""
    return "gpt-4"


def assert_evaluation_passed(result: EvaluationResult, message: str = "") -> None:
    """Assert that an evaluation passed."""
    if not result.passed:
        msg = f"Evaluation failed with score {result.average_score:.2f}"
        if message:
            msg = f"{message}: {msg}"
        msg += f"\nDetails: {result.overall_comments}"
        if result.error:
            msg += f"\nError: {result.error}"
        pytest.fail(msg)


def assert_tools_called(
    result: EvaluationResult,
    expected_tools: list[str],
    exact: bool = True,
) -> None:
    """Assert that specific tools were called."""
    tools_used = result.tools_used or []

    if exact:
        # Exact match required
        if set(tools_used) != set(expected_tools):
            pytest.fail(f"Tool mismatch - Expected: {expected_tools}, Got: {tools_used}")
    else:
        # Just check if expected tools are included
        missing = set(expected_tools) - set(tools_used)
        if missing:
            pytest.fail(f"Missing expected tools: {list(missing)}. Tools called: {tools_used}")


def assert_min_score(
    result: EvaluationResult,
    min_score: float,
    dimension: str | None = None,
) -> None:
    """Assert minimum score requirement."""
    if dimension:
        # Check specific dimension
        score = getattr(result, dimension)
        if score < min_score:
            pytest.fail(f"{dimension} score {score:.2f} is below minimum {min_score}")
    # Check average score
    elif result.average_score < min_score:
        pytest.fail(f"Average score {result.average_score:.2f} is below minimum {min_score}")


def assert_no_tool_errors(result: EvaluationResult) -> None:
    """Assert that no tools failed during execution."""
    if result.failed_tool_calls > 0:
        error_details = [
            f"- {call['tool_name']}: {call.get('error_message', 'Unknown error')}"
            for call in result.tool_call_details
            if not call.get("success", True)
        ]
        pytest.fail(f"{result.failed_tool_calls} tool(s) failed:\n" + "\n".join(error_details))


# Fixture-based approach for marker tests
@pytest.fixture
async def mcp_result(
    request: pytest.FixtureRequest, mcp_evaluator: MCPEvaluator
) -> EvaluationResult | None:
    """
    Fixture that automatically runs evaluation for tests marked with @pytest.mark.mcp_eval.

    Usage:
    @pytest.mark.mcp_eval(prompt="test", expected_tools=["tool"])
    async def test_something(mcp_result):
        assert mcp_result.passed
    """
    marker = request.node.get_closest_marker("mcp_eval")
    if not marker:
        return None

    # Extract marker arguments
    prompt = marker.kwargs.get("prompt")
    if not prompt:
        pytest.fail("@pytest.mark.mcp_eval requires 'prompt' argument")

    expected_tools = marker.kwargs.get("expected_tools")
    expected_result = marker.kwargs.get("expected_result")
    min_score = marker.kwargs.get("min_score", 3.0)

    # Run evaluation
    result = await mcp_evaluator.evaluate_prompt(
        prompt=prompt,
        expected_tools=expected_tools,
        expected_result=expected_result,
        min_score=min_score,
    )

    # Automatic validation - tests will fail if these assertions fail
    assert_evaluation_passed(result)

    if expected_tools:
        assert_tools_called(result, expected_tools)

    return result
