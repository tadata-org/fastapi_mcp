from unittest.mock import patch, Mock
from fastapi import FastAPI, APIRouter
import mcp.types as types

from fastapi_mcp import FastApiMCP


def test_warn_if_too_many_tools():
    """Test that a warning is issued when there are too many tools."""
    # Create a simple app
    app = FastAPI()
    
    # Create tools list with more than 10 tools
    tools = [
        types.Tool(
            name=f"tool_{i}", 
            description="A test tool",
            inputSchema={"type": "object", "properties": {}, "title": f"Tool{i}Arguments"}
        ) for i in range(11)
    ]
    
    # Create FastApiMCP instance
    mcp_server = FastApiMCP(app)
    
    # Patch the logger.warning method
    with patch("fastapi_mcp.server.logger.warning") as mock_warning:
        # Call the warning method
        mcp_server._warn_if_too_many_tools(tools)
        
        # Check that warning was called with the correct message
        mock_warning.assert_called_once()
        assert "More than 10 tools exposed (11)" in mock_warning.call_args[0][0]
        assert "To disable this warning" in mock_warning.call_args[0][0]


def test_warn_if_too_many_tools_no_warning():
    """Test that no warning is issued when there are 10 or fewer tools."""
    # Create a simple app
    app = FastAPI()
    
    # Create tools list with exactly 10 tools
    tools = [
        types.Tool(
            name=f"tool_{i}", 
            description="A test tool",
            inputSchema={"type": "object", "properties": {}, "title": f"Tool{i}Arguments"}
        ) for i in range(10)
    ]
    
    # Create FastApiMCP instance
    mcp_server = FastApiMCP(app)
    
    # Patch the logger.warning method
    with patch("fastapi_mcp.server.logger.warning") as mock_warning:
        # Call the warning method
        mcp_server._warn_if_too_many_tools(tools)
        
        # Check that warning was not called
        mock_warning.assert_not_called()


def test_warn_if_non_get_endpoints():
    """Test that a warning is issued when there are non-GET endpoints."""
    # Create a simple app
    app = FastAPI()
    
    # Create FastApiMCP instance
    mcp_server = FastApiMCP(app)
    
    # Create a list of non-GET tools
    non_get_tools = ["create_item (POST)", "update_item (PUT)", "delete_item (DELETE)"]
    
    # Patch the logger.warning method
    with patch("fastapi_mcp.server.logger.warning") as mock_warning:
        # Call the warning method
        mcp_server._warn_if_non_get_endpoints(non_get_tools)
        
        # Check that warning was called with the correct message
        mock_warning.assert_called_once()
        warning_msg = mock_warning.call_args[0][0]
        assert "Non-GET endpoints exposed as tools:" in warning_msg
        for tool in non_get_tools:
            assert tool in warning_msg
        assert "To disable this warning" in warning_msg


def test_warn_if_non_get_endpoints_no_warning():
    """Test that no warning is issued when there are no non-GET endpoints."""
    # Create a simple app
    app = FastAPI()
    
    # Create FastApiMCP instance
    mcp_server = FastApiMCP(app)
    
    # Create an empty list of non-GET tools
    non_get_tools = []
    
    # Patch the logger.warning method
    with patch("fastapi_mcp.server.logger.warning") as mock_warning:
        # Call the warning method
        mcp_server._warn_if_non_get_endpoints(non_get_tools)
        
        # Check that warning was not called
        mock_warning.assert_not_called()


def test_warn_if_auto_generated_operation_ids():
    """Test that warnings are issued for auto-generated operation IDs."""
    # Create a simple app
    app = FastAPI()
    
    # Create FastApiMCP instance
    mcp_server = FastApiMCP(app)
    
    # Create tools with auto-generated operation IDs
    tools = [
        types.Tool(
            name="items__get", 
            description="Double underscore",
            inputSchema={"type": "object", "properties": {}, "title": "Items__getArguments"}
        ),
        types.Tool(
            name="items_get", 
            description="Single underscore + method",
            inputSchema={"type": "object", "properties": {}, "title": "Items_getArguments"}
        ),
        types.Tool(
            name="users__post", 
            description="Double underscore + POST",
            inputSchema={"type": "object", "properties": {}, "title": "Users__postArguments"}
        ),
        types.Tool(
            name="normal_name", 
            description="Normal name without patterns",
            inputSchema={"type": "object", "properties": {}, "title": "NormalNameArguments"}
        )
    ]
    
    # Patch the logger.warning method
    with patch("fastapi_mcp.server.logger.warning") as mock_warning:
        # Call the warning method
        mcp_server._warn_if_auto_generated_operation_ids(tools)
        
        # Check that warning was called three times (for the first three tools)
        assert mock_warning.call_count == 3
        
        # Check the warning messages
        warnings = [call[0][0] for call in mock_warning.call_args_list]
        assert any("Tool 'items__get'" in warning for warning in warnings)
        assert any("Tool 'items_get'" in warning for warning in warnings)
        assert any("Tool 'users__post'" in warning for warning in warnings)
        assert not any("Tool 'normal_name'" in warning for warning in warnings)
        assert all("To disable this warning" in warning for warning in warnings)


