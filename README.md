<p align="center"><a href="https://github.com/tadata-org/fastapi_mcp"><img src="https://github.com/user-attachments/assets/7e44e98b-a0ba-4aff-a68a-4ffee3a6189c" alt="fastapi-to-mcp" height=100/></a></p>
<h1 align="center">FastAPI-MCP</h1>
<p align="center">A zero-configuration tool for automatically exposing FastAPI endpoints as Model Context Protocol (MCP) tools.</p>
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

- **Zero configuration** - Just point it at your FastAPI app and it works, with automatic discovery of endpoints and conversion to MCP tools
- **Schema & docs preservation** - Keep the same request/response models and preserve documentation of all your endpoints
- **Flexible deployment** - Mount your MCP server to the same FastAPI application, or deploy separately
- **Custom endpoint exposure** - Control which endpoints become MCP tools using operation IDs and tags
- **ASGI transport** - Uses FastAPI's ASGI interface directly by default for efficient communication

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

> **Note on `base_url`**: While `base_url` is optional, it is highly recommended to provide it explicitly. The `base_url` tells the MCP server where to send API requests when tools are called. Without it, the library will attempt to determine the URL automatically, which may not work correctly in deployed environments where the internal and external URLs differ.

## Documentation, Examples and Advanced Usage

FastAPI-MCP provides comprehensive documentation in the `docs` folder:
- [Best Practices](docs/00_BEST_PRACTICES.md) - Essential guidelines for converting APIs to MCP tools safely and effectively
- [FAQ](docs/00_FAQ.md) - Frequently asked questions about usage, development and support
- [Tool Naming](docs/01_tool_naming.md) - Best practices for naming your MCP tools using operation IDs
- [Connecting to MCP Server](docs/02_connecting_to_the_mcp_server.md) - How to connect various MCP clients like Cursor and Claude Desktop
- [Advanced Usage](docs/03_advanced_usage.md) - Advanced features like custom schemas, endpoint filtering, and separate deployment

Check out the [examples directory](examples) for code samples demonstrating these features in action.

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
