from typing import Any, Dict, Set, Optional


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


def resolve_schema_references(
    schema_part: Dict[str, Any],
    reference_schema: Dict[str, Any],
    visited_refs: Optional[Set[str]] = None,
    skip_components: bool = True,
) -> Dict[str, Any]:
    """
    Resolve schema references with cycle detection and performance optimization.

    Args:
        schema_part: The part of the schema being processed that may contain references
        reference_schema: The complete schema used to resolve references from
        visited_refs: Set of currently being resolved references (for cycle detection)
        skip_components: Whether to skip processing the components section

    Returns:
        The schema with references resolved
    """
    if visited_refs is None:
        visited_refs = set()

    if not isinstance(schema_part, dict):
        return schema_part

    part = schema_part.copy()

    if "$ref" in part:
        ref_path = part["$ref"]
        if ref_path in visited_refs:
            return {"$ref": ref_path}
        visited_refs.add(ref_path)
        try:
            if ref_path.startswith("#/components/schemas/"):
                model_name = ref_path.split("/")[-1]
                comps = reference_schema.get("components", {}).get("schemas", {})
                if model_name in comps:
                    ref_schema = comps[model_name]
                    resolved_ref = resolve_schema_references(
                        ref_schema, reference_schema, visited_refs, skip_components
                    )
                    part.pop("$ref", None)
                    if isinstance(resolved_ref, dict) and "$ref" not in resolved_ref:
                        part.update(resolved_ref)
        finally:
            # Cleanup
            visited_refs.discard(ref_path)

        return part

    # Recursively resolve references in all dictionary values
    for key, value in list(part.items()):
        if skip_components and key == "components":
            continue

        if isinstance(value, dict):
            part[key] = resolve_schema_references(value, reference_schema, visited_refs, skip_components)
        elif isinstance(value, list):
            part[key] = [
                resolve_schema_references(item, reference_schema, visited_refs, skip_components)
                if isinstance(item, dict)
                else item
                for item in value
            ]
    return part


def resolve_schema_for_display(
    schema: Dict[str, Any],
    components: Dict[str, Any],
    cache: Optional[Dict[str, Dict[str, Any]]] = None,
    stack: Optional[Set[str]] = None,
) -> Dict[str, Any]:
    """
    Resolve a specific schema for display with caching and cycle detection.

    This function is optimized for just-in-time resolution of specific schemas
    without processing the entire components tree.

    Args:
        schema: The schema to resolve
        components: The components section containing schema definitions
        cache: Cache for memoizing resolved schemas
        stack: Stack for cycle detection

    Returns:
        The resolved schema
    """
    if not isinstance(schema, dict):
        return schema

    cache = cache or {}
    stack = stack or set()

    # Handle direct $ref first
    if "$ref" in schema:
        ref = schema["$ref"]

        # Break the cycle
        if ref in stack:
            return {"$ref": ref}

        if ref in cache:
            return cache[ref]

        if not ref.startswith("#/components/schemas/"):
            return schema

        name = ref.split("/")[-1]
        target = components.get("schemas", {}).get(name, {})
        stack.add(ref)
        resolved = resolve_schema_for_display(target, components, cache, stack)
        stack.remove(ref)
        cache[ref] = resolved if isinstance(resolved, dict) else target
        return cache[ref]

    # Recursively resolve the schema but don't descend into the components subtree
    out = schema.copy()
    for k, v in list(out.items()):
        if k == "components":
            continue
        if isinstance(v, dict):
            out[k] = resolve_schema_for_display(v, components, cache, stack)
        elif isinstance(v, list):
            out[k] = [resolve_schema_for_display(i, components, cache, stack) if isinstance(i, dict) else i for i in v]
    return out


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
