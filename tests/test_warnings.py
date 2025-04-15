import pytest
from fastapi import FastAPI, APIRouter
from fastapi_mcp import FastApiMCP
import logging


@pytest.fixture
def app_with_too_many_tools():
    """Create a FastAPI app with more than 10 endpoints to trigger the 'too many tools' warning."""
    app = FastAPI(
        title="App with Too Many Tools",
        description="An app with more than 10 endpoints to test warnings",
    )
    
    # Create more than 10 GET endpoints
    for i in range(11):
        @app.get(f"/items/{i}", operation_id=f"get_item_{i}")
        async def get_item(item_id: int = i):
            return {"item_id": item_id, "name": f"Item {item_id}"}
    
    return app


@pytest.fixture
def app_with_non_get_endpoints():
    """Create a FastAPI app with non-GET endpoints to trigger the warning."""
    app = FastAPI(
        title="App with Non-GET Endpoints",
        description="An app with various HTTP methods to test warnings",
    )
    
    @app.get("/items", operation_id="list_items")
    async def list_items():
        return [{"id": 1, "name": "Item 1"}, {"id": 2, "name": "Item 2"}]
    
    @app.post("/items", operation_id="create_item")
    async def create_item(item: dict):
        return {"id": 3, **item}
    
    @app.put("/items/{item_id}", operation_id="update_item")
    async def update_item(item_id: int, item: dict):
        return {"id": item_id, **item}
    
    @app.delete("/items/{item_id}", operation_id="delete_item")
    async def delete_item(item_id: int):
        return {"message": f"Item {item_id} deleted"}
    
    return app


@pytest.fixture
def app_with_auto_generated_ids():
    """Create a FastAPI app with auto-generated operation IDs to trigger the warning."""
    app = FastAPI(
        title="App with Auto-generated IDs",
        description="An app with auto-generated operation IDs to test warnings",
    )
    
    # Routes with auto-generated operation IDs (no explicit operation_id provided)
    @app.get("/auto-generated")
    async def auto_generated_route():
        return {"message": "Auto-generated operation_id"}
    
    @app.get("/auto-generated-2")
    async def auto_generated_route_get():
        return {"message": "Another auto-generated operation_id"}
    
    # Route with explicit operation_id
    @app.get("/explicit", operation_id="explicit_operation_id")
    async def explicit_route():
        return {"message": "Explicit operation_id"}
    
    return app


def test_warn_if_too_many_tools(app_with_too_many_tools, caplog):
    """Test that a warning is issued when there are too many tools."""
    # Set up logging capture
    caplog.set_level(logging.WARNING)
    
    # Create FastApiMCP instance
    _ = FastApiMCP(app_with_too_many_tools)
    
    # Check that warning was logged
    assert any("More than 10 tools exposed" in record.message for record in caplog.records)
    assert any("To disable this warning" in record.message for record in caplog.records)


def test_warn_if_too_many_tools_no_warning(app_with_too_many_tools, caplog):
    """Test that no warning is issued when disable_warnings=True."""
    # Set up logging capture
    caplog.set_level(logging.WARNING)
    
    # Create FastApiMCP instance with warnings disabled
    _ = FastApiMCP(app_with_too_many_tools, disable_warnings=True)
    
    # Check that no warning was logged
    assert not any("More than 10 tools exposed" in record.message for record in caplog.records)


def test_warn_if_non_get_endpoints(app_with_non_get_endpoints, caplog):
    """Test that a warning is issued when there are non-GET endpoints."""
    # Set up logging capture
    caplog.set_level(logging.WARNING)
    
    # Create FastApiMCP instance
    _ = FastApiMCP(app_with_non_get_endpoints)
    
    # Check that warning was logged
    assert any("Non-GET endpoints exposed as tools" in record.message for record in caplog.records)
    assert any("create_item (POST)" in record.message for record in caplog.records)
    assert any("update_item (PUT)" in record.message for record in caplog.records)
    assert any("delete_item (DELETE)" in record.message for record in caplog.records)
    assert any("To disable this warning" in record.message for record in caplog.records)


