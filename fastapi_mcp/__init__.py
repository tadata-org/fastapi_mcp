"""
FastAPI-MCP: Automatic MCP server generator for FastAPI applications.

Created by Tadata Inc. (https://github.com/tadata-org)
"""

__version__ = "0.1.5"

from .server import add_mcp_server, create_mcp_server, mount_mcp_server
from .http_tools import create_mcp_tools_from_openapi

__all__ = [
    "add_mcp_server",
    "create_mcp_server",
    "mount_mcp_server",
    "create_mcp_tools_from_openapi",
]
