"""
Server module for FastAPI-MCP.

This module provides functionality for creating and mounting MCP servers to FastAPI applications.
"""

from typing import Dict, Optional, Any

from fastapi import FastAPI
from mcp.server.fastmcp import FastMCP
from mcp.server.sse import SseServerTransport
from fastapi import Request

from .http_tools import create_mcp_tools_from_openapi


def create_mcp_server(
    app: FastAPI,
    name: Optional[str] = None,
    description: Optional[str] = None,
    capabilities: Optional[Dict[str, Any]] = None,
) -> FastMCP:
    """
    Create an MCP server from a FastAPI app.

    Args:
        app: The FastAPI application
        name: Name for the MCP server (defaults to app.title)
        description: Description for the MCP server (defaults to app.description)
        capabilities: Optional capabilities for the MCP server

    Returns:
        The created FastMCP instance
    """
    # Use app details if not provided
    server_name = name or app.title or "FastAPI MCP"
    server_description = description or app.description

    # Create the MCP server
    mcp_server = FastMCP(server_name, server_description)

    # Configure server capabilities if provided
    if capabilities:
        for capability, value in capabilities.items():
            # TODO: Maybe revise this hacky approach
            mcp_server.settings.capabilities[capability] = value  # type: ignore

    return mcp_server


def mount_mcp_server(
    app: FastAPI,
    mcp_server: FastMCP,
    mount_path: str = "/mcp",
    serve_tools: bool = True,
    base_url: Optional[str] = None,
    describe_all_responses: bool = False,
    describe_full_response_schema: bool = False,
) -> None:
    """
    Mount an MCP server to a FastAPI app.

    Args:
        app: The FastAPI application
        mcp_server: The MCP server to mount
        mount_path: Path where the MCP server will be mounted
        serve_tools: Whether to serve tools from the FastAPI app
        base_url: Base URL for API requests
        describe_all_responses: Whether to include all possible response schemas in tool descriptions. Recommended to keep False, as the LLM will probably derive if there is an error.
        describe_full_response_schema: Whether to include full json schema for responses in tool descriptions. Recommended to keep False, as examples are more LLM friendly, and save tokens.
    """
    # Normalize mount path
    if not mount_path.startswith("/"):
        mount_path = f"/{mount_path}"
    if mount_path.endswith("/"):
        mount_path = mount_path[:-1]

    # Create SSE transport for MCP messages
    sse_transport = SseServerTransport(f"{mount_path}/messages/")

    # Define MCP connection handler
    async def handle_mcp_connection(request: Request):
        async with sse_transport.connect_sse(request.scope, request.receive, request._send) as streams:
            await mcp_server._mcp_server.run(
                streams[0],
                streams[1],
                mcp_server._mcp_server.create_initialization_options(),
            )

    # Serve tools from the FastAPI app if requested
    if serve_tools:
        create_mcp_tools_from_openapi(
            app,
            mcp_server,
            base_url,
            describe_all_responses=describe_all_responses,
            describe_full_response_schema=describe_full_response_schema,
        )
    
    # Mount the MCP connection handler
    app.get(mount_path)(handle_mcp_connection)
    app.mount(f"{mount_path}/messages/", app=sse_transport.handle_post_message)



def add_mcp_server(
    app: FastAPI,
    mount_path: str = "/mcp",
    name: Optional[str] = None,
    description: Optional[str] = None,
    capabilities: Optional[Dict[str, Any]] = None,
    serve_tools: bool = True,
    base_url: Optional[str] = None,
    describe_all_responses: bool = False,
    describe_full_response_schema: bool = False,
) -> FastMCP:
    """
    Add an MCP server to a FastAPI app.

    Args:
        app: The FastAPI application
        mount_path: Path where the MCP server will be mounted
        name: Name for the MCP server (defaults to app.title)
        description: Description for the MCP server (defaults to app.description)
        capabilities: Optional capabilities for the MCP server
        serve_tools: Whether to serve tools from the FastAPI app
        base_url: Base URL for API requests (defaults to http://localhost:$PORT)
        describe_all_responses: Whether to include all possible response schemas in tool descriptions. Recommended to keep False, as the LLM will probably derive if there is an error.
        describe_full_response_schema: Whether to include full json schema for responses in tool descriptions. Recommended to keep False, as examples are more LLM friendly, and save tokens.

    Returns:
        The FastMCP instance that was created and mounted
    """
    # Create MCP server
    mcp_server = create_mcp_server(app, name, description, capabilities)

    # Mount MCP server to FastAPI app
    mount_mcp_server(
        app,
        mcp_server,
        mount_path,
        serve_tools,
        base_url,
        describe_all_responses=describe_all_responses,
        describe_full_response_schema=describe_full_response_schema,
    )

    return mcp_server
