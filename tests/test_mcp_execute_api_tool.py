import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import FastAPI

from fastapi_mcp import FastApiMCP
from mcp.types import TextContent


@pytest.mark.asyncio
async def test_execute_api_tool_success(simple_fastapi_app: FastAPI):
    """Test successful execution of an API tool."""
    mcp = FastApiMCP(simple_fastapi_app)

    # Mock the HTTP client response
    mock_response = MagicMock()
    mock_response.json.return_value = {"id": 1, "name": "Test Item"}
    mock_response.status_code = 200
    mock_response.text = '{"id": 1, "name": "Test Item"}'

    # Mock the HTTP client
    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response

    # Test parameters
    tool_name = "get_item"
    arguments = {"item_id": 1}

    # Execute the tool
    with patch.object(mcp, "_http_client", mock_client):
        result = await mcp._execute_api_tool(
            client=mock_client, tool_name=tool_name, arguments=arguments, operation_map=mcp.operation_map
        )

    # Verify the result
    assert len(result) == 1
    assert isinstance(result[0], TextContent)
    assert result[0].text == '{\n  "id": 1,\n  "name": "Test Item"\n}'

    # Verify the HTTP client was called correctly
    mock_client.get.assert_called_once_with("/items/1", params={}, headers={})


@pytest.mark.asyncio
async def test_execute_api_tool_with_query_params(simple_fastapi_app: FastAPI):
    """Test execution of an API tool with query parameters."""
    mcp = FastApiMCP(simple_fastapi_app)

    # Mock the HTTP client response
    mock_response = MagicMock()
    mock_response.json.return_value = [{"id": 1, "name": "Item 1"}, {"id": 2, "name": "Item 2"}]
    mock_response.status_code = 200
    mock_response.text = '[{"id": 1, "name": "Item 1"}, {"id": 2, "name": "Item 2"}]'

    # Mock the HTTP client
    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response

    # Test parameters
    tool_name = "list_items"
    arguments = {"skip": 0, "limit": 2}

    # Execute the tool
    with patch.object(mcp, "_http_client", mock_client):
        result = await mcp._execute_api_tool(
            client=mock_client, tool_name=tool_name, arguments=arguments, operation_map=mcp.operation_map
        )

    # Verify the result
    assert len(result) == 1
    assert isinstance(result[0], TextContent)

    # Verify the HTTP client was called with query parameters
    mock_client.get.assert_called_once_with("/items/", params={"skip": 0, "limit": 2}, headers={})


@pytest.mark.asyncio
async def test_execute_api_tool_with_body(simple_fastapi_app: FastAPI):
    """Test execution of an API tool with request body."""
    mcp = FastApiMCP(simple_fastapi_app)

    # Mock the HTTP client response
    mock_response = MagicMock()
    mock_response.json.return_value = {"id": 1, "name": "New Item"}
    mock_response.status_code = 200
    mock_response.text = '{"id": 1, "name": "New Item"}'

    # Mock the HTTP client
    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response

    # Test parameters. Note: the tool's advertised inputSchema flattens the
    # Item model's fields (id, name, ...), so the caller provides those — and
    # the executor forwards exactly the declared body fields, which is also
    # the payload the real FastAPI endpoint expects.
    tool_name = "create_item"
    arguments = {"id": 1, "name": "New Item", "price": 10.0, "tags": ["tag1"], "description": "New item description"}

    # Execute the tool
    with patch.object(mcp, "_http_client", mock_client):
        result = await mcp._execute_api_tool(
            client=mock_client, tool_name=tool_name, arguments=arguments, operation_map=mcp.operation_map
        )

    # Verify the result
    assert len(result) == 1
    assert isinstance(result[0], TextContent)

    # Verify the HTTP client was called with the request body
    mock_client.post.assert_called_once_with("/items/", params={}, headers={}, json=arguments)


@pytest.mark.asyncio
async def test_execute_api_tool_body_survives_path_param_collision(
    simple_fastapi_app_with_body_path_collision: FastAPI,
):
    """Regression test for issue #319 (part 2): a body field whose name collides
    with a path parameter must still reach the request body payload. Previously
    the executor popped path params out of the flattened argument dict before
    building the body, silently deleting the colliding body field and causing
    FastAPI to answer 422."""
    mcp = FastApiMCP(simple_fastapi_app_with_body_path_collision)

    mock_response = MagicMock()
    mock_response.json.return_value = {"ok": True}
    mock_response.status_code = 200
    mock_response.text = '{"ok": true}'

    mock_client = AsyncMock()
    mock_client.put.return_value = mock_response

    arguments = {"item_id": 42, "quantity": 7}
    with patch.object(mcp, "_http_client", mock_client):
        await mcp._execute_api_tool(
            client=mock_client,
            tool_name="update_order",
            arguments=arguments,
            operation_map=mcp.operation_map,
        )

    # Path substituted...
    mock_client.put.assert_called_once()
    call = mock_client.put.call_args
    assert call.args[0] == "/orders/42"
    # ...AND body keeps the colliding field.
    assert call.kwargs.get("json") == {"item_id": 42, "quantity": 7}


