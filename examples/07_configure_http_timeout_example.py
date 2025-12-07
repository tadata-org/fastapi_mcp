"""
This example shows how to configure the HTTP client timeout for the MCP server.
In case you have API endpoints that take longer than 10 seconds to respond, you can increase the timeout.
"""

from examples.shared.apps.items import app  # The FastAPI app
from examples.shared.setup import setup_logging

import httpx

from fastapi_mcp import FastApiMCP

setup_logging()


mcp = FastApiMCP(
    app,
    http_client=httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://apiserver",
        timeout=60.0,
    ),
)
mcp.mount_http()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
