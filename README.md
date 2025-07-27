# PyMCPEvals

> **⚠️ Still Under Development** - APIs may change. Use with caution in production.

**Server-focused evaluation framework for MCP (Model Context Protocol) servers.**

🚀 **Test your MCP server capabilities, not LLM conversation patterns.**

**"Are my MCP server's tools working correctly and being used as expected?"**

PyMCPEvals separates what you **can control** (server) from what you **cannot** (LLM behavior):

### ✅ What You Control (We Test This)
- Tool implementation correctness
- Tool parameter validation  
- Error handling and recovery
- Tool result formatting
- Multi-turn state management

### ❌ What You Cannot Control (We Ignore This)
- LLM conversation patterns
- How LLMs choose to use tools
- LLM response formatting
- Whether LLMs provide intermediate responses

## Key Pain Points Solved

- **🚫 Manual Tool Testing**: Automated assertions verify exact tool calls
- **❓ Multi-step Failures**: Track tool chaining across conversation turns
- **🐛 Silent Tool Errors**: Instant feedback when expected tools aren't called
- **📊 CI/CD Integration**: JUnit XML output for automated testing pipelines

## Quick Start

```bash
pip install pymcpevals
pymcpevals init                    # Create template config
pymcpevals run evals.yaml         # Run evaluations
```

## Example Configuration

```yaml
model:
  provider: openai
  name: gpt-4

server:
  command: ["python", "my_server.py"]

evaluations:
  - name: "weather_check"
    prompt: "What's the weather in Boston?"
    expected_tools: ["get_weather"]  # ✅ Validates tool usage
    expected_result: "Should call weather API and return conditions"
    threshold: 3.5
    
  - name: "multi_step"
    turns:
      - role: "user"
        content: "What's the weather in London?"
        expected_tools: ["get_weather"]
      - role: "user"  
        content: "And in Paris?"
        expected_tools: ["get_weather"]
    expected_result: "Should provide weather for both cities"
    threshold: 4.0
```

**Output**: Pass/fail status, tool validation, execution metrics, and server-focused scoring.

## How It Works

1. **Connect** to your MCP server via FastMCP
2. **Execute** prompts and track tool calls
3. **Validate** expected tools are called (instant feedback)
4. **Evaluate** server performance (ignores LLM style)
5. **Report** results with actionable insights

## What Makes This Different

**Precise Tool Assertions**: Unlike traditional evaluations that judge LLM responses, PyMCPEvals validates:

- ✅ **Exact tool calls**: `assert_tools_called(result, ["add", "multiply"])`
- ✅ **Tool execution success**: `assert_no_tool_errors(result)`  
- ✅ **Multi-turn trajectories**: Test tool chaining across conversation steps
- ✅ **Instant failure detection**: No expensive LLM evaluation for obvious failures

## Usage

### CLI

```bash
# Basic usage
pymcpevals run evals.yaml

# Override server/model
pymcpevals run evals.yaml --server "node server.js" --model gpt-4

# Different outputs
pymcpevals run evals.yaml --output table    # Simple table
pymcpevals run evals.yaml --output json     # Full JSON
pymcpevals run evals.yaml --output junit    # CI/CD format
```

### Pytest Integration

```python
from pymcpevals import (
    assert_tools_called, 
    assert_evaluation_passed,
    assert_min_score,
    assert_no_tool_errors,
    ConversationTurn
)

# Simple marker-based test
@pytest.mark.mcp_eval(
    prompt="What is 15 + 27?",
    expected_tools=["add"],
    min_score=4.0
)
async def test_basic_addition(mcp_result):
    assert_evaluation_passed(mcp_result)
    assert_tools_called(mcp_result, ["add"])
    assert "42" in mcp_result.server_response

# Multi-turn trajectory testing
async def test_math_sequence(mcp_evaluator):
    turns = [
        ConversationTurn(role="user", content="What is 10 + 5?", expected_tools=["add"]),
        ConversationTurn(role="user", content="Now multiply by 2", expected_tools=["multiply"])
    ]
    result = await mcp_evaluator.evaluate_trajectory(turns, min_score=4.0)
    
    # Rich assertions
    assert_evaluation_passed(result)
    assert_tools_called(result, ["add", "multiply"])
    assert_no_tool_errors(result)
    assert_min_score(result, 4.0, dimension="accuracy")
    assert "30" in str(result.conversation_history)

# Run with: pytest -m mcp_eval
```

## Examples

