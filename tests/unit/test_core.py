"""Unit tests for core evaluation logic and behavior."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pymcpevals.core import _execute_tool_call, evaluate_case, grade, grade_trajectory
from pymcpevals.types import ConversationTurn, EvaluationCase


class TestEvaluationRouting:
    """Test that evaluation functions route correctly based on case type."""

    @pytest.mark.asyncio
    async def test_single_prompt_routing(self):
        """Test that single prompt cases route to correct evaluation function."""
        case = EvaluationCase(name="single_test", prompt="Test prompt")

        with patch("pymcpevals.core.evaluate_mcp_server") as mock_single:
            mock_single.return_value = MagicMock(passed=True)

            await evaluate_case("test_server", case, "gpt-4")

            # Should call single prompt evaluation
            mock_single.assert_called_once_with(
                "test_server",
                "Test prompt",
                "gpt-4",
                None,  # expected_result
                None,  # expected_tools
            )

    @pytest.mark.asyncio
    async def test_trajectory_routing(self):
        """Test that trajectory cases route to correct evaluation function."""
        case = EvaluationCase(
            name="trajectory_test",
            turns=[
                ConversationTurn(role="user", content="Step 1"),
                ConversationTurn(role="user", content="Step 2"),
            ],
        )

        with patch("pymcpevals.core.evaluate_mcp_server_trajectory") as mock_trajectory:
            mock_trajectory.return_value = MagicMock(passed=True)

            await evaluate_case("test_server", case, "gpt-4")

            # Should call trajectory evaluation
            mock_trajectory.assert_called_once()
            args = mock_trajectory.call_args[0]
            assert args[0] == "test_server"  # server_source
            assert len(args[1]) == 2  # turns
            assert args[2] == "gpt-4"  # model

    @pytest.mark.asyncio
    async def test_invalid_case_handling(self):
        """Test handling of invalid evaluation cases."""
        # Test with actual invalid case creation (will raise during validation)
        with pytest.raises(ValueError, match="Must specify either"):
            EvaluationCase(name="invalid")


class TestToolValidationBehavior:
    """Test tool validation behavior and failure scenarios."""

    @pytest.mark.asyncio
    async def test_expected_tools_not_called(self):
        """Test behavior when expected tools are not called."""
        from pymcpevals.core import grade

        # Test grading function directly with missing tools
        result = await grade(
            model="gpt-4",
            prompt="Add 2 + 2",
            server_response="The answer is 4",
            expected_tools=["add"],
            tools_used=[],  # No tools were used
        )

        # Should fail when expected tools aren't used
        assert result.passed is False
        # The grading function should penalize for missing expected tools

    @pytest.mark.asyncio
    async def test_connection_error_handling(self):
        """Test graceful handling of connection errors."""
        from pymcpevals.core import evaluate_mcp_server

        # Test with clearly invalid server source
        result = await evaluate_mcp_server(
            server_source="invalid://protocol/server", prompt="Test prompt", model="gpt-4"
        )

        # Should fail gracefully with error information
        assert result.passed is False
        assert result.error is not None
        assert any(
            word in result.overall_comments.lower()
            for word in ["connection", "failed", "transport", "error"]
        )


class TestGradingBehavior:
    """Test grading function behavior and prompt construction."""

    @pytest.mark.asyncio
    async def test_grading_focuses_on_server_capabilities(self):
        """Test that grading prompt focuses on server capabilities, not LLM style."""
        mock_llm_response = MagicMock()
        mock_llm_response.choices = [MagicMock()]
        mock_llm_response.choices[
            0
        ].message.content = """{
            "accuracy": 4,
            "completeness": 4,
            "relevance": 4,
            "clarity": 4,
            "reasoning": 4,
            "overall_comments": "Server capabilities adequate"
        }"""

        with patch("pymcpevals.core.acompletion") as mock_llm:
            mock_llm.return_value = mock_llm_response

            await grade(
                model="gpt-4",
                prompt="Test prompt",
                server_response="Test response",
                expected_tools=["test_tool"],
                tools_used=["test_tool"],
            )

            # Check that the prompt sent to LLM focuses on server
            call_args = mock_llm.call_args
            prompt_content = call_args[1]["messages"][0]["content"]

            # Should mention server capabilities, not LLM behavior
            assert "server" in prompt_content.lower()
            assert "tool" in prompt_content.lower()
            # Should explicitly ignore LLM style
            assert "ignore" in prompt_content.lower()

    @pytest.mark.asyncio
    async def test_grading_json_parse_error_handling(self):
        """Test handling of malformed JSON responses from grading LLM."""
        mock_llm_response = MagicMock()
        mock_llm_response.choices = [MagicMock()]
        mock_llm_response.choices[0].message.content = "Invalid JSON response"

        with patch("pymcpevals.core.acompletion", return_value=mock_llm_response):
            result = await grade(
                model="gpt-4",
                prompt="Test",
                server_response="Test",
            )

            # Should handle JSON parse errors gracefully
            assert result.passed is False
            assert "Failed to parse" in result.overall_comments

    @pytest.mark.asyncio
    async def test_successful_tool_usage_grading(self):
        """Test grading when tools are used successfully."""
        mock_llm_response = MagicMock()
        mock_llm_response.choices = [MagicMock()]
        mock_llm_response.choices[
            0
        ].message.content = """{
            "accuracy": 4,
            "completeness": 4,
            "relevance": 4,
            "clarity": 4,
            "reasoning": 4,
            "overall_comments": "Server tools executed correctly"
        }"""

        with patch("pymcpevals.core.acompletion", return_value=mock_llm_response):
            result = await grade(
                model="gpt-4",
                prompt="What is 2 + 2?",
                server_response="The answer is 4",
                expected_tools=["add"],
                tools_used=["add"],
            )

            # Should pass when tools match expectations
            assert result.passed is True
            assert result.average_score >= 3.0
            assert "correctly" in result.overall_comments.lower()


class TestToolExecutionEdgeCases:
    """Test tool execution edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_tool_hallucination_handling(self):
        """Test handling when LLM calls non-existent tools."""
        # Mock client and tool call for hallucinated tool
        mock_client = AsyncMock()
        mock_tool_call = MagicMock()
        mock_tool_call.function.name = "nonexistent_tool"
        mock_tool_call.function.arguments = '{"param": "value"}'
        mock_tool_call.id = "call_123"

        tool_call_details = []
        tools_used = []
        available_tools = ["real_tool", "another_tool"]  # nonexistent_tool not in list

        result = await _execute_tool_call(
            mock_client, mock_tool_call, tool_call_details, tools_used, available_tools
        )

        # Should return error message
        assert result["role"] == "tool"
        assert result["tool_call_id"] == "call_123"
        assert "does not exist" in result["content"]

        # Should record hallucination in details
        assert len(tool_call_details) == 1
        assert tool_call_details[0]["success"] is False
        assert tool_call_details[0]["hallucinated"] is True
        assert tool_call_details[0]["tool_name"] == "nonexistent_tool"

        # Should not add to tools_used since it doesn't exist
        assert tools_used == []

    @pytest.mark.asyncio
    async def test_tool_execution_timing(self):
        """Test that tool execution timing is recorded accurately."""
        mock_client = AsyncMock()
        mock_tool_call = MagicMock()
        mock_tool_call.function.name = "test_tool"
        mock_tool_call.function.arguments = '{"param": "value"}'
        mock_tool_call.id = "call_123"

        # Mock successful tool execution
        mock_result = MagicMock()
        mock_result.data = "tool result"
        mock_client.call_tool.return_value = mock_result

        tool_call_details = []
        tools_used = []

        result = await _execute_tool_call(
            mock_client, mock_tool_call, tool_call_details, tools_used
        )

        # Should record execution time
        assert len(tool_call_details) == 1
        assert "execution_time_ms" in tool_call_details[0]
        assert tool_call_details[0]["execution_time_ms"] >= 0
        assert tool_call_details[0]["success"] is True
        assert tools_used == ["test_tool"]

    @pytest.mark.asyncio
    async def test_tool_result_formatting_variations(self):
        """Test different tool result formats are handled correctly."""
        mock_client = AsyncMock()
        mock_tool_call = MagicMock()
        mock_tool_call.function.name = "test_tool"
        mock_tool_call.function.arguments = '{"param": "value"}'
        mock_tool_call.id = "call_123"

        # Test .data attribute
        mock_result = MagicMock()
        mock_result.data = "result from data"
        mock_client.call_tool.return_value = mock_result

        result = await _execute_tool_call(mock_client, mock_tool_call, [], [])
        assert result["content"] == "result from data"

        # Test .content as string
        mock_result = MagicMock()
        del mock_result.data  # Remove data attribute
        mock_result.content = "result from content"
        mock_client.call_tool.return_value = mock_result

        result = await _execute_tool_call(mock_client, mock_tool_call, [], [])
        assert result["content"] == "result from content"

        # Test .content as list
        mock_item = MagicMock()
        mock_item.text = "item text"
        mock_result.content = [mock_item]
        mock_client.call_tool.return_value = mock_result

        result = await _execute_tool_call(mock_client, mock_tool_call, [], [])
        assert result["content"] == "item text"

    @pytest.mark.asyncio
    async def test_long_tool_result_truncation(self):
        """Test that long tool results are truncated in preview."""
        mock_client = AsyncMock()
        mock_tool_call = MagicMock()
        mock_tool_call.function.name = "test_tool"
        mock_tool_call.function.arguments = "{}"
        mock_tool_call.id = "call_123"

        # Create long result (> 100 chars)
        long_result = "x" * 150  # 150 character result
        mock_result = MagicMock()
        mock_result.data = long_result
        mock_client.call_tool.return_value = mock_result

        tool_call_details = []

        await _execute_tool_call(mock_client, mock_tool_call, tool_call_details, [])

        # Should truncate preview but keep full content in result
        assert len(tool_call_details) == 1
        preview = tool_call_details[0]["result_preview"]
        assert len(preview) == 103  # 100 chars + "..."
        assert preview.endswith("...")
        assert preview.startswith("x" * 100)


