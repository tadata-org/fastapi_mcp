"""
OpenAPI utility functions for FastAPI-MCP.

This module provides utility functions for working with OpenAPI schemas.
"""

from typing import Any, Dict, List, Optional, Union
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

PYTHON_TYPE_IMPORTS = {
        "List": List,
        "Dict": Dict,
        "Any": Any,
        "Optional": Optional,
        "Union": Union,
        "date": date,
        "datetime": datetime,
        "Decimal": Decimal,
        "UUID": UUID,
}
# Type mapping from OpenAPI types to Python types
OPENAPI_PYTHON_TYPES_MAP = {
    # Core data types (OpenAPI 3.x)
    "string": "str",
    "number": "Union[float, Decimal]",  # Could be float or Decimal for precision
    "integer": "int",
    "boolean": "bool",
    "null": "None",
    
    # Complex types
    "object": "Dict[str, Any]",  # More specific than Dict[Any, Any]
    "array": "List[Any]",
    
    # Numeric formats
    "int32": "int",
    "int64": "int",
    "float": "float",
    "double": "float",
    "decimal": "Decimal",
    
    # String formats - Common
    "date": "date",  # datetime.date
    "date-time": "datetime",  # datetime.datetime
    "time": "str",  # Could use datetime.time
    "duration": "str",  # Could use datetime.timedelta
    "password": "str",
    "byte": "bytes",  # base64 encoded
    "binary": "bytes",  # raw binary
    
    # String formats - Extended
    "email": "str",
    "uuid": "UUID",  # uuid.UUID
    "uri": "str",
    "uri-reference": "str",
    "uri-template": "str",
    "url": "str",
    "hostname": "str",
    "ipv4": "str",
    "ipv6": "str",
    "regex": "str",
    "json-pointer": "str",
    "relative-json-pointer": "str",
    
    # Rich text formats
    "markdown": "str",
    "html": "str",
    
    # Media types
    "image/*": "bytes",
    "audio/*": "bytes",
    "video/*": "bytes",
    "application/*": "bytes",
    
    # Special formats
    "format": "str",  # Custom format string
    "pattern": "str",  # Regular expression pattern
    "contentEncoding": "str",  # e.g., base64, quoted-printable
    "contentMediaType": "str",  # MIME type
    
    # Additional numeric formats
    "currency": "Decimal",  # For precise decimal calculations
    "percentage": "float",
    
    # Geographic coordinates
    "latitude": "float",
    "longitude": "float",
    
    # Time-related
    "timezone": "str",  # Could use zoneinfo.ZoneInfo in Python 3.9+
    "unix-time": "int",  # Unix timestamp
    "iso-week-date": "str",  # ISO 8601 week date
    
    # Specialized string formats
    "isbn": "str",
    "issn": "str",
    "iban": "str",
    "credit-card": "str",
    "phone": "str",
    "postal-code": "str",
    "language-code": "str",  # ISO 639 language codes
    "country-code": "str",  # ISO 3166 country codes
    "currency-code": "str",  # ISO 4217 currency codes
    
    # Default fallback
    "unknown": "Any"
}


def parse_parameters_for_args_schema(parameters: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Parse OpenAPI parameters into an arguments schema.
    
    Args:
        parameters: List of OpenAPI parameter objects
        
    Returns:
        Dictionary mapping parameter names to their types
    """
    args_schema = {}
    for param in parameters:
        param_name = param.get("name")
        param_schema = param.get("schema", {})
        
        # Handle anyOf case
        if "anyOf" in param_schema:
            types = set()
            for schema in param_schema["anyOf"]:
                type_val = schema.get("type")
                if type_val:
                    types.add(type_val)
            # If null is one of the types, remove it and make the field optional
            if "null" in types:
                types.remove("null")
                # Check if there are any remaining types after removing null
                if types:
                    args_schema[param_name] = f"Optional[{next(iter(types))}]"
                else:
                    args_schema[param_name] = "Optional[str]"
                continue
            # If we get here, there was no null type, so use first available type
            args_schema[param_name] = next(iter(types)) if types else "str"
        else:
            # Handle direct type specification
            args_schema[param_name] = param_schema.get("type", "string")
    
    return args_schema

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