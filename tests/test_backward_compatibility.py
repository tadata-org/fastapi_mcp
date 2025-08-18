"""
Backward compatibility tests for form parameter support.

These tests ensure that existing JSON endpoints continue to work without changes
and that mixed parameter scenarios work correctly.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import FastAPI

from fastapi_mcp import FastApiMCP
from mcp.types import TextContent


@pytest.mark.asyncio
async def test_json_endpoints_unchanged(simple_fastapi_app: FastAPI):
    """Test that existing JSON endpoints continue to work without changes."""
    mcp = FastApiMCP(simple_fastapi_app)

    # Mock the HTTP client response for JSON endpoint
    mock_response = MagicMock()
    mock_response.json.return_value = {"id": 1, "name": "Test Item", "price": 10.0}
    mock_response.status_code = 200
    mock_response.text = '{"id": 1, "name": "Test Item", "price": 10.0}'

    # Mock the HTTP client
    mock_client = AsyncMock()
    mock_client.request.return_value = mock_response

    # Test JSON POST request (create_item endpoint)
    tool_name = "create_item"
    arguments = {
        "item": {"id": 1, "name": "Test Item", "price": 10.0, "tags": ["tag1"], "description": "Test description"}
    }

    # Execute the tool
    with patch.object(mcp, "_http_client", mock_client):
        result = await mcp._execute_api_tool(
            client=mock_client, tool_name=tool_name, arguments=arguments, operation_map=mcp.operation_map
        )

    # Verify the result
    assert len(result) == 1
    assert isinstance(result[0], TextContent)

    # Verify the HTTP client was called with JSON (backward compatibility)
    mock_client.request.assert_called_once_with("post", "/items/", params={}, headers={}, json=arguments)


@pytest.mark.asyncio
async def test_get_endpoints_unchanged(simple_fastapi_app: FastAPI):
    """Test that GET endpoints continue to work unchanged."""
    mcp = FastApiMCP(simple_fastapi_app)

    # Mock the HTTP client response
    mock_response = MagicMock()
    mock_response.json.return_value = {"id": 1, "name": "Test Item"}
    mock_response.status_code = 200
    mock_response.text = '{"id": 1, "name": "Test Item"}'

    # Mock the HTTP client
    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response

    # Test GET request
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

    # Verify the HTTP client was called correctly (unchanged)
    mock_client.get.assert_called_once_with("/items/1", params={}, headers={})


@pytest.mark.asyncio
async def test_mixed_parameters_query_path_json(simple_fastapi_app: FastAPI):
    """Test mixed parameter scenarios with query, path, and JSON body parameters."""
    mcp = FastApiMCP(simple_fastapi_app)

    # Mock the HTTP client response
    mock_response = MagicMock()
    mock_response.json.return_value = {"id": 1, "name": "Updated Item"}
    mock_response.status_code = 200
    mock_response.text = '{"id": 1, "name": "Updated Item"}'

    # Mock the HTTP client
    mock_client = AsyncMock()
    mock_client.request.return_value = mock_response

    # Test PUT request with path parameter and JSON body
    tool_name = "update_item"
    arguments = {
        "item_id": 1,  # Path parameter
        "item": {  # JSON body
            "id": 1,
            "name": "Updated Item",
            "price": 15.0,
            "tags": ["updated"],
            "description": "Updated description",
        },
    }

    # Execute the tool
    with patch.object(mcp, "_http_client", mock_client):
        result = await mcp._execute_api_tool(
            client=mock_client, tool_name=tool_name, arguments=arguments, operation_map=mcp.operation_map
        )

    # Verify the result
    assert len(result) == 1
    assert isinstance(result[0], TextContent)

    # Verify the HTTP client was called correctly
    # Path parameter should be in URL, body should be JSON
    expected_body = {"item": arguments["item"]}
    mock_client.request.assert_called_once_with("put", "/items/1", params={}, headers={}, json=expected_body)


@pytest.mark.asyncio
async def test_mixed_parameters_query_path_only(simple_fastapi_app: FastAPI):
    """Test mixed parameter scenarios with only query and path parameters."""
    mcp = FastApiMCP(simple_fastapi_app)

    # Mock the HTTP client response
    mock_response = MagicMock()
    mock_response.json.return_value = [{"id": 1, "name": "Item 1"}]
    mock_response.status_code = 200
    mock_response.text = '[{"id": 1, "name": "Item 1"}]'

    # Mock the HTTP client
    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response

    # Test GET request with query parameters
    tool_name = "list_items"
    arguments = {
        "skip": 0,  # Query parameter
        "limit": 10,  # Query parameter
        "sort_by": "name",  # Query parameter
    }

    # Execute the tool
    with patch.object(mcp, "_http_client", mock_client):
        result = await mcp._execute_api_tool(
            client=mock_client, tool_name=tool_name, arguments=arguments, operation_map=mcp.operation_map
        )

    # Verify the result
    assert len(result) == 1
    assert isinstance(result[0], TextContent)

    # Verify the HTTP client was called correctly
    # All parameters should be in query params
    mock_client.get.assert_called_once_with("/items/", params={"skip": 0, "limit": 10, "sort_by": "name"}, headers={})


@pytest.mark.asyncio
async def test_error_handling_unchanged(simple_fastapi_app: FastAPI):
    """Test that error handling improvements don't break existing error responses."""
    mcp = FastApiMCP(simple_fastapi_app)

    # Mock the HTTP client response with error
    mock_response = MagicMock()
    mock_response.json.return_value = {"detail": "Item not found"}
    mock_response.status_code = 404
    mock_response.text = '{"detail": "Item not found"}'

    # Mock the HTTP client
    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response

    # Test error response
    tool_name = "get_item"
    arguments = {"item_id": 999}  # Non-existent item

    # Execute the tool and expect an exception
    with patch.object(mcp, "_http_client", mock_client):
        with pytest.raises(Exception) as exc_info:
            await mcp._execute_api_tool(
                client=mock_client, tool_name=tool_name, arguments=arguments, operation_map=mcp.operation_map
            )

    # Verify the error message format is unchanged
    error_message = str(exc_info.value)
    assert "Error calling get_item" in error_message
    assert "Status code: 404" in error_message
    assert "Item not found" in error_message