@pytest.mark.asyncio
async def test_execute_api_tool_non_object_body_passthrough(simple_fastapi_app_with_array_body: FastAPI):
    """Regression test for issue #319 (part 1): a top-level array (or primitive)
    request body is exposed as a single argument and passed through verbatim.
    Previously such operations generated a tool with NO body arguments, making
    them unreachable."""
    mcp = FastApiMCP(simple_fastapi_app_with_array_body)

    mock_response = MagicMock()
    mock_response.json.return_value = {"count": 2}
    mock_response.status_code = 200
    mock_response.text = '{"count": 2}'

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response

    arguments = {"payload": [{"name": "a"}, {"name": "b"}]}
    with patch.object(mcp, "_http_client", mock_client):
        await mcp._execute_api_tool(
            client=mock_client,
            tool_name="bulk_tags",
            arguments=arguments,
            operation_map=mcp.operation_map,
        )

    mock_client.post.assert_called_once()
    call = mock_client.post.call_args
    # The raw body value must be sent as the JSON document itself, not nested.
    assert call.kwargs.get("json") == [{"name": "a"}, {"name": "b"}]


@pytest.mark.asyncio
async def test_execute_api_tool_legacy_operation_map_keeps_leftover_body_behavior(simple_fastapi_app: FastAPI):
    """Operation maps produced by older versions (no body metadata) keep the
    historical leftover-arguments-as-body behavior."""
    mcp = FastApiMCP(simple_fastapi_app)

    mock_response = MagicMock()
    mock_response.json.return_value = {"ok": True}
    mock_response.status_code = 200
    mock_response.text = '{"ok": true}'

    mock_client = AsyncMock()
    mock_client.put.return_value = mock_response

    legacy_map = {
        "legacy_tool": {
            "path": "/orders/{item_id}",
            "method": "PUT",
            "parameters": [{"name": "item_id", "in": "path"}],
        }
    }
    with patch.object(mcp, "_http_client", mock_client):
        await mcp._execute_api_tool(
            client=mock_client,
            tool_name="legacy_tool",
            arguments={"item_id": 9, "extra": "x"},
            operation_map=legacy_map,
        )

    mock_client.put.assert_called_once()
    call = mock_client.put.call_args
    assert call.args[0] == "/orders/9"
    assert call.kwargs.get("json") == {"extra": "x"}


@pytest.mark.asyncio
async def test_execute_api_tool_with_non_ascii_chars(simple_fastapi_app: FastAPI):
    """Test execution of an API tool with non-ASCII characters."""
    mcp = FastApiMCP(simple_fastapi_app)

    # Test data with both ASCII and non-ASCII characters
    test_data = {
        "id": 1,
        "name": "你好 World",  # Chinese characters + ASCII
        "price": 10.0,
        "tags": ["tag1", "标签2"],  # Chinese characters in tags
        "description": "这是一个测试描述",  # All Chinese characters
    }

    # Mock the HTTP client response
    mock_response = MagicMock()
    mock_response.json.return_value = test_data
    mock_response.status_code = 200
    mock_response.text = (
        '{"id": 1, "name": "你好 World", "price": 10.0, "tags": ["tag1", "标签2"], "description": "这是一个测试描述"}'
    )

    # Mock the HTTP client
    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response

    # Test parameters
    tool_name = "get_item"
    arguments = {"item_id": 1}

    # Execute the tool
    with patch.object(mcp, "_http_client", mock_client):
        result = await mcp._execute_api_tool(
            client=mock_client, tool_name=tool_name, arguments=arguments, operation_map=mcp.operation_map
        )

    # Verify the result
    assert len(result) == 1
    assert isinstance(result[0], TextContent)

    # Verify that the response contains both ASCII and non-ASCII characters
    response_text = result[0].text
    assert "你好" in response_text  # Chinese characters preserved
    assert "World" in response_text  # ASCII characters preserved
    assert "标签2" in response_text  # Chinese characters in tags preserved
    assert "这是一个测试描述" in response_text  # All Chinese description preserved

    # Verify the HTTP client was called correctly
    mock_client.get.assert_called_once_with("/items/1", params={}, headers={})
