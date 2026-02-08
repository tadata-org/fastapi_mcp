from examples.shared.apps.items import app  # The FastAPI app
from examples.shared.setup import setup_logging

from fastapi_mcp import FastApiMCP

setup_logging()

# Add MCP server to the FastAPI app
mcp = FastApiMCP(app)

# Mount the MCP server to the FastAPI app
mcp.mount_http()


if __name__ == "__main__":
    import os
    import uvicorn

    # Set HOST=0.0.0.0 to expose on your network.
    uvicorn.run(app, host=os.getenv("HOST", "127.0.0.1"), port=8000)
