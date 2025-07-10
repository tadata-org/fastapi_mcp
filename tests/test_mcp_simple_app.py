import json

import pytest
import mcp.types as types
from mcp.server.lowlevel import Server
from mcp.shared.memory import create_connected_server_and_client_session
from fastapi import FastAPI

from fastapi_mcp import FastApiMCP

from .fixtures.types import Item


@pytest.fixture
def fastapi_mcp(simple_fastapi_app: FastAPI) -> FastApiMCP:
    mcp = FastApiMCP(
        simple_fastapi_app,
        name="Test MCP Server",
        description="Test description",
    )
    mcp.mount()
    return mcp


@pytest.fixture
def fastapi_mcp_with_custom_header(simple_fastapi_app: FastAPI) -> FastApiMCP:
    mcp = FastApiMCP(
        simple_fastapi_app,
        name="Test MCP Server with custom header",
        description="Test description",
        headers=["X-Custom-Header"],
    )
    mcp.mount()
    return mcp


@pytest.fixture
def lowlevel_server_simple_app(fastapi_mcp: FastApiMCP) -> Server:
    return fastapi_mcp.server


@pytest.mark.asyncio
async def test_list_tools(lowlevel_server_simple_app: Server):
    """Test listing tools via direct MCP connection."""
    async with create_connected_server_and_client_session(lowlevel_server_simple_app) as client_session:
        tools_result = await client_session.list_tools()

        assert len(tools_result.tools) > 0

        tool_names = [tool.name for tool in tools_result.tools]
        expected_operations = ["list_items", "get_item", "create_item", "update_item", "delete_item", "raise_error"]
        for op in expected_operations:
            assert op in tool_names


@pytest.mark.asyncio
async def test_call_tool_get_item_1(lowlevel_server_simple_app: Server):
    async with create_connected_server_and_client_session(lowlevel_server_simple_app) as client_session:
        response = await client_session.call_tool("get_item", {"item_id": 1})

        assert not response.isError
        assert len(response.content) > 0

        text_content = next(c for c in response.content if isinstance(c, types.TextContent))
        result: dict = json.loads(text_content.text)
        parsed_result = Item(**result)

        assert parsed_result.id == 1
        assert parsed_result.name == "Item 1"
        assert parsed_result.price == 10.0
        assert parsed_result.tags == ["tag1", "tag2"]


@pytest.mark.asyncio
async def test_call_tool_get_item_2(lowlevel_server_simple_app: Server):
    async with create_connected_server_and_client_session(lowlevel_server_simple_app) as client_session:
        response = await client_session.call_tool("get_item", {"item_id": 2})

        assert not response.isError
        assert len(response.content) > 0

        text_content = next(c for c in response.content if isinstance(c, types.TextContent))
        result: dict = json.loads(text_content.text)
        parsed_result = Item(**result)

        assert parsed_result.id == 2
        assert parsed_result.name == "Item 2"
        assert parsed_result.price == 20.0
        assert parsed_result.tags == ["tag2", "tag3"]


@pytest.mark.asyncio
async def test_call_tool_raise_error(lowlevel_server_simple_app: Server):
    async with create_connected_server_and_client_session(lowlevel_server_simple_app) as client_session:
        response = await client_session.call_tool("raise_error", {})

        assert response.isError
        assert len(response.content) > 0

        text_content = next(c for c in response.content if isinstance(c, types.TextContent))
        assert "500" in text_content.text
        assert "internal server error" in text_content.text.lower()


@pytest.mark.asyncio
async def test_error_handling(lowlevel_server_simple_app: Server):
    async with create_connected_server_and_client_session(lowlevel_server_simple_app) as client_session:
        response = await client_session.call_tool("get_item", {})

        assert response.isError
        assert len(response.content) > 0

        text_content = next(c for c in response.content if isinstance(c, types.TextContent))
        assert "item_id" in text_content.text.lower() or "missing" in text_content.text.lower()
        assert "422" in text_content.text, "Expected a 422 status to appear in the response text"


