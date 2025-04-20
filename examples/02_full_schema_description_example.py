
"""
This example shows how to describe the full response schema instead of just a response example.
"""
from examples.shared.items_app import app # The FastAPI app
from fastapi_mcp import FastApiMCP

mcp = FastApiMCP(
    app,
    describe_full_response_schema=True,  # Include all possible response schemas in tool descriptions
    describe_all_responses=True,  # Include full JSON schema in tool descriptions
)
mcp.mount()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
