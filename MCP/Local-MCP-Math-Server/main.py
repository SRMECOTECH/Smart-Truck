from fastmcp import FastMCP
# Create MCP server
mcp = FastMCP("Math MCP Server")


# Addition
@mcp.tool()
def add(a: float, b: float) -> float:
    """
    Add two numbers.
    """
    return a + b


# Subtraction
@mcp.tool()
def subtract(a: float, b: float) -> float:
    """
    Subtract second number from first.
    """
    return a - b


# Multiplication
@mcp.tool()
def multiply(a: float, b: float) -> float:
    """
    Multiply two numbers.
    """
    return a * b


# Division
@mcp.tool()
def divide(a: float, b: float) -> float:
    """
    Divide first number by second.
    """
    if b == 0:
        raise ValueError("Division by zero is not allowed")
    return a / b


# Run server
if __name__ == "__main__":
    mcp.run()