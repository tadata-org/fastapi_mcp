from typing import Any
from unittest.mock import AsyncMock, MagicMock

import anyio
import pytest
from fastapi import WebSocket, WebSocketDisconnect
from mcp import JSONRPCRequest
from mcp.shared.message import SessionMessage
from mcp.types import JSONRPCMessage
from pydantic import ValidationError

from fastapi_mcp.transport.websocket import FastApiWebSocketTransport


@pytest.fixture
def mock_transport() -> FastApiWebSocketTransport:
    return FastApiWebSocketTransport()


@pytest.fixture
def mock_websocket():
    mock = MagicMock(spec=WebSocket)
    mock.url.path = "/mcp"
    mock.headers = {}
    mock.query_params = {}
    return mock


@pytest.mark.anyio
async def test_websocket_transport_basic_message_flow(
    mock_transport: FastApiWebSocketTransport, mock_websocket: MagicMock
) -> None:
    """Test basic message flow through WebSocket transport."""
    # Set up mock WebSocket to accept connection and receive/send messages
    mock_websocket.accept = AsyncMock()

    # Use a list to track calls
    received_messages: list[str] = []
    sent_messages: list[str] = []

    async def mock_receive_text():
        if not received_messages:
            received_messages.append('{"jsonrpc": "2.0", "method": "initialize", "id": "test-1", "params": {}}')
            return received_messages[0]
        else:
            # Simulate disconnect after one message
            raise WebSocketDisconnect()

    async def mock_send_text(data):
        sent_messages.append(data)

    mock_websocket.receive_text = mock_receive_text
    mock_websocket.send_text = mock_send_text

    # Create a test message to send
    test_message = SessionMessage(
        JSONRPCMessage.model_validate({"jsonrpc": "2.0", "id": "test-response", "result": {"status": "ok"}})
    )

    # Test the transport
    async with mock_transport.connect_websocket(mock_websocket) as (read_stream, write_stream):
        # Send a message through the write stream first
        await write_stream.send(test_message)

        # Give some time for async processing
        await anyio.sleep(0.1)

        # Read the incoming message from the read stream
        received_message = await read_stream.receive()

        # Verify the received message
        assert isinstance(received_message, SessionMessage)
        assert isinstance(received_message.message.root, JSONRPCRequest)
        assert received_message.message.root.id == "test-1"
        assert received_message.message.root.method == "initialize"

    # Verify WebSocket interactions
    mock_websocket.accept.assert_called_once_with(subprotocol="mcp")
    # Check that at least one message was sent
    assert len(sent_messages) > 0
    assert "test-response" in sent_messages[0]


@pytest.mark.anyio
async def test_websocket_transport_validation_error(
    mock_transport: FastApiWebSocketTransport, mock_websocket: MagicMock
) -> None:
    """Test handling of invalid JSON messages."""
    mock_websocket.accept = AsyncMock()
    mock_websocket.receive_text = AsyncMock(
        side_effect=[
            '{"invalid": "json-rpc message"}',  # Invalid JSON-RPC
            WebSocketDisconnect(),
        ]
    )
    mock_websocket.send_text = AsyncMock()

    async with mock_transport.connect_websocket(mock_websocket) as (read_stream, write_stream):
        # Should receive a ValidationError
        received = await read_stream.receive()
        assert isinstance(received, ValidationError)


@pytest.mark.anyio
async def test_websocket_transport_disconnect_handling(
    mock_transport: FastApiWebSocketTransport, mock_websocket: MagicMock
) -> None:
    """Test graceful handling of WebSocket disconnection."""
    mock_websocket.accept = AsyncMock()
    mock_websocket.receive_text = AsyncMock(side_effect=WebSocketDisconnect())
    mock_websocket.send_text = AsyncMock()

    # Should not raise an exception when WebSocket disconnects
    async with mock_transport.connect_websocket(mock_websocket) as (read_stream, write_stream):
        pass  # Connection should close gracefully


@pytest.mark.anyio
async def test_websocket_transport_http_request_info_injection(
    mock_transport: FastApiWebSocketTransport, mock_websocket: MagicMock
) -> None:
    """Test that HTTP request info is properly injected into messages."""
    mock_websocket.accept = AsyncMock()
    mock_websocket.url.path = "/test/path"
    mock_websocket.headers = {"authorization": "Bearer test-token"}
    mock_websocket.query_params = {"param1": "value1"}
    mock_websocket.receive_text = AsyncMock(
        side_effect=[
            '{"jsonrpc": "2.0", "method": "test_method", "id": "test-1", "params": {"arg1": "value1"}}',
            WebSocketDisconnect(),
        ]
    )
    mock_websocket.send_text = AsyncMock()

    async with mock_transport.connect_websocket(mock_websocket) as (read_stream, write_stream):
        received_message = await read_stream.receive()

        assert isinstance(received_message, SessionMessage)
        # Check that HTTP request info was injected
        assert isinstance(received_message.message.root, JSONRPCRequest)
        assert received_message.message.root.params is not None
        params: dict[str, Any] = received_message.message.root.params
        assert "_http_request_info" in params
        http_info = params["_http_request_info"]
        assert http_info["method"] == "WEBSOCKET"
        assert http_info["path"] == "/test/path"
        assert http_info["headers"]["authorization"] == "Bearer test-token"
        assert http_info["query_params"]["param1"] == "value1"


@pytest.mark.anyio
async def test_websocket_transport_send_disconnect_handling(
    mock_transport: FastApiWebSocketTransport, mock_websocket: MagicMock
) -> None:
    """Test handling of disconnect during message sending."""
    mock_websocket.accept = AsyncMock()
    mock_websocket.receive_text = AsyncMock(side_effect=WebSocketDisconnect())
    mock_websocket.send_text = AsyncMock(side_effect=WebSocketDisconnect())

    test_message = SessionMessage(JSONRPCMessage.model_validate({"jsonrpc": "2.0", "id": "test", "result": {}}))

    async with mock_transport.connect_websocket(mock_websocket) as (read_stream, write_stream):
        # Should not raise exception when send fails due to disconnect
        await write_stream.send(test_message)


@pytest.mark.anyio
async def test_websocket_transport_exception_handling(
    mock_transport: FastApiWebSocketTransport, mock_websocket: MagicMock
) -> None:
    """Test handling of general exceptions during WebSocket operations."""
    mock_websocket.accept = AsyncMock()
    mock_websocket.receive_text = AsyncMock(side_effect=Exception("Test exception"))
    mock_websocket.send_text = AsyncMock()

    # Should handle exceptions gracefully without crashing
    async with mock_transport.connect_websocket(mock_websocket) as (read_stream, write_stream):
        pass  # Should complete without raising
