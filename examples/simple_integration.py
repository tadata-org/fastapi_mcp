"""
Simple example of using FastAPI-MCP to add an MCP server to a FastAPI app.
"""

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional

from fastapi_mcp import add_mcp_server


# Create a simple FastAPI app
app = FastAPI(
    title="Example API",
    description="A simple example API with integrated MCP server",
    version="0.1.0",
)


# Define some models
class Item(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    price: float
    tags: List[str] = []


# In-memory database
items_db: dict[int, Item] = {}


# Define some endpoints
@app.get("/items/", response_model=List[Item], tags=["items", "include_in_mcp"])
async def list_items(skip: int = 0, limit: int = 10):
    """
    List all items in the database.

    Returns a list of items, with pagination support.
    """
    return list(items_db.values())[skip : skip + limit]


@app.get("/items/{item_id}", response_model=Item, tags=["items", "include_in_mcp"])
async def read_item(item_id: int):
    """
    Get a specific item by its ID.

    Raises a 404 error if the item does not exist.
    """
    if item_id not in items_db:
        raise HTTPException(status_code=404, detail="Item not found")
    return items_db[item_id]


@app.post("/items/", response_model=Item, tags=["items", "include_in_mcp"])
async def create_item(item: Item):
    """
    Create a new item in the database.

    Returns the created item with its assigned ID.
    """
    items_db[item.id] = item
    return item


@app.put("/items/{item_id}", response_model=Item, tags=["items", "include_in_mcp"])
async def update_item(item_id: int, item: Item):
    """
    Update an existing item.

    Raises a 404 error if the item does not exist.
    """
    if item_id not in items_db:
        raise HTTPException(status_code=404, detail="Item not found")

    item.id = item_id
    items_db[item_id] = item
    return item


@app.delete("/items/{item_id}", tags=["items", "include_in_mcp"])
async def delete_item(item_id: int):
    """
    Delete an item from the database.

    Raises a 404 error if the item does not exist.
    """
    if item_id not in items_db:
        raise HTTPException(status_code=404, detail="Item not found")

    del items_db[item_id]
    return {"message": "Item deleted successfully"}


@app.get("/items/search/", response_model=List[Item], tags=["search", "include_in_mcp"])
async def search_items(
    q: Optional[str] = Query(None, description="Search query string"),
    min_price: Optional[float] = Query(None, description="Minimum price"),
    max_price: Optional[float] = Query(None, description="Maximum price"),
    tags: List[str] = Query([], description="Filter by tags"),
):
    """
    Search for items with various filters.

    Returns a list of items that match the search criteria.
    """
    results = list(items_db.values())

    # Filter by search query
    if q:
        q = q.lower()
        results = [
            item for item in results if q in item.name.lower() or (item.description and q in item.description.lower())
        ]

    # Filter by price range
    if min_price is not None:
        results = [item for item in results if item.price >= min_price]
    if max_price is not None:
        results = [item for item in results if item.price <= max_price]

    # Filter by tags
    if tags:
        results = [item for item in results if all(tag in item.tags for tag in tags)]

    return results


# Add sample data
sample_items = [
    Item(id=1, name="Hammer", description="A tool for hammering nails", price=9.99, tags=["tool", "hardware"]),
    Item(id=2, name="Screwdriver", description="A tool for driving screws", price=7.99, tags=["tool", "hardware"]),
    Item(id=3, name="Wrench", description="A tool for tightening bolts", price=12.99, tags=["tool", "hardware"]),
    Item(id=4, name="Saw", description="A tool for cutting wood", price=19.99, tags=["tool", "hardware", "cutting"]),
    Item(id=5, name="Drill", description="A tool for drilling holes", price=49.99, tags=["tool", "hardware", "power"]),
]

for item in sample_items:
    items_db[item.id] = item


# Add MCP server to the FastAPI app
mcp_server = add_mcp_server(
    app,
    mount_path="/mcp",
    name="Item API MCP",
    description="MCP server for the Item API",
    base_url="http://localhost:8000",
    describe_all_responses=False,  # Only describe the success response in tool descriptions
    describe_full_response_schema=False,  # Only show LLM-friendly example response in tool descriptions, not the full json schema
)


# Optionally, you can add custom MCP tools not based on FastAPI endpoints
@mcp_server.tool()
async def get_item_count() -> int:
    """Get the total number of items in the database."""
    return len(items_db)


# Run the server if this file is executed directly
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
