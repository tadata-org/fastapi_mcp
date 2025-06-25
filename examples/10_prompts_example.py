"""
Example demonstrating MCP Prompts support in FastAPI-MCP.

This example shows how to create prompt templates that can be used by MCP clients
to generate structured messages for AI models.
"""

from typing import Optional
from fastapi import FastAPI

from fastapi_mcp import FastApiMCP, PromptMessage, TextContent
from examples.shared.setup import setup_logging

setup_logging()

app = FastAPI(
    title="Prompts Example API", description="An example API demonstrating MCP Prompts functionality", version="1.0.0"
)

# Create MCP server
mcp = FastApiMCP(app)


# Regular FastAPI endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


# Example 1: Simple prompt without parameters
@mcp.prompt("welcome", title="Welcome Message", description="Generate a friendly welcome message")
def welcome_prompt():
    """Generate a welcome message."""
    return PromptMessage(
        role="user",
        content=TextContent(text="Please provide a warm and friendly welcome message for new users of our API."),
    )


# Example 2: Prompt with parameters
@mcp.prompt("code_review", title="Code Review Assistant", description="Request code review with specific focus areas")
def code_review_prompt(code: str, language: str = "python", focus: str = "all"):
    """Generate a code review prompt with customizable parameters."""
    focus_instructions = {
        "performance": "Focus on performance optimizations and efficiency improvements.",
        "security": "Focus on security vulnerabilities and best practices.",
        "style": "Focus on code style, readability, and formatting.",
        "bugs": "Focus on finding potential bugs and logical errors.",
        "all": "Provide comprehensive review covering all aspects.",
    }

    instruction = focus_instructions.get(focus, focus_instructions["all"])

    return PromptMessage(
        role="user",
        content=TextContent(
            text=f"""Please review this {language} code:

            ```{language}
            {code}
            ```

            {instruction}

            Please provide:
            1. Overall assessment
            2. Specific issues found (if any)
            3. Improvement suggestions
            4. Best practices recommendations
            """),
        )


# Example 3: Multi-message prompt (conversation starter)
@mcp.prompt(
    "api_documentation",
    title="API Documentation Helper",
    description="Generate comprehensive API documentation prompts",
)
def api_docs_prompt(endpoint_path: Optional[str] = None):
    """Generate prompts for API documentation help."""
    if endpoint_path:
        return [
            PromptMessage(
                role="user",
                content=TextContent(text=f"Please explain how to use the {endpoint_path} endpoint in detail."),
            ),
            PromptMessage(
                role="assistant",
                content=TextContent(
                    text="I'd be happy to help you understand this API endpoint. Let me analyze it for you."
                ),
            ),
            PromptMessage(
                role="user", content=TextContent(text="Please include request/response examples and common use cases.")
            ),
        ]
    else:
        # Generate dynamic content based on current API routes
        routes_info = []
        for route in app.routes:
            if hasattr(route, "methods") and hasattr(route, "path"):
                methods = ", ".join(route.methods)
                routes_info.append(f"- {methods} {route.path}")

        return PromptMessage(
            role="user",
            content=TextContent(
                text=f"""Help me understand this API:

                Available endpoints:
                {chr(10).join(routes_info)}

                Please provide:
                1. Overview of the API's purpose
                2. How to use each endpoint effectively
                3. Authentication requirements (if any)
                4. Common workflows and examples
                """),
        )


# Example 4: Dynamic prompt using app state
@mcp.prompt("troubleshoot", title="API Troubleshooting Assistant", description="Help troubleshoot API issues")
async def troubleshoot_prompt(error_message: str, endpoint: Optional[str] = None, status_code: Optional[int] = None):
    """Generate troubleshooting prompts based on error information."""
    context_parts = [f"Error message: {error_message}"]

    if endpoint:
        context_parts.append(f"Endpoint: {endpoint}")
    if status_code:
        context_parts.append(f"Status code: {status_code}")

    context = "\n".join(context_parts)

    return PromptMessage(
        role="user",
        content=TextContent(
            text=f"""I'm experiencing an issue with this API:

            {context}

            Please help me:
            1. Understand what might be causing this error
            2. Suggest troubleshooting steps
            3. Provide solutions or workarounds
            4. Recommend preventive measures

            Please be specific and provide actionable advice.
            """),
        )


# Example 5: Prompt with image content (for future multi-modal support)
@mcp.prompt(
    "visual_analysis", title="Visual Content Analyzer", description="Analyze visual content with custom instructions"
)
def visual_analysis_prompt(analysis_type: str = "general", specific_focus: Optional[str] = None):
    """Generate prompts for visual content analysis."""
    base_instruction = {
        "general": "Please provide a comprehensive analysis of this image.",
        "technical": "Please analyze the technical aspects of this image (composition, lighting, etc.).",
        "content": "Please describe the content and context of this image in detail.",
        "accessibility": "Please provide an accessibility-focused description of this image.",
    }

    instruction = base_instruction.get(analysis_type, base_instruction["general"])

    if specific_focus:
        instruction += f" Pay special attention to: {specific_focus}"

    return PromptMessage(role="user", content=TextContent(text=instruction))


# Mount the MCP server
mcp.mount()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
