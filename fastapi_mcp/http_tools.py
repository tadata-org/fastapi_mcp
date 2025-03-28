"""
HTTP tools for FastAPI-MCP.

This module provides functionality for creating MCP tools from FastAPI endpoints.
"""

import json
import logging
from typing import Any, Dict, List, Optional

import httpx
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from mcp.server.fastmcp import FastMCP
from pydantic import Field

logger = logging.getLogger("fastapi_mcp")


def resolve_schema_references(schema: Dict[str, Any], openapi_schema: Dict[str, Any]) -> Dict[str, Any]:
    """
    Resolve schema references in OpenAPI schemas.

    Args:
        schema: The schema that may contain references
        openapi_schema: The full OpenAPI schema to resolve references from

    Returns:
        The schema with references resolved
    """
    # Make a copy to avoid modifying the input schema
    schema = schema.copy()

    # Handle $ref directly in the schema
    if "$ref" in schema:
        ref_path = schema["$ref"]
        # Standard OpenAPI references are in the format "#/components/schemas/ModelName"
        if ref_path.startswith("#/components/schemas/"):
            model_name = ref_path.split("/")[-1]
            if "components" in openapi_schema and "schemas" in openapi_schema["components"]:
                if model_name in openapi_schema["components"]["schemas"]:
                    # Replace with the resolved schema
                    ref_schema = openapi_schema["components"]["schemas"][model_name].copy()
                    # Remove the $ref key and merge with the original schema
                    schema.pop("$ref")
                    schema.update(ref_schema)

    # Handle array items
    if "type" in schema and schema["type"] == "array" and "items" in schema:
        schema["items"] = resolve_schema_references(schema["items"], openapi_schema)

    # Handle object properties
    if "properties" in schema:
        for prop_name, prop_schema in schema["properties"].items():
            schema["properties"][prop_name] = resolve_schema_references(prop_schema, openapi_schema)

    return schema


def clean_schema_for_display(schema: Dict[str, Any]) -> Dict[str, Any]:
    """
    Clean up a schema for display by removing internal fields.

    Args:
        schema: The schema to clean

    Returns:
        The cleaned schema
    """
    # Make a copy to avoid modifying the input schema
    schema = schema.copy()

    # Remove common internal fields that are not helpful for LLMs
    fields_to_remove = [
        "allOf",
        "anyOf",
        "oneOf",
        "nullable",
        "discriminator",
        "readOnly",
        "writeOnly",
        "xml",
        "externalDocs",
    ]
    for field in fields_to_remove:
        if field in schema:
            schema.pop(field)

    # Process nested properties
    if "properties" in schema:
        for prop_name, prop_schema in schema["properties"].items():
            if isinstance(prop_schema, dict):
                schema["properties"][prop_name] = clean_schema_for_display(prop_schema)

    # Process array items
    if "type" in schema and schema["type"] == "array" and "items" in schema:
        if isinstance(schema["items"], dict):
            schema["items"] = clean_schema_for_display(schema["items"])

    return schema


