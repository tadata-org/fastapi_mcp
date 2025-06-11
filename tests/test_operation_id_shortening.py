import logging
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from fastapi_mcp import FastApiMCP
from fastapi_mcp.openapi.convert import convert_openapi_to_mcp_tools


def create_app_with_long_operation_ids() -> FastAPI:
    """Create a FastAPI app with intentionally long operation IDs."""
    app = FastAPI(title="Test App", version="1.0.0")

    @app.get("/api/v1/organizations/departments/employees/profiles/{employee_id}")
    async def get_employee_profile_details_with_full_information(employee_id: int):
        """Get detailed employee profile information."""
        return {"employee_id": employee_id}

    @app.post("/api/v1/financial/reports/quarterly/consolidated/generate")
    async def generate_consolidated_quarterly_financial_report(year: int, quarter: int):
        """Generate a consolidated quarterly financial report."""
        return {"year": year, "quarter": quarter}

    return app


def test_fastapi_mcp_with_operation_id_shortening():
    """Test that FastApiMCP properly applies operation ID shortening."""
    app = create_app_with_long_operation_ids()

    # Create FastApiMCP instance with max_operation_id_length
    mcp = FastApiMCP(
        app, name="Test MCP", description="Test MCP with operation ID shortening", max_operation_id_length=50
    )

    # Check that operation IDs were shortened
    assert len(mcp.tools) == 2

    for tool in mcp.tools:
        assert len(tool.name) <= 50

    # Check that operation_id_mappings contains the shortened IDs
    assert len(mcp.operation_id_mappings) == 2

    # Verify the mappings exist for our shortened IDs
    for shortened_id, original_id in mcp.operation_id_mappings.items():
        assert len(shortened_id) <= 50
        assert len(original_id) > 50  # Original IDs should be longer
        assert shortened_id in [tool.name for tool in mcp.tools]


def test_fastapi_mcp_without_operation_id_shortening():
    """Test that FastApiMCP doesn't shorten when max_operation_id_length is None."""
    app = create_app_with_long_operation_ids()

    # Create FastApiMCP instance without max_operation_id_length
    mcp = FastApiMCP(
        app, name="Test MCP", description="Test MCP without operation ID shortening", max_operation_id_length=None
    )

    # Check that operation IDs were NOT shortened
    assert len(mcp.tools) == 2

    # All operation IDs should be their original length (> 50 chars)
    for tool in mcp.tools:
        assert len(tool.name) > 50

    # operation_id_mappings should be empty when no shortening occurs
    assert len(mcp.operation_id_mappings) == 0


def test_fastapi_mcp_operation_map_preservation():
    """Test that operation_map correctly maps shortened IDs to operation details."""
    app = create_app_with_long_operation_ids()

    mcp = FastApiMCP(app, name="Test MCP", description="Test MCP", max_operation_id_length=40)

    # Verify that operation_map uses shortened IDs as keys
    for tool in mcp.tools:
        assert tool.name in mcp.operation_map
        operation_detail = mcp.operation_map[tool.name]

        # Check that operation details are preserved
        assert "path" in operation_detail
        assert "method" in operation_detail
        assert "original_operation_id" in operation_detail

        # The original_operation_id should be longer than the tool name
        assert len(operation_detail["original_operation_id"]) > len(tool.name)


def test_convert_openapi_with_max_length():
    """Test the convert_openapi_to_mcp_tools function with max_operation_id_length."""
    app = create_app_with_long_operation_ids()

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        openapi_version=app.openapi_version,
        description=app.description,
        routes=app.routes,
    )

    # Test with shortening
    tools, operation_map, id_mappings = convert_openapi_to_mcp_tools(openapi_schema, max_operation_id_length=45)

    assert len(tools) == 2
    assert len(operation_map) == 2
    assert len(id_mappings) == 2

    for tool in tools:
        assert len(tool.name) <= 45

    # Test without shortening
    tools_no_short, operation_map_no_short, id_mappings_no_short = convert_openapi_to_mcp_tools(
        openapi_schema, max_operation_id_length=None
    )

    assert len(id_mappings_no_short) == 0
    for tool in tools_no_short:
        assert len(tool.name) > 45


def test_default_max_operation_id_length():
    """Test that the default max_operation_id_length is 60."""
    app = create_app_with_long_operation_ids()

    # Create FastApiMCP without specifying max_operation_id_length
    mcp = FastApiMCP(app)

    # The default should be 60
    assert mcp._max_operation_id_length == 60

    # Check that operation IDs respect the default limit
    for tool in mcp.tools:
        assert len(tool.name) <= 60


def create_app_with_collision_prone_ids() -> FastAPI:
    """Create a FastAPI app with operation IDs that will collide when shortened."""
    app = FastAPI(title="Collision Test App", version="1.0.0")

    # These two endpoints have different paths but could potentially create the same shortened ID
    # due to having the same function name and HTTP method
    @app.get("/api/v1/users/profiles/data", operation_id="get_data_api_v1_users_profiles_data_get")
    async def get_data():
        return {"source": "users_profiles"}

    @app.get("/api/v1/products/catalog/data", operation_id="get_data_api_v1_products_catalog_data_get")
    async def get_data_products():
        return {"source": "products_catalog"}

    # These two are designed to have very similar structure but different content
    @app.post(
        "/api/v1/reports/financial/generate", operation_id="generate_report_api_v1_reports_financial_generate_post"
    )
    async def generate_report_financial():
        return {"type": "financial"}

    @app.post(
        "/api/v1/reports/analytics/generate", operation_id="generate_report_api_v1_reports_analytics_generate_post"
    )
    async def generate_report_analytics():
        return {"type": "analytics"}

    return app


