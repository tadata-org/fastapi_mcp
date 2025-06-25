"""
Tests for MCP Prompts functionality.
"""

import pytest
from typing import List, Optional
from fastapi import FastAPI

from fastapi_mcp import FastApiMCP, PromptMessage, TextContent, ImageContent
from fastapi_mcp.prompts import PromptRegistry


class TestPromptRegistry:
    """Test the PromptRegistry class."""

    def test_empty_registry(self):
        """Test that empty registry works correctly."""
        registry = PromptRegistry()
        assert not registry.has_prompts()
        assert registry.get_prompt_list() == []

    def test_register_simple_prompt(self):
        """Test registering a simple prompt function."""
        registry = PromptRegistry()

        @registry.register_prompt("test_prompt", "Test Prompt", "A test prompt")
        def simple_prompt():
            return PromptMessage(role="user", content=TextContent(text="Hello, world!"))

        assert registry.has_prompts()
        prompts = registry.get_prompt_list()
        assert len(prompts) == 1

        prompt = prompts[0]
        assert prompt.name == "test_prompt"
        assert prompt.description == "A test prompt"
        assert len(prompt.arguments) == 0

    def test_register_prompt_with_parameters(self):
        """Test registering a prompt with parameters."""
        registry = PromptRegistry()

        @registry.register_prompt("param_prompt", "Parameterized Prompt")
        def param_prompt(message: str, count: int = 1):
            return PromptMessage(role="user", content=TextContent(text=f"Message: {message}, Count: {count}"))

        prompts = registry.get_prompt_list()
        assert len(prompts) == 1

        prompt = prompts[0]
        assert len(prompt.arguments) == 2

        # Check required parameter
        message_arg = next(arg for arg in prompt.arguments if arg.name == "message")
        assert message_arg.required is True

        # Check optional parameter
        count_arg = next(arg for arg in prompt.arguments if arg.name == "count")
        assert count_arg.required is False

    @pytest.mark.asyncio
    async def test_execute_prompt(self):
        """Test executing a registered prompt."""
        registry = PromptRegistry()

        @registry.register_prompt("echo_prompt")
        def echo_prompt(text: str):
            return PromptMessage(role="user", content=TextContent(text=f"Echo: {text}"))

        messages = await registry.get_prompt("echo_prompt", {"text": "Hello"})
        assert len(messages) == 1

        message = messages[0]
        assert message.role == "user"
        assert hasattr(message.content, "text")
        assert "Echo: Hello" in message.content.text

    @pytest.mark.asyncio
    async def test_execute_async_prompt(self):
        """Test executing an async prompt function."""
        registry = PromptRegistry()

        @registry.register_prompt("async_prompt")
        async def async_prompt(name: str):
            return PromptMessage(role="user", content=TextContent(text=f"Hello, {name}!"))

        messages = await registry.get_prompt("async_prompt", {"name": "World"})
        assert len(messages) == 1
        assert "Hello, World!" in messages[0].content.text

    @pytest.mark.asyncio
    async def test_execute_nonexistent_prompt(self):
        """Test executing a prompt that doesn't exist."""
        registry = PromptRegistry()

        with pytest.raises(ValueError, match="Prompt 'missing' not found"):
            await registry.get_prompt("missing")

    @pytest.mark.asyncio
    async def test_prompt_returns_list(self):
        """Test prompt that returns multiple messages."""
        registry = PromptRegistry()

        @registry.register_prompt("multi_prompt")
        def multi_prompt():
            return [
                PromptMessage(role="user", content=TextContent(text="First message")),
                PromptMessage(role="assistant", content=TextContent(text="Second message")),
            ]

        messages = await registry.get_prompt("multi_prompt")
        assert len(messages) == 2
        assert messages[0].role == "user"
        assert messages[1].role == "assistant"


class TestFastAPIMCPPrompts:
    """Test prompts integration with FastApiMCP."""

    def test_fastapi_mcp_has_prompt_decorator(self):
        """Test that FastApiMCP has a prompt decorator."""
        app = FastAPI()
        mcp = FastApiMCP(app)

        assert hasattr(mcp, "prompt")
        assert hasattr(mcp, "prompt_registry")
        assert isinstance(mcp.prompt_registry, PromptRegistry)

    def test_fastapi_mcp_prompt_registration(self):
        """Test registering prompts through FastApiMCP."""
        app = FastAPI()
        mcp = FastApiMCP(app)

        @mcp.prompt("test_prompt", title="Test", description="Test prompt")
        def test_prompt(input_text: str):
            return PromptMessage(role="user", content=TextContent(text=f"Input: {input_text}"))

        assert mcp.prompt_registry.has_prompts()
        prompts = mcp.prompt_registry.get_prompt_list()
        assert len(prompts) == 1
        assert prompts[0].name == "test_prompt"

    @pytest.mark.asyncio
    async def test_fastapi_mcp_prompt_execution(self):
        """Test executing prompts through FastApiMCP."""
        app = FastAPI()
        mcp = FastApiMCP(app)

        @mcp.prompt("greet", description="Greeting prompt")
        def greet_prompt(name: str, greeting: str = "Hello"):
            return PromptMessage(role="user", content=TextContent(text=f"{greeting}, {name}!"))

        messages = await mcp.prompt_registry.get_prompt("greet", {"name": "Alice", "greeting": "Hi"})

        assert len(messages) == 1
        assert "Hi, Alice!" in messages[0].content.text


