"""pymcpevals - Python package for evaluating MCP server implementations."""

from .core import evaluate_case, evaluate_mcp_server, grade, grade_sync, run_evals  # noqa: F401
from .types import (
    ConversationTurn,  # noqa: F401
    EvaluationCase,  # noqa: F401
    EvaluationConfig,  # noqa: F401
    EvaluationResult,  # noqa: F401
    EvaluationSummary,  # noqa: F401
    ModelConfig,  # noqa: F401
    ServerConfig,  # noqa: F401
)

# Import pytest plugin helpers for programmatic use
try:
    from .pytest_plugin import (
        MCPEvaluator,  # noqa: F401
        assert_evaluation_passed,  # noqa: F401
        assert_min_score,  # noqa: F401
        assert_no_tool_errors,  # noqa: F401
        assert_tools_called,  # noqa: F401
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

__all__ = tuple(_base_exports + _pytest_exports)