class TestGradingEdgeCases:
    """Test grading function edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_grading_markdown_json_extraction(self):
        """Test extraction of JSON from markdown code blocks."""
        mock_llm_response = MagicMock()
        mock_llm_response.choices = [MagicMock()]
        # Response wrapped in markdown
        mock_llm_response.choices[
            0
        ].message.content = """```json
{
    "accuracy": 4,
    "completeness": 4,
    "relevance": 4,
    "clarity": 4,
    "reasoning": 4,
    "overall_comments": "Good performance"
}
```"""

        with patch("pymcpevals.core.acompletion", return_value=mock_llm_response):
            result = await grade(
                model="gpt-4", prompt="Test prompt", server_response="Test response"
            )

            # Should successfully parse despite markdown formatting
            assert result.accuracy == 4
            assert result.passed is True
            assert "Good performance" in result.overall_comments


class TestTrajectoryValidation:
    """Test trajectory-specific validation and tool tracking."""

    @pytest.mark.asyncio
    async def test_trajectory_tool_validation_fast_fail(self):
        """Test that trajectory evaluation fails fast on tool mismatches."""
        # Create turns with specific tool expectations
        turns = [
            ConversationTurn(role="user", content="Step 1", expected_tools=["tool_a"]),
            ConversationTurn(role="user", content="Step 2", expected_tools=["tool_b"]),
        ]

        # Mock conversation history with tool mismatch
        conversation_history = [
            {"role": "system", "content": "System prompt"},
            {"role": "user", "content": "Step 1"},
            {
                "role": "assistant",
                "content": "Response 1",
                "_turn_metadata": {
                    "turn_index": 0,
                    "expected_tools": ["tool_a"],
                    "actual_tools": ["wrong_tool"],  # Mismatch!
                    "tools_match": False,
                },
            },
        ]

        # Should fail fast without calling grading LLM
        result = await grade_trajectory(
            model="gpt-4",
            conversation_history=conversation_history,
            turns=turns,
            tools_used=["wrong_tool"],
            tool_call_details=[],
        )

        # Should immediately fail due to tool mismatch
        assert result.passed is False
        assert result.average_score == 1.0
        assert "TOOL VALIDATION FAILED" in result.overall_comments
        assert "Expected [tool_a] but got [wrong_tool]" in result.overall_comments
