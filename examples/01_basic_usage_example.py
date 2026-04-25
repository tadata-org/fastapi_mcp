import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from examples.shared.apps.items import app  # The FastAPI app
from examples.shared.setup import setup_logging

from fastapi_mcp import FastApiMCP

setup_logging()

# Add MCP server to the FastAPI app
mcp = FastApiMCP(app)

# Mount the MCP server to the FastAPI app
mcp.mount_http()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
