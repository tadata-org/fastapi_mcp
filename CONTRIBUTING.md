# Contributing to FastAPI-MCP

First off, thank you for considering contributing to FastAPI-MCP!

## Development Setup

1.  Make sure you have Python 3.10+ installed
2.  Install [uv](https://docs.astral.sh/uv/getting-started/installation/) package manager
3.  Fork the repository
4.  Clone your fork

    ```bash
    git clone https://github.com/YOUR-USERNAME/fastapi_mcp.git
    cd fastapi-mcp

    # Add the upstream remote
    git remote add upstream https://github.com/tadata-org/fastapi_mcp.git
    ```

5.  Set up the development environment:

    ```bash
    uv sync
    ```

    That's it! The `uv sync` command will automatically create and use a virtual environment.

6.  Install pre-commit hooks:

    ```bash
    uv run pre-commit install
    uv run pre-commit run
    ```

    Pre-commit hooks will automatically run checks (like ruff, formatting, etc.) when you make a commit, ensuring your code follows our style guidelines.

### Running Commands

You have two options for running commands:

1.  **With the virtual environment activated**:
    ```bash
    source .venv/bin/activate  # On Windows: .venv\Scripts\activate

    # Then run commands directly
    pytest
    mypy .
    ruff check .
    ```

2.  **Without activating the virtual environment**:
    ```bash
    # Use uv run prefix for all commands
    uv run pytest
    uv run mypy .
    uv run ruff check .
    ```

Both approaches work - use whichever is more convenient for you.

> **Note:** For simplicity, commands in this guide are mostly written **without** the `uv run` prefix. If you haven't activated your virtual environment, remember to prepend `uv run` to all python-related commands and tools.

### Adding Dependencies

When adding new dependencies to the library:

1.  **Runtime dependencies** - packages needed to run the application:
    ```bash
    uv add new-package
    ```

2.  **Development dependencies** - packages needed for development, testing, or CI:
    ```bash
    uv add --group dev new-package
    ```

After adding dependencies, make sure to:
1.  Test that everything works with the new package
2.  Commit both `pyproject.toml` and `uv.lock` files:
    ```bash
    git add pyproject.toml uv.lock
    git commit -m "Add new-package dependency"
    ```

## Development Process

1. Fork the repository and set the upstream remote
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run type checking (`mypy .`)
5. Run the tests (`pytest`)
6. Format your code (`ruff check .` and `ruff format .`). Not needed if pre-commit is installed, as it will run it for you.
7. Commit your changes (`git commit -m 'Add some amazing feature'`)
8. Push to the branch (`git push origin feature/amazing-feature`)
9. Open a Pull Request. Make sure the Pull Request's base branch is [the original repository's](https://github.com/tadata-org/fastapi_mcp/) `main` branch.

## Code Style

We use the following tools to ensure code quality:

- **ruff** for linting and formatting
- **mypy** for type checking

Please make sure your code passes all checks before submitting a pull request:

```bash
# Check code formatting and style
ruff check .
ruff format .

# Check types
mypy .
```

## Testing

We use pytest for testing. Please write tests for any new features and ensure all tests pass:

```bash
# Run all tests
pytest
```

## Pull Request Process

1. Ensure your code follows the style guidelines of the project
2. Update the README.md with details of changes if applicable
3. The versioning scheme we use is [SemVer](http://semver.org/)
4. Include a descriptive commit message
5. Your pull request will be merged once it's reviewed and approved

## Code of Conduct

Please note we have a code of conduct, please follow it in all your interactions with the project.

- Be respectful and inclusive
- Be collaborative
- When disagreeing, try to understand why
- A diverse community is a strong community

## Questions?

Don't hesitate to open an issue if you have any questions about contributing to FastAPI-MCP.