<p align="center"><a href="https://github.com/tadata-org/fastapi_mcp"><img src="https://github.com/user-attachments/assets/7e44e98b-a0ba-4aff-a68a-4ffee3a6189c" alt="fastapi-to-mcp" height=100/></a></p>
<h1 align="center">FastAPI-MCP</h1>
<p align="center">Expose your FastAPI endpoints as Model Context Protocol (MCP) tools, with Auth!</p>
<div align="center">

[![PyPI version](https://img.shields.io/pypi/v/fastapi-mcp?color=%2334D058&label=pypi%20package)](https://pypi.org/project/fastapi-mcp/)
[![Python Versions](https://img.shields.io/pypi/pyversions/fastapi-mcp.svg)](https://pypi.org/project/fastapi-mcp/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009485.svg?logo=fastapi&logoColor=white)](#)
[![CI](https://github.com/tadata-org/fastapi_mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/tadata-org/fastapi_mcp/actions/workflows/ci.yml)
[![Coverage](https://codecov.io/gh/tadata-org/fastapi_mcp/branch/main/graph/badge.svg)](https://codecov.io/gh/tadata-org/fastapi_mcp)

</div>


<p align="center"><a href="https://github.com/tadata-org/fastapi_mcp"><img src="https://github.com/user-attachments/assets/b205adc6-28c0-4e3c-a68b-9c1a80eb7d0c" alt="fastapi-mcp-usage" height="400"/></a></p>


## Features

- **Authentication** built in, using your existing FastAPI dependencies!

- **FastAPI-native:** Not just another OpenAPI -> MCP converter

- **Zero/Minimal configuration** required - just point it at your FastAPI app and it works

- **Preserving schemas** of your request models and response models

- **Preserve documentation** of all your endpoints, just as it is in Swagger

- **Flexible deployment** - Mount your MCP server to the same app, or deploy separately

- **ASGI transport** - Uses FastAPI's ASGI interface directly for efficient communication


## Hosted Solution

If you prefer a managed hosted solution check out [tadata.com](https://tadata.com).

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

## MCP Prompts Support

FastAPI-MCP automatically generates helpful prompts for each of your API endpoints and supports custom prompts for enhanced AI interactions.

### Auto-Generated Tool Prompts

By default, every FastAPI endpoint automatically gets a corresponding prompt (named `use_{endpoint_name}`) that provides AI models with guidance on how to use that specific tool:

```python
from fastapi import FastAPI
from fastapi_mcp import FastApiMCP

app = FastAPI()

@app.post("/create_item")
async def create_item(name: str, price: float):
    """Create a new item in the inventory."""
    return {"name": name, "price": price}

# Auto-generation is enabled by default
mcp = FastApiMCP(app, auto_generate_prompts=True)  # This is the default
mcp.mount()

# Automatically creates a prompt named "use_create_item" with guidance
# on how to use the create_item tool effectively
```

#### Controlling Auto-Generation

You have full control over prompt auto-generation:

```python
# Option 1: Auto-generated prompts only (default)
mcp = FastApiMCP(app, auto_generate_prompts=True)

# Option 2: Disable auto-generation, use only custom prompts  
mcp = FastApiMCP(app, auto_generate_prompts=False)

# Option 3: Mixed approach - auto-generated + custom overrides
mcp = FastApiMCP(app, auto_generate_prompts=True)
# Then add custom prompts or override auto-generated ones
```

### Custom Prompt Overrides

You can override auto-generated prompts or create entirely custom ones:

```python
# Override the auto-generated prompt for better guidance
@mcp.prompt("use_create_item", title="Item Creation Guide")
def create_item_guide():
    return PromptMessage(
        role="user",
        content=TextContent(
            text="""Use the create_item tool to add items to inventory.

Best Practices:
- Use descriptive names (e.g., "Wireless Bluetooth Mouse")
- Set realistic prices in decimal format (e.g., 29.99)
- Include detailed descriptions for better categorization

This tool will validate inputs and return the created item details."""
        )
    )
```

### API Documentation Prompts

Create dynamic prompts that help with API understanding:

```python
@mcp.prompt("api_documentation")
def api_docs_prompt(endpoint_path: Optional[str] = None):
    if endpoint_path:
        return PromptMessage(
            role="user",
            content=TextContent(
                text=f"Please provide comprehensive documentation for {endpoint_path}, including parameters, examples, and use cases."
            )
        )
    else:
        # Generate overview of all endpoints
        return PromptMessage(
            role="user", 
            content=TextContent(text="Please explain this API's purpose and how to use its endpoints effectively.")
        )
```

### Welcome and Troubleshooting Prompts

```python
@mcp.prompt("welcome")
def welcome_prompt():
    return PromptMessage(
        role="user",
        content=TextContent(text="Please provide a friendly welcome message for API users.")
    )

@mcp.prompt("troubleshoot")  
async def troubleshoot_prompt(error_message: str, endpoint: Optional[str] = None):
    return PromptMessage(
        role="user",
        content=TextContent(
            text=f"Help troubleshoot this API issue: {error_message}" + 
                 (f" on endpoint {endpoint}" if endpoint else "")
        )
    )
```

## Documentation, Examples and Advanced Usage

FastAPI-MCP provides [comprehensive documentation](https://fastapi-mcp.tadata.com/). Additionaly, check out the [examples directory](examples) for code samples demonstrating these features in action.

## FastAPI-first Approach

FastAPI-MCP is designed as a native extension of FastAPI, not just a converter that generates MCP tools from your API. This approach offers several key advantages:

- **Native dependencies**: Secure your MCP endpoints using familiar FastAPI `Depends()` for authentication and authorization

- **ASGI transport**: Communicates directly with your FastAPI app using its ASGI interface, eliminating the need for HTTP calls from the MCP to your API

- **Unified infrastructure**: Your FastAPI app doesn't need to run separately from the MCP server (though [separate deployment](https://fastapi-mcp.tadata.com/advanced/deploy#deploying-separately-from-original-fastapi-app) is also supported)

This design philosophy ensures minimum friction when adding MCP capabilities to your existing FastAPI services.


## Development and Contributing

Thank you for considering contributing to FastAPI-MCP! We encourage the community to post Issues and create Pull Requests.

Before you get started, please see our [Contribution Guide](CONTRIBUTING.md).

## Community

Join [MCParty Slack community](https://join.slack.com/t/themcparty/shared_invite/zt-30yxr1zdi-2FG~XjBA0xIgYSYuKe7~Xg) to connect with other MCP enthusiasts, ask questions, and share your experiences with FastAPI-MCP.

## Requirements

- Python 3.10+ (Recommended 3.12)
- uv

## License

MIT License. Copyright (c) 2025 Tadata Inc.