def test_collision_detection_warning(caplog):
    """Test that collision warnings are properly logged."""
    app = create_app_with_collision_prone_ids()

    # We'll use a very short max length to force potential collisions
    # But since we use hashes, actual collisions should be very rare
    with caplog.at_level(logging.WARNING):
        mcp = FastApiMCP(
            app,
            name="Test MCP",
            description="Test collision detection",
            max_operation_id_length=25,  # Very short to stress test
        )

    # Check that all operations were still created (collisions don't prevent creation)
    assert len(mcp.tools) == 4

    # If any collisions occurred, they should be logged as warnings
    # Note: Due to MD5 hashing, actual collisions are unlikely even with short limits
    collision_warnings = [record for record in caplog.records if "Collision detected!" in record.message]

    # We don't assert that collisions MUST occur (they're probabilistic)
    # but if they do occur, we verify the warning format
    for warning in collision_warnings:
        assert "already exists" in warning.message
        assert "Original operation ID was" in warning.message
        assert "Consider using unique operation IDs" in warning.message


def test_no_collision_with_sufficient_length():
    """Test that no collisions occur with sufficient max_operation_id_length."""
    app = create_app_with_collision_prone_ids()

    # With a reasonable length, collisions should not occur
    with patch("fastapi_mcp.openapi.convert.logger") as mock_logger:
        mcp = FastApiMCP(app, name="Test MCP", description="Test no collisions", max_operation_id_length=60)

        # Verify no collision warnings were logged
        warning_calls = [call for call in mock_logger.warning.call_args_list if "Collision detected!" in str(call)]
        assert len(warning_calls) == 0

    # All tools should be created successfully
    assert len(mcp.tools) == 4

    # All tool names should be unique
    tool_names = [tool.name for tool in mcp.tools]
    assert len(tool_names) == len(set(tool_names))


def test_convert_function_with_collision_detection():
    """Test collision detection in convert_openapi_to_mcp_tools directly."""
    app = create_app_with_collision_prone_ids()

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        openapi_version=app.openapi_version,
        description=app.description,
        routes=app.routes,
    )

    # Test with very short limit to potentially trigger collisions
    with patch("fastapi_mcp.openapi.convert.logger") as mock_logger:
        tools, operation_map, id_mappings = convert_openapi_to_mcp_tools(openapi_schema, max_operation_id_length=20)

        # All tools should still be created
        assert len(tools) == 4

        # Check if any collision warnings were logged
        if mock_logger.warning.called:
            warning_messages = [call[0][0] for call in mock_logger.warning.call_args_list]
            collision_warnings = [msg for msg in warning_messages if "Collision detected!" in msg]

            # If collisions occurred, verify the warning format
            for warning in collision_warnings:
                assert "already exists" in warning
                assert "Original operation ID was" in warning


def test_operation_ids_under_limit_not_modified():
    """Test that operation IDs under the limit are not modified."""
    app = FastAPI(title="Short IDs App", version="1.0.0")

    # Create endpoints with short operation IDs
    @app.get("/users", operation_id="list_users")
    async def list_users():
        return []

    @app.post("/users", operation_id="create_user")
    async def create_user():
        return {}

    @app.get("/products", operation_id="list_products")
    async def list_products():
        return []

    # Create MCP with a limit larger than any of our operation IDs
    mcp = FastApiMCP(app, name="Test MCP", description="Test short IDs", max_operation_id_length=50)

    # Verify all operation IDs remain unchanged
    tool_names = [tool.name for tool in mcp.tools]
    assert "list_users" in tool_names
    assert "create_user" in tool_names
    assert "list_products" in tool_names

    # Verify no mappings were created (no shortening occurred)
    assert len(mcp.operation_id_mappings) == 0


def test_manual_operation_id_respected():
    """Test that manually specified operation IDs are respected by shortening."""
    app = FastAPI()

    # Short manual ID should be preserved
    @app.post("/api/v1/long/path", operation_id="short_id")
    def endpoint1():
        return {}

    # Long manual ID should be shortened
    @app.post("/api/v2/path", operation_id="this_is_a_very_long_manual_operation_id_that_exceeds_the_limit")
    def endpoint2():
        return {}

    # Auto-generated ID that will be long
    @app.post("/api/v1/very/long/path/segments/for/testing/auto/generation")
    def endpoint_without_manual_id():
        return {}

    mcp = FastApiMCP(app, max_operation_id_length=40)

    tool_names = {tool.name for tool in mcp.tools}

    # Short manual ID is preserved as-is
    assert "short_id" in tool_names

    # Long manual ID is shortened
    # From the logs, it becomes: this_id_that_exceeds_the_limit__168e39
    long_id_tools = [name for name in tool_names if "this" in name and name != "short_id"]
    assert len(long_id_tools) == 1
    long_id_tool = long_id_tools[0]
    assert len(long_id_tool) <= 40

    # Verify mapping exists for the shortened IDs
    assert long_id_tool in mcp.operation_id_mappings
    assert mcp.operation_id_mappings[long_id_tool] == "this_is_a_very_long_manual_operation_id_that_exceeds_the_limit"

    # Auto-generated ID should also be shortened
    auto_id_tool = next(name for name in tool_names if "endpoint_without_manual_id" in name)
    assert len(auto_id_tool) <= 40
    assert auto_id_tool in mcp.operation_id_mappings
