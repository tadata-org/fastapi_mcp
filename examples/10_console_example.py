"""
FastAPI-MCP Console Example
============================

IMPORTANT: Browser Access Instructions
----------------------------------------
DO NOT use http://0.0.0.0:8000 in your browser!

- '0.0.0.0' means the server listens on ALL network interfaces
- For browser access, use: http://localhost:8000/mcp-console
- Or use: http://127.0.0.1:8000/mcp-console

This example also adds a redirect from root path '/' to '/mcp-console'.
"""

import sys
import site
from pathlib import Path

user_site = site.getusersitepackages()
if user_site and user_site not in sys.path:
    sys.path.insert(0, user_site)

project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

print("=" * 70)
print("FastAPI-MCP Console Example - Starting Up")
print("=" * 70)
print()

try:
    from fastapi_mcp import FastApiMCP
    methods = [m for m in dir(FastApiMCP) if not m.startswith('_')]
    
    if 'mount_console' not in methods:
        print("ERROR: 'mount_console' method not found!")
        print()
        print("This means Python is importing an older installed version,")
        print("not the local development version with console feature.")
        print()
        print("Try this to fix:")
        print("  1. pip uninstall fastapi-mcp -y")
        print("  2. pip install -e . --user --force-reinstall --no-deps")
        print()
        print("Or check where it's importing from:")
        import fastapi_mcp
        print(f"  Imported from: {fastapi_mcp.__file__}")
        print(f"  Expected from: {project_root / 'fastapi_mcp'}")
        sys.exit(1)
    
    print("[OK] FastApiMCP loaded with mount_console method")
    print(f"     Available methods: {methods}")
    print()
    
except ImportError as e:
    print(f"ERROR: Failed to import fastapi_mcp: {e}")
    print()
    print("Try installing dependencies:")
    print("  pip install fastapi uvicorn pydantic mcp httpx --user")
    sys.exit(1)

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import RedirectResponse, HTMLResponse
from pydantic import BaseModel
from typing import List, Optional

CONSOLE_PATH = "/mcp-console"

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

@app.get("/", include_in_schema=False)
async def redirect_to_console():
    """
    Redirect root path to the MCP Console.
    
    This makes it easier for users - if they accidentally visit
    the root path, they'll be redirected to the console.
    """
    return RedirectResponse(url=CONSOLE_PATH)

@app.get("/welcome", include_in_schema=False)
async def welcome_page():
    """
    Welcome page that shows all available endpoints.
    """
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>FastAPI-MCP Console Demo</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                max-width: 800px;
                margin: 50px auto;
                padding: 20px;
                line-height: 1.6;
            }}
            h1 {{ color: #6366f1; }}
            .endpoint {{
                background: #f3f4f6;
                padding: 15px;
                margin: 10px 0;
                border-radius: 8px;
            }}
            .endpoint a {{
                color: #6366f1;
                text-decoration: none;
                font-weight: bold;
            }}
            .endpoint a:hover {{ text-decoration: underline; }}
            .highlight {{
                background: #dbeafe;
                padding: 15px;
                border-radius: 8px;
                margin: 20px 0;
                border-left: 4px solid #3b82f6;
            }}
            .warning {{
                background: #fef3c7;
                padding: 15px;
                border-radius: 8px;
                margin: 20px 0;
                border-left: 4px solid #f59e0b;
            }}
        </style>
    </head>
    <body>
        <h1>FastAPI-MCP Console Demo</h1>
        
        <div class="warning">
            <strong>Important:</strong> '0.0.0.0' is not a valid browser address!
            <br>Use <strong>localhost</strong> or <strong>127.0.0.1</strong> instead.
        </div>
        
        <p>Welcome to the FastAPI-MCP Console Demo!</p>
        
        <h2>Available Endpoints:</h2>
        
        <div class="highlight">
            <strong>Recommended: </strong>
            <a href="{CONSOLE_PATH}">Open MCP Console</a> 
            - View tools, test executions, see logs
        </div>
        
        <div class="endpoint">
            <a href="/docs">Swagger UI</a> - Interactive API documentation
        </div>
        
        <div class="endpoint">
            <a href="/openapi.json">OpenAPI Schema</a> - Raw API schema
        </div>
        
        <div class="endpoint">
            <a href="/health">Health Check</a> - Server status
        </div>
        
        <h2>Access URLs (for browser):</h2>
        <ul>
            <li><strong>Console:</strong> http://localhost:8000{CONSOLE_PATH}</li>
            <li><strong>Swagger:</strong> http://localhost:8000/docs</li>
            <li><strong>MCP HTTP:</strong> http://localhost:8000/mcp</li>
        </ul>
        
        <h2>Server Info:</h2>
        <ul>
            <li>Listening on: 0.0.0.0:8000 (all network interfaces)</li>
            <li>For local access: localhost:8000 or 127.0.0.1:8000</li>
        </ul>
    </body>
    </html>
    """
    return HTMLResponse(content=html)

@app.get("/users/", response_model=List[User], tags=["users"], operation_id="list_users")
async def list_users(
    skip: int = Query(0, ge=0, description="Number of users to skip"),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of users to return"),
    active_only: bool = Query(False, description="Only return active users"),
):
    """List all users with pagination support."""
    results = list(users_db.values())
    if active_only:
        results = [u for u in results if u.active]
    return results[skip : skip + limit]

@app.get("/users/{user_id}", response_model=User, tags=["users"], operation_id="get_user")
async def get_user(user_id: int):
    """Get a specific user by ID."""
    if user_id not in users_db:
        raise HTTPException(status_code=404, detail="User not found")
    return users_db[user_id]

@app.post("/users/", response_model=User, tags=["users"], operation_id="create_user")
async def create_user(user: CreateUserRequest):
    """Create a new user."""
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
    """Update an existing user."""
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
    """Delete a user."""
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
    """Search users with various filter options."""
    results = list(users_db.values())
    if q:
        q = q.lower()
        results = [u for u in results if q in u.name.lower() or q in u.email.lower()]
    if min_age is not None:
        results = [u for u in results if u.age is not None and u.age >= min_age]
    if max_age is not None:
        results = [u for u in results if u.age is not None and u.age <= max_age]
    if active is not None:
        results = [u for u in results if u.active == active]
    return results

@app.get("/health", tags=["system"], operation_id="health_check")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "users_count": len(users_db),
    }

mcp = FastApiMCP(app)
mcp.mount_http(mount_path="/mcp")
mcp.mount_console(
    mount_path=CONSOLE_PATH,
    log_max_size=1000,
)

print()
print("=" * 70)
print("Server is Ready!")
print("=" * 70)
print()
print("IMPORTANT: Browser Access URLs")
print("  - DO NOT use: http://0.0.0.0:8000")
print("  - USE THIS:    http://localhost:8000" + CONSOLE_PATH)
print("  - OR:          http://127.0.0.1:8000" + CONSOLE_PATH)
print()
print("Available Endpoints (localhost):")
print("  - MCP Console:  http://localhost:8000" + CONSOLE_PATH)
print("  - Welcome Page: http://localhost:8000/welcome")
print("  - Swagger UI:   http://localhost:8000/docs")
print("  - MCP HTTP:     http://localhost:8000/mcp")
print()
print("Features:")
print("  - Root path '/' redirects to console")
print("  - View all registered MCP tools")
print("  - Test tool executions with custom parameters")
print("  - View real-time call logs with timings")
print()
print("=" * 70)
print("Press Ctrl+C to stop the server")
print("=" * 70)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
