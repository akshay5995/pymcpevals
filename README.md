# PyMCPEvals

> **⚠️ Still Under Development** - This project is actively being developed. APIs may change and features are being added. Please use with caution in production environments.

**Evaluation framework for MCP (Model Context Protocol) servers with LLM-based scoring.**

🚀 **Help MCP server developers test their tools by evaluating whether they successfully accomplish user goals.**

## Features

- 📊 **LLM-based Evaluation**: Uses GPT-4, Claude, Gemini and other models to score server responses
- 🔍 **Tool Usage Tracking**: Monitor which tools are called and their success/failure rates  
- ⚡ **Single & Multi-turn Testing**: Support both simple prompts and complex conversation trajectories
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
    threshold: 3.5
    
  - name: "data_insights" 
    description: "Can users get insights from their database?"
    prompt: "Show me my best performing products this month"
    expected_result: "Should query database and provide ranked product list"
    threshold: 4.0

  - name: "multi_step_weather"
    description: "Test multi-step weather analysis"
    turns:
      - role: "user"
        content: "What's the weather like in London?"
        expected_tools: ["get_weather"]
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
- 📊 Detailed scores: accuracy, completeness, relevance, clarity, reasoning
- 🔧 Tool usage summary and execution times
- 💭 LLM judge comments and feedback

## How It Works

PyMCPEvals tests whether your MCP server helps users accomplish their goals:

1. **🔗 Connect** to your MCP server using FastMCP
2. **🔍 Discover** available tools from the server  
3. **⚡ Execute** user prompts and track tool calls
4. **📊 Grade** results using LLM judges (1-5 scale)
5. **📋 Report** scores and tool usage details

## Core Problem Solved

**"Do my MCP tools actually help users accomplish their goals?"**

Instead of just testing if your tools work, PyMCPEvals tests if they're **useful**:

- ✅ Can my weather server help someone plan their day?
- ✅ Does my database server help users get insights?  
- ✅ Can my file system server help users organize documents?

## Evaluation Types

### 1. Single-Prompt Evaluations

Test individual prompts to verify basic functionality:

```yaml
evaluations:
  - name: "basic_weather"
    prompt: "What's the weather in Boston?"
    expected_result: "Should call weather API and return current conditions"
    threshold: 3.0
```

### 2. Multi-Turn Trajectories

Test complex conversations with multiple exchanges:

```yaml
evaluations:
  - name: "weather_comparison"
    turns:
      - role: "user"
        content: "What's the weather in Boston?"
        expected_tools: ["get_weather"]
      - role: "user"  
        content: "How does that compare to New York?"
        expected_tools: ["get_weather"]
    expected_result: "Should provide weather for both cities with comparison"
    threshold: 4.0
```

## Installation

```bash
pip install pymcpevals
```

## Usage

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
    threshold: 3.5
    tags: ["analysis", "data"]

  - name: "multi_step_task"
    description: "Test multi-step problem solving"
    turns:
      - role: "user"
        content: "I need help with my weather data analysis"
        expected_tools: ["get_weather"]
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
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━┓
┃ Name                        ┃ Accuracy ┃ Completeness ┃ Relevance ┃ Clarity ┃ Reasoning ┃ Average ┃ Status ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━┩
│ Weather planning query      │ 4.5      │ 4.0          │ 5.0       │ 4.2     │ 4.1       │ 4.36    │ PASS   │
│ Data analysis task          │ 3.1      │ 3.3          │ 3.8       │ 3.5     │ 3.2       │ 3.38    │ PASS   │
└─────────────────────────────┴──────────┴──────────────┴───────────┴─────────┴───────────┴─────────┴────────┘

Summary: 2/2 passed (100.0%) - Average: 3.87/5.0
```

### Detailed View (--output detailed)

```
MCP Server Evaluation Results

┏━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━┳━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Test                  ┃ Status ┃ Score┃ Tools Used         ┃ Time   ┃ Errors ┃ Notes                        ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━╇━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ Weather planning      │ PASS   │ 4.36 │ weather_api        │ 245ms  │ 0      │ Good weather integration     │
│ Data analysis         │ PASS   │ 3.38 │ query_db, analyze  │ 891ms  │ 0      │ Retrieved and analyzed data  │
└───────────────────────┴────────┴──────┴────────────────────┴────────┴────────┴──────────────────────────────┘

Summary: 2/2 passed (100.0%) - Average: 3.87/5.0
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
```

## Key Benefits

### For MCP Server Developers
- **🔍 Goal-Oriented Testing**: Test if your tools actually help users accomplish tasks
- **⚡ Tool Usage Insights**: See which tools are used and their success rates
- **📊 Detailed Scoring**: 5-dimensional scoring (accuracy, completeness, relevance, clarity, reasoning)
- **🛠️ Easy Integration**: Works with any MCP server via FastMCP

### For Development Teams  
- **🚀 CI/CD Integration**: JUnit XML output for automated testing pipelines
- **📈 Progress Tracking**: Monitor improvement over time with consistent scoring
- **🔄 Regression Testing**: Ensure new changes don't break existing functionality
- **⚖️ Model Comparison**: Test across different LLM providers

## Acknowledgments

🙏 **Huge kudos to [mcp-evals](https://github.com/mclenhard/mcp-evals)** - This Python package was heavily inspired by the excellent Node.js implementation by [@mclenhard](https://github.com/mclenhard). The original mcp-evals project pioneered LLM-based evaluation for MCP servers and established many of the patterns and approaches we've adapted for the Python ecosystem.

If you're working in a Node.js environment, definitely check out the original [mcp-evals](https://github.com/mclenhard/mcp-evals) project, which also includes GitHub Action integration and monitoring capabilities.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality  
4. Ensure all tests pass
5. Submit a pull request

## License

MIT - see LICENSE file.
