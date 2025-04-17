"""
This example shows how to run the MCP server and the FastAPI app separately.
"""
from fastapi import FastAPI
import asyncio
import uvicorn

from examples.shared.apps.items import app
from examples.shared.setup import setup_logging

from fastapi_mcp import FastApiMCP

setup_logging()


MCP_SERVER_HOST = "localhost"
MCP_SERVER_PORT = 8000
ITEMS_API_HOST = "localhost"
ITEMS_API_PORT = 8001


# Take the FastAPI app only as a source for MCP server generation
mcp = FastApiMCP(
    app,
    base_url=f"http://{ITEMS_API_HOST}:{ITEMS_API_PORT}",  # Note how the base URL is the **Items API** URL, not the MCP server URL
)

# And then mount the MCP server to a separate FastAPI app
mcp_app = FastAPI()
mcp.mount(mcp_app)


def run_items_app():
    uvicorn.run(app, port=ITEMS_API_PORT)


def run_mcp_app():
    uvicorn.run(mcp_app, port=MCP_SERVER_PORT)


# The MCP server depends on the Items API to be available, so we need to run both.
async def main():
    await asyncio.gather(asyncio.to_thread(run_items_app), asyncio.to_thread(run_mcp_app))


if __name__ == "__main__":
    asyncio.run(main())
