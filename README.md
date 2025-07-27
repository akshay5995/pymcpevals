# PyMCPEvals

> **⚠️ Still Under Development** - This project is actively being developed. APIs may change and features are being added. Please use with caution in production environments.

**Server-focused evaluation framework for MCP (Model Context Protocol) servers.**

🚀 **Help MCP server developers test their tools by evaluating server capabilities, not LLM conversation patterns.**

## Features

- 🎯 **Server-Focused Evaluation**: Judges MCP server capabilities, not LLM conversation style
- ✅ **Programmatic Tool Validation**: Instantly fail tests when expected tools aren't called
- 🔧 **Tool Execution Tracking**: Monitor tool success/failure, timing, and error handling
- 🔄 **Multi-turn Trajectories**: Test tool chaining and state management across conversation turns
- ⚡ **Fast Fail Validation**: Deterministic checks before expensive LLM evaluation
- 🛠️ **FastMCP Integration**: Seamless connection to MCP servers via stdio or HTTP
- 📋 **Multiple Output Formats**: Table, detailed, JSON, and JUnit XML for CI/CD

## Quick Start

```bash
# Install
pip install pymcpevals

# Create a template configuration
pymcpevals init

# Edit evals.yaml with your server and test cases
# Run evaluations
pymcpevals run evals.yaml
```

## Simple Example

Create `evals.yaml`:

```yaml
model:
  provider: openai
  name: gpt-4

server:
  command: ["python", "my_server.py"]

evaluations:
  - name: "weather_planning"
    description: "Can users plan their day with weather info?"
    prompt: "What should I wear tomorrow in San Francisco?"
    expected_result: "Should provide weather forecast and clothing suggestions"
    expected_tools: ["get_weather"]  # ✅ Validates these tools are called
    threshold: 3.5
    
  - name: "data_insights" 
    description: "Can users get insights from their database?"
    prompt: "Show me my best performing products this month"
    expected_result: "Should query database and provide ranked product list"
    expected_tools: ["query_database", "analyze_data"]  # ✅ Must call these exact tools
    threshold: 4.0

  - name: "multi_step_weather"
    description: "Test multi-step weather analysis"
    turns:
      - role: "user"
        content: "What's the weather like in London?"
        expected_tools: ["get_weather"]  # ✅ Per-turn tool validation
      - role: "user"
        content: "And how about Paris?"
        expected_tools: ["get_weather"]
    expected_result: "Should provide weather for both cities"
    threshold: 4.0
```

Run evaluations:

```bash
pymcpevals run evals.yaml
```

You'll get output showing:
- ✅/❌ Pass/fail status with scores (1-5 scale) 
- 🔧 **Tool validation**: Instant feedback if expected tools weren't called
- 📊 **Server scores**: Tool accuracy, availability, error handling, result formatting
- ⏱️ **Performance metrics**: Tool execution times and success rates
- 💭 **Server-focused feedback**: Comments about tool capabilities, not conversation style

## How It Works

PyMCPEvals focuses on **server capabilities** you can control as a developer:

1. **🔗 Connect** to your MCP server using FastMCP
2. **🔍 Discover** available tools from the server  
3. **⚡ Execute** user prompts and track tool calls
4. **✅ Validate** expected tools are called (instant programmatic check)
5. **🎯 Evaluate** server tool performance (ignores LLM conversation style)
6. **📋 Report** tool execution results and server capabilities

## Core Problem Solved

**"Are my MCP server's tools working correctly and being used as expected?"**

PyMCPEvals separates what you **can control** (server) from what you **cannot** (LLM behavior):

### ✅ **What Server Developers Control (We Test This)**
- Tool implementation correctness
- Tool parameter validation
- Error handling and recovery
- Tool result formatting
- Multi-turn state management

### ❌ **What Server Developers Cannot Control (We Ignore This)**
- LLM conversation patterns
- How LLMs choose to use tools
- LLM response formatting
- Whether LLMs provide intermediate responses

## Evaluation Types

### 1. Single-Prompt Evaluations

Test individual prompts to verify basic functionality:

```yaml
evaluations:
  - name: "basic_weather"
    prompt: "What's the weather in Boston?"
    expected_result: "Should call weather API and return current conditions"
    expected_tools: ["get_weather"]  # Programmatically validates tool usage
    threshold: 3.0
```

**Programmatic Tool Validation**: When `expected_tools` is specified, the test will instantly fail if:
- ❌ Expected tools are not attempted (even if they error)
- ❌ Unexpected tools are called  
- ❌ No tools are called when some were expected

