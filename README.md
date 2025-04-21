<p align="center"><a href="https://github.com/tadata-org/fastapi_mcp"><img src="https://github.com/user-attachments/assets/7e44e98b-a0ba-4aff-a68a-4ffee3a6189c" alt="fastapi-to-mcp" height=100/></a></p>
<h1 align="center">FastAPI-MCP</h1>
<p align="center">Expose your FastAPI endpoints as Model Context Protocol (MCP) tools, with Auth!</p>
<div align="center">

[![PyPI version](https://badge.fury.io/py/fastapi-mcp.svg)](https://pypi.org/project/fastapi-mcp/)
[![Python Versions](https://img.shields.io/pypi/pyversions/fastapi-mcp.svg)](https://pypi.org/project/fastapi-mcp/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009485.svg?logo=fastapi&logoColor=white)](#)
![](https://badge.mcpx.dev?type=dev 'MCP Dev')
[![CI](https://github.com/tadata-org/fastapi_mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/tadata-org/fastapi_mcp/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/tadata-org/fastapi_mcp/branch/main/graph/badge.svg)](https://codecov.io/gh/tadata-org/fastapi_mcp)

</div>

<p align="center"><a href="https://github.com/tadata-org/fastapi_mcp"><img src="https://github.com/user-attachments/assets/b205adc6-28c0-4e3c-a68b-9c1a80eb7d0c" alt="fastapi-mcp-usage" height="400"/></a></p>


## Features

- **FastAPI-native:** Not just another OpenAPI -> MCP converter

- **Authentication** built in, using your existing FastAPI dependencies!

- **Zero/Minimal configuration** required - just point it at your FastAPI app and it works

- **Preserving schemas** of your request models and response models

- **Preserve documentation** of all your endpoints, just as it is in Swagger

- **Flexible deployment** - Mount your MCP server to the same app, or deploy separately

- **ASGI transport** - Uses FastAPI's ASGI interface directly for efficient communication


## Installation

We recommend using [uv](https://docs.astral.sh/uv/), a fast Python package installer:

```bash
uv add fastapi-mcp
```

Alternatively, you can install with pip:

```bash
pip install fastapi-mcp
```

## Basic Usage

The simplest way to use FastAPI-MCP is to add an MCP server directly to your FastAPI application:

```python
from fastapi import FastAPI
from fastapi_mcp import FastApiMCP

app = FastAPI()

mcp = FastApiMCP(app)

# Mount the MCP server directly to your FastAPI app
mcp.mount()
```

That's it! Your auto-generated MCP server is now available at `https://app.base.url/mcp`.

# Authentication and Authorization

FastAPI-MCP supports authentication and authorization using your existing FastAPI dependencies.

It also supports the full OAuth 2 flow, compliant with [MCP Spec 2025-03-26](https://modelcontextprotocol.io/specification/2025-03-26/basic/authorization).

It's worth noting that most MCP clients currently do not support the latest MCP spec, so for our examples we might use a bridge client such as `npx mcp-remote`. We recommend you use it as well, and we'll show our examples using it.

## Basic Token Passthrough

If you just want to be able to pass a valid authorization header, without supporting a full authentication flow, you don't need to do anything special.

You just need to make sure your MCP client is sending it:

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

This is enough to pass the authorization header to your FastAPI endpoints.

Optionally, if you want your MCP server to reject requests without an authorization header, you can add a dependency:

```python
from fastapi import Depends
from fastapi_mcp import FastApiMCP, AuthConfig

mcp = FastApiMCP(
    app,
    name="Protected MCP",
    auth_config=AuthConfig(
        dependencies=[Depends(verify_auth)],
    ),
)
mcp.mount()
```

## OAuth Flow

FastAPI-MCP supports the full OAuth 2 flow, compliant with [MCP Spec 2025-03-26](https://modelcontextprotocol.io/specification/2025-03-26/basic/authorization).

It would look something like this:

```python
from fastapi import Depends
from fastapi_mcp import FastApiMCP, AuthConfig

mcp = FastApiMCP(
    app,
    name="MCP With OAuth",
    auth_config=AuthConfig(
        issuer=f"https://auth.example.com/",
        authorize_url=f"https://auth.example.com/authorize",
        oauth_metadata_url=f"https://auth.example.com/.well-known/oauth-authorization-server",
        audience="my-audience",
        client_id="my-client-id",
        client_secret="my-client-secret",
        dependencies=[Depends(verify_auth)],
        setup_proxies=True,
    ),
)

mcp.mount()
```

And you can call it like:

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

You can use it with any OAuth provider that supports the OAuth 2 spec. See explanation on [AuthConfig](#authconfig-explained) for more details.

## Custom OAuth Metadata

If you already have a properly configured OAuth server that works with MCP clients, or if you want full control over the metadata, you can provide your own OAuth metadata directly:

```python
from fastapi import Depends
from fastapi_mcp import FastApiMCP, AuthConfig

mcp = FastApiMCP(
    app,
    name="MCP With Custom OAuth",
    auth_config=AuthConfig(
        # Provide your own complete OAuth metadata
        custom_oauth_metadata={
            "issuer": "https://auth.example.com",
            "authorization_endpoint": "https://auth.example.com/authorize",
            "token_endpoint": "https://auth.example.com/token",
            "registration_endpoint": "https://auth.example.com/register",
            "scopes_supported": ["openid", "profile", "email"],
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code"],
            "token_endpoint_auth_methods_supported": ["none"],
            "code_challenge_methods_supported": ["S256"]
        },

        # Your auth checking dependency
        dependencies=[Depends(verify_auth)],
    ),
)

mcp.mount()
```

This approach gives you complete control over the OAuth metadata and is useful when:
- You have a fully MCP-compliant OAuth server already configured
- You need to customize the OAuth flow beyond what the proxy approach offers
- You're using a custom or specialized OAuth implementation

For this to work, you have to make sure mcp-remote is running [on a fixed port](#add-a-fixed-port-to-mcp-remote), for example `8080`, and then configure the callback URL to `http://127.0.0.1:8080/oauth/callback` in your OAuth provider.

## Working Example with Auth0

For a complete working example of OAuth integration with Auth0, check out the [auth_example_auth0.py](examples/auth_example_auth0.py) in the examples folder. This example demonstrates the simple case of using Auth0 as an OAuth provider, with a working example of the OAuth flow.

For it to work, you need an .env file in the root of the project with the following variables:

```
AUTH0_DOMAIN=your-tenant.auth0.com
AUTH0_AUDIENCE=https://your-tenant.auth0.com/api/v2/
AUTH0_CLIENT_ID=your-client-id
AUTH0_CLIENT_SECRET=your-client-secret
```

You also need to make sure to configure callback URLs properly in your Auth0 dashboard.

## AuthConfig Explained

### `setup_proxies=True`

Most OAuth providers need some adaptation to work with MCP clients. This is where `setup_proxies=True` comes in - it creates proxy endpoints that make your OAuth provider compatible with MCP clients:

```python
mcp = FastApiMCP(
    app,
    auth_config=AuthConfig(
        # Your OAuth provider information
        issuer="https://auth.example.com",
        authorize_url="https://auth.example.com/authorize",
        oauth_metadata_url="https://auth.example.com/.well-known/oauth-authorization-server",

        # Credentials registered with your OAuth provider
        client_id="your-client-id",
        client_secret="your-client-secret",

        # Recommended, since some clients don't specify them
        audience="your-api-audience",
        default_scope="openid profile email",

        # Your auth checking dependency
        dependencies=[Depends(verify_auth)],

        # Create compatibility proxies - usually needed!
        setup_proxies=True,
    ),
)
```

You also need to make sure to configure callback URLs properly in your OAuth provider. With mcp-remote for example, you have to [use a fixed port](#add-a-fixed-port-to-mcp-remote).

### Why Use Proxies?

Proxies solve several problems:

1. **Missing registration endpoints**: The MCP spec expects OAuth providers to support dynamic client registration, but many don't. The `setup_fake_dynamic_registration=True` option creates a compatible endpoint that just returns a static client ID and secret.

2. **Scope handling**: Some MCP clients don't properly request scopes, so our proxy adds the necessary scopes for you.

3. **Audience requirements**: Some OAuth providers require an audience parameter that MCP clients don't always provide. The proxy adds this automatically.

### Add a fixed port to mcp-remote

```json
{
  "mcpServers": {
    "example": {
      "command": "npx",
      "args": [
        "mcp-remote",
        "http://localhost:8000/mcp",
        "8080"
      ]
    }
  }
}
```

Normally, mcp-remote will start on a random port, making it impossible to configure the OAuth provider's callback URL properly.


You have to make sure mcp-remote is running on a fixed port, for example `8080`, and then configure the callback URL to `http://127.0.0.1:8080/oauth/callback` in your OAuth provider.

## Tool Naming

FastAPI-MCP uses the `operation_id` from your FastAPI routes as the MCP tool names. When you don't specify an `operation_id`, FastAPI auto-generates one, but these can be cryptic.

Compare these two endpoint definitions:

```python
# Auto-generated operation_id (something like "read_user_users__user_id__get")
@app.get("/users/{user_id}")
async def read_user(user_id: int):
    return {"user_id": user_id}

# Explicit operation_id (tool will be named "get_user_info")
@app.get("/users/{user_id}", operation_id="get_user_info")
async def read_user(user_id: int):
    return {"user_id": user_id}
```

For clearer, more intuitive tool names, we recommend adding explicit `operation_id` parameters to your FastAPI route definitions.

To find out more, read FastAPI's official docs about [advanced config of path operations.](https://fastapi.tiangolo.com/advanced/path-operation-advanced-configuration/)

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

## Examples

See the [examples](examples) directory for complete examples.

## Connecting to the MCP Server using SSE

Once your FastAPI app with MCP integration is running, you can connect to it with any MCP client supporting SSE, such as Cursor:

1. Run your application.

2. In Cursor -> Settings -> MCP, use the URL of your MCP server endpoint (e.g., `http://localhost:8000/mcp`) as sse.

3. Cursor will discover all available tools and resources automatically.

## Connecting to the MCP Server using [mcp-remote](https://www.npmjs.com/package/mcp-remote)

If your MCP client does not support SSE, or, if you want want to support authentication, we recommend using `mcp-remote` as a bridge.

All the most popular MCP clients (Claude Desktop, Cursor & Windsurf) use the following config format:

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

## FastAPI-first Approach

FastAPI-MCP is designed as a native extension of FastAPI, not just a converter that generates MCP tools from your API. This approach offers several key advantages:

- **Native dependencies**: Secure your MCP endpoints using familiar FastAPI `Depends()` for authentication and authorization

- **ASGI transport**: Communicates directly with your FastAPI app using its ASGI interface, eliminating the need for HTTP calls from the MCP to your API

- **Unified infrastructure**: Your FastAPI app doesn't need to run separately from the MCP server (though [separate deployment](#deploying-separately-from-original-fastapi-app) is also supported)

This design philosophy ensures minimum friction when adding MCP capabilities to your existing FastAPI services.

## Development and Contributing

Thank you for considering contributing to FastAPI-MCP! We encourage the community to post Issues and Pull Requests.

Before you get started, please see our [Contribution Guide](CONTRIBUTING.md).

## Community

Join [MCParty Slack community](https://join.slack.com/t/themcparty/shared_invite/zt-30yxr1zdi-2FG~XjBA0xIgYSYuKe7~Xg) to connect with other MCP enthusiasts, ask questions, and share your experiences with FastAPI-MCP.

## Requirements

- Python 3.10+ (Recommended 3.12)
- uv

## License

MIT License. Copyright (c) 2024 Tadata Inc.
