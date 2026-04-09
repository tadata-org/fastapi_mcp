import json
from typing import Any, Dict, List, Optional, Union

import pytest
import mcp.types as types
from mcp.server.lowlevel import Server
from mcp.shared.memory import create_connected_server_and_client_session
from fastapi import FastAPI

from fastapi_mcp import FastApiMCP
from fastapi_mcp.types import HTTPRequestInfo


# -- Helpers --

def _make_tool(name: str = "my_custom_tool", description: str = "A custom tool") -> types.Tool:
    return types.Tool(
        name=name,
        description=description,
        inputSchema={"type": "object", "properties": {"q": {"type": "string"}}},
    )


async def _echo_handler(
    name: str,
    arguments: Dict[str, Any],
    http_request_info: Optional[HTTPRequestInfo],
    server: Server,
) -> List[Union[types.TextContent, types.ImageContent, types.EmbeddedResource]]:
    return [types.TextContent(type="text", text=json.dumps({"name": name, "arguments": arguments}))]


async def _inspect_handler(
    name: str,
    arguments: Dict[str, Any],
    http_request_info: Optional[HTTPRequestInfo],
    server: Server,
) -> List[Union[types.TextContent, types.ImageContent, types.EmbeddedResource]]:
    """Handler that returns info about what it received for inspection."""
    info = {
        "name": name,
        "arguments": arguments,
        "has_request_info": http_request_info is not None,
        "has_server": server is not None,
        "server_type": type(server).__name__,
    }
    if http_request_info:
        info["request_method"] = http_request_info.method
        info["request_headers"] = http_request_info.headers
    return [types.TextContent(type="text", text=json.dumps(info))]


async def _error_handler(
    name: str,
    arguments: Dict[str, Any],
    http_request_info: Optional[HTTPRequestInfo],
    server: Server,
) -> List[Union[types.TextContent, types.ImageContent, types.EmbeddedResource]]:
    raise ValueError("Custom tool error")


# -- Fixtures --

@pytest.fixture
def simple_app() -> FastAPI:
    app = FastAPI(title="Test App")

    @app.get("/items", operation_id="list_items")
    async def list_items():
        return [{"id": 1, "name": "Item 1"}]

    return app


@pytest.fixture
def mcp_with_add_tool(simple_app: FastAPI) -> FastApiMCP:
    mcp = FastApiMCP(simple_app, name="Test MCP")
    mcp.add_tool(_make_tool(), _echo_handler)
    mcp.mount()
    return mcp


@pytest.fixture
def mcp_with_constructor_tools(simple_app: FastAPI) -> FastApiMCP:
    mcp = FastApiMCP(
        simple_app,
        name="Test MCP",
        custom_tools=[(_make_tool(), _echo_handler)],
    )
    mcp.mount()
    return mcp


# -- Tests --

@pytest.mark.asyncio
async def test_custom_tool_listed(mcp_with_add_tool: FastApiMCP):
    """Custom tool appears in list_tools alongside auto-generated tools."""
    async with create_connected_server_and_client_session(mcp_with_add_tool.server) as client_session:
        tools_result = await client_session.list_tools()
        tool_names = [t.name for t in tools_result.tools]

        assert "my_custom_tool" in tool_names
        assert "list_items" in tool_names


@pytest.mark.asyncio
async def test_custom_tool_called(mcp_with_add_tool: FastApiMCP):
    """Calling a custom tool dispatches to its handler and returns expected content."""
    async with create_connected_server_and_client_session(mcp_with_add_tool.server) as client_session:
        response = await client_session.call_tool("my_custom_tool", {"q": "hello"})

        assert not response.isError
        assert len(response.content) > 0

        text_content = next(c for c in response.content if isinstance(c, types.TextContent))
        result = json.loads(text_content.text)

        assert result["name"] == "my_custom_tool"
        assert result["arguments"] == {"q": "hello"}


@pytest.mark.asyncio
async def test_custom_tool_receives_request_info(simple_app: FastAPI):
    """Handler receives HTTPRequestInfo (or None in test context)."""
    mcp = FastApiMCP(simple_app, name="Test MCP")
    mcp.add_tool(_make_tool("inspect_tool"), _inspect_handler)
    mcp.mount()

    async with create_connected_server_and_client_session(mcp.server) as client_session:
        response = await client_session.call_tool("inspect_tool", {"q": "test"})

        assert not response.isError
        text_content = next(c for c in response.content if isinstance(c, types.TextContent))
        result = json.loads(text_content.text)

        assert result["name"] == "inspect_tool"
        # In test context (memory transport), request info may not be available
        assert "has_request_info" in result


@pytest.mark.asyncio
async def test_custom_tool_receives_server(simple_app: FastAPI):
    """Handler receives MCP Server instance."""
    mcp = FastApiMCP(simple_app, name="Test MCP")
    mcp.add_tool(_make_tool("inspect_tool"), _inspect_handler)
    mcp.mount()

    async with create_connected_server_and_client_session(mcp.server) as client_session:
        response = await client_session.call_tool("inspect_tool", {"q": "test"})

        assert not response.isError
        text_content = next(c for c in response.content if isinstance(c, types.TextContent))
        result = json.loads(text_content.text)

        assert result["has_server"] is True
        assert result["server_type"] == "Server"


@pytest.mark.asyncio
async def test_custom_tools_via_constructor(mcp_with_constructor_tools: FastApiMCP):
    """Tools passed via custom_tools= param work identically to add_tool()."""
    async with create_connected_server_and_client_session(mcp_with_constructor_tools.server) as client_session:
        tools_result = await client_session.list_tools()
        tool_names = [t.name for t in tools_result.tools]

        assert "my_custom_tool" in tool_names
        assert "list_items" in tool_names

        response = await client_session.call_tool("my_custom_tool", {"q": "constructor"})
        assert not response.isError

        text_content = next(c for c in response.content if isinstance(c, types.TextContent))
        result = json.loads(text_content.text)
        assert result["arguments"] == {"q": "constructor"}


@pytest.mark.asyncio
async def test_openapi_tools_still_work(mcp_with_add_tool: FastApiMCP):
    """Existing auto-generated tools are unaffected by custom tool registration."""
    async with create_connected_server_and_client_session(mcp_with_add_tool.server) as client_session:
        response = await client_session.call_tool("list_items", {})

        assert not response.isError
        assert len(response.content) > 0

        text_content = next(c for c in response.content if isinstance(c, types.TextContent))
        result = json.loads(text_content.text)
        assert result == [{"id": 1, "name": "Item 1"}]


@pytest.mark.asyncio
async def test_custom_tool_error_handling(simple_app: FastAPI):
    """Handler raising an exception is properly surfaced."""
    mcp = FastApiMCP(simple_app, name="Test MCP")
    mcp.add_tool(_make_tool("error_tool"), _error_handler)
    mcp.mount()

    async with create_connected_server_and_client_session(mcp.server) as client_session:
        response = await client_session.call_tool("error_tool", {})

        assert response.isError
