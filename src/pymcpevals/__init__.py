"""pymcpevals - Python package for evaluating MCP server implementations."""

from .core import evaluate_case, evaluate_mcp_server, grade, grade_sync, run_evals
from .types import (
    ConversationTurn,
    EvaluationCase,
    EvaluationConfig,
    EvaluationResult,
    EvaluationSummary,
    ModelConfig,
    ServerConfig,
)

# Import pytest plugin helpers for programmatic use
try:
    from .pytest_plugin import (
        MCPEvaluator,
        assert_evaluation_passed,
        assert_min_score,
        assert_no_tool_errors,
        assert_tools_called,
    )

    # Add to __all__ if pytest is available
    _pytest_exports = [
        "MCPEvaluator",
        "assert_evaluation_passed",
        "assert_min_score",
        "assert_no_tool_errors",
        "assert_tools_called",
    ]
except ImportError:
    # Pytest not installed, plugin features not available
    _pytest_exports = []

__version__ = "0.1.0"

# Build __all__ dynamically to include pytest exports if available
_base_exports = [
    "ConversationTurn",
    "EvaluationCase",
    "EvaluationConfig",
    "EvaluationResult",
    "EvaluationSummary",
    "ModelConfig",
    "ServerConfig",
    "evaluate_case",
    "evaluate_mcp_server",
    "grade",
    "grade_sync",
    "run_evals",
]

__all__ = _base_exports + _pytest_exports
