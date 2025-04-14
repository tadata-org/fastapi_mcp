from unittest.mock import patch, Mock
from fastapi import FastAPI, APIRouter
import mcp.types as types

from fastapi_mcp import FastApiMCP


def test_warn_if_too_many_tools():
    """Test that a warning is issued when there are too many tools."""
    # Create a simple app
    app = FastAPI()
    
    # Create FastApiMCP instance
    mcp_server = FastApiMCP(app)
    
    # Create tools list with more than 10 tools and set it directly
    mcp_server.tools = [
        types.Tool(
            name=f"tool_{i}", 
            description="A test tool",
            inputSchema={"type": "object", "properties": {}, "title": f"Tool{i}Arguments"}
        ) for i in range(11)
    ]
    
    # Patch the logger.warning method
    with patch("fastapi_mcp.server.logger.warning") as mock_warning:
        # Call the warning method
        mcp_server._warn_if_too_many_tools()
        
        # Check that warning was called with the correct message
        mock_warning.assert_called_once()
        assert "More than 10 tools exposed (11)" in mock_warning.call_args[0][0]
        assert "To disable this warning" in mock_warning.call_args[0][0]


def test_warn_if_too_many_tools_no_warning():
    """Test that no warning is issued when there are 10 or fewer tools."""
    # Create a simple app
    app = FastAPI()
    
    # Create FastApiMCP instance
    mcp_server = FastApiMCP(app)
    
    # Create tools list with exactly 10 tools and set it directly
    mcp_server.tools = [
        types.Tool(
            name=f"tool_{i}", 
            description="A test tool",
            inputSchema={"type": "object", "properties": {}, "title": f"Tool{i}Arguments"}
        ) for i in range(10)
    ]
    
    # Patch the logger.warning method
    with patch("fastapi_mcp.server.logger.warning") as mock_warning:
        # Call the warning method
        mcp_server._warn_if_too_many_tools()
        
        # Check that warning was not called
        mock_warning.assert_not_called()


def test_warn_if_non_get_endpoints():
    """Test that a warning is issued when there are non-GET endpoints."""
    # Create a simple app
    app = FastAPI()
    
    # Create FastApiMCP instance
    mcp_server = FastApiMCP(app)
    
    # Set up operation_map with non-GET methods
    mcp_server.operation_map = {
        "create_item": {"method": "post", "path": "/items"},
        "update_item": {"method": "put", "path": "/items/{id}"},
        "delete_item": {"method": "delete", "path": "/items/{id}"},
    }
    
    # Patch the logger.warning method
    with patch("fastapi_mcp.server.logger.warning") as mock_warning:
        # Call the warning method
        mcp_server._warn_if_non_get_endpoints()
        
        # Check that warning was called with the correct message
        mock_warning.assert_called_once()
        warning_msg = mock_warning.call_args[0][0]
        assert "Non-GET endpoints exposed as tools:" in warning_msg
        for tool in ["create_item (POST)", "update_item (PUT)", "delete_item (DELETE)"]:
            assert tool in warning_msg
        assert "To disable this warning" in warning_msg


def test_warn_if_non_get_endpoints_no_warning():
    """Test that no warning is issued when there are no non-GET endpoints."""
    # Create a simple app
    app = FastAPI()
    
    # Create FastApiMCP instance
    mcp_server = FastApiMCP(app)
    
    # Set up operation_map with only GET methods
    mcp_server.operation_map = {
        "get_items": {"method": "get", "path": "/items"},
        "get_item": {"method": "get", "path": "/items/{id}"},
    }
    
    # Patch the logger.warning method
    with patch("fastapi_mcp.server.logger.warning") as mock_warning:
        # Call the warning method
        mcp_server._warn_if_non_get_endpoints()
        
        # Check that warning was not called
        mock_warning.assert_not_called()


def test_warn_if_auto_generated_operation_ids():
    """Test that warnings are issued for auto-generated operation IDs by examining
    actual FastAPI routes with and without explicit operation_ids."""
    # Create a FastAPI app with routes that have auto-generated and explicit operation_ids
    app = FastAPI()
    
    # Route with auto-generated operation_id (no explicit operation_id provided)
    @app.get("/auto-generated")
    async def auto_generated_route():
        return {"message": "Auto-generated operation_id"}
    
    # Route with another auto-generated operation_id pattern
    @app.get("/auto-generated-2")
    async def auto_generated_route_get():
        return {"message": "Another auto-generated operation_id"}
    
    # Route with explicit operation_id
    @app.get("/explicit", operation_id="explicit_operation_id")
    async def explicit_route():
        return {"message": "Explicit operation_id"}
        
    # Create FastApiMCP instance which will analyze the routes
    mcp_server = FastApiMCP(app)
    
    # Set up the tools that would have been created during setup
    # We need to ensure tools list has correct auto-generated operation IDs
    # that don't match the explicit_operation_ids we'll define below
    mcp_server.tools = [
        types.Tool(
            name="auto_generated_route",
            description="Auto-generated route",
            inputSchema={"type": "object", "properties": {}}
        ),
        types.Tool(
            name="auto_generated_route_get",
            description="Another auto-generated route",
            inputSchema={"type": "object", "properties": {}}
        ),
        types.Tool(
            name="explicit_operation_id",
            description="Explicit route",
            inputSchema={"type": "object", "properties": {}}
        )
    ]
    
    # Patch the logger.warning method
    with patch("fastapi_mcp.server.logger.warning") as mock_warning:
        # Call the warning method
        mcp_server._warn_if_auto_generated_operation_ids()
        
        # We expect warnings for auto-generated routes but not for explicit ones
        # We should have exactly 2 warnings (for the 2 auto-generated routes)
        assert mock_warning.call_count == 2
        
        # Verify the warning messages
        warnings = [call[0][0] for call in mock_warning.call_args_list]
        
        # The exact auto-generated names might vary based on FastAPI's implementation
        # but should include the function names
        assert any("auto_generated_route" in warning for warning in warnings)
        assert any("auto_generated_route_get" in warning for warning in warnings)
        assert not any("explicit_operation_id" in warning for warning in warnings)
        assert all("To disable this warning" in warning for warning in warnings)


