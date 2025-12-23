import json
import logging
from typing import Any, Dict, List, Tuple

import mcp.types as types

from .utils import (
    clean_schema_for_display,
    generate_example_from_schema,
    resolve_schema_references,
    get_single_param_type_from_schema,
)

logger = logging.getLogger(__name__)


def convert_openapi_to_mcp_tools(
    openapi_schema: Dict[str, Any],
    describe_all_responses: bool = False,
    describe_full_response_schema: bool = False,
) -> Tuple[List[types.Tool], Dict[str, Dict[str, Any]]]:
    """
    Convert OpenAPI operations to MCP tools.

    Args:
        openapi_schema: The OpenAPI schema
        describe_all_responses: Whether to include all possible response schemas in tool descriptions
        describe_full_response_schema: Whether to include full response schema in tool descriptions

    Returns:
        A tuple containing:
        - A list of MCP tools
        - A mapping of operation IDs to operation details for HTTP execution
    """
    # Resolve all references in the schema at once
    resolved_openapi_schema = resolve_schema_references(openapi_schema, openapi_schema)

    tools = []
    operation_map = {}

    # Process each path in the OpenAPI schema
    for path, path_item in resolved_openapi_schema.get("paths", {}).items():
        for method, operation in path_item.items():
            # Skip non-HTTP methods
            if method not in ["get", "post", "put", "delete", "patch"]:
                logger.warning(f"Skipping non-HTTP method: {method}")
                continue

            # Get operation metadata
            operation_id = operation.get("operationId")
            metadata = operation.get("_meta")
            annotations = operation.get("annotations")
            if not metadata:
                metadata = {
                    'openai/toolInvocation/invoking': 'Buscando',
                    'openai/toolInvocation/invoked': 'Revisado',
                    'openai/widgetAccessible': False,
                }
            if not annotations:
                annotations = {
                    'destructiveHint': False,
                    'openWorldHint': False,
                    'readOnlyHint': True,
                }
            if not operation_id:
                logger.warning(f"Skipping operation with no operationId: {operation}")
                continue

            # Save operation details for later HTTP calls
            operation_map[operation_id] = {
                "path": path,
                "method": method,
                "parameters": operation.get("parameters", []),
                "request_body": operation.get("requestBody", {}),
            }

            summary = operation.get("summary", "")
            description = operation.get("description", "")

            # Build tool description
            tool_description = f"{summary}" if summary else f"{method.upper()} {path}"
            if description:
                tool_description += f"\n\n{description}"

            # Add response information to the description
            responses = operation.get("responses", {})
            if responses:
                response_info = "\n\n### Responses:\n"

                # Find the success response
                success_codes = range(200, 300)
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

                                # Clean the schema for display
                                display_schema = clean_schema_for_display(schema)

                                # Try to get example response
                                example_response = None

                                # Check if content has examples
                                if "examples" in content_data:
                                    for example_key, example_data in content_data["examples"].items():
                                        if "value" in example_data:
                                            example_response = example_data["value"]
                                            break
                                # If content has example
                                elif "example" in content_data:
                                    example_response = content_data["example"]

                                # If we have an example response, add it to the docs
                                if example_response:
                                    response_info += "\n\n**Example Response:**\n```json\n"
                                    response_info += json.dumps(example_response, indent=2)
                                    response_info += "\n```"
                                # Otherwise generate an example from the schema
                                else:
                                    generated_example = generate_example_from_schema(display_schema)
                                    if generated_example:
                                        response_info += "\n\n**Example Response:**\n```json\n"
                                        response_info += json.dumps(generated_example, indent=2)
                                        response_info += "\n```"

                                # Only include full schema information if requested
                                if describe_full_response_schema:
                                    # Format schema information based on its type
                                    if display_schema.get("type") == "array" and "items" in display_schema:
                                        items_schema = display_schema["items"]

                                        response_info += "\n\n**Output Schema:** Array of items with the following structure:\n```json\n"
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

            for param in operation.get("parameters", []):
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
            request_body = operation.get("requestBody", {})
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

                properties[param_name] = param_schema.copy()
                properties[param_name]["title"] = param_name
                if param_desc:
                    properties[param_name]["description"] = param_desc

                if "type" not in properties[param_name]:
                    properties[param_name]["type"] = param_schema.get("type", "string")

                if param_required:
                    required_props.append(param_name)

            # Add query parameters to properties
            for param_name, param in query_params:
                param_schema = param.get("schema", {})
                param_desc = param.get("description", "")
                param_required = param.get("required", False)

                properties[param_name] = param_schema.copy()
                properties[param_name]["title"] = param_name
                if param_desc:
                    properties[param_name]["description"] = param_desc

                if "type" not in properties[param_name]:
                    properties[param_name]["type"] = get_single_param_type_from_schema(param_schema)

                if "default" in param_schema:
                    properties[param_name]["default"] = param_schema["default"]

                if param_required:
                    required_props.append(param_name)

            # Add body parameters to properties
            for param_name, param in body_params:
                param_schema = param.get("schema", {})
                param_desc = param.get("description", "")
                param_required = param.get("required", False)

                properties[param_name] = param_schema.copy()
                properties[param_name]["title"] = param_name
                if param_desc:
                    properties[param_name]["description"] = param_desc

                if "type" not in properties[param_name]:
                    properties[param_name]["type"] = get_single_param_type_from_schema(param_schema)

                if "default" in param_schema:
                    properties[param_name]["default"] = param_schema["default"]

                if param_required:
                    required_props.append(param_name)

            # Create a proper input schema for the tool
            input_schema = {"type": "object", "properties": properties, "title": f"{operation_id}Arguments"}

            if required_props:
                input_schema["required"] = required_props

            # Create the MCP tool definition
            tool = types.Tool(name=operation_id, description=tool_description, inputSchema=input_schema,
                              _meta = metadata, annotations=annotations)

            tools.append(tool)

    return tools, operation_map
