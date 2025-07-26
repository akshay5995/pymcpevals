"""Unit tests for data model validation and computed properties."""

import pytest
from pydantic import ValidationError

from pymcpevals.types import (
    ConversationTurn,
    EvaluationCase,
    EvaluationResult,
    ModelConfig,
    ServerConfig,
)


class TestModelConfig:
    """Test ModelConfig validation and computed properties."""

    def test_model_string_generation(self):
        """Test model string generation for different providers."""
        test_cases = [
            ("openai", "gpt-4", "gpt-4"),
            ("gemini", "gemini-pro", "gemini/gemini-pro"),
            ("vertex_ai", "gemini-pro", "vertex_ai/gemini-pro"),
            ("anthropic", "claude-3", "anthropic/claude-3"),
        ]

        for provider, model_name, expected in test_cases:
            config = ModelConfig(provider=provider, name=model_name)
            assert config.model_string == expected

    def test_default_values(self):
        """Test default configuration values."""
        config = ModelConfig()
        assert config.provider == "openai"
        assert config.name == "gpt-4"
        assert config.api_key is None


class TestServerConfig:
    """Test ServerConfig validation and computed properties."""

    def test_server_source_resolution(self):
        """Test server source resolution for different configurations."""
        # Command-based
        config = ServerConfig(command=["node", "server.js"])
        assert config.get_server_source() == ["node", "server.js"]

        # URL-based
        config = ServerConfig(url="https://api.example.com/mcp")
        assert config.get_server_source() == "https://api.example.com/mcp"

        # No configuration should raise error
        config = ServerConfig()
        with pytest.raises(ValueError, match="No valid server configuration"):
            config.get_server_source()


class TestEvaluationCase:
    """Test EvaluationCase validation and computed properties."""

    def test_single_prompt_mode_detection(self):
        """Test single prompt mode detection and turn generation."""
        case = EvaluationCase(
            name="basic_test", prompt="What is 2 + 2?", expected_tools=["add"], threshold=3.0
        )

        assert case.is_single_prompt is True
        assert case.is_trajectory is False
        assert len(case.turns) == 1
        assert case.turns[0].content == "What is 2 + 2?"
        # The expected_tools from the case level are not automatically copied to the turn
        # This is actually correct behavior - the turn itself doesn't have expected_tools set

    def test_trajectory_mode_detection(self):
        """Test trajectory mode detection."""
        turns = [
            ConversationTurn(role="user", content="Step 1"),
            ConversationTurn(role="user", content="Step 2"),
        ]
        case = EvaluationCase(name="multi_step", turns=turns, threshold=3.5)

        assert case.is_trajectory is True
        assert case.is_single_prompt is False
        assert len(case.turns) == 2

    def test_validation_rules(self):
        """Test evaluation case validation rules."""
        # Cannot have both prompt and turns
        with pytest.raises(ValueError, match="Cannot specify both"):
            EvaluationCase(
                name="invalid",
                prompt="Single prompt",
                turns=[ConversationTurn(role="user", content="Turn")],
            )

        # Must have either prompt or turns
        with pytest.raises(ValueError, match="Must specify either"):
            EvaluationCase(name="invalid")

        # Invalid threshold
        with pytest.raises(ValidationError):
            EvaluationCase(name="invalid", prompt="Test", threshold=6.0)  # > 5


class TestEvaluationResult:
    """Test EvaluationResult validation and computed properties."""

    def test_score_validation(self):
        """Test score validation constraints."""
        # Valid scores
        result = EvaluationResult(
            accuracy=3.5,
            completeness=4.0,
            relevance=2.5,
            clarity=5.0,
            reasoning=1.0,
            average_score=3.2,
            overall_comments="Test",
            model_used="gpt-4",
            server_source="test",
        )
        assert result.accuracy == 3.5

        # Invalid scores should raise validation error
        with pytest.raises(ValidationError):
            EvaluationResult(
                accuracy=6.0,  # > 5
                completeness=4.0,
                relevance=4.0,
                clarity=4.0,
                reasoning=4.0,
                average_score=4.0,
                overall_comments="Test",
                model_used="gpt-4",
                server_source="test",
            )

    def test_passed_calculation(self):
        """Test automatic passed calculation based on score."""
        # High score should pass
        result = EvaluationResult(
            accuracy=4.0,
            completeness=4.0,
            relevance=4.0,
            clarity=4.0,
            reasoning=4.0,
            average_score=4.0,
            overall_comments="Good",
            model_used="gpt-4",
            server_source="test",
        )
        assert result.passed is True

        # Low score should fail
        result = EvaluationResult(
            accuracy=2.0,
            completeness=2.0,
            relevance=2.0,
            clarity=2.0,
            reasoning=2.0,
            average_score=2.0,
            overall_comments="Poor",
            model_used="gpt-4",
            server_source="test",
        )
        assert result.passed is False