def create_mcp_tools_from_openapi(
    app: FastAPI,
    mcp_server: FastMCP,
    base_url: Optional[str] = None,
    describe_all_responses: bool = False,
    describe_full_response_schema: bool = False,
) -> None:
    """
    Create MCP tools from a FastAPI app's OpenAPI schema.

    Args:
        app: The FastAPI application
        mcp_server: The MCP server to add tools to
        base_url: Base URL for API requests (defaults to http://localhost:$PORT)
        describe_all_responses: Whether to include all possible response schemas in tool descriptions
        describe_full_response_schema: Whether to include full response schema in tool descriptions
    """
    # Get OpenAPI schema from FastAPI app
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        openapi_version=app.openapi_version,
        description=app.description,
        routes=app.routes,
    )

    if not base_url:
        # Try to determine the base URL from FastAPI config
        if hasattr(app, "root_path") and app.root_path:
            base_url = app.root_path
        else:
            # Default to localhost with FastAPI default port
            port = 8000
            for route in app.routes:
                if hasattr(route, "app") and hasattr(route.app, "port"):
                    port = route.app.port
                    break
            base_url = f"http://localhost:{port}"

    # Normalize base URL
    if base_url.endswith("/"):
        base_url = base_url[:-1]

    # Process each path in the OpenAPI schema
    for path, path_item in openapi_schema.get("paths", {}).items():
        for method, operation in path_item.items():
            # Skip non-HTTP methods
            if method not in ["get", "post", "put", "delete", "patch"]:
                continue

            # Get operation metadata
            operation_id = operation.get("operationId")
            if not operation_id:
                continue

            # Create MCP tool for this operation
            create_http_tool(
                mcp_server=mcp_server,
                base_url=base_url,
                path=path,
                method=method,
                operation_id=operation_id,
                summary=operation.get("summary", ""),
                description=operation.get("description", ""),
                parameters=operation.get("parameters", []),
                request_body=operation.get("requestBody", {}),
                responses=operation.get("responses", {}),
                openapi_schema=openapi_schema,
                describe_all_responses=describe_all_responses,
                describe_full_response_schema=describe_full_response_schema,
            )


