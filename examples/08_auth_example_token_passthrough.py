"""
This example shows how to reject any request without a valid token passed in the Authorization header.

In order to configure the auth header, the config file for the MCP server should looks like this:
```json
{
  "mcpServers": {
    "remote-example": {
      "command": "npx",
      "args": [
        "mcp-remote",
        "http://localhost:8000/mcp",
        "--header",
        "Authorization:${AUTH_HEADER}"
      ]
    },
    "env": {
      "AUTH_HEADER": "Bearer <your-token>"
    }
  }
}
```
"""
from examples.shared.apps.items import app # The FastAPI app
from examples.shared.setup import setup_logging

from fastapi import Depends
from fastapi.security import HTTPBearer

from fastapi_mcp import FastApiMCP, AuthConfig

setup_logging()

# Scheme for the Authorization header
token_auth_scheme = HTTPBearer()

# Create a private endpoint
@app.get("/private")
async def private(token = Depends(token_auth_scheme)):
    return token.credentials

# Create the MCP server with the token auth scheme
mcp = FastApiMCP(
    app,
    name="Protected MCP",
    auth_config=AuthConfig(
        dependencies=[Depends(token_auth_scheme)],
    ),
)

# Mount the MCP server
mcp.mount()


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(app, host="0.0.0.0", port=8000)