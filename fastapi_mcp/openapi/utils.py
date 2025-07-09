import hashlib
from typing import Any, Dict


def shorten_operation_id(operation_id: str, max_length: int) -> str:
    """
    Shorten an operation ID to fit within a maximum length while preserving semantic meaning.

    This function implements a collision-resistant shortening algorithm that:
    1. Preserves operation IDs that are already within the limit
    2. For longer IDs, extracts components (function name, path segments, HTTP method)
    3. Generates a 6-character MD5 hash for uniqueness
    4. Prioritizes the most specific path segments (rightmost)
    5. Intelligently truncates function names if needed

    Args:
        operation_id: The original operation ID to potentially shorten
        max_length: The maximum allowed length for the operation ID

    Returns:
        The original operation ID if within limit, or a shortened version

    Example:
        >>> shorten_operation_id("get_user_profile_api_v1_users_profiles_user_id_get", 50)
        'get_user_profile_users_profiles_user_id_get_e1e2e3'
    """
    # Return as-is if already within limit
    if len(operation_id) <= max_length:
        return operation_id

    # Generate 6-character hash from the full original operation ID
    hash_value = hashlib.md5(operation_id.encode()).hexdigest()[:6]

    # Extract components based on FastAPI's default pattern
    # Pattern: {function_name}_{path_segments}_{http_method}
    parts = operation_id.split("_")

    # Extract HTTP method (last part)
    http_method = ""
    if parts and parts[-1] in ["get", "post", "put", "delete", "patch", "head", "options"]:
        http_method = parts[-1]
        parts = parts[:-1]

    # Extract function name (first part, may be multiple words)
    # Function names often contain underscores, so we need to identify where the path starts
    # Heuristic: path segments are usually shorter and may include version indicators like 'v1'
    function_name_parts = []
    path_segments = []

    # Common path indicators
    path_indicators = {"api", "v1", "v2", "v3", "admin", "auth", "public", "private"}

    found_path = False
    for i, part in enumerate(parts):
        if not found_path and part.lower() in path_indicators:
            found_path = True
            path_segments = parts[i:]
            break
        elif not found_path:
            function_name_parts.append(part)

    # If no path indicators found, assume first part is function name, rest is path
    if not found_path and parts:
        function_name_parts = [parts[0]] if parts else []
        path_segments = parts[1:] if len(parts) > 1 else []

    function_name = "_".join(function_name_parts) if function_name_parts else ""

    # Calculate available space for path segments
    # Format: {function_name}_{truncated_path}_{http_method}_{hash}
    fixed_parts_length = len(function_name) + len(http_method) + len(hash_value) + 3  # 3 underscores

    # Handle case where fixed parts alone exceed max_length
    if fixed_parts_length >= max_length:
        # Truncate function name intelligently
        available_for_function = max_length - len(http_method) - len(hash_value) - 3
        if available_for_function > 10:  # Ensure we have reasonable space
            # Preserve start and end of function name
            half = (available_for_function - 3) // 2  # -3 for "..."
            function_name = function_name[:half] + "..." + function_name[-(available_for_function - half - 3) :]
        else:
            # Very extreme case, just truncate
            function_name = function_name[:available_for_function]

        # No room for path segments
        return f"{function_name}_{http_method}_{hash_value}"

    # Calculate space available for path segments
    available_for_path = max_length - fixed_parts_length

    # Build path from right to left (most specific segments first)
    selected_segments: list[str] = []
    current_length = 0

    for segment in reversed(path_segments):
        segment_length = len(segment) + (1 if selected_segments else 0)  # +1 for underscore if not first
        if current_length + segment_length <= available_for_path:
            selected_segments.append(segment)
            current_length += segment_length
        else:
            break

    # Reverse to get correct order
    selected_segments.reverse()

    # Build final shortened operation ID
    path_part = "_".join(selected_segments) if selected_segments else ""

    if path_part:
        return f"{function_name}_{path_part}_{http_method}_{hash_value}"
    else:
        return f"{function_name}_{http_method}_{hash_value}"


def get_single_param_type_from_schema(param_schema: Dict[str, Any]) -> str:
    """
    Get the type of a parameter from the schema.
    If the schema is a union type, return the first type.
    """
    if "anyOf" in param_schema:
        types = {schema.get("type") for schema in param_schema["anyOf"] if schema.get("type")}
        if "null" in types:
            types.remove("null")
        if types:
            return next(iter(types))
        return "string"
    return param_schema.get("type", "string")


def resolve_schema_references(schema_part: Dict[str, Any], reference_schema: Dict[str, Any]) -> Dict[str, Any]:
    """
    Resolve schema references in OpenAPI schemas.

    Args:
        schema_part: The part of the schema being processed that may contain references
        reference_schema: The complete schema used to resolve references from

    Returns:
        The schema with references resolved
    """
    # Make a copy to avoid modifying the input schema
    schema_part = schema_part.copy()

    # Handle $ref directly in the schema
    if "$ref" in schema_part:
        ref_path = schema_part["$ref"]
        # Standard OpenAPI references are in the format "#/components/schemas/ModelName"
        if ref_path.startswith("#/components/schemas/"):
            model_name = ref_path.split("/")[-1]
            if "components" in reference_schema and "schemas" in reference_schema["components"]:
                if model_name in reference_schema["components"]["schemas"]:
                    # Replace with the resolved schema
                    ref_schema = reference_schema["components"]["schemas"][model_name].copy()
                    # Remove the $ref key and merge with the original schema
                    schema_part.pop("$ref")
                    schema_part.update(ref_schema)

    # Recursively resolve references in all dictionary values
    for key, value in schema_part.items():
        if isinstance(value, dict):
            schema_part[key] = resolve_schema_references(value, reference_schema)
        elif isinstance(value, list):
            # Only process list items that are dictionaries since only they can contain refs
            schema_part[key] = [
                resolve_schema_references(item, reference_schema) if isinstance(item, dict) else item for item in value
            ]

    return schema_part


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


def generate_example_from_schema(schema: Dict[str, Any]) -> Any:
    """
    Generate a simple example response from a JSON schema.

    Args:
        schema: The JSON schema to generate an example from

    Returns:
        An example object based on the schema
    """
    if not schema or not isinstance(schema, dict):
        return None

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
