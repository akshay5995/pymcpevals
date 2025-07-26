"""pymcpevals - Python package for evaluating MCP server implementations."""

from .core import evaluate_case, evaluate_mcp_server, grade, grade_sync, run_evals
from .types import (
    EvaluationCase,
    EvaluationConfig,
    EvaluationSummary,
    ModelConfig,
    ServerConfig,
)

__version__ = "0.1.0"
__all__ = [
    "EvaluationCase",
    "EvaluationConfig",
    "EvaluationSummary",
    "ModelConfig",
    "ServerConfig",
    "evaluate_case",
    "evaluate_mcp_server",
    "grade",
    "grade_sync",
    "run_evals",
]
