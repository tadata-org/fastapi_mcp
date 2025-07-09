from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
import mcp.types as types

from fastapi_mcp.openapi.convert import convert_openapi_to_mcp_tools
from fastapi_mcp.openapi.utils import (
    clean_schema_for_display,
    generate_example_from_schema,
    get_single_param_type_from_schema,
    shorten_operation_id,
)


def test_simple_app_conversion(simple_fastapi_app: FastAPI):
    openapi_schema = get_openapi(
        title=simple_fastapi_app.title,
        version=simple_fastapi_app.version,
        openapi_version=simple_fastapi_app.openapi_version,
        description=simple_fastapi_app.description,
        routes=simple_fastapi_app.routes,
    )

    tools, operation_map, _ = convert_openapi_to_mcp_tools(openapi_schema)

    assert len(tools) == 6
    assert len(operation_map) == 6

    expected_operations = ["list_items", "get_item", "create_item", "update_item", "delete_item", "raise_error"]
    for op in expected_operations:
        assert op in operation_map

    for tool in tools:
        assert isinstance(tool, types.Tool)
        assert tool.name in expected_operations
        assert tool.description is not None
        assert tool.inputSchema is not None


def test_complex_app_conversion(complex_fastapi_app: FastAPI):
    openapi_schema = get_openapi(
        title=complex_fastapi_app.title,
        version=complex_fastapi_app.version,
        openapi_version=complex_fastapi_app.openapi_version,
        description=complex_fastapi_app.description,
        routes=complex_fastapi_app.routes,
    )

    tools, operation_map, _ = convert_openapi_to_mcp_tools(openapi_schema)

    expected_operations = ["list_products", "get_product", "create_order", "get_customer"]
    assert len(tools) == len(expected_operations)
    assert len(operation_map) == len(expected_operations)

    for op in expected_operations:
        assert op in operation_map

    for tool in tools:
        assert isinstance(tool, types.Tool)
        assert tool.name in expected_operations
        assert tool.description is not None
        assert tool.inputSchema is not None


def test_describe_full_response_schema(simple_fastapi_app: FastAPI):
    openapi_schema = get_openapi(
        title=simple_fastapi_app.title,
        version=simple_fastapi_app.version,
        openapi_version=simple_fastapi_app.openapi_version,
        description=simple_fastapi_app.description,
        routes=simple_fastapi_app.routes,
    )

    tools_full, _, _ = convert_openapi_to_mcp_tools(openapi_schema, describe_full_response_schema=True)

    tools_simple, _, _ = convert_openapi_to_mcp_tools(openapi_schema, describe_full_response_schema=False)

    for i, tool in enumerate(tools_full):
        assert tool.description is not None
        assert tools_simple[i].description is not None

        tool_desc = tool.description or ""
        simple_desc = tools_simple[i].description or ""

        assert len(tool_desc) >= len(simple_desc)

        if tool.name == "delete_item":
            continue

        assert "**Output Schema:**" in tool_desc

        if "**Output Schema:**" in simple_desc:
            assert len(tool_desc) > len(simple_desc)


def test_describe_all_responses(complex_fastapi_app: FastAPI):
    openapi_schema = get_openapi(
        title=complex_fastapi_app.title,
        version=complex_fastapi_app.version,
        openapi_version=complex_fastapi_app.openapi_version,
        description=complex_fastapi_app.description,
        routes=complex_fastapi_app.routes,
    )

    tools_all, _, _ = convert_openapi_to_mcp_tools(openapi_schema, describe_all_responses=True)

    tools_success, _, _ = convert_openapi_to_mcp_tools(openapi_schema, describe_all_responses=False)

    create_order_all = next(t for t in tools_all if t.name == "create_order")
    create_order_success = next(t for t in tools_success if t.name == "create_order")

    assert create_order_all.description is not None
    assert create_order_success.description is not None

    all_desc = create_order_all.description or ""
    success_desc = create_order_success.description or ""

    assert "400" in all_desc
    assert "404" in all_desc
    assert "422" in all_desc

    assert all_desc.count("400") >= success_desc.count("400")


