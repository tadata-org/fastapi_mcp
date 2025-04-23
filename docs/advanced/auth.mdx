---
title: Authentication & Authorization
icon: key
---

FastAPI-MCP supports authentication and authorization using your existing FastAPI dependencies.

It also supports the full OAuth 2 flow, compliant with [MCP Spec 2025-03-26](https://modelcontextprotocol.io/specification/2025-03-26/basic/authorization).

It's worth noting that most MCP clients currently do not support the latest MCP spec, so for our examples we might use a bridge client such as `npx mcp-remote`. We recommend you use it as well, and we'll show our examples using it.

## Basic Token Passthrough

If you just want to be able to pass a valid authorization header, without supporting a full authentication flow, you don't need to do anything special.

You just need to make sure your MCP client is sending it:

```json {8-9, 13}
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

```python {1-2, 7-9}
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

For a complete working example of authorization header, check out the [Token Passthrough Example](https://github.com/tadata-org/fastapi_mcp/blob/main/examples/08_auth_example_token_passthrough.py) in the examples folder.

## OAuth Flow

FastAPI-MCP supports the full OAuth 2 flow, compliant with [MCP Spec 2025-03-26](https://modelcontextprotocol.io/specification/2025-03-26/basic/authorization).

It would look something like this:

```python {7-16}
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

```python {9, 22}
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

For a complete working example of OAuth integration with Auth0, check out the [Auth0 Example](https://github.com/tadata-org/fastapi_mcp/blob/main/examples/09_auth_example_auth0.py) in the examples folder. This example demonstrates the simple case of using Auth0 as an OAuth provider, with a working example of the OAuth flow.

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

1.  **Missing registration endpoints**:  
    The MCP spec expects OAuth providers to support [dynamic client registration (RFC 7591)](https://datatracker.ietf.org/doc/html/rfc7591), but many don't.  
    Furthermore, dynamic client registration is probably overkill for most use cases.  
    The `setup_fake_dynamic_registration` option (True by default) creates a compatible endpoint that just returns a static client ID and secret.

2.  **Scope handling**:  
    Some MCP clients don't properly request scopes, so our proxy adds the necessary scopes for you.

3.  **Audience requirements**:  
    Some OAuth providers require an audience parameter that MCP clients don't always provide. The proxy adds this automatically.

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
