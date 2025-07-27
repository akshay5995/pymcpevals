"""
Example pytest tests for pymcpevals plugin.

Demonstrates key testing patterns similar to the YAML configuration examples.
"""

import pytest

from pymcpevals import ConversationTurn, EvaluationResult, MCPEvaluator
from pymcpevals.pytest_plugin import assert_evaluation_passed, assert_tools_called


# Example 1: Simple marker-based test (like local_server_basic.yaml)
@pytest.mark.mcp_eval(
    prompt="What is 15 + 27?",
    expected_tools=["add"],
    expected_result="Should use add tool and return 42",
    min_score=4.0,
)
async def test_basic_addition_marker(mcp_result: EvaluationResult | None) -> None:
    """Test basic addition using marker - equivalent to basic_addition in YAML."""
    assert mcp_result is not None
    assert mcp_result.passed
    assert "42" in (mcp_result.server_response or "")


# Example 2: Direct evaluator usage for error handling
async def test_division_by_zero_direct(mcp_evaluator: MCPEvaluator) -> None:
    """Test error handling - equivalent to division_by_zero in YAML."""
    result = await mcp_evaluator.evaluate_prompt(
        prompt="What happens if I divide 10 by 0?",
        expected_tools=["divide"],
        expected_result="Should handle division by zero error gracefully",
        min_score=3.5,
    )

    assert_evaluation_passed(result)
    assert_tools_called(result, ["divide"])

    # Check that error was communicated
    response_lower = (result.server_response or "").lower()
    assert any(word in response_lower for word in ["error", "cannot", "undefined", "infinity"])


# Example 3: Multi-turn trajectory (like trajectory_evaluation.yaml)
async def test_simple_math_sequence(mcp_evaluator: MCPEvaluator) -> None:
    """Test multi-step math sequence - equivalent to simple_math_sequence in YAML."""
    turns = [
        ConversationTurn(role="user", content="What is 10 + 5?", expected_tools=["add"]),
        ConversationTurn(
            role="user", content="Now multiply that result by 2", expected_tools=["multiply"]
        ),
    ]

    result = await mcp_evaluator.evaluate_trajectory(
        turns=turns, expected_result="Should calculate (10+5)*2 = 30", min_score=4.0
    )

    assert_evaluation_passed(result)
    assert_tools_called(result, ["add", "multiply"])
    assert "30" in str(result.conversation_history)
