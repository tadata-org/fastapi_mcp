from examples.shared.apps import items
from examples.shared.setup import setup_logging

from fastapi import FastAPI
from fastapi_mcp import FastApiMCP

setup_logging()


app = FastAPI()
app.include_router(items.router)


# Add MCP server to the FastAPI app
mcp = FastApiMCP(app)


# MCP server
mcp.mount()


# This endpoint will not be registered as a tool, since it was added after the MCP instance was created
@items.router.get("/new/endpoint/", operation_id="new_endpoint", response_model=dict[str, str])
async def new_endpoint():
    return {"message": "Hello, world!"}


# But if you re-run the setup, the new endpoints will now be exposed.
mcp.setup_server()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(items.router, host="0.0.0.0", port=8000)
