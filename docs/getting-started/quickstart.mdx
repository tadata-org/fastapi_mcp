---
title: Quickstart
icon: rocket
---

This guide will help you quickly run your first MCP server using FastAPI-MCP.

If you haven't already installed FastAPI-MCP, follow the [installation instructions](/getting-started/installation).

## Creating a basic MCP server

To create a basic MCP server, import or create a FastAPI app, wrap it with the `FastApiMCP` class and mount the MCP to your existing application:

```python {2, 8, 11}
from fastapi import FastAPI
from fastapi_mcp import FastApiMCP

# Create (or import) a FastAPI app
app = FastAPI()

# Create an MCP server based on this app
mcp = FastApiMCP(app)

# Mount the MCP server directly to your app
mcp.mount()
```

For more usage examples, see [Examples](https://github.com/tadata-org/fastapi_mcp/tree/main/examples) section in the project.

## Running the server

By running your FastAPI, your MCP will run at `https://app.base.url/mcp`. 

For example, by using uvicorn, add to your code:
```python {9-11}
from fastapi import FastAPI
from fastapi_mcp import FastApiMCP

app = FastAPI()

mcp = FastApiMCP(app)
mcp.mount()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```
and run the server using `python fastapi_mcp_server.py`, which will serve you the MCP at `http://localhost:8000/mcp`.

## Connecting a client to the MCP server

Once your FastAPI app with MCP integration is running, you would want to connect it to an MCP client. 

### Connecting to the MCP Server using SSE

For any MCP client supporting SSE, you will simply need to provide the MCP url.

All the most popular MCP clients (Claude Desktop, Cursor & Windsurf) use the following config format:

```json
{
  "mcpServers": {
    "fastapi-mcp": {
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

### Connecting to the MCP Server using [mcp-remote](https://www.npmjs.com/package/mcp-remote)

If you want to support authentication, or your MCP client does not support SSE, we recommend using `mcp-remote` as a bridge.

```json
{
  "mcpServers": {
    "fastapi-mcp": {
      "command": "npx",
      "args": [
        "mcp-remote",
        "http://localhost:8000/mcp",
        "8080"  // Optional port number. Necessary if you want your OAuth to work and you don't have dynamic client registration.
      ]
    }
  }
}
```



