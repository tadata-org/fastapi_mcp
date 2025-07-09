"""
Example demonstrating MCP Prompts support in FastAPI-MCP.

This example shows:
1. How to create custom prompt templates for AI interactions
2. Three different approaches to controlling prompt auto-generation:
   - Auto-generated prompts only (default)
   - Custom prompts only (disabled auto-generation)
   - Mixed approach (auto-generated + custom overrides)
3. API-related prompts including tool guidance and troubleshooting
4. How to override auto-generated prompts with enhanced custom versions
"""

from typing import Optional
from fastapi import FastAPI

from fastapi_mcp import FastApiMCP, PromptMessage, TextContent
from examples.shared.setup import setup_logging

setup_logging()

app = FastAPI(
    title="Prompts Example API", description="An example API demonstrating MCP Prompts functionality", version="1.0.0"
)

# Create MCP server with auto-generated prompts enabled (default: True)
# Set auto_generate_prompts=False to disable auto-generation and only use custom prompts
mcp = FastApiMCP(app, auto_generate_prompts=True)

# ===== PROMPT CONTROL OPTIONS =====
# This example demonstrates three different approaches to managing prompts:
#
# Option 1: Auto-generated prompts only (default behavior)
# mcp = FastApiMCP(app, auto_generate_prompts=True)  # This is what we're using above
#
# Option 2: Custom prompts only (no auto-generation)
# mcp = FastApiMCP(app, auto_generate_prompts=False)
# # Then define only custom prompts with @mcp.prompt()
#
# Option 3: Mixed approach (auto-generated + custom overrides)
# mcp = FastApiMCP(app, auto_generate_prompts=True)  # Auto-generate for all tools
# # Then override specific ones or add additional custom prompts


# Regular FastAPI endpoints (these will get auto-generated prompts)
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/items")
async def list_items(skip: int = 0, limit: int = 10):
    """List all items with pagination."""
    # This would return actual items in a real app
    return [{"id": i, "name": f"Item {i}"} for i in range(skip, skip + limit)]


@app.post("/items")
async def create_item(name: str, description: str, price: float):
    """Create a new item."""
    return {"id": 123, "name": name, "description": description, "price": price}


# Example 1: Basic welcome prompt
@mcp.prompt("welcome", title="Welcome Message", description="Generate a friendly welcome message")
def welcome_prompt():
    """Generate a welcome message for API users."""
    return PromptMessage(
        role="user",
        content=TextContent(text="Please provide a warm and friendly welcome message for new users of our API."),
    )


# Example 2: Custom tool prompt override (demonstrates Option 3: Mixed approach)
# This overrides the auto-generated prompt for the create_item tool
@mcp.prompt("use_create_item", title="Create Item Tool Guide", description="Custom guidance for creating items")
def create_item_guide():
    """Override the default auto-generated prompt for the create_item tool.

    This demonstrates how you can enhance auto-generated prompts with custom,
    domain-specific guidance while keeping auto-generation for other tools.
    """
    return PromptMessage(
        role="user",
        content=TextContent(
            text="""Use the create_item tool to add new items to the inventory system.

**Best Practices:**
1. Always provide a unique, descriptive name for new items
2. Include a clear, detailed description explaining the item's purpose
3. Set a reasonable price (must be greater than 0)
4. Consider the target audience when naming and describing items

**Parameter Guidelines:**
- **name**: Use clear, concise naming (e.g., "Wireless Bluetooth Headphones")
- **description**: Be specific about features and use cases
- **price**: Use decimal format for currency (e.g., 29.99)

**Common Issues to Avoid:**
- Vague or unclear item names
- Missing or incomplete descriptions  
- Negative or zero prices
- Duplicate item names

**Example:**
```
name: "Professional Wireless Mouse"
description: "Ergonomic wireless mouse with precision tracking, suitable for office work and gaming"
price: 45.99
```

This tool will create the item and return the generated item with its assigned details.

**Note**: This is a custom override of the auto-generated prompt. The other endpoints
(health_check, list_items) will use their auto-generated prompts for guidance.
            """
        ),
    )


# Example 3: API documentation prompt
@mcp.prompt(
    "api_documentation",
    title="API Documentation Helper",
    description="Generate comprehensive API documentation prompts",
)
def api_docs_prompt(endpoint_path: Optional[str] = None):
    """Generate prompts for API documentation help."""
    if endpoint_path:
        return PromptMessage(
            role="user",
            content=TextContent(
                text=f"""Please provide comprehensive documentation for the {endpoint_path} endpoint.

Include the following details:
1. **Purpose**: What this endpoint does and when to use it
2. **HTTP Method**: GET, POST, PUT, DELETE, etc.
3. **Parameters**: All required and optional parameters with types and descriptions
4. **Request Examples**: Sample requests with proper formatting
5. **Response Format**: Expected response structure and data types
6. **Status Codes**: Possible HTTP status codes and their meanings
7. **Error Handling**: Common errors and how to resolve them
8. **Use Cases**: Practical examples of when to use this endpoint

Make the documentation clear and actionable for developers.
                """
            ),
        )
    else:
        # Generate dynamic content based on current API routes
        routes_info = []
        for route in app.routes:
            if hasattr(route, "methods") and hasattr(route, "path"):
                # Filter out internal routes
                if not route.path.startswith("/mcp") and route.path != "/docs" and route.path != "/openapi.json":
                    methods = ", ".join(m for m in route.methods if m != "HEAD")
                    routes_info.append(f"- {methods} {route.path}")

        return PromptMessage(
            role="user",
            content=TextContent(
                text=f"""Help me understand this API and create comprehensive documentation.

**Available API Endpoints:**
{chr(10).join(routes_info)}

Please provide:
1. **API Overview**: Purpose and main functionality of this API
2. **Getting Started**: How to begin using the API
3. **Endpoint Guide**: Brief description of what each endpoint does
4. **Common Workflows**: Step-by-step guides for typical use cases
5. **Best Practices**: Recommendations for effective API usage
6. **Error Handling**: How to handle common errors and edge cases

**Focus Areas:**
- Make it beginner-friendly but comprehensive
- Include practical examples
- Explain the relationships between different endpoints
- Provide guidance on proper usage patterns

Note: This API also supports MCP (Model Context Protocol) prompts to help with tool usage.
                """
            ),
        )


