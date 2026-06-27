import pytest
from mcp.server.lowlevel.server import Server

from fastapi_mcp.transport.http import FastApiHttpSessionManager


@pytest.mark.anyio
async def test_session_manager_startup_waits_for_task_group() -> None:
    """Regression for #259: startup must initialize the session manager task group."""
    mcp_server = Server("test-server")
    manager = FastApiHttpSessionManager(mcp_server=mcp_server)

    await manager._ensure_session_manager_started()

    assert manager._manager_started is True
    assert manager._session_manager is not None
    assert manager._session_manager._task_group is not None

    await manager.shutdown()
