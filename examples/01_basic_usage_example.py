
"""
This example shows a simple MCP server created from a FastAPI app.
"""
from examples.shared.items_app import app # The FastAPI app
from fastapi_mcp import FastApiMCP

# Add MCP server to the FastAPI app
mcp = FastApiMCP(
    app,
    name="Item API MCP",
    description="MCP server for the Item API",
)

# Mount the MCP server to the FastAPI app
mcp.mount()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
