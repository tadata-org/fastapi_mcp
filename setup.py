from setuptools import setup
import tomli

# Read dependencies from pyproject.toml
with open("pyproject.toml", "rb") as f:
    pyproject_data = tomli.load(f)

# Get dependencies from pyproject.toml
dependencies = pyproject_data["project"]["dependencies"]

setup(
    name="fastapi-mcp",
    version="0.1.7",
    description="Automatic MCP server generator for FastAPI applications - converts FastAPI endpoints to MCP tools for LLM integration",
    author="Tadata Inc.",
    author_email="itay@tadata.com",
    packages=["fastapi_mcp"],
    python_requires=">=3.10",
    install_requires=dependencies,
    entry_points={
        "console_scripts": [
            "fastapi-mcp=fastapi_mcp.cli:app",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Internet :: WWW/HTTP",
        "Framework :: FastAPI",
    ],
    keywords=["fastapi", "openapi", "mcp", "llm", "claude", "ai", "tools", "api", "conversion"],
    project_urls={
        "Homepage": "https://github.com/tadata-org/fastapi_mcp",
        "Documentation": "https://github.com/tadata-org/fastapi_mcp#readme",
        "Bug Tracker": "https://github.com/tadata-org/fastapi_mcp/issues",
        "PyPI": "https://pypi.org/project/fastapi-mcp/",
        "Source Code": "https://github.com/tadata-org/fastapi_mcp",
        "Changelog": "https://github.com/tadata-org/fastapi_mcp/blob/main/CHANGELOG.md",
    },
)
