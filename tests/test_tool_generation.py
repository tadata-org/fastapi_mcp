import pytest
from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional

from fastapi_mcp import add_mcp_server


class Item(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    price: float
    tags: List[str] = []


@pytest.fixture
def sample_app():
    """Create a sample FastAPI app for testing."""
    app = FastAPI(
        title="Test API",
        description="A test API for unit testing",
        version="0.1.0",
    )

    @app.get("/items/", response_model=List[Item], tags=["items"])
    async def list_items(skip: int = 0, limit: int = 10):
        """
        List all items.

        Returns a list of items, with pagination support.
        """
        return []

    @app.get("/items/{item_id}", response_model=Item, tags=["items"])
    async def read_item(item_id: int):
        """
        Get a specific item by ID.

        Returns the item with the specified ID.
        """
        return {"id": item_id, "name": "Test Item", "price": 0.0}

    @app.post("/items/", response_model=Item, tags=["items"])
    async def create_item(item: Item):
        """
        Create a new item.

        Returns the created item.
        """
        return item

    return app


def test_tool_generation_basic(sample_app):
    """Test that MCP tools are properly generated with default settings."""
    # Create MCP server and register tools
    mcp_server = add_mcp_server(sample_app, serve_tools=True, base_url="http://localhost:8000")

    # Extract tools for inspection
    tools = mcp_server._tool_manager.list_tools()

    # Tool count may include the MCP endpoint itself, so check for at least the API endpoints
    assert len(tools) >= 3, f"Expected at least 3 tools, got {len(tools)}"

    # Check each tool has required properties
    for tool in tools:
        assert hasattr(tool, "name"), "Tool missing 'name' property"
        assert hasattr(tool, "description"), "Tool missing 'description' property"
        assert hasattr(tool, "parameters"), "Tool missing 'parameters' property"
        assert hasattr(tool, "fn_metadata"), "Tool missing 'fn_metadata' property"

        # With describe_all_responses=False by default, description should only include success response code
        assert "200" in tool.description, f"Expected success response code in description for {tool.name}"
        assert "422" not in tool.description, f"Expected not to see 422 response in tool description for {tool.name}"

        # With describe_full_response_schema=False by default, description should not include the full output schema, only an example
        assert "Example Response" in tool.description, f"Expected example response in description for {tool.name}"
        assert "Output Schema" not in tool.description, (
            f"Expected not to see output schema in description for {tool.name}"
        )

    # Verify specific parameters are present in the appropriate tools
    list_items_tool = next((t for t in tools if t.name == "list_items_items__get"), None)
    assert list_items_tool is not None, "list_items tool not found"
    assert "skip" in list_items_tool.parameters["properties"], "Expected 'skip' parameter"
    assert "limit" in list_items_tool.parameters["properties"], "Expected 'limit' parameter"


def test_tool_generation_with_full_schema(sample_app):
    """Test that MCP tools include full response schema when requested."""
    # Create MCP server with full schema for all operations
    mcp_server = add_mcp_server(
        sample_app, serve_tools=True, base_url="http://localhost:8000", describe_full_response_schema=True
    )

    # Extract tools for inspection
    tools = mcp_server._tool_manager.list_tools()

    # Check all tools have the appropriate schema information
    for tool in tools:
        description = tool.description
        # Check that the tool includes information about the Item schema
        assert "Item" in description, f"Item schema should be included in the description for {tool.name}"
        assert "price" in description, f"Item properties should be included in the description for {tool.name}"


def test_tool_generation_with_all_responses(sample_app):
    """Test that MCP tools include all possible responses when requested."""
    # Create MCP server with all response status codes
    mcp_server = add_mcp_server(
        sample_app, serve_tools=True, base_url="http://localhost:8000", describe_all_responses=True
    )

    # Extract tools for inspection
    tools = mcp_server._tool_manager.list_tools()

    # Check all API tools include all response status codes
    for tool in tools:
        assert "200" in tool.description, f"Expected success response code in description for {tool.name}"
        assert "422" in tool.description, f"Expected 422 response code in description for {tool.name}"


def test_tool_generation_with_all_responses_and_full_schema(sample_app):
    """Test that MCP tools include all possible responses and full schema when requested."""
    # Create MCP server with all response status codes and full schema
    mcp_server = add_mcp_server(
        sample_app,
        serve_tools=True,
        base_url="http://localhost:8000",
        describe_all_responses=True,
        describe_full_response_schema=True,
    )

    # Extract tools for inspection
    tools = mcp_server._tool_manager.list_tools()

    # Check all tools include all response status codes and the full output schema
    for tool in tools:
        assert "200" in tool.description, f"Expected success response code in description for {tool.name}"
        assert "422" in tool.description, f"Expected 422 response code in description for {tool.name}"
        assert "Output Schema" in tool.description, f"Expected output schema in description for {tool.name}"


def test_custom_tool_addition(sample_app):
    """Test that custom tools can be added alongside API tools."""
    # Create MCP server with API tools
    mcp_server = add_mcp_server(sample_app, serve_tools=True, base_url="http://localhost:8000")

    # Get initial tool count
    initial_tool_count = len(mcp_server._tool_manager.list_tools())

    # Add a custom tool
    @mcp_server.tool()
    async def custom_tool() -> str:
        """A custom tool for testing."""
        return "Test result"

    # Extract tools for inspection
    tools = mcp_server._tool_manager.list_tools()

    # Verify we have one more tool than before
    assert len(tools) == initial_tool_count + 1, f"Expected {initial_tool_count + 1} tools, got {len(tools)}"

    # Find both API tools and custom tools
    list_items_tool = next((t for t in tools if t.name == "list_items_items__get"), None)
    assert list_items_tool is not None, "API tool (list_items) not found"

    custom_tool_def = next((t for t in tools if t.name == "custom_tool"), None)
    assert custom_tool_def is not None, "Custom tool not found"
    assert custom_tool_def.description == "A custom tool for testing.", "Custom tool description not preserved"
