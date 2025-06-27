"""
Integration test to verify WebSocket transport works with FastAPI-MCP.
"""

import pytest
from fastapi import FastAPI
from fastapi_mcp import FastApiMCP


def test_websocket_transport_mount():
    """Test that WebSocket transport can be mounted successfully."""
    app = FastAPI()

    @app.get("/test")
    async def test_endpoint():
        return {"message": "test"}

    mcp = FastApiMCP(app, name="Test WebSocket MCP")

    # Should not raise any exception
    mcp.mount(transport="websocket")

    # Verify the server was set up
    assert mcp.server is not None


def test_websocket_transport_with_custom_path():
    """Test WebSocket transport with custom mount path."""
    app = FastAPI()

    @app.get("/api/test")
    async def test_endpoint():
        return {"data": "test"}

    mcp = FastApiMCP(app, name="Custom Path WebSocket MCP")

    # Mount on custom path
    mcp.mount(mount_path="/custom-mcp", transport="websocket")

    assert mcp.server is not None


def test_invalid_transport_raises_error():
    """Test that invalid transport raises ValueError."""
    app = FastAPI()
    mcp = FastApiMCP(app, name="Invalid Transport MCP")

    with pytest.raises(ValueError, match="Invalid transport"):
        mcp.mount(transport="invalid")


def test_multiple_transports_on_same_app():
    """Test mounting both SSE and WebSocket transports on the same app."""
    app = FastAPI()

    @app.get("/shared")
    async def shared_endpoint():
        return {"transport": "both"}

    sse_mcp = FastApiMCP(app, name="SSE MCP")
    websocket_mcp = FastApiMCP(app, name="WebSocket MCP")

    # Should be able to mount both without conflict
    sse_mcp.mount(mount_path="/sse", transport="sse")
    websocket_mcp.mount(mount_path="/ws", transport="websocket")

    assert sse_mcp.server is not None
    assert websocket_mcp.server is not None
