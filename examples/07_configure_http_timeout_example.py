"""
This example shows how to configure the HTTP client timeout for the MCP server.
In case you have API endpoints that take longer than 5 seconds to respond, you can increase the timeout.
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from examples.shared.apps.items import app  # The FastAPI app
from examples.shared.setup import setup_logging

import httpx

from fastapi_mcp import FastApiMCP

setup_logging()


mcp = FastApiMCP(app, http_client=httpx.AsyncClient(timeout=20))
mcp.mount_http()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
