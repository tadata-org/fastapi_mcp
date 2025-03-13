# FastAPI-MCP

A zero-configuration tool for automatically exposing FastAPI endpoints as Model Context Protocol (MCP) tools.

[![PyPI version](https://badge.fury.io/py/fastapi-mcp.svg)](https://pypi.org/project/fastapi-mcp/)
[![Python Versions](https://img.shields.io/pypi/pyversions/fastapi-mcp.svg)](https://pypi.org/project/fastapi-mcp/)

## Features

- **Direct integration** - Mount an MCP server directly to your FastAPI app
- **Zero configuration** required - just point it at your FastAPI app and it works
- **Automatic discovery** of all FastAPI endpoints and conversion to MCP tools
- **Preserving schemas** of your request models and response models
- **Preserve documentation** of all your endpoints, just as it is in Swagger
- **Extend** - Add custom MCP tools alongside the auto-generated ones

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
from fastapi_mcp import add_mcp_server

# Your FastAPI app
app = FastAPI()

# Mount the MCP server to your app
add_mcp_server(
    app,                    # Your FastAPI app
    mount_path="/mcp",      # Where to mount the MCP server
    name="My API MCP",      # Name for the MCP server
)
```

That's it! Your auto-generated MCP server is now available at `https://app.base.url/mcp`.

By default, all paths listed in the FastAPI app provided _will not have MCP tools created for them._
There are a fair number of paths that folks might not want tools for- as such, tool creation is `opt-in`.

If you wish to include a path in tool creation, you can do so using a `include_in_mcp` tag

Ex)

```
    @app.post("/items/", response_model=Item, tags=["items", "include_in_mcp"])
    async def create_item(item: Item):
        """
        Create a new item.

        Returns the created item.
        """
        return item
```

## Advanced Usage

FastAPI-MCP provides several ways to customize and control how your MCP server is created and configured. Here are some advanced usage patterns:

```python
from fastapi import FastAPI
from fastapi_mcp import add_mcp_server

app = FastAPI()

mcp_server = add_mcp_server(
    app,                                    # Your FastAPI app
    mount_path="/mcp",                      # Where to mount the MCP server
    name="My API MCP",                      # Name for the MCP server
    describe_all_responses=True,            # False by default. Include all possible response schemas in tool descriptions, instead of just the successful response.
    describe_full_response_schema=True      # False by default. Include full JSON schema in tool descriptions, instead of just an LLM-friendly response example.
)

# Optionally add custom tools in addition to existing APIs.
@mcp_server.tool()
async def get_server_time() -> str:
    """Get the current server time."""
    from datetime import datetime
    return datetime.now().isoformat()
```

## Examples

See the [examples](examples) directory for complete examples.

## Connecting to the MCP Server

Once your FastAPI app with MCP integration is running, you can connect to it with any MCP client, such as Claude:

1. Run your application
2. In Claude, use the URL of your MCP server endpoint (e.g., `http://localhost:8000/mcp`)
3. Claude will discover all available tools and resources automatically

## Development and Contributing

If you're interested in contributing to FastAPI-MCP:

```bash
# Clone the repository
git clone https://github.com/tadata-org/fastapi_mcp.git
cd fastapi_mcp

# Create a virtual environment and install dependencies with uv
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv add -e ".[dev]"

# Run tests
uv run pytest
```

For more details about contributing, see [CONTRIBUTING.md](CONTRIBUTING.md).

## Community

Join [MCParty Slack community](https://join.slack.com/t/themcparty/shared_invite/zt-30yxr1zdi-2FG~XjBA0xIgYSYuKe7~Xg) to connect with other MCP enthusiasts, ask questions, and share your experiences with FastAPI-MCP.

## Requirements

- Python 3.10+
- uv

## License

MIT License. Copyright (c) 2024 Tadata Inc.

## About

Developed and maintained by [Tadata Inc.](https://github.com/tadata-org)