@pytest.mark.asyncio
async def test_operation_map_structure_unchanged(simple_fastapi_app: FastAPI):
    """Test that operation map structure includes new fields but maintains backward compatibility."""
    mcp = FastApiMCP(simple_fastapi_app)

    # Check that operation map has expected structure
    assert "create_item" in mcp.operation_map
    operation = mcp.operation_map["create_item"]

    # Verify existing fields are still present
    assert "path" in operation
    assert "method" in operation
    assert "parameters" in operation
    assert "request_body" in operation

    # Verify new fields are added (but may be None for JSON endpoints)
    assert "content_type" in operation
    assert "form_fields" in operation

    # For JSON endpoints, these should be None or empty
    # (since simple_fastapi_app uses JSON, not form parameters)
    assert operation["content_type"] is None or operation["content_type"] == "application/json"
    assert operation["form_fields"] == []


@pytest.mark.asyncio
async def test_no_content_type_fallback_to_json(simple_fastapi_app: FastAPI):
    """Test that endpoints with no specific content type fall back to JSON behavior."""
    mcp = FastApiMCP(simple_fastapi_app)

    # Mock the HTTP client response
    mock_response = MagicMock()
    mock_response.json.return_value = {"id": 1, "name": "Test Item"}
    mock_response.status_code = 200
    mock_response.text = '{"id": 1, "name": "Test Item"}'

    # Mock the HTTP client
    mock_client = AsyncMock()
    mock_client.request.return_value = mock_response

    # Test POST request without specific content type
    tool_name = "create_item"
    arguments = {"item": {"id": 1, "name": "Test Item", "price": 10.0}}

    # Execute the tool
    with patch.object(mcp, "_http_client", mock_client):
        result = await mcp._execute_api_tool(
            client=mock_client, tool_name=tool_name, arguments=arguments, operation_map=mcp.operation_map
        )

    # Verify the result
    assert len(result) == 1
    assert isinstance(result[0], TextContent)

    # Verify the HTTP client was called with JSON (fallback behavior)
    mock_client.request.assert_called_once_with("post", "/items/", params={}, headers={}, json=arguments)


