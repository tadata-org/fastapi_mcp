# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.5]

### Fixed
- [Issue #25](https://github.com/tadata-org/fastapi_mcp/issues/25): Dynamically creating tools function so tools are useable.

## [0.1.4]

### Fixed
- [Issue #8](https://github.com/tadata-org/fastapi_mcp/issues/8): Converted tools unuseable due to wrong passing of arguments.

## [0.1.3]

### Fixed
- Dependency resolution issue with `mcp` package and `pydantic-settings`

## [0.1.2]

### Changed
- Complete refactor: transformed from a code generator to a direct integration library
- Replaced the CLI-based approach with a direct API for adding MCP servers to FastAPI applications
- Integrated MCP servers now mount directly to FastAPI apps at runtime instead of generating separate code
- Simplified the API with a single `add_mcp_server` function for quick integration
- Removed code generation entirely in favor of runtime integration

### Added
- Main `add_mcp_server` function for simple MCP server integration
- Support for adding custom MCP tools alongside API-derived tools
- Improved test suite
- Manage with uv

### Removed
- CLI interface and all associated commands (generate, run, install, etc.)
- Code generation functionality

## [0.1.1] - 2024-07-03

### Fixed
- Added support for PEP 604 union type syntax (e.g., `str | None`) in FastAPI endpoints
- Improved type handling in model field generation for newer Python versions (3.10+)
- Fixed compatibility issues with modern type annotations in path parameters, query parameters, and Pydantic models

## [0.1.0] - 2024-03-08

### Added
- Initial release of FastAPI-MCP
- Core functionality for converting FastAPI applications to MCP servers
- CLI tool for generating, running, and installing MCP servers
- Automatic discovery of FastAPI endpoints
- Type-safe conversion from FastAPI endpoints to MCP tools
- Documentation preservation from FastAPI to MCP
- Claude integration for easy installation and use
- API integration that automatically makes HTTP requests to FastAPI endpoints
- Examples directory with sample FastAPI application
- Basic test suite 