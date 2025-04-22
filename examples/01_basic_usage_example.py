from examples.shared.apps.items import app # The FastAPI app
from examples.shared.setup import setup_logging

from fastapi_mcp import FastApiMCP

setup_logging()

# Add MCP server to the FastAPI app
mcp = FastApiMCP(app)

# Mount the MCP server to the FastAPI app
mcp.mount()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)