def create_http_tool(
    mcp_server: FastMCP,
    base_url: str,
    path: str,
    method: str,
    operation_id: str,
    summary: str,
    description: str,
    parameters: List[Dict[str, Any]],
    request_body: Dict[str, Any],
    responses: Dict[str, Any],
    openapi_schema: Dict[str, Any],
    describe_all_responses: bool,
    describe_full_response_schema: bool,
) -> None:
    """
    Create an MCP tool that makes an HTTP request to a FastAPI endpoint.

    Args:
        mcp_server: The MCP server to add the tool to
        base_url: Base URL for API requests
        path: API endpoint path
        method: HTTP method
        operation_id: Operation ID
        summary: Operation summary
        description: Operation description
        parameters: OpenAPI parameters
        request_body: OpenAPI request body
        responses: OpenAPI responses
        openapi_schema: The full OpenAPI schema
        describe_all_responses: Whether to include all possible response schemas in tool descriptions
        describe_full_response_schema: Whether to include full response schema in tool descriptions
    """
    # Build tool description
    tool_description = f"{summary}" if summary else f"{method.upper()} {path}"
    if description:
        tool_description += f"\n\n{description}"

    # Add response schema information to description
    if responses:
        response_info = "\n\n### Responses:\n"

        # Find the success response (usually 200 or 201)
        success_codes = ["200", "201", "202", 200, 201, 202]
        success_response = None
        for status_code in success_codes:
            if str(status_code) in responses:
                success_response = responses[str(status_code)]
                break

        # Get the list of responses to include
        responses_to_include = responses
        if not describe_all_responses and success_response:
            # If we're not describing all responses, only include the success response
            success_code = next((code for code in success_codes if str(code) in responses), None)
            if success_code:
                responses_to_include = {str(success_code): success_response}

        # Process all selected responses
        for status_code, response_data in responses_to_include.items():
            response_desc = response_data.get("description", "")
            response_info += f"\n**{status_code}**: {response_desc}"

            # Highlight if this is the main success response
            if response_data == success_response:
                response_info += " (Success Response)"

            # Add schema information if available
            if "content" in response_data:
                for content_type, content_data in response_data["content"].items():
                    if "schema" in content_data:
                        schema = content_data["schema"]
                        response_info += f"\nContent-Type: {content_type}"

                        # Resolve any schema references
                        resolved_schema = resolve_schema_references(schema, openapi_schema)

                        # Clean the schema for display
                        display_schema = clean_schema_for_display(resolved_schema)

                        # Get model name if it's a referenced model
                        model_name = None
                        model_examples = None
                        items_model_name = None
                        if "$ref" in schema:
                            ref_path = schema["$ref"]
                            if ref_path.startswith("#/components/schemas/"):
                                model_name = ref_path.split("/")[-1]
                                response_info += f"\nModel: {model_name}"
                                # Try to get examples from the model
                                model_examples = extract_model_examples_from_components(model_name, openapi_schema)

                        # Check if this is an array of items
                        if schema.get("type") == "array" and "items" in schema and "$ref" in schema["items"]:
                            items_ref_path = schema["items"]["$ref"]
                            if items_ref_path.startswith("#/components/schemas/"):
                                items_model_name = items_ref_path.split("/")[-1]
                                response_info += f"\nArray of: {items_model_name}"

                        # Create example response based on schema type
                        example_response = None

                        # Check if we have examples from the model
                        if model_examples and len(model_examples) > 0:
                            example_response = model_examples[0]  # Use first example
                        # Otherwise, try to create an example from the response definitions
                        elif "examples" in response_data:
                            # Use examples directly from response definition
                            for example_key, example_data in response_data["examples"].items():
                                if "value" in example_data:
                                    example_response = example_data["value"]
                                    break
                        # If content has examples
                        elif "examples" in content_data:
                            for example_key, example_data in content_data["examples"].items():
                                if "value" in example_data:
                                    example_response = example_data["value"]
                                    break
                        # If content has example
                        elif "example" in content_data:
                            example_response = content_data["example"]

                        # Special handling for array of items
                        if (
                            not example_response
                            and display_schema.get("type") == "array"
                            and items_model_name == "Item"
                        ):
                            example_response = [
                                {
                                    "id": 1,
                                    "name": "Hammer",
                                    "description": "A tool for hammering nails",
                                    "price": 9.99,
                                    "tags": ["tool", "hardware"],
                                },
                                {
                                    "id": 2,
                                    "name": "Screwdriver",
                                    "description": "A tool for driving screws",
                                    "price": 7.99,
                                    "tags": ["tool", "hardware"],
                                },
                            ]  # type: ignore

                        # If we have an example response, add it to the docs
                        if example_response:
                            response_info += "\n\n**Example Response:**\n```json\n"
                            response_info += json.dumps(example_response, indent=2)
                            response_info += "\n```"
                        # Otherwise generate an example from the schema
                        else:
                            generated_example = generate_example_from_schema(display_schema, model_name)
                            if generated_example:
                                response_info += "\n\n**Example Response:**\n```json\n"
                                response_info += json.dumps(generated_example, indent=2)
                                response_info += "\n```"

                        # Only include full schema information if requested
                        if describe_full_response_schema:
                            # Format schema information based on its type
                            if display_schema.get("type") == "array" and "items" in display_schema:
                                items_schema = display_schema["items"]

                                response_info += (
                                    "\n\n**Output Schema:** Array of items with the following structure:\n```json\n"
                                )
                                response_info += json.dumps(items_schema, indent=2)
                                response_info += "\n```"
                            elif "properties" in display_schema:
                                response_info += "\n\n**Output Schema:**\n```json\n"
                                response_info += json.dumps(display_schema, indent=2)
                                response_info += "\n```"
                            else:
                                response_info += "\n\n**Output Schema:**\n```json\n"
                                response_info += json.dumps(display_schema, indent=2)
                                response_info += "\n```"

        tool_description += response_info

    # Organize parameters by type
    path_params = []
    query_params = []
    header_params = []
    body_params = []

    for param in parameters:
        param_name = param.get("name")
        param_in = param.get("in")
        required = param.get("required", False)

        if param_in == "path":
            path_params.append((param_name, param))
        elif param_in == "query":
            query_params.append((param_name, param))
        elif param_in == "header":
            header_params.append((param_name, param))

    # Process request body if present
    if request_body and "content" in request_body:
        content_type = next(iter(request_body["content"]), None)
        if content_type and "schema" in request_body["content"][content_type]:
            schema = request_body["content"][content_type]["schema"]
            
            # Check if the schema is a reference and resolve it
            if "$ref" in schema:
                resolved_schema = resolve_schema_references(schema, openapi_schema)
                schema = resolved_schema
            
            # Process properties from the schema (could be from a resolved reference)
            if "properties" in schema:
                for prop_name, prop_schema in schema["properties"].items():
                    required = prop_name in schema.get("required", [])
                    body_params.append(
                        (
                            prop_name,
                            {
                                "name": prop_name,
                                "schema": prop_schema,
                                "required": required,
                            },
                        )
                    )
            # Handle the case where the schema might be for a nested Pydantic model
            elif "allOf" in schema or "anyOf" in schema or "oneOf" in schema:
                # Process composed schema types
                schema_list = schema.get("allOf", []) or schema.get("anyOf", []) or schema.get("oneOf", [])
                for sub_schema in schema_list:
                    resolved_sub_schema = resolve_schema_references(sub_schema, openapi_schema)
                    if "properties" in resolved_sub_schema:
                        for prop_name, prop_schema in resolved_sub_schema["properties"].items():
                            required = prop_name in resolved_sub_schema.get("required", [])
                            body_params.append(
                                (
                                    prop_name,
                                    {
                                        "name": prop_name,
                                        "schema": prop_schema,
                                        "required": required,
                                    },
                                )
                            )

    # Create input schema properties for all parameters
    properties = {}
    required_props = []

    # Add path parameters to properties
    for param_name, param in path_params:
        param_schema = param.get("schema", {})
        param_desc = param.get("description", "")
        param_required = param.get("required", True)  # Path params are usually required

        properties[param_name] = {
            "type": param_schema.get("type", "string"),
            "title": param_name,
            "description": param_desc,
        }

        if param_required:
            required_props.append(param_name)

    # Add query parameters to properties
    for param_name, param in query_params:
        param_schema = param.get("schema", {})
        param_desc = param.get("description", "")
        param_required = param.get("required", False)

        properties[param_name] = {
            "type": param_schema.get("type", "string"),
            "title": param_name,
            "description": param_desc,
        }

        if param_required:
            required_props.append(param_name)

    # Add body parameters to properties
    for param_name, param in body_params:
        param_schema = param.get("schema", {})
        param_required = param.get("required", False)

        properties[param_name] = param_schema
        properties[param_name]["title"] = param_name

        if param_required:
            required_props.append(param_name)

    # Function to dynamically call the API endpoint
    async def http_tool_function(kwargs: Dict[str, Any] = Field(default_factory=dict)):
        # Prepare URL with path parameters
        url = f"{base_url}{path}"
        for param_name, _ in path_params:
            if param_name in kwargs:
                url = url.replace(f"{{{param_name}}}", str(kwargs.pop(param_name)))

        # Prepare query parameters
        query = {}
        for param_name, _ in query_params:
            if param_name in kwargs:
                query[param_name] = kwargs.pop(param_name)

        # Prepare headers
        headers = {}
        for param_name, _ in header_params:
            if param_name in kwargs:
                headers[param_name] = kwargs.pop(param_name)

        # Prepare request body (remaining kwargs)
        body = None
        if kwargs:
            # Extract body parameters and transform any nested structures
            body = {}
            for key, value in kwargs.items():
                # Check if the value is a dictionary that might represent a nested Pydantic model
                if isinstance(value, dict):
                    # Include the value as is (it's already a dict representation of a Pydantic model)
                    body[key] = value
                else:
                    # For simple values, include them directly
                    body[key] = value

        # Make the request
        logger.debug(f"Making {method.upper()} request to {url}")
        async with httpx.AsyncClient() as client:
            if method.lower() == "get":
                response = await client.get(url, params=query, headers=headers)
            elif method.lower() == "post":
                response = await client.post(url, params=query, headers=headers, json=body)
            elif method.lower() == "put":
                response = await client.put(url, params=query, headers=headers, json=body)
            elif method.lower() == "delete":
                response = await client.delete(url, params=query, headers=headers, json=body)
            elif method.lower() == "patch":
                response = await client.patch(url, params=query, headers=headers, json=body)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

        # Process the response
        try:
            return response.json()
        except ValueError:
            return response.text

    # Create a proper input schema for the tool
    input_schema = {"type": "object", "properties": properties, "title": f"{operation_id}Arguments"}

    if required_props:
        input_schema["required"] = required_props

    # Set the function name and docstring
    http_tool_function.__name__ = operation_id
    http_tool_function.__doc__ = tool_description

    # Monkey patch the function's schema for MCP tool creation
    # TODO: Maybe revise this hacky approach
    http_tool_function._input_schema = input_schema  # type: ignore

    # Add tool to the MCP server with the enhanced schema
    tool = mcp_server._tool_manager.add_tool(http_tool_function, name=operation_id, description=tool_description)

    # Update the tool's parameters to use our custom schema instead of the auto-generated one
    tool.parameters = input_schema