@pytest.mark.asyncio
async def test_complex_tool_arguments(lowlevel_server_simple_app: Server):
    test_item = {
        "id": 42,
        "name": "Test Item",
        "description": "A test item for MCP",
        "price": 9.99,
        "tags": ["test", "mcp"],
    }

    async with create_connected_server_and_client_session(lowlevel_server_simple_app) as client_session:
        response = await client_session.call_tool("create_item", test_item)

        assert not response.isError
        assert len(response.content) > 0

        text_content = next(c for c in response.content if isinstance(c, types.TextContent))
        result = json.loads(text_content.text)

        assert result["id"] == test_item["id"]
        assert result["name"] == test_item["name"]
        assert result["price"] == test_item["price"]
        assert result["tags"] == test_item["tags"]


@pytest.mark.asyncio
async def test_call_tool_list_items_default(lowlevel_server_simple_app: Server):
    async with create_connected_server_and_client_session(lowlevel_server_simple_app) as client_session:
        response = await client_session.call_tool("list_items", {})

        assert not response.isError
        assert len(response.content) > 0

        text_content = next(c for c in response.content if isinstance(c, types.TextContent))
        results = json.loads(text_content.text)
        assert len(results) == 3  # Default should return all three items with default pagination

        # Check first item matches expected data
        item = results[0]
        assert item["id"] == 1
        assert item["name"] == "Item 1"


@pytest.mark.asyncio
async def test_call_tool_list_items_with_pagination(lowlevel_server_simple_app: Server):
    async with create_connected_server_and_client_session(lowlevel_server_simple_app) as client_session:
        response = await client_session.call_tool("list_items", {"skip": 1, "limit": 1})

        assert not response.isError
        assert len(response.content) > 0

        text_content = next(c for c in response.content if isinstance(c, types.TextContent))
        results = json.loads(text_content.text)
        assert len(results) == 1

        # Should be the second item in the list (after skipping the first)
        item = results[0]
        assert item["id"] == 2
        assert item["name"] == "Item 2"


@pytest.mark.asyncio
async def test_call_tool_get_item_not_found(lowlevel_server_simple_app: Server):
    async with create_connected_server_and_client_session(lowlevel_server_simple_app) as client_session:
        response = await client_session.call_tool("get_item", {"item_id": 999})

        assert response.isError
        assert len(response.content) > 0

        text_content = next(c for c in response.content if isinstance(c, types.TextContent))
        assert "404" in text_content.text
        assert "not found" in text_content.text.lower()


@pytest.mark.asyncio
async def test_call_tool_update_item(lowlevel_server_simple_app: Server):
    test_update = {
        "item_id": 3,
        "id": 3,
        "name": "Updated Item 3",
        "description": "Updated description",
        "price": 35.99,
        "tags": ["updated", "modified"],
    }

    async with create_connected_server_and_client_session(lowlevel_server_simple_app) as client_session:
        response = await client_session.call_tool("update_item", test_update)

        assert not response.isError
        assert len(response.content) > 0

        text_content = next(c for c in response.content if isinstance(c, types.TextContent))
        result = json.loads(text_content.text)

        assert result["id"] == test_update["item_id"]
        assert result["name"] == test_update["name"]
        assert result["description"] == test_update["description"]
        assert result["price"] == test_update["price"]
        assert result["tags"] == test_update["tags"]


@pytest.mark.asyncio
async def test_call_tool_delete_item(lowlevel_server_simple_app: Server):
    async with create_connected_server_and_client_session(lowlevel_server_simple_app) as client_session:
        response = await client_session.call_tool("delete_item", {"item_id": 3})

        assert not response.isError
        # The endpoint returns 204 No Content, so we expect an empty response
        text_content = next(c for c in response.content if isinstance(c, types.TextContent))
        assert (
            text_content.text.strip() == "{}" or text_content.text.strip() == "null" or text_content.text.strip() == ""
        )


