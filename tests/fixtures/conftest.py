from typing import Any
from fastapi import FastAPI


def make_fastapi_app_base(parametrized_config: dict[str, Any] | None = None) -> FastAPI:
    fastapi_config: dict[str, Any] = {
        "title": "Test API",
        "description": "A test API app for unit testing",
        "version": "0.1.0",
    }
    app = FastAPI(**fastapi_config | parametrized_config if parametrized_config is not None else {})
    return app