@pytest.mark.asyncio
async def test_delete_endpoints_unchanged(simple_fastapi_app: FastAPI):
    """Test that DELETE endpoints continue to work unchanged."""
    mcp = FastApiMCP(simple_fastapi_app)

    # Mock the HTTP client response
    mock_response = MagicMock()
    mock_response.json.return_value = None
    mock_response.status_code = 204
    mock_response.text = ""

    # Mock the HTTP client
    mock_client = AsyncMock()
    mock_client.delete.return_value = mock_response

    # Test DELETE request
    tool_name = "delete_item"
    arguments = {"item_id": 1}

    # Execute the tool
    with patch.object(mcp, "_http_client", mock_client):
        result = await mcp._execute_api_tool(
            client=mock_client, tool_name=tool_name, arguments=arguments, operation_map=mcp.operation_map
        )

    # Verify the result
    assert len(result) == 1
    assert isinstance(result[0], TextContent)

    # Verify the HTTP client was called correctly (unchanged)
    mock_client.delete.assert_called_once_with("/items/1", params={}, headers={})


@pytest.mark.asyncio
async def test_response_formatting_unchanged(simple_fastapi_app: FastAPI):
    """Test that response formatting remains unchanged for JSON responses."""
    mcp = FastApiMCP(simple_fastapi_app)

    # Mock the HTTP client response with complex JSON
    complex_response = {
        "id": 1,
        "name": "Test Item",
        "price": 10.0,
        "tags": ["tag1", "tag2"],
        "metadata": {"created_at": "2023-01-01T00:00:00Z", "updated_at": "2023-01-02T00:00:00Z"},
    }
    mock_response = MagicMock()
    mock_response.json.return_value = complex_response
    mock_response.status_code = 200
    mock_response.text = '{"id": 1, "name": "Test Item", "price": 10.0, "tags": ["tag1", "tag2"], "metadata": {"created_at": "2023-01-01T00:00:00Z", "updated_at": "2023-01-02T00:00:00Z"}}'

    # Mock the HTTP client
    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response

    # Test GET request
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

    # Verify the response is properly formatted JSON (unchanged behavior)
    response_text = result[0].text
    assert "id" in response_text
    assert "name" in response_text
    assert "metadata" in response_text
    # Should be formatted with indentation
    assert "  " in response_text  # Indentation indicates JSON formatting


@pytest.mark.asyncio
async def test_header_forwarding_unchanged(simple_fastapi_app: FastAPI):
    """Test that header forwarding behavior remains unchanged."""
    mcp = FastApiMCP(simple_fastapi_app)

    # Mock the HTTP client response
    mock_response = MagicMock()
    mock_response.json.return_value = {"id": 1, "name": "Test Item"}
    mock_response.status_code = 200
    mock_response.text = '{"id": 1, "name": "Test Item"}'

    # Mock the HTTP client
    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response

    # Create HTTP request info with authorization header
    from fastapi_mcp.types import HTTPRequestInfo

    http_request_info = HTTPRequestInfo(
        method="GET",
        path="/test",
        headers={"authorization": "Bearer test-token", "x-custom": "custom-value"},
        cookies={},
        query_params={},
        body=None,
    )

    # Test GET request with header forwarding
    tool_name = "get_item"
    arguments = {"item_id": 1}

    # Execute the tool
    with patch.object(mcp, "_http_client", mock_client):
        result = await mcp._execute_api_tool(
            client=mock_client,
            tool_name=tool_name,
            arguments=arguments,
            operation_map=mcp.operation_map,
            http_request_info=http_request_info,
        )

    # Verify the result
    assert len(result) == 1
    assert isinstance(result[0], TextContent)

    # Verify the HTTP client was called with forwarded authorization header
    # (unchanged behavior - only authorization header should be forwarded by default)
    mock_client.get.assert_called_once_with("/items/1", params={}, headers={"authorization": "Bearer test-token"})


