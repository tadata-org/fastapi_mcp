from fastapi import FastAPI
from fastapi_mcp import add_mcp_server
from fastapi_mcp.documentation_tools import create_documentation_tools

# Create a very basic FastAPI app
app = FastAPI(
    title="Basic API",
    description="A basic API with integrated MCP server",
    version="0.1.0",
)

@app.get("/")
async def root():
    return {"message": "Hello World"}

@app.get("/greet/{name}")
async def greet(name: str):
    return {"message": f"Hello, {name}!"}

# Add MCP server to the FastAPI app
mcp_server = add_mcp_server(
    app,
    mount_path="/mcp",
    name="Basic API MCP",
    description="MCP server for the Basic API",
    base_url="http://localhost:8000",
)

# Create documentation tools for the MCP server
# Based on a single file
create_documentation_tools(mcp_server, "README.md")
# Based on a list of files
# create_documentation_tools(mcp_server, ["README.md", "README2.md", "llms.txt"])
# Based on a directory
# create_documentation_tools(mcp_server, "docs")

# Run the server if this file is executed directly
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
