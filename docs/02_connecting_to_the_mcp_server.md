# Connecting a client to the MCP server

## Connecting to the MCP Server using SSE

Once your FastAPI app with MCP integration is running, you can connect to it with any MCP client supporting SSE, such as Cursor:

1. Run your application.
2. In Cursor -> Settings -> MCP, use the URL of your MCP server endpoint (e.g., `http://localhost:8000/mcp`) as sse.
3. Cursor will discover all available tools and resources automatically.

## Connecting to the MCP Server using [mcp-proxy stdio](https://github.com/sparfenyuk/mcp-proxy?tab=readme-ov-file#1-stdio-to-sse)

If your MCP client does not support SSE, for example Claude Desktop:

1. Run your application.
2. Install [mcp-proxy](https://github.com/sparfenyuk/mcp-proxy?tab=readme-ov-file#installing-via-pypi), for example: `uv tool install mcp-proxy`.
3. Add in Claude Desktop MCP config file (`claude_desktop_config.json`):

On Windows:
```json
{
  "mcpServers": {
    "my-api-mcp-proxy": {
        "command": "mcp-proxy",
        "args": ["http://127.0.0.1:8000/mcp"]
    }
  }
}
```
On MacOS:
```json
{
  "mcpServers": {
    "my-api-mcp-proxy": {
        "command": "/Full/Path/To/Your/Executable/mcp-proxy",
        "args": ["http://127.0.0.1:8000/mcp"]
    }
  }
}
```
Find the path to mcp-proxy by running in Terminal: `which mcp-proxy`.

4. Claude Desktop will discover all available tools and resources automatically.
