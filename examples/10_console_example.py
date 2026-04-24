"""
Example demonstrating the MCP Web Console feature.

This example shows how to:
1. Create a FastAPI app with some endpoints
2. Add MCP server capabilities
3. Mount the Web Console for visualization and debugging

Access the console at: http://localhost:8000/mcp-console
"""

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional

from fastapi_mcp import FastApiMCP


app = FastAPI(
    title="MCP Console Demo",
    description="A demo FastAPI app with MCP Web Console",
    version="1.0.0",
)


class User(BaseModel):
    id: int
    name: str
    email: str
    age: Optional[int] = None
    active: bool = True


class CreateUserRequest(BaseModel):
    name: str
    email: str
    age: Optional[int] = None


class UpdateUserRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    age: Optional[int] = None
    active: Optional[bool] = None


users_db: dict[int, User] = {}


sample_users = [
    User(id=1, name="Alice Johnson", email="alice@example.com", age=30),
    User(id=2, name="Bob Smith", email="bob@example.com", age=25),
    User(id=3, name="Charlie Brown", email="charlie@example.com", age=35),
]
for user in sample_users:
    users_db[user.id] = user


@app.get("/users/", response_model=List[User], tags=["users"], operation_id="list_users")
async def list_users(
    skip: int = Query(0, ge=0, description="Number of users to skip"),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of users to return"),
    active_only: bool = Query(False, description="Only return active users"),
):
    """
    List all users with pagination support.

    Returns a paginated list of users from the database.
    """
    results = list(users_db.values())

    if active_only:
        results = [u for u in results if u.active]

    return results[skip : skip + limit]


@app.get("/users/{user_id}", response_model=User, tags=["users"], operation_id="get_user")
async def get_user(user_id: int):
    """
    Get a specific user by ID.

    Returns the user details if found, otherwise raises a 404 error.
    """
    if user_id not in users_db:
        raise HTTPException(status_code=404, detail="User not found")
    return users_db[user_id]


@app.post("/users/", response_model=User, tags=["users"], operation_id="create_user")
async def create_user(user: CreateUserRequest):
    """
    Create a new user.

    Generates a new unique ID for the user and adds them to the database.
    Returns the created user with the assigned ID.
    """
    new_id = max(users_db.keys(), default=0) + 1
    new_user = User(
        id=new_id,
        name=user.name,
        email=user.email,
        age=user.age,
        active=True,
    )
    users_db[new_id] = new_user
    return new_user


@app.put("/users/{user_id}", response_model=User, tags=["users"], operation_id="update_user")
async def update_user(user_id: int, user: UpdateUserRequest):
    """
    Update an existing user.

    Only updates the fields that are provided in the request.
    Raises a 404 error if the user does not exist.
    """
    if user_id not in users_db:
        raise HTTPException(status_code=404, detail="User not found")

    existing = users_db[user_id]

    if user.name is not None:
        existing.name = user.name
    if user.email is not None:
        existing.email = user.email
    if user.age is not None:
        existing.age = user.age
    if user.active is not None:
        existing.active = user.active

    return existing


@app.delete("/users/{user_id}", tags=["users"], operation_id="delete_user")
async def delete_user(user_id: int):
    """
    Delete a user.

    Removes the user from the database.
    Raises a 404 error if the user does not exist.
    """
    if user_id not in users_db:
        raise HTTPException(status_code=404, detail="User not found")

    del users_db[user_id]
    return {"message": "User deleted successfully", "user_id": user_id}


@app.get("/users/search/", response_model=List[User], tags=["search"], operation_id="search_users")
async def search_users(
    q: Optional[str] = Query(None, description="Search query for name or email"),
    min_age: Optional[int] = Query(None, description="Minimum age filter"),
    max_age: Optional[int] = Query(None, description="Maximum age filter"),
    active: Optional[bool] = Query(None, description="Filter by active status"),
):
    """
    Search users with various filter options.

    Allows searching by name/email, and filtering by age range and active status.
    """
    results = list(users_db.values())

    if q:
        q = q.lower()
        results = [
            user for user in results
            if q in user.name.lower() or q in user.email.lower()
        ]

    if min_age is not None:
        results = [user for user in results if user.age is not None and user.age >= min_age]

    if max_age is not None:
        results = [user for user in results if user.age is not None and user.age <= max_age]

    if active is not None:
        results = [user for user in results if user.active == active]

    return results


@app.get("/health", tags=["system"], operation_id="health_check")
async def health_check():
    """
    Health check endpoint.

    Returns the current health status of the application.
    """
    return {
        "status": "healthy",
        "users_count": len(users_db),
    }


mcp = FastApiMCP(app)

mcp.mount_http()

mcp.mount_console(
    mount_path="/mcp-console",
    log_max_size=1000,
)

print("=" * 60)
print("FastAPI-MCP Console Demo")
print("=" * 60)
print()
print("Available endpoints:")
print("  - Swagger UI:  http://localhost:8000/docs")
print("  - MCP HTTP:    http://localhost:8000/mcp")
print("  - MCP Console: http://localhost:8000/mcp-console")
print()
print("Access the Web Console to:")
print("  - View all registered MCP tools")
print("  - See tool descriptions, parameters, and responses")
print("  - Test tool executions with custom parameters")
print("  - View real-time call logs with timings")
print()
print("=" * 60)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