Check out the `examples/` directory for:
- `calculator_server.py` - Simple MCP server for testing
- `local_server_basic.yaml` - Basic evaluation configuration examples
- `trajectory_evaluation.yaml` - Multi-turn conversation examples
- `test_simple_plugin_example.py` - Pytest integration examples

Run the examples:
```bash
# Test with the example calculator server
pymcpevals run examples/local_server_basic.yaml

# Run pytest examples
cd examples && pytest test_simple_plugin_example.py
```

## Installation

```bash
pip install pymcpevals
```

## Environment Setup

```bash
export OPENAI_API_KEY="sk-..."        # or ANTHROPIC_API_KEY
export GEMINI_API_KEY="..."           # for Gemini models
```

## Output Formats

### Table View (default)
```
┌──────────────────────────────────────────┬────────┬─────┬──────┬─────┬──────┬──────┬──────┬───────┐
│ Name                                     │ Status │ Acc │ Comp │ Rel │ Clar │ Reas │ Avg  │ Tools │
├──────────────────────────────────────────┼────────┼─────┼──────┼─────┼──────┼──────┼──────┼───────┤
│ What is 15 + 27?                         │ PASS   │ 4.5 │ 4.2  │ 5.0 │ 4.8  │ 4.1  │ 4.52 │ ✓     │
│ What happens if I divide 10 by 0?        │ PASS   │ 4.0 │ 4.1  │ 4.5 │ 4.2  │ 3.8  │ 4.12 │ ✓     │
│ Multi-turn test                          │ PASS   │ 4.2 │ 4.5  │ 4.8 │ 4.1  │ 4.3  │ 4.38 │ ✓     │
└──────────────────────────────────────────┴────────┴─────┴──────┴─────┴──────┴──────┴──────┴───────┘

Summary: 3/3 passed (100.0%) - Average: 4.34/5.0
```

### Detailed View (--output detailed)
```
┌─────────────────────────┬────────┬──────┬────────────────────┬────────────────────┬────────┬────────┬──────────────────────────────┐
│ Test                    │ Status │ Score│ Expected Tools     │ Tools Used         │ Time   │ Errors │ Notes                        │
├─────────────────────────┼────────┼──────┼────────────────────┼────────────────────┼────────┼────────┼──────────────────────────────┤
│ What is 15 + 27?        │ PASS   │ 4.5  │ add                │ add                │ 12ms   │ 0      │ OK                           │
│ What happens if I div...│ PASS   │ 4.1  │ divide             │ divide             │ 8ms    │ 1      │ Handled error correctly      │
│ Multi-turn test         │ PASS   │ 4.4  │ add, multiply      │ add, multiply      │ 23ms   │ 0      │ Tool chaining successful     │
└─────────────────────────┴────────┴──────┴────────────────────┴────────────────────┴────────┴────────┴──────────────────────────────┘

🔧 Tool Execution Details:
• add: Called 2 times, avg 10ms, 100% success rate
• divide: Called 1 time, 8ms, handled error gracefully  
• multiply: Called 1 time, 13ms, 100% success rate

Summary: 3/3 passed (100.0%) - Average: 4.33/5.0
```

## Key Benefits

### For MCP Server Developers
- **🎯 Server-Focused Testing**: Test your server capabilities, not LLM behavior
- **✅ Instant Tool Validation**: Get immediate feedback if wrong tools are called (no LLM needed)
- **🔧 Tool Execution Insights**: See success rates, timing, and error handling
- **🔄 Multi-turn Validation**: Test tool chaining and state management
- **📊 Capability Scoring**: LLM judges server tool performance, ignoring conversation style
- **🛠️ Easy Integration**: Works with any MCP server via FastMCP

### For Development Teams  
- **🚀 CI/CD Integration**: JUnit XML output for automated testing pipelines
- **📈 Progress Tracking**: Monitor improvement over time with consistent scoring
- **🔄 Regression Testing**: Ensure new changes don't break existing functionality
- **⚖️ Model Comparison**: Test across different LLM providers

## Acknowledgments

🙏 **Huge kudos to [mcp-evals](https://github.com/mclenhard/mcp-evals)** - This Python package was heavily inspired by the excellent Node.js implementation by [@mclenhard](https://github.com/mclenhard).

If you're working in a Node.js environment, definitely check out the original [mcp-evals](https://github.com/mclenhard/mcp-evals) project, which also includes GitHub Action integration and monitoring capabilities.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality  
4. Ensure all tests pass
5. Submit a pull request

## License

MIT - see LICENSE file.
