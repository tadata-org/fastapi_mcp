from typing import Optional, List, Any

from fastapi import FastAPI, Query, Path, Body, HTTPException
import pytest

from tests.fixtures.conftest import make_fastapi_app_base

from .types import Item


def make_simple_fastapi_app(parametrized_config: dict[str, Any] | None = None) -> FastAPI:
    app = make_fastapi_app_base(parametrized_config=parametrized_config)
    items = [
        Item(id=1, name="Item 1", price=10.0, tags=["tag1", "tag2"], description="Item 1 description"),
        Item(id=2, name="Item 2", price=20.0, tags=["tag2", "tag3"]),
        Item(id=3, name="Item 3", price=30.0, tags=["tag3", "tag4"], description="Item 3 description"),
    ]

    @app.get("/items/", response_model=List[Item], tags=["items"], operation_id="list_items")
    async def list_items(
        skip: int = Query(0, description="Number of items to skip"),
        limit: int = Query(10, description="Max number of items to return"),
        sort_by: Optional[str] = Query(None, description="Field to sort by"),
    ) -> List[Item]:
        """List all items with pagination and sorting options."""
        return items[skip : skip + limit]

    @app.get("/items/{item_id}", response_model=Item, tags=["items"], operation_id="get_item")
    async def read_item(
        item_id: int = Path(..., description="The ID of the item to retrieve"),
        include_details: bool = Query(False, description="Include additional details"),
    ) -> Item:
        """Get a specific item by its ID with optional details."""
        found_item = next((item for item in items if item.id == item_id), None)
        if found_item is None:
            raise HTTPException(status_code=404, detail="Item not found")
        return found_item

    @app.post("/items/", response_model=Item, tags=["items"], operation_id="create_item")
    async def create_item(item: Item = Body(..., description="The item to create")) -> Item:
        """Create a new item in the database."""
        items.append(item)
        return item

    @app.put("/items/{item_id}", response_model=Item, tags=["items"], operation_id="update_item")
    async def update_item(
        item_id: int = Path(..., description="The ID of the item to update"),
        item: Item = Body(..., description="The updated item data"),
    ) -> Item:
        """Update an existing item."""
        item.id = item_id
        return item

    @app.delete("/items/{item_id}", status_code=204, tags=["items"], operation_id="delete_item")
    async def delete_item(item_id: int = Path(..., description="The ID of the item to delete")) -> None:
        """Delete an item from the database."""
        return None

    @app.get("/error", tags=["error"], operation_id="raise_error")
    async def raise_error() -> None:
        """Fail on purpose and cause a 500 error."""
        raise Exception("This is a test error")

    return app


@pytest.fixture
def simple_fastapi_app() -> FastAPI:
    return make_simple_fastapi_app()


@pytest.fixture
def simple_fastapi_app_with_root_path() -> FastAPI:
    return make_simple_fastapi_app(parametrized_config={"root_path": "/api/v1"})
