"""Test that tag filtering works correctly with operation ID shortening."""

from fastapi import FastAPI
from fastapi_mcp import FastApiMCP


def test_tag_filtering_with_shortened_operation_ids():
    """Test that include_tags works correctly when operation IDs are shortened."""
    app = FastAPI()

    # Create endpoints with long operation IDs that will be shortened
    @app.post("/api/v1/very/long/path/segments/for/testing/shortening/endpoint1", tags=["TestTag1"])
    def very_long_function_name_that_will_definitely_exceed_the_limit():
        """Endpoint 1 with a very long operation ID."""
        return {"message": "endpoint1"}

    @app.post("/api/v1/another/very/long/path/segments/for/testing/shortening/endpoint2", tags=["TestTag1"])
    def another_very_long_function_name_that_exceeds_the_character_limit():
        """Endpoint 2 with a very long operation ID."""
        return {"message": "endpoint2"}

    @app.get("/api/v1/short", tags=["TestTag2"])
    def short_endpoint():
        """Endpoint with a short operation ID."""
        return {"message": "short"}

    # Create MCP server with tag filtering and operation ID shortening
    mcp = FastApiMCP(app, include_tags=["TestTag1"], max_operation_id_length=50)

    # The long operation IDs should be shortened but still included
    assert len(mcp.tools) == 2

    # Verify that both tools have shortened names
    tool_names = {tool.name for tool in mcp.tools}
    for name in tool_names:
        assert len(name) <= 50
        # Should end with hash
        assert "_" in name

    # Verify operation_id_mappings contains the shortened IDs
    assert len(mcp.operation_id_mappings) == 2

    # Test with different tag
    mcp2 = FastApiMCP(app, include_tags=["TestTag2"], max_operation_id_length=50)

    assert len(mcp2.tools) == 1
    assert mcp2.tools[0].name == "short_endpoint_api_v1_short_get"

    # Test with all tags
    mcp3 = FastApiMCP(app, include_tags=["TestTag1", "TestTag2"], max_operation_id_length=50)

    assert len(mcp3.tools) == 3


def test_exclude_tags_with_shortened_operation_ids():
    """Test that exclude_tags works correctly when operation IDs are shortened."""
    app = FastAPI()

    @app.post("/api/v1/very/long/path/segments/for/testing/shortening/excluded", tags=["ExcludeMe"])
    def very_long_function_name_that_should_be_excluded():
        """Endpoint that should be excluded."""
        return {"message": "excluded"}

    @app.get("/api/v1/included", tags=["IncludeMe"])
    def included_endpoint():
        """Endpoint that should be included."""
        return {"message": "included"}

    mcp = FastApiMCP(app, exclude_tags=["ExcludeMe"], max_operation_id_length=50)

    # Only the included endpoint should be present
    assert len(mcp.tools) == 1
    assert mcp.tools[0].name == "included_endpoint_api_v1_included_get"


def test_operation_filtering_with_shortened_ids():
    """Test include_operations and exclude_operations with shortened IDs."""
    app = FastAPI()

    @app.post("/api/v1/very/long/path/segments/for/testing/shortening/include_me")
    def very_long_function_name_to_include():
        """Endpoint to include."""
        return {"message": "include"}

    @app.post("/api/v1/very/long/path/segments/for/testing/shortening/exclude_me")
    def very_long_function_name_to_exclude():
        """Endpoint to exclude."""
        return {"message": "exclude"}

    # Test with original operation IDs (before shortening)
    original_include = (
        "very_long_function_name_to_include_api_v1_very_long_path_segments_for_testing_shortening_include_me_post"
    )
    original_exclude = (
        "very_long_function_name_to_exclude_api_v1_very_long_path_segments_for_testing_shortening_exclude_me_post"
    )

    mcp = FastApiMCP(app, include_operations=[original_include], max_operation_id_length=50)

    assert len(mcp.tools) == 1
    # The tool name should be shortened
    assert len(mcp.tools[0].name) <= 50
    assert mcp.tools[0].name in mcp.operation_id_mappings

    # Test exclude_operations
    mcp2 = FastApiMCP(app, exclude_operations=[original_exclude], max_operation_id_length=50)

    assert len(mcp2.tools) == 1
    # Should include the other endpoint (shortened)
    assert len(mcp2.tools[0].name) <= 50
