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

## Documentation, Examples and Advanced Usage

FastAPI-MCP provides comprehensive documentation in the `docs` folder:
- [Best Practices](docs/00_BEST_PRACTICES.md) - Essential guidelines for converting APIs to MCP tools safely and effectively
- [FAQ](docs/00_FAQ.md) - Frequently asked questions about usage, development and support
- [Tool Naming](docs/01_tool_naming.md) - Best practices for naming your MCP tools using operation IDs
- [Connecting to MCP Server](docs/02_connecting_to_the_mcp_server.md) - How to connect various MCP clients like Cursor and Claude Desktop
- [Authentication and Authorization](docs/03_authentication_and_authorization.md) - How to authenticate and authorize your MCP tools
- [Advanced Usage](docs/04_advanced_usage.md) - Advanced features like custom schemas, endpoint filtering, and separate deployment

Check out the [examples directory](examples) for code samples demonstrating these features in action.

## FastAPI-first Approach

FastAPI-MCP is designed as a native extension of FastAPI, not just a converter that generates MCP tools from your API. This approach offers several key advantages:

- **Native dependencies**: Secure your MCP endpoints using familiar FastAPI `Depends()` for authentication and authorization

- **ASGI transport**: Communicates directly with your FastAPI app using its ASGI interface, eliminating the need for HTTP calls from the MCP to your API

- **Unified infrastructure**: Your FastAPI app doesn't need to run separately from the MCP server (though [separate deployment](docs/04_advanced_usage.md#deploying-separately-from-original-fastapi-app) is also supported)

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

MIT License. Copyright (c) 2024 Tadata Inc.
