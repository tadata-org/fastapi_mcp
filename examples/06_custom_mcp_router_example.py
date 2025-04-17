"""
This example shows how to mount the MCP server to a specific APIRouter, giving a custom mount path.
"""
from examples.shared.apps.items import app
from examples.shared.setup import setup_logging

from fastapi import APIRouter
from fastapi_mcp import FastApiMCP

setup_logging()


router = APIRouter(prefix="/other/route")
app.include_router(router)

mcp = FastApiMCP(app)

# Mount the MCP server to a specific router.
# It will now only be available at `/other/route/mcp`
mcp.mount(router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