def test_warn_if_non_get_endpoints_no_warning(app_with_non_get_endpoints, caplog):
    """Test that no warning is issued when disable_warnings=True."""
    # Set up logging capture
    caplog.set_level(logging.WARNING)
    
    # Create FastApiMCP instance with warnings disabled
    _ = FastApiMCP(app_with_non_get_endpoints, disable_warnings=True)
    
    # Check that no warning was logged
    assert not any("Non-GET endpoints exposed as tools" in record.message for record in caplog.records)


def test_warn_if_auto_generated_operation_ids(app_with_auto_generated_ids, caplog):
    """Test that warnings are issued for auto-generated operation IDs."""
    # Set up logging capture
    caplog.set_level(logging.WARNING)
    
    # Create FastApiMCP instance
    _ = FastApiMCP(app_with_auto_generated_ids)
    
    # Check that warning was logged for auto-generated IDs but not for explicit ones
    assert any("auto_generated_route" in record.message for record in caplog.records)
    assert any("auto_generated_route_get" in record.message for record in caplog.records)
    assert not any("explicit_operation_id" in record.message for record in caplog.records)
    assert any("To disable this warning" in record.message for record in caplog.records)


def test_warn_if_auto_generated_operation_ids_no_warning(app_with_auto_generated_ids, caplog):
    """Test that no warning is issued when disable_warnings=True."""
    # Set up logging capture
    caplog.set_level(logging.WARNING)
    
    # Create FastApiMCP instance with warnings disabled
    _ = FastApiMCP(app_with_auto_generated_ids, disable_warnings=True)
    
    # Check that no warning was logged
    assert not any("auto_generated_route" in record.message for record in caplog.records)
    assert not any("auto_generated_route_get" in record.message for record in caplog.records)


def test_disable_all_warnings(app_with_too_many_tools, caplog):
    """Test that all warnings can be disabled via the disable_warnings parameter."""
    # Set up logging capture
    caplog.set_level(logging.WARNING)
    
    # Create FastApiMCP instance with warnings disabled
    _ = FastApiMCP(app_with_too_many_tools, disable_warnings=True)
    
    # Check that no warnings were logged
    assert not any("More than 10 tools exposed" in record.message for record in caplog.records)
    assert not any("Non-GET endpoints exposed as tools" in record.message for record in caplog.records)
    assert not any("auto_generated_route" in record.message for record in caplog.records)


def test_integration_all_warnings(caplog):
    """Test that all warnings are issued during server setup when needed."""
    # Set up logging capture
    caplog.set_level(logging.WARNING)
    
    # Create a FastAPI app with all warning scenarios
    app = FastAPI()
    router = APIRouter()
    
    # Auto-generated operation IDs
    @router.get("/items/")
    async def get_items():
        return {"items": []}
    
    # Non-GET endpoint
    @router.post("/items/")
    async def create_item():
        return {"message": "Item created"}
    
    # Add enough routes to trigger the "too many tools" warning
    for i in range(10):
        @router.get(f"/other-route-{i}/")
        async def other_route_get():
            return {"message": "OK"}
    
    app.include_router(router)
    
    # Create FastApiMCP instance
    _ = FastApiMCP(app)
    
    # Check that all warnings were logged
    assert any("More than 10 tools exposed" in record.message for record in caplog.records)
    assert any("Non-GET endpoints exposed as tools" in record.message for record in caplog.records)
    assert any("create_item_items__post (POST)" in record.message for record in caplog.records)
    assert any("appears to have an auto-generated operation_id" in record.message for record in caplog.records)


def test_integration_warnings_disabled(caplog):
    """Test that warnings are not issued during server setup when disable_warnings=True."""
    # Set up logging capture
    caplog.set_level(logging.WARNING)
    
    # Create a FastAPI app with all warning scenarios
    app = FastAPI()
    
    # Auto-generated operation ID
    @app.get("/items/")
    async def get_items():
        return {"items": []}
    
    # Non-GET endpoint
    @app.post("/items/")
    async def create_item():
        return {"message": "Item created"}
    
    # Create FastApiMCP instance with warnings disabled
    _ = FastApiMCP(app, disable_warnings=True)
    
    # Check that no warnings were logged
    assert len(caplog.records) == 0 