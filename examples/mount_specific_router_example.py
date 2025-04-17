from examples.shared.apps import items
from examples.shared.setup import setup_logging

from fastapi import FastAPI, APIRouter
from fastapi_mcp import FastApiMCP

setup_logging()


other_router = APIRouter(prefix="/other/route")

app = FastAPI()
app.include_router(items.router)
app.include_router(other_router)

mcp = FastApiMCP(
    app,
    name="Item API MCP",
    description="MCP server for the Item API",
    base_url="http://localhost:8000",
)

# Mount the MCP server to a specific router.
# It will now only be available at `/other/route/mcp`
mcp.mount(other_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(items.router, host="0.0.0.0", port=8000)
