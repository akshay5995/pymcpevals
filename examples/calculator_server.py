#!/usr/bin/env python3
"""
Simple calculator MCP server for demonstration purposes.
Provides basic arithmetic operations.
"""

from fastmcp import FastMCP


def create_calculator_server():
    """Create a calculator MCP server with basic arithmetic operations."""
    server = FastMCP("Calculator")

    @server.tool
    def add(a: float, b: float) -> float:
        """Add two numbers together."""
        return a + b

    @server.tool
    def subtract(a: float, b: float) -> float:
        """Subtract second number from first number."""
        return a - b

    @server.tool
    def multiply(a: float, b: float) -> float:
        """Multiply two numbers."""
        return a * b

    @server.tool
    def divide(a: float, b: float) -> float:
        """Divide first number by second number."""
        if b == 0:
            raise ValueError("Cannot divide by zero")
        return a / b

    @server.tool
    def power(base: float, exponent: float) -> float:
        """Raise base to the power of exponent."""
        return base**exponent

    @server.tool
    def square_root(n: float) -> float:
        """Calculate square root of a number."""
        if n < 0:
            raise ValueError("Cannot calculate square root of negative number")
        return n**0.5

    return server


if __name__ == "__main__":
    # Run the server
    server = create_calculator_server()
    server.run()
    # if you want to use the http transport, uncomment the following line
    # server.run(transport="http", port=3001)