@pytest.mark.asyncio
async def test_mixed_form_and_json_endpoints():
    """Test that form parameter endpoints can coexist with JSON endpoints."""
    from fastapi import FastAPI, Form
    from fastapi_mcp.openapi.convert import convert_openapi_to_mcp_tools
    from fastapi.openapi.utils import get_openapi

    # Create a test app with both JSON and form endpoints
    app = FastAPI(title="Mixed Test App", description="Test app with both JSON and form endpoints")

    @app.post("/json-endpoint", operation_id="json_endpoint")
    async def json_endpoint(data: dict):
        return {"received": data}

    @app.post("/form-endpoint", operation_id="form_endpoint")
    async def form_endpoint(name: str = Form(...), age: int = Form(...)):
        return {"name": name, "age": age}

    # Get OpenAPI schema and convert to MCP tools
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        openapi_version=app.openapi_version,
        description=app.description,
        routes=app.routes,
    )

    tools, operation_map = convert_openapi_to_mcp_tools(openapi_schema)

    # Verify both endpoints are present
    tool_names = [tool.name for tool in tools]
    assert "json_endpoint" in tool_names
    assert "form_endpoint" in tool_names

    # Verify operation map has correct content types
    json_op = operation_map["json_endpoint"]
    form_op = operation_map["form_endpoint"]

    # JSON endpoint should have JSON content type or None (fallback)
    assert json_op["content_type"] in [None, "application/json"]
    assert json_op["form_fields"] == []

    # Form endpoint should have form content type and form fields
    assert form_op["content_type"] == "application/x-www-form-urlencoded"
    assert set(form_op["form_fields"]) == {"name", "age"}


@pytest.mark.asyncio
async def test_content_type_priority_with_multiple_types():
    """Test that content type priority works correctly when multiple types are available."""
    from fastapi_mcp.openapi.convert import _detect_content_type_and_form_fields

    # Mock request body with multiple content types
    request_body = {
        "content": {
            "application/json": {"schema": {"type": "object", "properties": {"data": {"type": "string"}}}},
            "application/x-www-form-urlencoded": {
                "schema": {"type": "object", "properties": {"name": {"type": "string"}, "age": {"type": "integer"}}}
            },
        }
    }

    # Should prioritize form-encoded over JSON
    content_type, form_fields = _detect_content_type_and_form_fields(request_body)
    assert content_type == "application/x-www-form-urlencoded"
    assert set(form_fields) == {"name", "age"}


@pytest.mark.asyncio
async def test_fallback_behavior_on_detection_failure():
    """Test that the system falls back to JSON behavior when content type detection fails."""
    from fastapi_mcp.openapi.convert import _detect_content_type_and_form_fields

    # Mock request body with unsupported content type
    request_body = {"content": {"application/xml": {"schema": {"type": "string"}}}}

    # Should fall back to None (JSON behavior)
    content_type, form_fields = _detect_content_type_and_form_fields(request_body)
    assert content_type is None
    assert form_fields == []


@pytest.mark.asyncio
async def test_empty_request_body_handling():
    """Test that empty or missing request bodies are handled correctly."""
    from fastapi_mcp.openapi.convert import _detect_content_type_and_form_fields

    # Test with empty request body
    content_type, form_fields = _detect_content_type_and_form_fields({})
    assert content_type is None
    assert form_fields == []

    # Test with None request body
    content_type, form_fields = _detect_content_type_and_form_fields(None)
    assert content_type is None
    assert form_fields == []

    # Test with request body without content
    request_body = {"description": "Test endpoint"}
    content_type, form_fields = _detect_content_type_and_form_fields(request_body)
    assert content_type is None
    assert form_fields == []
