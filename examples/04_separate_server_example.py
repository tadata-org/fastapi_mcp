"""
This example shows how to run the MCP server and the FastAPI app separately.
You can create an MCP server from one FastAPI app, and mount it to a different app.
"""
from fastapi import FastAPI

from examples.shared.apps.items import app
from examples.shared.setup import setup_logging

from fastapi_mcp import FastApiMCP

setup_logging()

MCP_SERVER_HOST = "localhost"
MCP_SERVER_PORT = 8000
ITEMS_API_HOST = "localhost"
ITEMS_API_PORT = 8001


# Take the FastAPI app only as a source for MCP server generation
mcp = FastApiMCP(app)

# Mount the MCP server to a separate FastAPI app
mcp_app = FastAPI()
mcp.mount(mcp_app)

# Run the MCP server separately from the original FastAPI app.
# It still works 🚀
# Your original API is **not exposed**, only via the MCP server.
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(mcp_app, host="0.0.0.0", port=8000)