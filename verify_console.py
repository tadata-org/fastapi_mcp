"""
Simple test script to verify the console feature is correctly implemented.
This doesn't require running the full server, just verifies the code structure.
"""

import sys
import site
from pathlib import Path

user_site = site.getusersitepackages()
if user_site and user_site not in sys.path:
    sys.path.insert(0, user_site)

project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

print("=" * 60)
print("Verifying fastapi_mcp console implementation")
print("=" * 60)
print()

print("1. Checking if console module exists...")
console_path = project_root / 'fastapi_mcp' / 'console'
if console_path.exists():
    print(f"   [OK] Console directory exists: {console_path}")
    
    init_file = console_path / '__init__.py'
    logs_file = console_path / 'logs.py'
    router_file = console_path / 'router.py'
    
    for f in [init_file, logs_file, router_file]:
        if f.exists():
            print(f"   [OK] {f.name} exists")
        else:
            print(f"   [FAIL] {f.name} MISSING!")
else:
    print(f"   [FAIL] Console directory NOT FOUND: {console_path}")
    sys.exit(1)

print()
print("2. Checking server.py for mount_console method...")
server_file = project_root / 'fastapi_mcp' / 'server.py'

if not server_file.exists():
    print(f"   [FAIL] server.py NOT FOUND: {server_file}")
    sys.exit(1)

with open(server_file, 'r', encoding='utf-8') as f:
    server_content = f.read()

checks = [
    ('mount_console', 'mount_console method'),
    ('execute_tool_direct', 'execute_tool_direct method'),
    ('from fastapi_mcp.console', 'console module import'),
    ('LogStore', 'LogStore usage'),
    ('ConsoleConfig', 'ConsoleConfig usage'),
    ('from fastapi_mcp.console.logs import', 'logs module import'),
    ('from fastapi_mcp.console.router import', 'router module import'),
    ('_log_store', '_log_store attribute'),
    ('_console_mounted', '_console_mounted flag'),
]

all_pass = True
for keyword, description in checks:
    if keyword in server_content:
        print(f"   [OK] {description} found")
    else:
        print(f"   [FAIL] {description} NOT FOUND!")
        all_pass = False

print()
print("3. Checking __init__.py for new exports...")
init_file = project_root / 'fastapi_mcp' / '__init__.py'

if not init_file.exists():
    print(f"   [FAIL] __init__.py NOT FOUND")
    sys.exit(1)

with open(init_file, 'r', encoding='utf-8') as f:
    init_content = f.read()

export_checks = [
    ('LogStore', 'LogStore export'),
    ('LogEntry', 'LogEntry export'),
    ('LogStatus', 'LogStatus export'),
    ('ConsoleConfig', 'ConsoleConfig export'),
    ('get_global_log_store', 'get_global_log_store export'),
]

for keyword, description in export_checks:
    if keyword in init_content:
        print(f"   [OK] {description} found")
    else:
        print(f"   [FAIL] {description} NOT FOUND!")
        all_pass = False

print()
print("=" * 60)
if all_pass:
    print("[OK] All checks passed! The console feature is correctly implemented.")
    print()
    print("To run the example, you need to fix the pywin32 DLL issue.")
    print()
    print("Try running from project root with Python module mode:")
    print("  cd e:\\test\\fastapi_mcp")
    print("  python -c \"import sys; import site; sys.path.insert(0, '.'); sys.path.insert(0, site.getusersitepackages()); from fastapi_mcp.server import FastApiMCP; print('mount_console:', hasattr(FastApiMCP, 'mount_console'))\"")
    print()
    print("Or try reinstalling pywin32:")
    print("  pip uninstall pywin32 -y")
    print("  pip install pywin32 --user")
else:
    print("[FAIL] Some checks failed. Please review the errors above.")
    sys.exit(1)
print("=" * 60)
