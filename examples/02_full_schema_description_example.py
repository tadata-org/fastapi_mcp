"""
This example shows how to describe the full response schema instead of just a response example.
"""

from examples.shared.apps.items import app  # The FastAPI app
from examples.shared.setup import setup_logging

from fastapi_mcp import FastApiMCP

setup_logging()

# Add MCP server to the FastAPI app
mcp = FastApiMCP(
    app,
    name="Item API MCP",
    description="MCP server for the Item API",
    describe_full_response_schema=True,  # Describe the full response JSON-schema instead of just a response example
    describe_all_responses=True,  # Describe all the possible responses instead of just the success (2XX) response
)

mcp.mount_http()

if __name__ == "__main__":
    import os
    import uvicorn

    # Set HOST=0.0.0.0 to expose on your network.
    uvicorn.run(app, host=os.getenv("HOST", "127.0.0.1"), port=8000)