class TestPromptTypes:
    """Test prompt-related type definitions."""

    def test_text_content_creation(self):
        """Test creating TextContent."""
        content = TextContent(text="Hello, world!")
        assert content.type == "text"
        assert content.text == "Hello, world!"

    def test_image_content_creation(self):
        """Test creating ImageContent."""
        content = ImageContent(data="base64data", mimeType="image/png")
        assert content.type == "image"
        assert content.data == "base64data"
        assert content.mimeType == "image/png"

    def test_prompt_message_creation(self):
        """Test creating PromptMessage."""
        message = PromptMessage(role="user", content=TextContent(text="Test message"))
        assert message.role == "user"
        assert message.content.type == "text"
        assert message.content.text == "Test message"


class TestPromptComplexScenarios:
    """Test complex prompt scenarios."""

    @pytest.mark.asyncio
    async def test_prompt_with_complex_types(self):
        """Test prompt with complex parameter types."""
        registry = PromptRegistry()

        @registry.register_prompt("complex_prompt")
        def complex_prompt(items: List[str], count: Optional[int] = None, enabled: bool = True):
            text = f"Items: {items}, Count: {count}, Enabled: {enabled}"
            return PromptMessage(role="user", content=TextContent(text=text))

        prompts = registry.get_prompt_list()
        prompt = prompts[0]

        # Check that we have the right number of arguments
        assert len(prompt.arguments) == 3

        # Execute the prompt
        messages = await registry.get_prompt("complex_prompt", {"items": ["a", "b", "c"], "count": 5, "enabled": False})

        assert len(messages) == 1
        assert "Items: ['a', 'b', 'c']" in messages[0].content.text

    @pytest.mark.asyncio
    async def test_prompt_error_handling(self):
        """Test error handling in prompt execution."""
        registry = PromptRegistry()

        @registry.register_prompt("error_prompt")
        def error_prompt():
            raise ValueError("Test error")

        with pytest.raises(ValueError, match="Error executing prompt 'error_prompt'"):
            await registry.get_prompt("error_prompt")


class TestAutoGeneratedToolPrompts:
    """Test auto-generation of tool prompts."""

    def test_auto_register_tool_prompts(self):
        """Test that tool prompts are auto-registered."""
        from fastapi import FastAPI
        from fastapi_mcp.openapi.convert import convert_openapi_to_mcp_tools
        from fastapi.openapi.utils import get_openapi
        
        app = FastAPI()
        
        @app.get("/test")
        async def test_endpoint():
            """Test endpoint."""
            return {"message": "test"}
        
        # Generate OpenAPI schema and convert to tools
        openapi_schema = get_openapi(
            title=app.title, version=app.version, routes=app.routes
        )
        tools, operation_map = convert_openapi_to_mcp_tools(openapi_schema)
        
        registry = PromptRegistry()
        registry.auto_register_tool_prompts(tools, operation_map)
        
        # Check that auto-generated prompts exist
        assert registry.has_prompts()
        prompts = registry.get_prompt_list()
        
        # Should have one prompt for the test endpoint
        tool_prompts = [p for p in prompts if p.name.startswith("use_")]
        assert len(tool_prompts) >= 1
        
        # Check the auto-generated prompt has correct content
        use_test_prompt = tool_prompts[0]
        assert "Best practices and guidance" in use_test_prompt.description

    @pytest.mark.asyncio
    async def test_auto_generated_prompt_execution(self):
        """Test executing an auto-generated prompt."""
        from fastapi import FastAPI
        from fastapi_mcp.openapi.convert import convert_openapi_to_mcp_tools
        from fastapi.openapi.utils import get_openapi
        
        app = FastAPI()
        
        @app.post("/create_item")
        async def create_item(name: str, price: float):
            """Create a new item."""
            return {"name": name, "price": price}
        
        # Generate tools and auto-register prompts
        openapi_schema = get_openapi(
            title=app.title, version=app.version, routes=app.routes
        )
        tools, operation_map = convert_openapi_to_mcp_tools(openapi_schema)
        
        registry = PromptRegistry()
        registry.auto_register_tool_prompts(tools, operation_map)
        
        # Find and execute the auto-generated prompt
        prompts = registry.get_prompt_list()
        tool_prompts = [p for p in prompts if p.name.startswith("use_")]
        assert len(tool_prompts) >= 1
        
        # Execute the first auto-generated prompt
        prompt_name = tool_prompts[0].name
        messages = await registry.get_prompt(prompt_name)
        
        assert len(messages) == 1
        message = messages[0]
        assert message.role == "user"
        assert "Key Guidelines" in message.content.text
        assert "Best Practices" in message.content.text
