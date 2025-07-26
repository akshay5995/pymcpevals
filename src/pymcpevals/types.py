"""Pydantic types for pymcpevals."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ConversationTurn(BaseModel):
    """A single turn in a conversation trajectory."""

    role: str = Field(description="Role (user, assistant, or system)")
    content: str = Field(description="Content of the turn")
    expected_tools: list[str] | None = Field(
        default=None, description="Expected tools that should be called in this turn"
    )
    expected_result: str | None = Field(
        default=None, description="Expected outcome or behavior for this turn"
    )


# Keep EvaluationResult for backward compatibility and internal grade functions
class EvaluationResult(BaseModel):
    """Basic evaluation result (kept for backward compatibility)."""

    accuracy: float = Field(ge=1, le=5, description="Accuracy score from 1-5")
    completeness: float = Field(ge=1, le=5, description="Completeness score from 1-5")
    relevance: float = Field(ge=1, le=5, description="Relevance score from 1-5")
    clarity: float = Field(ge=1, le=5, description="Clarity score from 1-5")
    reasoning: float = Field(ge=1, le=5, description="Reasoning score from 1-5")
    average_score: float = Field(ge=1, le=5, description="Average of all scores")
    overall_comments: str = Field(description="Summary of strengths and weaknesses")

    # Metadata - supports both single prompt and trajectory modes
    prompt: str | None = Field(default=None, description="Original user prompt (single-turn mode)")
    server_response: str | None = Field(
        default=None, description="Response from MCP server (single-turn mode)"
    )
    conversation_history: list[dict[str, Any]] | None = Field(
        default=None, description="Full conversation history (trajectory mode)"
    )
    tools_used: list[str] | None = Field(
        default=None, description="List of tools that were called during evaluation"
    )
    expected_tools: list[str] | None = Field(
        default=None, description="List of tools that were expected to be called"
    )
    expected_result: str | None = Field(
        default=None,
        description="Expected behavior description",
    )
    model_used: str = Field(description="LLM model used for evaluation")
    server_source: str = Field(description="Source of the MCP server")
    error: str | None = Field(default=None, description="Error message if evaluation failed")
    passed: bool = Field(default=False, description="Whether the evaluation passed the threshold")

    # Server developer focused fields
    total_execution_time_ms: float = Field(
        default=0.0, description="Total tool execution time in milliseconds"
    )
    failed_tool_calls: int = Field(default=0, description="Number of failed tool calls")
    tool_call_details: list[dict[str, Any]] = Field(
        default_factory=list, description="Detailed tool call information"
    )

    def model_post_init(self, __context: Any) -> None:
        """Set passed field based on average score if not explicitly set."""
        if self.passed is False and hasattr(self, "average_score"):
            self.passed = self.average_score >= 3.0

    def __str__(self) -> str:
        """Human-readable summary."""
        status = "PASS" if self.passed else "FAIL"
        return f"[{status}] Average: {self.average_score:.1f}/5.0 - {self.overall_comments[:50]}..."


class ModelConfig(BaseModel):
    """LLM model configuration."""

    provider: str = Field(
        default="openai", description="LLM provider (openai, anthropic, gemini, vertex_ai, etc.)"
    )
    name: str = Field(default="gpt-4", description="Model name")
    api_key: str | None = Field(default=None, description="API key override")

    @property
    def model_string(self) -> str:
        """Get the model string for litellm."""
        if self.provider == "openai":
            return self.name
        if self.provider == "gemini":
            # For Gemini, litellm expects formats like "gemini/gemini-pro"
            return f"gemini/{self.name}"
        if self.provider == "vertex_ai":
            # For Vertex AI (Google's managed Gemini)
            return f"vertex_ai/{self.name}"
        return f"{self.provider}/{self.name}"


class ServerConfig(BaseModel):
    """MCP server configuration."""

    # For stdio servers
    command: list[str] | None = Field(default=None, description="Command to run server")
    env: dict[str, str] | None = Field(default=None, description="Environment variables")

    # For HTTP servers
    url: str | None = Field(default=None, description="Server URL")
    headers: dict[str, str] | None = Field(default=None, description="HTTP headers")

    # For FastMCP server instances
    server_instance: Any | None = Field(default=None, description="FastMCP server instance")

    def get_server_source(self, config_path: str | None = None) -> Any:
        """Get the appropriate server source for FastMCP Client."""
        if self.server_instance is not None:
            return self.server_instance
        if self.url is not None:
            return self.url
        if self.command is not None:
            # For stdio servers, if command is ["python", "script.py"], resolve path properly
            if (
                len(self.command) == 2
                and self.command[0] == "python"
                and self.command[1].endswith(".py")
            ):
                import os

                script_path = self.command[1]

                # If not absolute, try to resolve relative to config file or current directory
                if not os.path.isabs(script_path):
                    # Try relative to config file directory first
                    if config_path:
                        config_dir = os.path.dirname(config_path)
                        potential_path = os.path.join(config_dir, script_path)
                        if os.path.exists(potential_path):
                            script_path = os.path.abspath(potential_path)
                        else:
                            # Try current directory
                            script_path = os.path.abspath(script_path)
                    else:
                        script_path = os.path.abspath(script_path)

                # Check if the script file exists
                if os.path.exists(script_path):
                    return script_path
                # File doesn't exist, return command array so FastMCP can give a better error
                return self.command

            # For other command formats, return as is
            return self.command
        raise ValueError("No valid server configuration provided")


class EvaluationCase(BaseModel):
    """Single evaluation case - supports both single prompt and trajectory modes."""

    name: str = Field(description="Name of the evaluation")
    description: str | None = Field(default=None, description="Description of what this tests")

    # Single prompt mode
    prompt: str | None = Field(
        default=None, description="User prompt to evaluate (single-turn mode)"
    )
    expected_result: str | None = Field(
        default=None,
        description="Expected behavior description (single-turn mode)",
    )
    expected_tools: list[str] | None = Field(
        default=None,
        description="Expected tools to be called (single-turn mode)",
    )

    # Trajectory mode
    turns: list[ConversationTurn] | None = Field(
        default=None, description="Conversation trajectory (multi-turn mode)"
    )

    threshold: float | None = Field(
        default=3.0,
        ge=1,
        le=5,
        description="Minimum average score to pass",
    )
    tags: list[str] | None = Field(default=None, description="Tags for categorization")

    @property
    def is_trajectory(self) -> bool:
        """Check if this is a trajectory-based evaluation."""
        return self.prompt is None and self.turns is not None and len(self.turns) > 0

    @property
    def is_single_prompt(self) -> bool:
        """Check if this is a single prompt evaluation."""
        return self.prompt is not None

    def model_post_init(self, __context: Any) -> None:
        """Validate that either prompt or turns is provided, but not both."""
        if self.prompt and self.turns:
            raise ValueError(
                "Cannot specify both 'prompt' and 'turns'. Use either single-prompt or trajectory mode."
            )
        if not self.prompt and not self.turns:
            raise ValueError("Must specify either 'prompt' (single-turn) or 'turns' (trajectory).")

        # If using single prompt mode, create a single turn internally for consistency
        if self.prompt and not self.turns:
            self.turns = [
                ConversationTurn(
                    role="user", content=self.prompt, expected_result=self.expected_result
                )
            ]


class EvaluationConfig(BaseModel):
    """Complete evaluation configuration."""

    model: ModelConfig = Field(default_factory=ModelConfig, description="LLM model configuration")
    server: ServerConfig = Field(description="MCP server configuration")
    evaluations: list[EvaluationCase] = Field(description="List of evaluations to run")

    # Global settings
    timeout: float | None = Field(default=30.0, description="Timeout for each evaluation")
    parallel: bool | None = Field(default=False, description="Run evaluations in parallel")


class EvaluationSummary(BaseModel):
    """Summary of all evaluation results."""

    total_evaluations: int = Field(description="Total number of evaluations")
    passed: int = Field(description="Number of evaluations that passed")
    failed: int = Field(description="Number of evaluations that failed")
    average_score: float = Field(description="Overall average score")
    results: list[EvaluationResult] = Field(description="Individual evaluation results")

    @property
    def pass_rate(self) -> float:
        """Calculate pass rate as percentage."""
        if self.total_evaluations == 0:
            return 0.0
        return (self.passed / self.total_evaluations) * 100

    def __str__(self) -> str:
        """Human-readable summary."""
        return f"Results: {self.passed}/{self.total_evaluations} passed ({self.pass_rate:.1f}%) - Average: {self.average_score:.1f}/5.0"
