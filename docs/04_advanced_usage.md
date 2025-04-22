## Advanced Usage

FastAPI-MCP provides several ways to customize and control how your MCP server is created and configured. Here are some advanced usage patterns:

### Customizing Schema Description

```python
from fastapi import FastAPI
from fastapi_mcp import FastApiMCP

app = FastAPI()

mcp = FastApiMCP(
    app,
    name="My API MCP",
    describe_all_responses=True,     # Include all possible response schemas in tool descriptions
    describe_full_response_schema=True  # Include full JSON schema in tool descriptions
)

mcp.mount()
```

### Customizing Exposed Endpoints

You can control which FastAPI endpoints are exposed as MCP tools using Open API operation IDs or tags:

```python
from fastapi import FastAPI
from fastapi_mcp import FastApiMCP

app = FastAPI()

# Only include specific operations
mcp = FastApiMCP(
    app,
    include_operations=["get_user", "create_user"]
)

# Exclude specific operations
mcp = FastApiMCP(
    app,
    exclude_operations=["delete_user"]
)

# Only include operations with specific tags
mcp = FastApiMCP(
    app,
    include_tags=["users", "public"]
)

# Exclude operations with specific tags
mcp = FastApiMCP(
    app,
    exclude_tags=["admin", "internal"]
)

# Combine operation IDs and tags (include mode)
mcp = FastApiMCP(
    app,
    include_operations=["user_login"],
    include_tags=["public"]
)

mcp.mount()
```

Notes on filtering:
- You cannot use both `include_operations` and `exclude_operations` at the same time
- You cannot use both `include_tags` and `exclude_tags` at the same time
- You can combine operation filtering with tag filtering (e.g., use `include_operations` with `include_tags`)
- When combining filters, a greedy approach will be taken. Endpoints matching either criteria will be included

### Deploying Separately from Original FastAPI App

You are not limited to serving the MCP on the same FastAPI app from which it was created.

You can create an MCP server from one FastAPI app, and mount it to a different app:

```python
from fastapi import FastAPI
from fastapi_mcp import FastApiMCP

# Your API app
api_app = FastAPI()
# ... define your API endpoints on api_app ...

# A separate app for the MCP server
mcp_app = FastAPI()

# Create MCP server from the API app
mcp = FastApiMCP(api_app)

# Mount the MCP server to the separate app
mcp.mount(mcp_app)

# Now you can run both apps separately:
# uvicorn main:api_app --host api-host --port 8001
# uvicorn main:mcp_app --host mcp-host --port 8000
```

### Adding Endpoints After MCP Server Creation

If you add endpoints to your FastAPI app after creating the MCP server, you'll need to refresh the server to include them:

```python
from fastapi import FastAPI
from fastapi_mcp import FastApiMCP

app = FastAPI()
# ... define initial endpoints ...

# Create MCP server
mcp = FastApiMCP(app)
mcp.mount()

# Add new endpoints after MCP server creation
@app.get("/new/endpoint/", operation_id="new_endpoint")
async def new_endpoint():
    return {"message": "Hello, world!"}

# Refresh the MCP server to include the new endpoint
mcp.setup_server()
```

### Communication with the FastAPI App

FastAPI-MCP uses ASGI transport by default, which means it communicates directly with your FastAPI app without making HTTP requests. This is more efficient and doesn't require a base URL.

It's not even necessary that the FastAPI server will run. See the examples folder for more.

If you need to specify a custom base URL or use a different transport method, you can provide your own `httpx.AsyncClient`:

```python
import httpx
from fastapi import FastAPI
from fastapi_mcp import FastApiMCP

app = FastAPI()

# Use a custom HTTP client with a specific base URL
custom_client = httpx.AsyncClient(
    base_url="https://api.example.com",
    timeout=30.0
)

mcp = FastApiMCP(
    app,
    http_client=custom_client
)

mcp.mount()
```