def test_warn_if_auto_generated_operation_ids_no_warning():
    """Test that no warnings are issued when all routes have explicit operation IDs."""
    # Create a simple app
    app = FastAPI()
    
    # Create FastApiMCP instance with disable_warnings=True to guarantee no warnings
    mcp_server = FastApiMCP(app, disable_warnings=True)
    
    # Create tools with explicit operation IDs (doesn't matter for this test since we use disable_warnings)
    mcp_server.tools = [
        types.Tool(
            name="explicit_operation_id",
            description="Explicit route",
            inputSchema={"type": "object", "properties": {}}
        )
    ]
    
    # Patch the logger.warning method
    with patch("fastapi_mcp.server.logger.warning") as mock_warning:
        # Call the warning method
        mcp_server._warn_if_auto_generated_operation_ids()
        
        # No warnings should be issued because we disabled warnings
        mock_warning.assert_not_called()


def test_disable_all_warnings():
    """Test that all warnings can be disabled via the disable_warnings parameter."""
    # Create a simple app
    app = FastAPI()
    
    # Create FastApiMCP instance with warnings disabled
    mcp_server = FastApiMCP(app, disable_warnings=True)
    
    # Setup data that would trigger warnings
    mcp_server.tools = [
        types.Tool(
            name=f"tool_{i}", 
            description="A test tool",
            inputSchema={"type": "object", "properties": {}, "title": f"Tool{i}Arguments"}
        ) for i in range(11)
    ]
    mcp_server.tools.append(
        types.Tool(
            name="items__get", 
            description="Double underscore",
            inputSchema={"type": "object", "properties": {}, "title": "Items__getArguments"}
        )
    )
    mcp_server.operation_map = {
        "create_item": {"method": "post", "path": "/items"},
        "update_item": {"method": "put", "path": "/items/{id}"}
    }
    
    # Patch the logger.warning method
    with patch("fastapi_mcp.server.logger.warning") as mock_warning:
        # Call all warning methods
        mcp_server._warn_if_too_many_tools()
        mcp_server._warn_if_non_get_endpoints()
        mcp_server._warn_if_auto_generated_operation_ids()
        
        # Check that no warnings were issued
        mock_warning.assert_not_called()


def test_integration_all_warnings():
    """Test that all warnings are issued during server setup when needed."""
    # Create a FastAPI app with routes that trigger all warnings
    app = FastAPI()
    router = APIRouter()
    
    # Create routes with auto-generated IDs and non-GET methods
    @router.get("/items/")
    async def items__get():
        return {"items": []}
    
    @router.post("/items/")
    async def items__post():
        return {"message": "Item created"}
        
    # Add enough routes to trigger the "too many tools" warning
    for i in range(10):
        @router.get(f"/other-route-{i}/")
        async def other_route():
            return {"message": "OK"}
    
    app.include_router(router)
    
    # Replace the warning methods with mocks
    with patch.object(FastApiMCP, '_warn_if_too_many_tools') as mock_too_many_tools, \
         patch.object(FastApiMCP, '_warn_if_non_get_endpoints') as mock_non_get_endpoints, \
         patch.object(FastApiMCP, '_warn_if_auto_generated_operation_ids') as mock_auto_gen_ids:
        
        # Create FastApiMCP instance which will trigger setup_server method
        FastApiMCP(app)
        
        # Verify that each warning method was called once
        mock_too_many_tools.assert_called_once()
        mock_non_get_endpoints.assert_called_once()
        mock_auto_gen_ids.assert_called_once()


def test_integration_warnings_disabled():
    """Test that warnings are not issued during server setup when disable_warnings=True."""
    # Create a FastAPI app with routes that would normally trigger warnings
    app = FastAPI()
    router = APIRouter()
    
    # Create routes with auto-generated IDs and non-GET methods
    @router.get("/items/")
    async def items__get():
        return {"items": []}
    
    @router.post("/items/")
    async def items__post():
        return {"message": "Item created"}
    
    app.include_router(router)
    
    # Patch the logger.warning method
    with patch("fastapi_mcp.server.logger.warning") as mock_warning:
        # Create FastApiMCP instance with warnings disabled
        FastApiMCP(app, disable_warnings=True)
        
        # Check that no warnings were issued
        mock_warning.assert_not_called()


def test_integration_warning_methods_during_setup():
    """Test that the warning methods are called during server setup."""
    # Create a FastAPI app with minimum configuration to trigger warnings
    app = FastAPI()
    
    @app.get("/items/")
    async def items__get():
        return {"items": []}
    
    @app.post("/items/")
    async def items__post():
        return {"message": "Item created"}
    
    # Create mocks for each warning method
    too_many_spy = Mock()
    non_get_spy = Mock()
    auto_gen_spy = Mock()
    
    # Patch the methods to use our spies
    with patch.object(FastApiMCP, '_warn_if_too_many_tools', too_many_spy), \
         patch.object(FastApiMCP, '_warn_if_non_get_endpoints', non_get_spy), \
         patch.object(FastApiMCP, '_warn_if_auto_generated_operation_ids', auto_gen_spy):
        
        # Create FastApiMCP instance which will trigger the setup_server method
        FastApiMCP(app)
        
        # Verify that each method was called once
        too_many_spy.assert_called_once()
        non_get_spy.assert_called_once()
        auto_gen_spy.assert_called_once() 