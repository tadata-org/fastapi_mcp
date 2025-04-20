"""
This example shows how to re-register tools if you add endpoints after the MCP server was created.
"""
from examples.shared.items_app import app # The FastAPI app
from fastapi_mcp import FastApiMCP


mcp = FastApiMCP(app) # Add MCP server to the FastAPI app
mcp.mount() # MCP server


# This endpoint will not be registered as a tool, since it was added after the MCP instance was created
@app.get("/new/endpoint/", operation_id="new_endpoint", response_model=dict[str, str])
async def new_endpoint():
    return {"message": "Hello, world!"}


# But if you re-run the setup, the new endpoints will now be exposed.
mcp.setup_server()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