def test_warn_if_auto_generated_operation_ids_no_warning():
    """Test that no warnings are issued when there are no auto-generated operation IDs."""
    # Create a simple app
    app = FastAPI()
    
    # Create FastApiMCP instance
    mcp_server = FastApiMCP(app)
    
    # Create tools without auto-generated operation IDs
    tools = [
        types.Tool(
            name="list_items", 
            description="Normal name",
            inputSchema={"type": "object", "properties": {}, "title": "ListItemsArguments"}
        ),
        types.Tool(
            name="get_item", 
            description="Normal name",
            inputSchema={"type": "object", "properties": {}, "title": "GetItemArguments"}
        ),
        types.Tool(
            name="search", 
            description="Normal name",
            inputSchema={"type": "object", "properties": {}, "title": "SearchArguments"}
        )
    ]
    
    # Patch the logger.warning method
    with patch("fastapi_mcp.server.logger.warning") as mock_warning:
        # Call the warning method
        mcp_server._warn_if_auto_generated_operation_ids(tools)
        
        # Check that warning was not called
        mock_warning.assert_not_called()


def test_disable_all_warnings():
    """Test that all warnings can be disabled via the disable_warnings parameter."""
    # Create a simple app
    app = FastAPI()
    
    # Create FastApiMCP instance with warnings disabled
    mcp_server = FastApiMCP(app, disable_warnings=True)
    
    # Create test data that would normally trigger warnings
    tools = [
        types.Tool(
            name=f"tool_{i}", 
            description="A test tool",
            inputSchema={"type": "object", "properties": {}, "title": f"Tool{i}Arguments"}
        ) for i in range(11)
    ]
    tools.append(
        types.Tool(
            name="items__get", 
            description="Double underscore",
            inputSchema={"type": "object", "properties": {}, "title": "Items__getArguments"}
        )
    )
    non_get_tools = ["create_item (POST)", "update_item (PUT)"]
    
    # Patch the logger.warning method
    with patch("fastapi_mcp.server.logger.warning") as mock_warning:
        # Call all warning methods
        mcp_server._warn_if_too_many_tools(tools)
        mcp_server._warn_if_non_get_endpoints(non_get_tools)
        mcp_server._warn_if_auto_generated_operation_ids(tools)
        
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
        
        # Create FastApiMCP instance which will trigger the setup_server method
        FastApiMCP(app)
        
        # Verify that each warning method was called at least once
        mock_too_many_tools.assert_called_once()
        mock_non_get_endpoints.assert_called_once()
        mock_auto_gen_ids.assert_called_once()
        
        # You can also check what arguments were passed to the methods
        tools_arg = mock_too_many_tools.call_args[0][0]
        assert len(tools_arg) > 10, "Expected more than 10 tools to trigger warning"
        
        non_get_tools_arg = mock_non_get_endpoints.call_args[0][0]
        assert any("POST" in tool for tool in non_get_tools_arg), "Expected a POST tool to be identified"
        
        auto_gen_tools_arg = mock_auto_gen_ids.call_args[0][0]
        assert any("__get" in tool.name for tool in auto_gen_tools_arg), "Expected a tool with auto-generated ID"


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
    """Test that the warning methods are called during server setup with proper arguments."""
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
        
        # Verify that each method was called
        too_many_spy.assert_called_once()
        non_get_spy.assert_called_once()
        auto_gen_spy.assert_called_once()
        
        # Verify that the arguments to each method were of the correct type
        assert isinstance(too_many_spy.call_args[0][0], list), "First argument should be the tools list"
        assert isinstance(non_get_spy.call_args[0][0], list), "First argument should be the non_get_tools list"
        assert isinstance(auto_gen_spy.call_args[0][0], list), "First argument should be the tools list" 