**Server-Focused LLM Evaluation**: The LLM judge focuses only on server capabilities:
- ✅ Were tool results accurate and well-formatted?
- ✅ Did the server provide the necessary tools to complete the task?
- ✅ Did tools execute successfully or handle errors appropriately?
- ❌ Ignores empty content during tool calls (normal behavior)
- ❌ Ignores LLM conversation style and patterns

## Why Server-Focused Evaluation?

Traditional evaluation judges **LLM conversation patterns**, but MCP server developers can't control that. PyMCPEvals focuses on what you **can** control:

```
❌ Old Approach: "LLM didn't provide intermediate responses"
✅ New Approach: "Server tools returned correct results in proper format"

❌ Old Approach: "Conversation flow was awkward" 
✅ New Approach: "Tools chained successfully across turns"

❌ Old Approach: "Response formatting was poor"
✅ New Approach: "Tool error handling worked correctly"
```

**Key Insight**: Empty content during tool calls is **normal** in MCP. PyMCPEvals understands this and evaluates the **server's tool capabilities**, not the LLM's conversation style.

### 2. Multi-Turn Trajectories

Test tool chaining and state management across conversation turns:

```yaml
evaluations:
  - name: "multi_step_calculation"
    description: "Test tool chaining across turns"
    turns:
      - role: "user"
        content: "What is 10 + 5?"
        expected_tools: ["add"]
      - role: "user"  
        content: "Now multiply that result by 2"
        expected_tools: ["multiply"]
    expected_result: "Should chain tools to calculate (10+5)*2 = 30"
    threshold: 4.0
```

**Trajectory Focus**: Tests server capabilities across multiple turns:
- ✅ Can tools be chained together successfully?
- ✅ Does the server maintain state between turns?
- ✅ Do tools provide results in formats that enable chaining?
- ✅ Can the server handle errors and continue the conversation?

## Installation

```bash
pip install pymcpevals
```

## Usage

### Programmatic Usage with Pytest Plugin

PyMCPEvals includes a pytest plugin for easy integration into your test suite:

```python
# conftest.py
import pytest

# Note: pymcpevals plugin is automatically loaded via entry point

@pytest.fixture
def mcp_server():
    return {
        "command": ["python", "my_server.py"],
        "env": {"DEBUG": "false"}
    }

@pytest.fixture
def mcp_model():
    return "claude-3-5-sonnet-20241022"  # or "gpt-4"
```

#### Marker-Based Testing

Use pytest markers for simple test definitions:

```python
import pytest

@pytest.mark.mcp_eval(
    prompt="What is 15 + 27?",
    expected_tools=["add"],
    expected_result="Should use add tool and return 42",
    min_score=4.0
)
async def test_basic_addition_marker(mcp_result):
    """Test runs automatically via marker."""
    assert mcp_result.passed
    assert "42" in mcp_result.server_response
```

#### Direct Evaluator Usage

For more control, use the evaluator directly:

```python
from pymcpevals import MCPEvaluator, assert_evaluation_passed, assert_tools_called

async def test_division_by_zero_direct(mcp_evaluator: MCPEvaluator):
    """Test error handling with direct evaluator."""
    result = await mcp_evaluator.evaluate_prompt(
        prompt="What happens if I divide 10 by 0?",
        expected_tools=["divide"],
        expected_result="Should handle division by zero error gracefully",
        min_score=3.5
    )
    
    assert_evaluation_passed(result)
    assert_tools_called(result, ["divide"])
    
    # Check that error was communicated
    response_lower = result.server_response.lower()
    assert any(word in response_lower for word in ["error", "cannot", "undefined"])
```

#### Multi-Turn Trajectory Testing

Test complex interactions across multiple turns:

```python
from pymcpevals import ConversationTurn

async def test_simple_math_sequence(mcp_evaluator: MCPEvaluator):
    """Test multi-step math sequence."""
    turns = [
        ConversationTurn(
            role="user",
            content="What is 10 + 5?",
            expected_tools=["add"]
        ),
        ConversationTurn(
            role="user", 
            content="Now multiply that result by 2",
            expected_tools=["multiply"]
        )
    ]
    
    result = await mcp_evaluator.evaluate_trajectory(
        turns=turns,
        expected_result="Should calculate (10+5)*2 = 30",
        min_score=4.0
    )
    
    assert_evaluation_passed(result)
    assert_tools_called(result, ["add", "multiply"])
    assert "30" in str(result.conversation_history)
```

#### Custom Assertions

Use built-in assertion helpers for precise validation:

