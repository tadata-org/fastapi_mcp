from typing import List

from fastapi import FastAPI, Body
from pydantic import BaseModel
import pytest

from tests.fixtures.conftest import make_fastapi_app_base


class Tag(BaseModel):
    name: str


def make_app_with_array_body() -> FastAPI:
    """App with a top-level (non-object) array request body (#319 part 1)."""
    app = make_fastapi_app_base()

    @app.post("/bulk-tags", operation_id="bulk_tags")
    async def bulk_tags(tags: List[Tag] = Body(..., description="The tags to create")):
        return {"count": len(tags)}

    return app


def make_app_with_body_path_collision() -> FastAPI:
    """App where a body field name collides with a path parameter (#319 part 2)."""

    class OrderRequest(BaseModel):
        item_id: int
        quantity: int

    from fastapi import Path

    app = make_fastapi_app_base()

    @app.put("/orders/{item_id}", operation_id="update_order")
    async def update_order(
        item_id: int = Path(..., description="The ID of the order to update"),
        order: OrderRequest = Body(..., description="The order update"),
    ):
        return {"path_id": item_id, "body_id": order.item_id, "quantity": order.quantity}

    return app


@pytest.fixture
def simple_fastapi_app_with_array_body() -> FastAPI:
    return make_app_with_array_body()


@pytest.fixture
def simple_fastapi_app_with_body_path_collision() -> FastAPI:
    return make_app_with_body_path_collision()
