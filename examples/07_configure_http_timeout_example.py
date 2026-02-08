"""
This example shows how to configure the HTTP client timeout for the MCP server.
In case you have API endpoints that take longer than 5 seconds to respond, you can increase the timeout.
"""

from examples.shared.apps.items import app  # The FastAPI app
from examples.shared.setup import setup_logging

import httpx

from fastapi_mcp import FastApiMCP

setup_logging()


mcp = FastApiMCP(app, http_client=httpx.AsyncClient(timeout=20))
mcp.mount_http()


if __name__ == "__main__":
    import os
    import uvicorn

    # Set HOST=0.0.0.0 to expose on your network.
    uvicorn.run(app, host=os.getenv("HOST", "127.0.0.1"), port=8000)