```python
from pymcpevals import (
    assert_evaluation_passed,
    assert_tools_called, 
    assert_min_score,
    assert_no_tool_errors
)

async def test_with_custom_assertions(mcp_evaluator: MCPEvaluator):
    result = await mcp_evaluator.evaluate_prompt("Test prompt")
    
    # Validate overall success
    assert_evaluation_passed(result, "Server should handle basic requests")
    
    # Validate specific tools were called
    assert_tools_called(result, ["expected_tool"], exact=True)
    
    # Validate minimum scores per dimension
    assert_min_score(result, 4.0, dimension="accuracy")
    assert_min_score(result, 3.5)  # overall average
    
    # Validate no tool execution failures
    assert_no_tool_errors(result)
```

#### Running Pytest Tests

```bash
# Run all MCP tests
pytest -m mcp_eval

# Run with API key (use your preferred provider)
export ANTHROPIC_API_KEY="your-key"
pytest examples/test_simple_plugin_example.py

# Run specific test types
pytest -k "marker" -v  # Run marker-based tests
pytest -k "direct" -v  # Run direct evaluator tests

# Run with verbose output
pytest -v -s examples/
```

### CLI Interface

```bash
# Create template config
pymcpevals init evals.yaml

# Run evaluations
pymcpevals run evals.yaml

# Override server for quick testing
pymcpevals run evals.yaml --server "node server.js"

# Override model 
pymcpevals run evals.yaml --model claude-3-opus-20240229 --provider anthropic

# Parallel execution
pymcpevals run evals.yaml --parallel

# Different output formats
pymcpevals run evals.yaml --output table     # Simple table view
pymcpevals run evals.yaml --output detailed  # Detailed with tool info
pymcpevals run evals.yaml --output json      # Full JSON
pymcpevals run evals.yaml --output junit --output-file results.xml  # CI/CD
```

### Simple Interface

```bash
# Direct evaluation: pymcpevals eval <config> <server>
pymcpevals eval evals.yaml server.py
```

## Configuration

### YAML Configuration

```yaml
# Model configuration
model:
  provider: openai     # openai, anthropic, gemini, etc.
  name: gpt-4         # Model name
  # api_key: ${OPENAI_API_KEY}  # Optional, uses env var

# Server configuration  
server:
  # For local servers (stdio transport)
  command: ["python", "my_server.py"]
  env:
    DEBUG: "true"
    
  # For remote servers (HTTP transport)  
  # url: "https://api.example.com/mcp"
  # headers:
  #   Authorization: "Bearer ${API_TOKEN}"

# Evaluations to run
evaluations:
  - name: "basic_functionality"
    description: "Test core server capabilities"  
    prompt: "What can you help me with?"
    expected_result: "Should describe available tools and capabilities"
    threshold: 3.0  # Minimum score to pass (1-5 scale)
    tags: ["basic"]
    
  - name: "specific_task"
    description: "Test domain-specific functionality"
    prompt: "Help me analyze my sales data for trends"
    expected_result: "Should use appropriate tools to analyze sales data"
    expected_tools: ["query_database", "analyze_trends"]  # Programmatic validation
    threshold: 3.5
    tags: ["analysis", "data"]

  - name: "multi_step_task"
    description: "Test multi-step problem solving"
    turns:
      - role: "user"
        content: "I need help with my weather data analysis"
        expected_tools: ["get_weather"]  # Per-turn validation
      - role: "user"
        content: "Can you compare today's weather with last week?"
        expected_tools: ["get_weather", "compare_data"]
    expected_result: "Should gather weather data and perform comparison"
    threshold: 4.0
    tags: ["multi-step"]

# Global settings
timeout: 30.0      # Timeout per evaluation
parallel: false    # Run evaluations in parallel
```

### Environment Variables

```bash
# API keys
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
export GEMINI_API_KEY="..."
```

## Server Transport Support

PyMCPEvals uses [FastMCP](https://github.com/jlowin/fastmcp) for server connections:

### Local Servers (Stdio)

```yaml
server:
  command: ["python", "server.py"]
  env:
    DEBUG: "true"
```

### Remote Servers (HTTP)

```yaml
server:
  url: "https://api.example.com/mcp"  
  headers:
    Authorization: "Bearer ${API_TOKEN}"
    Custom-Header: "value"
```

## Example Output

### Table View (--output table)

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
                                    Evaluation Results                                    
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

## Development

```bash
# Install in development mode
git clone https://github.com/akshay5995/pymcpevals
cd pymcpevals
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black src/
ruff check src/
mypy src/
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
