"""
Test cases for circular reference handling in OpenAPI schema resolution.
"""

import pytest
from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional
from fastapi.openapi.utils import get_openapi

from fastapi_mcp.openapi.convert import convert_openapi_to_mcp_tools
from fastapi_mcp.openapi.utils import resolve_schema_references


class User(BaseModel):
    """User model with circular reference to Post."""

    id: int
    name: str
    posts: List["Post"] = []


class Post(BaseModel):
    """Post model with circular reference to User."""

    id: int
    title: str
    author: "User"
    comments: List["Comment"] = []


class Comment(BaseModel):
    """Comment model with circular reference to Post."""

    id: int
    content: str
    post: "Post"


class TreeNode(BaseModel):
    """Tree node with self-reference."""

    id: int
    value: str
    children: List["TreeNode"] = []
    parent: Optional["TreeNode"] = None


def create_circular_reference_app() -> FastAPI:
    """Create a FastAPI app with circular reference models."""
    app = FastAPI(title="Circular Reference Test", version="1.0.0")

    @app.get("/users/{user_id}", operation_id="get_user")
    async def get_user(user_id: int) -> User:
        """Get a user by ID."""
        return User(id=user_id, name="Test User", posts=[])

    @app.get("/posts/{post_id}", operation_id="get_post")
    async def get_post(post_id: int) -> Post:
        """Get a post by ID."""
        return Post(id=post_id, title="Test Post", author=User(id=1, name="Author"))

    @app.get("/comments/{comment_id}", operation_id="get_comment")
    async def get_comment(comment_id: int) -> Comment:
        """Get a comment by ID."""
        return Comment(
            id=comment_id, content="Test Comment", post=Post(id=1, title="Post", author=User(id=1, name="Author"))
        )

    @app.get("/tree/{node_id}", operation_id="get_tree_node")
    async def get_tree_node(node_id: int) -> TreeNode:
        """Get a tree node by ID."""
        return TreeNode(id=node_id, value="Test Node", children=[])

    return app


def test_circular_reference_schema_resolution():
    """Test that circular references are handled gracefully."""
    app = create_circular_reference_app()

    # Generate OpenAPI schema
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        openapi_version=app.openapi_version,
        description=app.description,
        routes=app.routes,
    )

    # Test that resolve_schema_references doesn't raise RecursionError
    try:
        resolved_schema = resolve_schema_references(openapi_schema, openapi_schema)
        assert resolved_schema is not None
        # Should not raise RecursionError
    except RecursionError as e:
        pytest.fail(f"RecursionError occurred: {e}")


def test_circular_reference_mcp_conversion():
    """Test that MCP conversion works with circular references."""
    app = create_circular_reference_app()

    # Generate OpenAPI schema
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        openapi_version=app.openapi_version,
        description=app.description,
        routes=app.routes,
    )

    # Test that convert_openapi_to_mcp_tools doesn't raise RecursionError
    try:
        tools, operation_map = convert_openapi_to_mcp_tools(openapi_schema)

        # Should successfully convert without errors
        assert len(tools) == 4  # get_user, get_post, get_comment, get_tree_node
        assert len(operation_map) == 4

        # Check that tools are created properly
        for tool in tools:
            assert tool.name in ["get_user", "get_post", "get_comment", "get_tree_node"]
            assert tool.description is not None
            assert tool.inputSchema is not None

    except RecursionError as e:
        pytest.fail(f"RecursionError occurred during MCP conversion: {e}")


def test_self_reference_schema():
    """Test schema with self-reference (TreeNode)."""
    app = create_circular_reference_app()

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        openapi_version=app.openapi_version,
        description=app.description,
        routes=app.routes,
    )

    # Test that self-referencing schemas are handled
    try:
        resolved_schema = resolve_schema_references(openapi_schema, openapi_schema)

        # Check that TreeNode schema is properly resolved
        tree_node_schema = resolved_schema["components"]["schemas"]["TreeNode"]
        assert "properties" in tree_node_schema
        assert "children" in tree_node_schema["properties"]

    except RecursionError as e:
        pytest.fail(f"RecursionError occurred with self-reference: {e}")


def test_complex_circular_reference():
    """Test complex circular reference chain: User -> Post -> Comment -> Post."""
    app = create_circular_reference_app()

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        openapi_version=app.openapi_version,
        description=app.description,
        routes=app.routes,
    )

    # Test that complex circular references are handled
    try:
        resolved_schema = resolve_schema_references(openapi_schema, openapi_schema)

        # Check that all schemas are resolved
        assert "components" in resolved_schema
        assert "schemas" in resolved_schema["components"]

        schemas = resolved_schema["components"]["schemas"]
        assert "User" in schemas
        assert "Post" in schemas
        assert "Comment" in schemas
        assert "TreeNode" in schemas

    except RecursionError as e:
        pytest.fail(f"RecursionError occurred with complex circular reference: {e}")


def test_circular_reference_with_visited_paths():
    """Test that visited paths tracking works correctly."""
    # Create a simple schema with circular reference
    schema_with_circular_ref = {
        "components": {
            "schemas": {
                "ModelA": {"type": "object", "properties": {"b": {"$ref": "#/components/schemas/ModelB"}}},
                "ModelB": {"type": "object", "properties": {"a": {"$ref": "#/components/schemas/ModelA"}}},
            }
        }
    }

    # Test that circular reference is detected and handled
    try:
        resolved = resolve_schema_references(schema_with_circular_ref, schema_with_circular_ref)
        assert resolved is not None
    except RecursionError as e:
        pytest.fail(f"RecursionError occurred with visited paths tracking: {e}")
