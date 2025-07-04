"""
Example demonstrating WebSocket transport for FastAPI-MCP.

This example shows how to mount an MCP server with WebSocket transport,
which enables bidirectional real-time communication between MCP clients and your FastAPI application.
"""

from fastapi import FastAPI
from fastapi_mcp import FastApiMCP

# Create a simple FastAPI app with some endpoints
app = FastAPI(title="WebSocket MCP Example", description="Example using WebSocket transport for MCP")


# Define some sample endpoints that will become MCP tools
@app.get("/hello")
async def get_hello(name: str = "World"):
    """Say hello to someone."""
    return {"message": f"Hello, {name}!"}


@app.post("/messages")
async def create_message(content: str, author: str = "Anonymous"):
    """Create a new message."""
    return {"id": 1, "content": content, "author": author, "timestamp": "2025-01-01T12:00:00Z"}


@app.get("/status")
async def get_status():
    """Get the application status."""
    return {"status": "healthy", "transport": "websocket"}


# Create MCP server with WebSocket transport
mcp = FastApiMCP(
    app,
    name="WebSocket MCP Example",
    description="An example MCP server using WebSocket transport for real-time communication",
)

# Mount the MCP server with WebSocket transport
mcp.mount(transport="websocket")

if __name__ == "__main__":
    import uvicorn

    print("Starting FastAPI server with WebSocket MCP transport...")
    print("WebSocket MCP endpoint available at: ws://127.0.0.1:8000/mcp")
    print("You can connect MCP clients to this WebSocket endpoint.")

    uvicorn.run(app, host="127.0.0.1", port=8000)