def test_schema_utils():
    schema = {
        "type": "object",
        "properties": {
            "id": {"type": "integer"},
            "name": {"type": "string"},
            "tags": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["id", "name"],
        "additionalProperties": False,
        "x-internal": "Some internal data",
    }

    cleaned = clean_schema_for_display(schema)

    assert "required" in cleaned
    assert "properties" in cleaned
    assert "type" in cleaned

    example = generate_example_from_schema(schema)
    assert "id" in example
    assert "name" in example
    assert "tags" in example
    assert isinstance(example["id"], int)
    assert isinstance(example["name"], str)
    assert isinstance(example["tags"], list)

    assert get_single_param_type_from_schema({"type": "string"}) == "string"
    assert get_single_param_type_from_schema({"type": "array", "items": {"type": "string"}}) == "array"

    array_schema = {"type": "array", "items": {"type": "string", "enum": ["red", "green", "blue"]}}
    array_example = generate_example_from_schema(array_schema)
    assert isinstance(array_example, list)
    assert len(array_example) > 0

    assert isinstance(array_example[0], str)


def test_parameter_handling(complex_fastapi_app: FastAPI):
    openapi_schema = get_openapi(
        title=complex_fastapi_app.title,
        version=complex_fastapi_app.version,
        openapi_version=complex_fastapi_app.openapi_version,
        description=complex_fastapi_app.description,
        routes=complex_fastapi_app.routes,
    )

    tools, operation_map, _ = convert_openapi_to_mcp_tools(openapi_schema)

    list_products_tool = next(tool for tool in tools if tool.name == "list_products")

    properties = list_products_tool.inputSchema["properties"]

    assert "product_id" not in properties  # This is from get_product, not list_products

    assert "category" in properties
    assert properties["category"].get("type") == "string"  # Enum converted to string
    assert "description" in properties["category"]
    assert "Filter by product category" in properties["category"]["description"]

    assert "min_price" in properties
    assert properties["min_price"].get("type") == "number"
    assert "description" in properties["min_price"]
    assert "Minimum price filter" in properties["min_price"]["description"]
    if "minimum" in properties["min_price"]:
        assert properties["min_price"]["minimum"] > 0  # gt=0 in Query param

    assert "in_stock_only" in properties
    assert properties["in_stock_only"].get("type") == "boolean"
    assert properties["in_stock_only"].get("default") is False  # Default value preserved

    assert "page" in properties
    assert properties["page"].get("type") == "integer"
    assert properties["page"].get("default") == 1  # Default value preserved
    if "minimum" in properties["page"]:
        assert properties["page"]["minimum"] >= 1  # ge=1 in Query param

    assert "size" in properties
    assert properties["size"].get("type") == "integer"
    if "minimum" in properties["size"] and "maximum" in properties["size"]:
        assert properties["size"]["minimum"] >= 1  # ge=1 in Query param
        assert properties["size"]["maximum"] <= 100  # le=100 in Query param

    assert "tag" in properties
    assert properties["tag"].get("type") == "array"

    required = list_products_tool.inputSchema.get("required", [])
    assert "page" not in required  # Has default value
    assert "category" not in required  # Optional parameter

    assert "list_products" in operation_map
    assert operation_map["list_products"]["path"] == "/products"
    assert operation_map["list_products"]["method"] == "get"

    get_product_tool = next(tool for tool in tools if tool.name == "get_product")
    get_product_props = get_product_tool.inputSchema["properties"]

    assert "product_id" in get_product_props
    assert get_product_props["product_id"].get("type") == "string"  # UUID converted to string
    assert "description" in get_product_props["product_id"]

    get_customer_tool = next(tool for tool in tools if tool.name == "get_customer")
    get_customer_props = get_customer_tool.inputSchema["properties"]

    assert "fields" in get_customer_props
    assert get_customer_props["fields"].get("type") == "array"
    if "items" in get_customer_props["fields"]:
        assert get_customer_props["fields"]["items"].get("type") == "string"


def test_request_body_handling(complex_fastapi_app: FastAPI):
    openapi_schema = get_openapi(
        title=complex_fastapi_app.title,
        version=complex_fastapi_app.version,
        openapi_version=complex_fastapi_app.openapi_version,
        description=complex_fastapi_app.description,
        routes=complex_fastapi_app.routes,
    )

    create_order_route = openapi_schema["paths"]["/orders"]["post"]
    original_request_body = create_order_route["requestBody"]["content"]["application/json"]["schema"]
    original_properties = original_request_body.get("properties", {})

    tools, operation_map, _ = convert_openapi_to_mcp_tools(openapi_schema)

    create_order_tool = next(tool for tool in tools if tool.name == "create_order")

    properties = create_order_tool.inputSchema["properties"]

    assert "customer_id" in properties
    assert "items" in properties
    assert "shipping_address_id" in properties
    assert "payment_method" in properties
    assert "notes" in properties

    for param_name in ["customer_id", "items", "shipping_address_id", "payment_method", "notes"]:
        if "description" in original_properties.get(param_name, {}):
            assert "description" in properties[param_name]
            assert properties[param_name]["description"] == original_properties[param_name]["description"]

    for param_name in ["customer_id", "items", "shipping_address_id", "payment_method", "notes"]:
        assert properties[param_name]["title"] == param_name

    for param_name in ["customer_id", "items", "shipping_address_id", "payment_method", "notes"]:
        if "default" in original_properties.get(param_name, {}):
            assert "default" in properties[param_name]
            assert properties[param_name]["default"] == original_properties[param_name]["default"]

    required = create_order_tool.inputSchema.get("required", [])
    assert "customer_id" in required
    assert "items" in required
    assert "shipping_address_id" in required
    assert "payment_method" in required
    assert "notes" not in required  # Optional in OrderRequest

    assert properties["items"].get("type") == "array"
    if "items" in properties["items"]:
        item_props = properties["items"]["items"]
        assert item_props.get("type") == "object"
        if "properties" in item_props:
            assert "product_id" in item_props["properties"]
            assert "quantity" in item_props["properties"]
            assert "unit_price" in item_props["properties"]
            assert "total" in item_props["properties"]

            for nested_param in ["product_id", "quantity", "unit_price", "total"]:
                assert "title" in item_props["properties"][nested_param]

                # Check if the original nested schema had descriptions
                original_item_schema = original_properties.get("items", {}).get("items", {}).get("properties", {})
                if "description" in original_item_schema.get(nested_param, {}):
                    assert "description" in item_props["properties"][nested_param]
                    assert (
                        item_props["properties"][nested_param]["description"]
                        == original_item_schema[nested_param]["description"]
                    )

    assert "create_order" in operation_map
    assert operation_map["create_order"]["path"] == "/orders"
    assert operation_map["create_order"]["method"] == "post"


def test_missing_type_handling(complex_fastapi_app: FastAPI):
    openapi_schema = get_openapi(
        title=complex_fastapi_app.title,
        version=complex_fastapi_app.version,
        openapi_version=complex_fastapi_app.openapi_version,
        description=complex_fastapi_app.description,
        routes=complex_fastapi_app.routes,
    )

    # Remove the type field from the product_id schema
    params = openapi_schema["paths"]["/products/{product_id}"]["get"]["parameters"]
    for param in params:
        if param.get("name") == "product_id" and "schema" in param:
            param["schema"].pop("type", None)
            break

    tools, operation_map, _ = convert_openapi_to_mcp_tools(openapi_schema)

    get_product_tool = next(tool for tool in tools if tool.name == "get_product")
    get_product_props = get_product_tool.inputSchema["properties"]

    assert "product_id" in get_product_props
    assert get_product_props["product_id"].get("type") == "string"  # Default type applied


def test_body_params_descriptions_and_defaults(complex_fastapi_app: FastAPI):
    """
    Test that descriptions and defaults from request body parameters
    are properly transferred to the MCP tool schema properties.
    """
    openapi_schema = get_openapi(
        title=complex_fastapi_app.title,
        version=complex_fastapi_app.version,
        openapi_version=complex_fastapi_app.openapi_version,
        description=complex_fastapi_app.description,
        routes=complex_fastapi_app.routes,
    )

    order_request_schema = openapi_schema["components"]["schemas"]["OrderRequest"]

    order_request_schema["properties"]["customer_id"]["description"] = "Test customer ID description"
    order_request_schema["properties"]["payment_method"]["description"] = "Test payment method description"
    order_request_schema["properties"]["notes"]["default"] = "Default order notes"

    item_schema = openapi_schema["components"]["schemas"]["OrderItem"]
    item_schema["properties"]["product_id"]["description"] = "Test product ID description"
    item_schema["properties"]["quantity"]["default"] = 1

    tools, _, _ = convert_openapi_to_mcp_tools(openapi_schema)

    create_order_tool = next(tool for tool in tools if tool.name == "create_order")
    properties = create_order_tool.inputSchema["properties"]

    assert "description" in properties["customer_id"]
    assert properties["customer_id"]["description"] == "Test customer ID description"

    assert "description" in properties["payment_method"]
    assert properties["payment_method"]["description"] == "Test payment method description"

    assert "default" in properties["notes"]
    assert properties["notes"]["default"] == "Default order notes"

    if "items" in properties:
        assert properties["items"]["type"] == "array"
        assert "items" in properties["items"]

        item_props = properties["items"]["items"]["properties"]

        assert "description" in item_props["product_id"]
        assert item_props["product_id"]["description"] == "Test product ID description"

        assert "default" in item_props["quantity"]
        assert item_props["quantity"]["default"] == 1


def test_body_params_edge_cases(complex_fastapi_app: FastAPI):
    """
    Test handling of edge cases for body parameters, such as:
    - Empty or missing descriptions
    - Missing type information
    - Empty properties object
    - Schema without properties
    """
    openapi_schema = get_openapi(
        title=complex_fastapi_app.title,
        version=complex_fastapi_app.version,
        openapi_version=complex_fastapi_app.openapi_version,
        description=complex_fastapi_app.description,
        routes=complex_fastapi_app.routes,
    )

    order_request_schema = openapi_schema["components"]["schemas"]["OrderRequest"]

    if "description" in order_request_schema["properties"]["customer_id"]:
        del order_request_schema["properties"]["customer_id"]["description"]

    if "type" in order_request_schema["properties"]["notes"]:
        del order_request_schema["properties"]["notes"]["type"]

    item_schema = openapi_schema["components"]["schemas"]["OrderItem"]

    if "properties" in item_schema["properties"]["total"]:
        del item_schema["properties"]["total"]["properties"]

    tools, _, _ = convert_openapi_to_mcp_tools(openapi_schema)

    create_order_tool = next(tool for tool in tools if tool.name == "create_order")
    properties = create_order_tool.inputSchema["properties"]

    assert "customer_id" in properties
    assert "title" in properties["customer_id"]
    assert properties["customer_id"]["title"] == "customer_id"

    assert "notes" in properties
    assert "type" in properties["notes"]
    assert properties["notes"]["type"] in ["string", "object"]  # Default should be either string or object

    if "items" in properties:
        item_props = properties["items"]["items"]["properties"]
        assert "total" in item_props


def test_shorten_operation_id_basic():
    """Test basic operation ID shortening functionality."""
    # Test case 1: ID within limit should not be shortened
    short_id = "get_user"
    assert shorten_operation_id(short_id, 50) == short_id

    # Test case 2: Long ID should be shortened
    long_id = "get_user_profile_api_v1_users_profiles_user_id_get"
    shortened = shorten_operation_id(long_id, 40)  # Use 40 to ensure shortening happens
    assert len(shortened) <= 40
    assert shortened.startswith("get_user_profile")
    assert "_get_" in shortened  # HTTP method should be present
    assert "user_id" in shortened  # Most specific path segment should be preserved

    # Test case 3: Very long function name
    very_long_func = "get_user_profile_details_with_preferences_and_settings_api_v1_users_get"
    shortened = shorten_operation_id(very_long_func, 40)
    assert len(shortened) <= 40
    assert "..." in shortened  # Should contain ellipsis for truncated function name


def test_shorten_operation_id_edge_cases():
    """Test edge cases for operation ID shortening."""
    # Test case 1: No path segments
    no_path = "create_user_post"
    shortened = shorten_operation_id(no_path, 20)
    assert len(shortened) <= 20
    # With no shortening needed, it should remain the same
    assert shortened == "create_user_post"

    # Test case 2: Single character segments
    single_char = "get_a_b_c_d_e_f_g_h_i_j_k_get"
    shortened = shorten_operation_id(single_char, 25)
    assert len(shortened) <= 25

    # Test case 3: No HTTP method
    no_method = "list_items_api_v1_items"
    shortened = shorten_operation_id(no_method, 20)
    assert len(shortened) <= 20

    # Test case 4: Only HTTP method
    only_method = "get"
    assert shorten_operation_id(only_method, 10) == only_method

    # Test case 5: Empty operation ID
    assert shorten_operation_id("", 10) == ""


def test_shorten_operation_id_hash_consistency():
    """Test that hash generation is consistent."""
    operation_id = "get_user_profile_api_v1_users_profiles_user_id_get"

    # Same input should always produce the same hash
    shortened1 = shorten_operation_id(operation_id, 40)
    shortened2 = shorten_operation_id(operation_id, 40)
    assert shortened1 == shortened2

    # Extract hash from shortened ID (last 6 characters before final underscore)
    hash1 = shortened1.split("_")[-1]
    hash2 = shortened2.split("_")[-1]
    assert hash1 == hash2
    assert len(hash1) == 6


def test_shorten_operation_id_different_lengths():
    """Test shortening with different max lengths."""
    operation_id = "get_user_profile_api_v1_users_profiles_user_id_get"

    # Test with different limits
    for max_length in [30, 40, 50, 60]:
        shortened = shorten_operation_id(operation_id, max_length)
        assert len(shortened) <= max_length

    # Test with two lengths that both require shortening
    short_limit = shorten_operation_id(operation_id, 30)
    medium_limit = shorten_operation_id(operation_id, 40)

    # Both shortened versions should have the same hash (last 6 chars)
    assert short_limit[-6:] == medium_limit[-6:]

    # The medium limit should preserve more path info
    assert len(medium_limit) > len(short_limit)


def test_shorten_operation_id_path_priority():
    """Test that rightmost path segments are prioritized."""
    operation_id = "get_data_api_v1_organizations_departments_employees_employee_id_get"
    shortened = shorten_operation_id(operation_id, 50)

    # Should prioritize rightmost segments
    assert "employee_id" in shortened
    assert "employees" in shortened or "departments" in shortened

    # Should not include leftmost segments when space is limited
    very_short = shorten_operation_id(operation_id, 35)
    assert "api" not in very_short
    assert "v1" not in very_short