# Example 4: API troubleshooting prompt
@mcp.prompt("troubleshoot", title="API Troubleshooting Assistant", description="Help troubleshoot API issues")
async def troubleshoot_prompt(error_message: str, endpoint: Optional[str] = None, status_code: Optional[int] = None):
    """Generate troubleshooting prompts based on error information."""
    context_parts = [f"**Error Message**: {error_message}"]

    if endpoint:
        context_parts.append(f"**Endpoint**: {endpoint}")
    if status_code:
        context_parts.append(f"**Status Code**: {status_code}")

    context = "\n".join(context_parts)

    return PromptMessage(
        role="user",
        content=TextContent(
            text=f"""I'm experiencing an issue with this API:

{context}

Please help me troubleshoot this issue:

1. **Root Cause Analysis**: What might be causing this error?
2. **Immediate Steps**: What should I check first?
3. **Resolution**: How can I fix this specific issue?
4. **Prevention**: How can I avoid this error in the future?
5. **Alternative Approaches**: Are there other ways to achieve the same goal?

**Additional Context to Consider:**
- Check if all required parameters are provided
- Verify parameter types and formats
- Ensure proper authentication if required
- Confirm the endpoint URL is correct
- Review any rate limiting or quota restrictions

Please provide specific, actionable advice based on the error details above.
            """
        ),
    )


# ===== DEMONSTRATION OF ALL THREE CONTROL OPTIONS =====


def demonstrate_prompt_control_options():
    """
    This function demonstrates all three prompt control options.
    Uncomment the sections below to try different approaches.
    """

    # ===== OPTION 1: Auto-generated prompts only =====
    # This is what we're using in the main example above
    print("Current setup: Auto-generated prompts enabled (default)")
    print("- Creates 'use_health_check', 'use_list_items', 'use_create_item' prompts automatically")
    print("- 'use_create_item' is overridden with our custom version")
    print("- Also includes custom prompts: 'welcome', 'api_documentation', 'troubleshoot'")

    """
    # ===== OPTION 2: Custom prompts only =====
    # Uncomment this section to try custom-only approach
    
    from fastapi import FastAPI
    
    app_custom = FastAPI(title="Custom Prompts Only API")
    
    @app_custom.get("/users")
    def list_users(): return [{"id": 1, "name": "User 1"}]
    
    @app_custom.post("/users") 
    def create_user(name: str): return {"id": 2, "name": name}
    
    # Disable auto-generation
    mcp_custom = FastApiMCP(app_custom, auto_generate_prompts=False)
    
    @mcp_custom.prompt("user_management_help")
    def user_help():
        return PromptMessage(
            role="user",
            content=TextContent(text="Help me manage users effectively...")
        )
    
    @mcp_custom.prompt("create_user_workflow")
    def user_workflow():
        return PromptMessage(
            role="user", 
            content=TextContent(text="Guide me through user creation...")
        )
    
    mcp_custom.mount("/custom-mcp")
    print("Custom-only setup would have only 2 prompts: user_management_help, create_user_workflow")
    """

    """
    # ===== OPTION 3: Mixed approach (what we're demonstrating above) =====
    # This is the approach used in our main example:
    # - Auto-generate prompts for all tools (auto_generate_prompts=True)
    # - Override specific auto-generated prompts (use_create_item)
    # - Add additional custom prompts (welcome, api_documentation, troubleshoot)
    
    # This gives you:
    # Auto-generated: use_health_check, use_list_items, use_create_item (overridden)
    # Custom: welcome, api_documentation, troubleshoot, use_create_item (custom version)
    """


# Mount the MCP server (this will auto-generate prompts for all tools)
mcp.mount()

# Print information about the current setup
if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("FastAPI-MCP Prompts Example")
    print("=" * 60)

    demonstrate_prompt_control_options()

    print(f"\nTotal prompts available: {len(mcp.prompt_registry.get_prompt_list())}")
    print("\nPrompt names:")
    for prompt in mcp.prompt_registry.get_prompt_list():
        prompt_type = "Auto-generated" if prompt.name.startswith("use_") else "Custom"
        if prompt.name == "use_create_item":
            prompt_type += " (Overridden)"
        print(f"  - {prompt.name} ({prompt_type})")

    print("\n" + "=" * 60)
    print("Choose your preferred approach:")
    print("1. Auto-generated only: FastApiMCP(app, auto_generate_prompts=True)")
    print("2. Custom only: FastApiMCP(app, auto_generate_prompts=False)")
    print("3. Mixed (current): Auto-generate + custom overrides/additions")
    print("=" * 60)

    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