@pytest.mark.asyncio
async def test_call_tool_get_item_with_details(lowlevel_server_simple_app: Server):
    async with create_connected_server_and_client_session(lowlevel_server_simple_app) as client_session:
        response = await client_session.call_tool("get_item", {"item_id": 1, "include_details": True})

        assert not response.isError
        assert len(response.content) > 0

        text_content = next(c for c in response.content if isinstance(c, types.TextContent))
        result: dict = json.loads(text_content.text)
        parsed_result = Item(**result)

        assert parsed_result.id == 1
        assert parsed_result.name == "Item 1"
        assert parsed_result.price == 10.0
        assert parsed_result.tags == ["tag1", "tag2"]
        assert parsed_result.description == "Item 1 description"


@pytest.mark.asyncio
async def test_headers_passthrough_to_tool_handler(fastapi_mcp: FastApiMCP):
    """Test that the original request's headers pass through to the MCP tool call handler."""
    from unittest.mock import patch, MagicMock
    from fastapi_mcp.types import HTTPRequestInfo

    # Test with uppercase "Authorization" header
    with patch.object(fastapi_mcp, "_request") as mock_request:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"result": "success"}'
        mock_response.json.return_value = {"result": "success"}
        mock_request.return_value = mock_response

        http_request_info = HTTPRequestInfo(
            method="POST",
            path="/test",
            headers={"Authorization": "Bearer token123"},
            cookies={},
            query_params={},
            body=None,
        )

        try:
            # Call the _execute_api_tool method directly
            # We don't care if it succeeds, just that _request gets the right headers
            await fastapi_mcp._execute_api_tool(
                client=fastapi_mcp._http_client,
                tool_name="get_item",
                arguments={"item_id": 1},
                operation_map=fastapi_mcp.operation_map,
                http_request_info=http_request_info,
            )
        except Exception:
            pass

        assert mock_request.called, "The _request method was not called"

        if mock_request.called:
            headers_arg = mock_request.call_args[0][4]  # headers are the 5th argument
            assert "Authorization" in headers_arg
            assert headers_arg["Authorization"] == "Bearer token123"

    # Test again with lowercase "authorization" header
    with patch.object(fastapi_mcp, "_request") as mock_request:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"result": "success"}'
        mock_response.json.return_value = {"result": "success"}
        mock_request.return_value = mock_response

        http_request_info = HTTPRequestInfo(
            method="POST",
            path="/test",
            headers={"authorization": "Bearer token456"},
            cookies={},
            query_params={},
            body=None,
        )

        try:
            await fastapi_mcp._execute_api_tool(
                client=fastapi_mcp._http_client,
                tool_name="get_item",
                arguments={"item_id": 1},
                operation_map=fastapi_mcp.operation_map,
                http_request_info=http_request_info,
            )
        except Exception:
            pass

        assert mock_request.called, "The _request method was not called"

        if mock_request.called:
            headers_arg = mock_request.call_args[0][4]  # headers are the 5th argument
            assert "authorization" in headers_arg
            assert headers_arg["authorization"] == "Bearer token456"


@pytest.mark.asyncio
async def test_custom_header_passthrough_to_tool_handler(fastapi_mcp_with_custom_header: FastApiMCP):
    from unittest.mock import patch, MagicMock
    from fastapi_mcp.types import HTTPRequestInfo

    # Test with custom header "X-Custom-Header"
    with patch.object(fastapi_mcp_with_custom_header, "_request") as mock_request:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"result": "success"}'
        mock_response.json.return_value = {"result": "success"}
        mock_request.return_value = mock_response

        http_request_info = HTTPRequestInfo(
            method="POST",
            path="/test",
            headers={"X-Custom-Header": "MyValue123"},
            cookies={},
            query_params={},
            body=None,
        )

        try:
            # Call the _execute_api_tool method directly
            # We don't care if it succeeds, just that _request gets the right headers
            await fastapi_mcp_with_custom_header._execute_api_tool(
                client=fastapi_mcp_with_custom_header._http_client,
                tool_name="get_item",
                arguments={"item_id": 1},
                operation_map=fastapi_mcp_with_custom_header.operation_map,
                http_request_info=http_request_info,
            )
        except Exception:
            pass

        assert mock_request.called, "The _request method was not called"

        if mock_request.called:
            headers_arg = mock_request.call_args[0][4]  # headers are the 5th argument
            assert "X-Custom-Header" in headers_arg
            assert headers_arg["X-Custom-Header"] == "MyValue123"
