"""
MCP Prompts support for FastAPI-MCP.

This module provides FastAPI-native decorators and utilities for defining
MCP-compliant prompts that can be discovered and executed by MCP clients.
"""

import logging
from typing import Callable, List, Dict, Any, Optional, get_type_hints, Union
from inspect import signature, Parameter, iscoroutinefunction
import mcp.types as types

from .types import PromptMessage, PromptArgument, TextContent

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

    def auto_register_tool_prompts(self, tools: List[types.Tool], operation_map: Dict[str, Dict[str, Any]]) -> None:
        """
        Automatically register default prompts for each tool.
        
        Args:
            tools: List of MCP tools to create prompts for
            operation_map: Mapping of operation IDs to operation details
        """
        for tool in tools:
            prompt_name = f"use_{tool.name}"
            
            # Skip if user has already registered a custom prompt with this name
            if prompt_name in self.prompts:
                logger.debug(f"Skipping auto-registration for {prompt_name} - custom prompt exists")
                continue
            
            # Generate prompt content for this tool
            prompt_content = self._generate_tool_prompt_content(tool, operation_map.get(tool.name, {}))
            
            # Create a simple prompt function
            def create_tool_prompt(content: str):
                def tool_prompt_func():
                    return PromptMessage(role="user", content=TextContent(type="text", text=content))
                return tool_prompt_func
            
            # Register the auto-generated prompt
            self.prompts[prompt_name] = {
                "name": prompt_name,
                "title": f"Usage Guide: {tool.name}",
                "description": f"Best practices and guidance for using the {tool.name} tool effectively",
                "arguments": [],
                "func": create_tool_prompt(prompt_content),
                "input_schema": {"type": "object", "properties": {}, "required": []},
                "auto_generated": True
            }
            
            logger.debug(f"Auto-registered prompt: {prompt_name}")

    def _generate_tool_prompt_content(self, tool: types.Tool, operation_info: Dict[str, Any]) -> str:
        """
        Generate helpful prompt content for a tool.
        
        Args:
            tool: The MCP tool to generate content for
            operation_info: Operation details from the operation map
            
        Returns:
            Generated prompt content as a string
        """
        # Focus on actionable guidance rather than repeating tool information
        content_parts = [
            f"You are about to use the **{tool.name}** tool.",
            "",
            "**Key Guidelines:**",
            "• Review the tool's description and parameter requirements carefully",
            "• Provide all required parameters with appropriate values",
            "• Use relevant data that matches the user's actual needs and context",
            "• Check the expected response format before interpreting results",
            "",
            "**Best Practices:**",
            "• Validate your inputs match the expected parameter types",
            "• Use values that make sense for the user's specific request",
            "• Handle potential errors gracefully",
            "• Consider the business logic and constraints of the operation",
            "",
            "**Execution Tips:**",
            "• Double-check required vs optional parameters",
            "• Use appropriate data formats (strings, numbers, booleans)",
            "• Consider edge cases and boundary conditions",
            "",
            "💡 **Pro Tip**: The tool description and schema contain all technical details. Focus on using parameters that are relevant to the user's specific request and goals."
        ]
        
        return "\n".join(content_parts)
