from examples.shared.apps import items
from examples.shared.setup import setup_logging

from fastapi import FastAPI
from fastapi_mcp import FastApiMCP

setup_logging()


app = FastAPI()
app.include_router(items.router)

# Add MCP server to the FastAPI app
mcp = FastApiMCP(app)

mcp.mount()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
