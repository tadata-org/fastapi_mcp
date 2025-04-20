"""
This example shows how to configure the HTTP client timeout for the MCP server.
In case you have API endpoints that take longer than 5 seconds to respond, you can increase the timeout.
"""
import httpx

from examples.shared.items_app import app # The FastAPI app
from fastapi_mcp import FastApiMCP


mcp = FastApiMCP(
    app,
    http_client=httpx.AsyncClient(timeout=20)
)
mcp.mount()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
