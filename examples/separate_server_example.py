from fastapi import FastAPI
import uvicorn

from examples.shared.apps import items
from examples.shared.setup import setup_logging

from fastapi_mcp import FastApiMCP

setup_logging()


app = FastAPI()
app.include_router(items.router)


# Take the FastAPI app only as a source for MCP server generation
mcp = FastApiMCP(app)


# And then mount the MCP server to a separate FastAPI app
mcp_app = FastAPI()
mcp.mount(mcp_app)


# Run the MCP server separately from the original FastAPI app.
# It still works 🚀
# Your original API is **not exposed**, only via the MCP server.
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(mcp_app, host="0.0.0.0", port=8000)