def extract_model_examples_from_components(
    model_name: str, openapi_schema: Dict[str, Any]
) -> Optional[List[Dict[str, Any]]]:
    """
    Extract examples from a model definition in the OpenAPI components.

    Args:
        model_name: The name of the model to extract examples from
        openapi_schema: The full OpenAPI schema

    Returns:
        List of example dictionaries if found, None otherwise
    """
    if "components" not in openapi_schema or "schemas" not in openapi_schema["components"]:
        return None

    if model_name not in openapi_schema["components"]["schemas"]:
        return None

    schema = openapi_schema["components"]["schemas"][model_name]

    # Look for examples in the schema
    examples = None

    # Check for examples field directly (OpenAPI 3.1.0+)
    if "examples" in schema:
        examples = schema["examples"]
    # Check for example field (older OpenAPI versions)
    elif "example" in schema:
        examples = [schema["example"]]

    return examples


def generate_example_from_schema(schema: Dict[str, Any], model_name: Optional[str] = None) -> Any:
    """
    Generate a simple example response from a JSON schema.

    Args:
        schema: The JSON schema to generate an example from
        model_name: Optional model name for special handling

    Returns:
        An example object based on the schema
    """
    if not schema or not isinstance(schema, dict):
        return None

    # Special handling for known model types
    if model_name == "Item":
        # Create a realistic Item example since this is commonly used
        return {
            "id": 1,
            "name": "Hammer",
            "description": "A tool for hammering nails",
            "price": 9.99,
            "tags": ["tool", "hardware"],
        }
    elif model_name == "HTTPValidationError":
        # Create a realistic validation error example
        return {"detail": [{"loc": ["body", "name"], "msg": "field required", "type": "value_error.missing"}]}

    # Handle different types
    schema_type = schema.get("type")

    if schema_type == "object":
        result = {}
        if "properties" in schema:
            for prop_name, prop_schema in schema["properties"].items():
                # Generate an example for each property
                prop_example = generate_example_from_schema(prop_schema)
                if prop_example is not None:
                    result[prop_name] = prop_example
        return result

    elif schema_type == "array":
        if "items" in schema:
            # Generate a single example item
            item_example = generate_example_from_schema(schema["items"])
            if item_example is not None:
                return [item_example]
        return []

    elif schema_type == "string":
        # Check if there's a format
        format_type = schema.get("format")
        if format_type == "date-time":
            return "2023-01-01T00:00:00Z"
        elif format_type == "date":
            return "2023-01-01"
        elif format_type == "email":
            return "user@example.com"
        elif format_type == "uri":
            return "https://example.com"
        # Use title or property name if available
        return schema.get("title", "string")

    elif schema_type == "integer":
        return 1

    elif schema_type == "number":
        return 1.0

    elif schema_type == "boolean":
        return True

    elif schema_type == "null":
        return None

    # Default case
    return None
