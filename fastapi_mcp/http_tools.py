"""
HTTP tools for FastAPI-MCP.

This module provides functionality for creating MCP tools from FastAPI endpoints.
"""

import json
import logging
from typing import Any, Callable, Dict, List, Optional

import httpx
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from mcp.server.fastmcp import FastMCP
from pydantic import Field

from .openapi_utils import (
    OPENAPI_PYTHON_TYPES_MAP,
    clean_schema_for_display,
    extract_model_examples_from_components,
    generate_example_from_schema,
    parse_parameters_for_args_schema,
    resolve_schema_references,
    PYTHON_TYPE_IMPORTS,
)

logger = logging.getLogger("fastapi_mcp")


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

def _create_http_tool_function(function_template: Callable, args_schema: Dict[str, Any], additional_variables: Dict[str, Any]) -> Callable:
    # Build parameter string with type hints
    param_list = []
    for name, type_info in args_schema.items():
        type_hint = OPENAPI_PYTHON_TYPES_MAP.get(type_info, 'Any')
        param_list.append(f"{name}: {type_hint}")
    parameters_str = ", ".join(param_list)
    
    dynamic_function_body = f"""async def dynamic_http_tool_function({parameters_str}):
        kwargs = {{{', '.join([f"'{k}': {k}" for k in args_schema.keys()])}}}
        return await http_tool_function_template(**kwargs)
    """
    
    # Create function namespace with required imports
    namespace = {
        "http_tool_function_template": function_template,
        **PYTHON_TYPE_IMPORTS,
        **additional_variables
    }
    
    # Execute the dynamic function definition
    exec(dynamic_function_body, namespace)
    return namespace["dynamic_http_tool_function"]

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

    # Create a proper input schema for the tool
    input_schema = {"type": "object", "properties": properties, "title": f"{operation_id}Arguments"}

    if required_props:
        input_schema["required"] = required_props
    
    # Dynamically create a function to  call the API endpoint
    async def http_tool_function_template(**kwargs):
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
        body = kwargs if kwargs else None

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
                response = await client.delete(url, params=query, headers=headers)
            elif method.lower() == "patch":
                response = await client.patch(url, params=query, headers=headers, json=body)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

        # Process the response
        try:
            return response.json()
        except ValueError:
            return response.text

    # Create the http_tool_function (with name and docstring)
    args_schema = parse_parameters_for_args_schema(parameters)
    additional_variables = {"path_params": path_params, "query_params": query_params, "header_params": header_params}
    http_tool_function = _create_http_tool_function(http_tool_function_template, args_schema, additional_variables)
    http_tool_function.__name__ = operation_id
    http_tool_function.__doc__ = tool_description

    # Monkey patch the function's schema for MCP tool creation
    # TODO: Maybe revise this hacky approach
    http_tool_function._input_schema = input_schema  # type: ignore

    # Add tool to the MCP server with the enhanced schema
    tool = mcp_server._tool_manager.add_tool(http_tool_function, name=operation_id, description=tool_description)

    # Update the tool's parameters to use our custom schema instead of the auto-generated one
    tool.parameters = input_schema
