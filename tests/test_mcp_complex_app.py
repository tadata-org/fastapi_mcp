import json

import pytest
import mcp.types as types
from mcp.server.lowlevel import Server
from mcp.shared.memory import create_connected_server_and_client_session
from fastapi import FastAPI

from fastapi_mcp import FastApiMCP

from .fixtures.types import Product, Customer, OrderResponse


@pytest.fixture
def fastapi_mcp(complex_fastapi_app: FastAPI) -> FastApiMCP:
    mcp = FastApiMCP(
        complex_fastapi_app,
        name="Test MCP Server",
        description="Test description",
    )
    mcp.mount()
    return mcp


@pytest.fixture
def lowlevel_server_complex_app(fastapi_mcp: FastApiMCP) -> Server:
    return fastapi_mcp.server


@pytest.mark.asyncio
async def test_list_tools(lowlevel_server_complex_app: Server):
    async with create_connected_server_and_client_session(lowlevel_server_complex_app) as client_session:
        tools_result = await client_session.list_tools()

        assert len(tools_result.tools) > 0

        tool_names = [tool.name for tool in tools_result.tools]
        expected_operations = ["list_products", "get_product", "create_order", "get_customer"]
        for op in expected_operations:
            assert op in tool_names


@pytest.mark.asyncio
async def test_call_tool_list_products_default(lowlevel_server_complex_app: Server):
    async with create_connected_server_and_client_session(lowlevel_server_complex_app) as client_session:
        response = await client_session.call_tool("list_products", {})

        assert not response.isError
        assert len(response.content) > 0

        text_content = next(c for c in response.content if isinstance(c, types.TextContent))
        result = json.loads(text_content.text)

        assert "items" in result
        assert result["total"] == 1
        assert result["page"] == 1
        assert len(result["items"]) == 1


@pytest.mark.asyncio
async def test_call_tool_list_products_with_filters(lowlevel_server_complex_app: Server):
    async with create_connected_server_and_client_session(lowlevel_server_complex_app) as client_session:
        response = await client_session.call_tool(
            "list_products",
            {"category": "electronics", "min_price": 10.0, "page": 1, "size": 10, "in_stock_only": True},
        )

        assert not response.isError
        assert len(response.content) > 0

        text_content = next(c for c in response.content if isinstance(c, types.TextContent))
        result = json.loads(text_content.text)

        assert "items" in result
        assert result["page"] == 1
        assert result["size"] == 10


@pytest.mark.asyncio
async def test_call_tool_get_product(lowlevel_server_complex_app: Server, example_product: Product):
    product_id = "123e4567-e89b-12d3-a456-426614174000"  # Valid UUID format

    async with create_connected_server_and_client_session(lowlevel_server_complex_app) as client_session:
        response = await client_session.call_tool("get_product", {"product_id": product_id})

        assert not response.isError
        assert len(response.content) > 0

        text_content = next(c for c in response.content if isinstance(c, types.TextContent))
        result = json.loads(text_content.text)

        assert result["id"] == product_id
        assert "name" in result
        assert "price" in result
        assert "description" in result


@pytest.mark.asyncio
async def test_call_tool_get_product_with_options(lowlevel_server_complex_app: Server):
    product_id = "123e4567-e89b-12d3-a456-426614174000"  # Valid UUID format

    async with create_connected_server_and_client_session(lowlevel_server_complex_app) as client_session:
        response = await client_session.call_tool(
            "get_product", {"product_id": product_id, "include_unavailable": True}
        )

        assert not response.isError
        assert len(response.content) > 0

        text_content = next(c for c in response.content if isinstance(c, types.TextContent))
        result = json.loads(text_content.text)

        assert result["id"] == product_id


@pytest.mark.asyncio
async def test_call_tool_create_order(lowlevel_server_complex_app: Server, example_order_response: OrderResponse):
    customer_id = "123e4567-e89b-12d3-a456-426614174000"  # Valid UUID format
    product_id = "123e4567-e89b-12d3-a456-426614174001"  # Valid UUID format
    shipping_address_id = "123e4567-e89b-12d3-a456-426614174002"  # Valid UUID format

    order_request = {
        "customer_id": customer_id,
        "items": [{"product_id": product_id, "quantity": 2, "unit_price": 29.99, "total": 59.98}],
        "shipping_address_id": shipping_address_id,
        "payment_method": "credit_card",
    }

    async with create_connected_server_and_client_session(lowlevel_server_complex_app) as client_session:
        response = await client_session.call_tool("create_order", order_request)

        assert not response.isError
        assert len(response.content) > 0

        text_content = next(c for c in response.content if isinstance(c, types.TextContent))
        result = json.loads(text_content.text)

        assert result["customer_id"] == customer_id
        assert "id" in result
        assert "status" in result
        assert "items" in result
        assert len(result["items"]) > 0


@pytest.mark.asyncio
async def test_call_tool_create_order_validation_error(lowlevel_server_complex_app: Server):
    # Missing required fields
    order_request = {
        # Missing customer_id
        "items": [],
        # Missing shipping_address_id
        "payment_method": "credit_card",
    }

    async with create_connected_server_and_client_session(lowlevel_server_complex_app) as client_session:
        response = await client_session.call_tool("create_order", order_request)

        assert response.isError
        assert len(response.content) > 0

        text_content = next(c for c in response.content if isinstance(c, types.TextContent))
        assert "422" in text_content.text or "validation" in text_content.text.lower()


@pytest.mark.asyncio
async def test_call_tool_get_customer(lowlevel_server_complex_app: Server, example_customer: Customer):
    customer_id = "123e4567-e89b-12d3-a456-426614174000"  # Valid UUID format

    async with create_connected_server_and_client_session(lowlevel_server_complex_app) as client_session:
        response = await client_session.call_tool("get_customer", {"customer_id": customer_id})

        assert not response.isError
        assert len(response.content) > 0

        text_content = next(c for c in response.content if isinstance(c, types.TextContent))
        result = json.loads(text_content.text)

        assert result["id"] == customer_id
        assert "full_name" in result
        assert "email" in result


@pytest.mark.asyncio
async def test_call_tool_get_customer_with_options(lowlevel_server_complex_app: Server):
    customer_id = "123e4567-e89b-12d3-a456-426614174000"  # Valid UUID format

    async with create_connected_server_and_client_session(lowlevel_server_complex_app) as client_session:
        response = await client_session.call_tool(
            "get_customer",
            {
                "customer_id": customer_id,
                "include_orders": True,
                "include_payment_methods": True,
                "fields": ["full_name", "email", "orders"],
            },
        )

        assert not response.isError
        assert len(response.content) > 0

        text_content = next(c for c in response.content if isinstance(c, types.TextContent))
        result = json.loads(text_content.text)

        assert result["id"] == customer_id


@pytest.mark.asyncio
async def test_error_handling_missing_parameter(lowlevel_server_complex_app: Server):
    async with create_connected_server_and_client_session(lowlevel_server_complex_app) as client_session:
        # Missing required product_id parameter
        response = await client_session.call_tool("get_product", {})

        assert response.isError
        assert len(response.content) > 0

        text_content = next(c for c in response.content if isinstance(c, types.TextContent))
        assert (
            "422" in text_content.text
            or "parameter" in text_content.text.lower()
            or "field" in text_content.text.lower()
        )
