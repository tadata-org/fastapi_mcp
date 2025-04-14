import logging
import pytest
from fastapi import FastAPI, APIRouter
from typing import Dict, Any

from fastapi_mcp import FastApiMCP


def test_non_get_methods_warning(caplog, simple_fastapi_app: FastAPI):
    """Test that a warning is logged when non-GET methods are exposed as tools."""
    # Set log capture to warning level
    caplog.set_level(logging.WARNING)
    
    # Create MCP server from app (which has POST, PUT, DELETE methods)
    mcp = FastApiMCP(simple_fastapi_app)
    
    # Check that the warning about non-GET methods was logged
    assert any("Non-GET endpoints exposed as tools" in record.message for record in caplog.records)
    
    # Check that the warning mentions the specific non-GET operations
    warning_message = next(record.message for record in caplog.records if "Non-GET endpoints exposed as tools" in record.message)
    non_get_operations = ["create_item (POST)", "update_item (PUT)", "delete_item (DELETE)"]
    for operation in non_get_operations:
        assert operation in warning_message, f"Warning should mention {operation}"


def test_auto_generated_operation_ids_warning(caplog):
    """Test that a warning is logged when auto-generated operation IDs are detected."""
    # Set log capture to warning level
    caplog.set_level(logging.WARNING)
    
    # Create a test app with auto-generated-looking operation IDs
    app = FastAPI(title="Test Auto-gen IDs")
    
    # Add routes with operation IDs that look auto-generated
    @app.get("/test1", operation_id="test__get")
    async def test1():
        return {"message": "test1"}
    
    @app.get("/test2", operation_id="test_with__get")
    async def test2():
        return {"message": "test2"}
    
    @app.post("/test3", operation_id="test_post")
    async def test3():
        return {"message": "test3"}
    
    # Create MCP server from this app
    mcp = FastApiMCP(app)
    
    # Check that warnings about auto-generated operation IDs were logged
    auto_gen_warnings = [record.message for record in caplog.records 
                         if "appears to have an auto-generated operation_id" in record.message]
    
    assert len(auto_gen_warnings) == 3, "Should have warnings for all three auto-generated-looking operation IDs"
    
    # Check that each operation ID is mentioned in a warning
    operation_ids = ["test__get", "test_with__get", "test_post"]
    for op_id in operation_ids:
        assert any(op_id in warning for warning in auto_gen_warnings), f"Warning for {op_id} not found"


def test_too_many_tools_warning(caplog):
    """Test that a warning is logged when more than 10 tools are exposed."""
    # Set log capture to warning level
    caplog.set_level(logging.WARNING)
    
    # Create a test app with more than 10 endpoints
    app = FastAPI(title="Test Too Many Tools")
    
    # Add 11 routes with unique operation IDs
    for i in range(11):
        @app.get(f"/item{i}", operation_id=f"get_item{i}")
        async def get_item(item_id: int = i):
            return {"item_id": item_id}
    
    # Create MCP server from this app
    mcp = FastApiMCP(app)
    
    # Check that the warning about too many tools was logged
    assert any("More than 10 tools exposed" in record.message for record in caplog.records)
    
    # Get the warning message
    warning_message = next(record.message for record in caplog.records 
                          if "More than 10 tools exposed" in record.message)
    
    # Verify that the warning includes the number of tools
    assert "(11)" in warning_message, "Warning should include the number of tools"


def test_filter_non_get_methods_no_warning(caplog, simple_fastapi_app: FastAPI):
    """Test that no warning is logged when only GET methods are included."""
    # Set log capture to warning level
    caplog.set_level(logging.WARNING)
    
    # Create MCP server from app but only include GET operations
    mcp = FastApiMCP(
        simple_fastapi_app, 
        include_operations=["list_items", "get_item", "raise_error"]
    )
    
    # Check that no warning about non-GET methods was logged
    assert not any("Non-GET endpoints exposed as tools" in record.message for record in caplog.records) 