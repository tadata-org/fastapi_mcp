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


def parse_param_schema_for_python_type_and_default(param_schema: Dict[str, Any]) -> tuple[str, bool]:
    """
    Parse OpenAPI parameters into a python type and default value string.
    
    Args:
        parameters: List of OpenAPI parameter objects
        
    Returns:
        A tuple containing:
            - A string representing the Python type annotation (e.g. "str", "Optional[int]", etc.)
            - A boolean indicating whether a default value is present
    """
    # Handle anyOf case
    if "anyOf" in param_schema:
        # Get a set of possible types for this parameter
        types = {schema.get("type") for schema in param_schema["anyOf"] if schema.get("type")}
        # If null is one of the types, make None the default value
        if "null" in types:
            types.remove("null")
            if types:
                return f"Optional[{OPENAPI_PYTHON_TYPES_MAP.get(next(iter(types)), 'Any')}] = None", True
            return f"Optional[str] = None", True
        return f"Union[{', '.join([OPENAPI_PYTHON_TYPES_MAP.get(t, 'Any') for t in types])}]", False
    
    # Handle direct type specification
    python_type = OPENAPI_PYTHON_TYPES_MAP.get(param_schema.get("type"), 'Any')
    default_value = param_schema.get("default")
    if default_value is not None:   
        return f"{python_type} = {default_value}", True
    return python_type, False

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
                resolve_schema_references(item, reference_schema) if isinstance(item, dict)
                else item 
                for item in value
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