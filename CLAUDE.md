# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Environment Setup
```bash
uv sync                    # Install dependencies and create virtual environment
uv run pre-commit install  # Install pre-commit hooks
```

### Testing
```bash
uv run pytest                     # Run all tests
uv run pytest tests/test_*.py     # Run specific test file
uv run pytest -k "test_name"      # Run specific test by name
```

### Code Quality
```bash
uv run ruff check .        # Lint code
uv run ruff format .       # Format code
uv run mypy .             # Type checking
uv run pre-commit run     # Run all pre-commit checks
```

### Build and Package
```bash
uv build                  # Build package distributions
```

### Running Examples
```bash
# From project root
uv run python examples/01_basic_usage_example.py
# Or any other example file in examples/
```

## Architecture Overview

FastAPI-MCP is a library that converts FastAPI applications into Model Context Protocol (MCP) servers, allowing LLMs to interact with FastAPI endpoints as tools.

### Core Components

- **FastApiMCP**: Main class in `fastapi_mcp/server.py` that wraps a FastAPI app and exposes it as an MCP server
- **OpenAPI Conversion**: `fastapi_mcp/openapi/` converts FastAPI's OpenAPI schema to MCP tool definitions
- **Transport Layer**: `fastapi_mcp/transport/` provides HTTP and SSE transport implementations
- **Authentication**: `fastapi_mcp/auth/` handles OAuth and token-based auth integration

### Key Architecture Patterns

1. **Native FastAPI Integration**: Uses FastAPI's ASGI interface directly rather than HTTP calls
2. **Transport Abstraction**: Supports both HTTP (`mount_http()`) and SSE (`mount()`) transports
3. **Schema Preservation**: Maintains FastAPI's request/response schemas and documentation
4. **Dependency Injection**: Leverages FastAPI's dependency system for authentication

### Package Structure
- `fastapi_mcp/server.py` - Main FastApiMCP class
- `fastapi_mcp/openapi/` - OpenAPI to MCP conversion logic
- `fastapi_mcp/transport/` - HTTP and SSE transport implementations  
- `fastapi_mcp/auth/` - Authentication and OAuth support
- `fastapi_mcp/types.py` - Core type definitions
- `examples/` - Usage examples demonstrating various features
- `tests/` - Comprehensive test suite with fixtures

## Testing Notes

- Tests use pytest with asyncio support
- Test fixtures in `tests/fixtures/` provide example FastAPI apps
- Real transport tests verify actual HTTP/SSE communication