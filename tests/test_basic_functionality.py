from fastapi import FastAPI
from mcp.server.lowlevel.server import Server

from fastapi_mcp import FastApiMCP


def test_create_mcp_server(simple_fastapi_app: FastAPI):
    """Test creating an MCP server without mounting it."""
    mcp = FastApiMCP(
        simple_fastapi_app,
        name="Test MCP Server",
        description="Test description",
    )

    # Verify the MCP server was created correctly
    assert mcp.name == "Test MCP Server"
    assert mcp.description == "Test description"
    assert isinstance(mcp.server, Server)
    assert len(mcp.tools) > 0, "Should have extracted tools from the app"
    assert len(mcp.operation_map) > 0, "Should have operation mapping"

    # Check that the operation map contains all expected operations from simple_app
    expected_operations = ["list_items", "get_item", "create_item", "update_item", "delete_item", "raise_error"]
    for op in expected_operations:
        assert op in mcp.operation_map, f"Operation {op} not found in operation map"


def test_default_values(simple_fastapi_app: FastAPI):
    """Test that default values are used when not explicitly provided."""
    mcp = FastApiMCP(simple_fastapi_app)

    # Verify default values
    assert mcp.name == simple_fastapi_app.title
    assert mcp.description == simple_fastapi_app.description

    # Mount with default path
    mcp.mount()

    # Check that the MCP server was properly mounted
    # Look for a route that includes our mount path in its pattern
    route_found = any("/mcp" in str(route) for route in simple_fastapi_app.routes)
    assert route_found, "MCP server mount point not found in app routes"


def test_normalize_paths(simple_fastapi_app: FastAPI):
    """Test that mount paths are normalized correctly."""
    mcp = FastApiMCP(simple_fastapi_app)

    # Test with path without leading slash
    mount_path = "test-mcp"
    mcp.mount(mount_path=mount_path)

    # Check that the route was added with a normalized path
    route_found = any("/test-mcp" in str(route) for route in simple_fastapi_app.routes)
    assert route_found, "Normalized mount path not found in app routes"

    # Create a new MCP server
    mcp2 = FastApiMCP(simple_fastapi_app)

    # Test with path with trailing slash
    mount_path = "/test-mcp2/"
    mcp2.mount(mount_path=mount_path)

    # Check that the route was added with a normalized path
    route_found = any("/test-mcp2" in str(route) for route in simple_fastapi_app.routes)
    assert route_found, "Normalized mount path not found in app routes"
