"""
Example demonstrating both SSE and WebSocket transports for FastAPI-MCP.

This example shows how to mount MCP servers with different transports on the same FastAPI application.
SSE is good for simple request-response patterns, while WebSocket provides real-time bidirectional communication.
"""

from fastapi import FastAPI
from fastapi_mcp import FastApiMCP

# Create a FastAPI app
app = FastAPI(
    title="Multi-Transport MCP Example", description="Example showing both SSE and WebSocket transports for MCP"
)


# Define some sample endpoints
@app.get("/echo")
async def echo_message(message: str):
    """Echo back a message."""
    return {"echo": message, "length": len(message)}


@app.get("/calculate")
async def calculate(operation: str, a: float, b: float):
    """Perform basic arithmetic operations."""
    if operation == "add":
        result = a + b
    elif operation == "subtract":
        result = a - b
    elif operation == "multiply":
        result = a * b
    elif operation == "divide":
        if b == 0:
            raise ValueError("Division by zero is not allowed")
        result = a / b
    else:
        raise ValueError(f"Unsupported operation: {operation}")

    return {"operation": operation, "a": a, "b": b, "result": result}


@app.get("/time")
async def get_current_time():
    """Get current timestamp."""
    from datetime import datetime

    return {"timestamp": datetime.now().isoformat()}


# Create MCP server instances for different transports
sse_mcp = FastApiMCP(
    app,
    name="SSE MCP Server",
    description="MCP server using Server-Sent Events transport",
)

websocket_mcp = FastApiMCP(
    app,
    name="WebSocket MCP Server",
    description="MCP server using WebSocket transport",
)

# Mount both transports on different paths
sse_mcp.mount(mount_path="/mcp-sse", transport="sse")
websocket_mcp.mount(mount_path="/mcp-ws", transport="websocket")

if __name__ == "__main__":
    import uvicorn

    print("Starting FastAPI server with both SSE and WebSocket MCP transports...")
    print("SSE MCP endpoint available at: http://127.0.0.1:8000/mcp-sse")
    print("WebSocket MCP endpoint available at: ws://127.0.0.1:8000/mcp-ws")
    print()
    print("Use SSE for simple request-response patterns.")
    print("Use WebSocket for real-time bidirectional communication.")

    uvicorn.run(app, host="127.0.0.1", port=8000)
