# Connecting a client to the MCP server

## Connecting to the MCP Server using SSE

Once your FastAPI app with MCP integration is running, you can connect to it with any MCP client supporting SSE.

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

## Connecting to the MCP Server using [mcp-remote](https://www.npmjs.com/package/mcp-remote)

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
