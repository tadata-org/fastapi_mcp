"""
MCP Prompts support for FastAPI-MCP.

This module provides FastAPI-native decorators and utilities for defining
MCP-compliant prompts that can be discovered and executed by MCP clients.
"""

import logging
from typing import Callable, List, Dict, Any, Optional, get_type_hints, Union
from inspect import signature, Parameter, iscoroutinefunction
import mcp.types as types

from .types import PromptMessage, PromptArgument

logger = logging.getLogger(__name__)


class PromptRegistry:
    """Registry for managing MCP prompts in a FastAPI application."""

    def __init__(self):
        self.prompts: Dict[str, Dict[str, Any]] = {}

    def register_prompt(
        self, name: str, title: Optional[str] = None, description: Optional[str] = None, func: Optional[Callable] = None
    ):
        """
        Register a prompt function with the registry.

        Args:
            name: Unique identifier for the prompt
            title: Human-readable title for the prompt
            description: Description of what the prompt does
            func: The prompt function to register
        """

        def decorator(func: Callable) -> Callable:
            # Extract argument schema from function signature
            sig = signature(func)
            type_hints = get_type_hints(func)

            arguments = []
            properties = {}
            required = []

            # Process function parameters to create prompt arguments
            for param_name, param in sig.parameters.items():
                if param_name in ["self", "cls"]:  # Skip self/cls parameters
                    continue

                param_type = type_hints.get(param_name, str)
                is_required = param.default == Parameter.empty
                param_desc = f"Parameter {param_name}"

                # Try to extract description from docstring or annotations
                if hasattr(param_type, "__doc__") and param_type.__doc__:
                    param_desc = param_type.__doc__

                arguments.append(PromptArgument(name=param_name, description=param_desc, required=is_required))

                # Create JSON schema property
                properties[param_name] = self._type_to_json_schema(param_type)
                if is_required:
                    required.append(param_name)

            # Store prompt definition
            self.prompts[name] = {
                "name": name,
                "title": title or name.replace("_", " ").title(),
                "description": description or func.__doc__ or f"Prompt: {name}",
                "arguments": arguments,
                "func": func,
                "input_schema": {
                    "type": "object",
                    "properties": properties,
                    "required": required if required else None,
                },
            }

            logger.debug(f"Registered prompt: {name}")
            return func

        if func is None:
            return decorator
        else:
            return decorator(func)

    def _type_to_json_schema(self, param_type: type) -> Dict[str, Any]:
        """Convert Python type to JSON schema property."""
        if param_type is str:
            return {"type": "string"}
        elif param_type is int:
            return {"type": "integer"}
        elif param_type is float:
            return {"type": "number"}
        elif param_type is bool:
            return {"type": "boolean"}
        elif hasattr(param_type, "__origin__"):
            # Handle generic types like List, Optional, etc.
            if param_type.__origin__ is list:
                return {"type": "array", "items": {"type": "string"}}
            elif param_type.__origin__ is Union:
                # Handle Optional types (Union[T, None])
                if hasattr(param_type, "__args__"):
                    args = param_type.__args__
                    if len(args) == 2 and type(None) in args:
                        non_none_type = args[0] if args[1] is type(None) else args[1]
                        return self._type_to_json_schema(non_none_type)

        # Default to string for unknown types
        return {"type": "string"}

    def get_prompt_list(self) -> List[types.Prompt]:
        """Get list of all registered prompts in MCP format."""
        mcp_prompts = []

        for prompt_def in self.prompts.values():
            # Convert our PromptArgument objects to MCP format
            mcp_arguments = []
            for arg in prompt_def["arguments"]:
                mcp_arguments.append(
                    types.PromptArgument(name=arg.name, description=arg.description, required=arg.required)
                )

            mcp_prompts.append(
                types.Prompt(name=prompt_def["name"], description=prompt_def["description"], arguments=mcp_arguments)
            )

        return mcp_prompts

    async def get_prompt(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> List[types.PromptMessage]:
        """
        Execute a prompt function and return the result.

        Args:
            name: Name of the prompt to execute
            arguments: Arguments to pass to the prompt function

        Returns:
            List of prompt messages in MCP format

        Raises:
            ValueError: If prompt is not found
        """
        if name not in self.prompts:
            raise ValueError(f"Prompt '{name}' not found")

        prompt_def = self.prompts[name]
        func = prompt_def["func"]
        args = arguments or {}

        try:
            # Call the prompt function
            if iscoroutinefunction(func):
                result = await func(**args)
            else:
                result = func(**args)

            # Ensure result is a list
            if not isinstance(result, list):
                result = [result]

            # Convert our PromptMessage objects to MCP format
            mcp_messages = []
            for msg in result:
                if isinstance(msg, PromptMessage):
                    # Convert content to MCP format
                    mcp_content: Union[types.TextContent, types.ImageContent, types.EmbeddedResource]
                    if hasattr(msg.content, "type"):
                        if msg.content.type == "text":
                            mcp_content = types.TextContent(type="text", text=msg.content.text)
                        elif msg.content.type == "image":
                            mcp_content = types.ImageContent(
                                type="image", data=msg.content.data, mimeType=msg.content.mimeType
                            )
                        elif msg.content.type == "audio":
                            # Note: mcp.types may not have AudioContent, so we'll use TextContent as fallback
                            mcp_content = types.TextContent(
                                type="text", text=f"[Audio content: {msg.content.mimeType}]"
                            )
                        else:
                            mcp_content = types.TextContent(type="text", text=str(msg.content))
                    else:
                        mcp_content = types.TextContent(type="text", text=str(msg.content))

                    mcp_messages.append(types.PromptMessage(role=msg.role, content=mcp_content))
                else:
                    # Handle string or other simple types
                    mcp_messages.append(
                        types.PromptMessage(role="user", content=types.TextContent(type="text", text=str(msg)))
                    )

            return mcp_messages

        except Exception as e:
            logger.error(f"Error executing prompt '{name}': {e}")
            raise ValueError(f"Error executing prompt '{name}': {str(e)}")

    def has_prompts(self) -> bool:
        """Check if any prompts are registered."""
        return len(self.prompts) > 0
