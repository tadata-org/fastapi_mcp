import pytest
import uuid
from uuid import UUID
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException, Request
from mcp.shared.message import SessionMessage
from pydantic import ValidationError
from anyio.streams.memory import MemoryObjectSendStream

from fastapi_mcp.transport.sse import FastApiSseTransport
from mcp.types import JSONRPCMessage, JSONRPCError


@pytest.fixture
def mock_transport() -> FastApiSseTransport:
    # Initialize transport with a mock endpoint
    transport = FastApiSseTransport("/messages")
    transport._read_stream_writers = {}
    return transport


@pytest.fixture
def valid_session_id():
    session_id = uuid.uuid4()
    return session_id


@pytest.fixture
def mock_writer():
    return AsyncMock(spec=MemoryObjectSendStream)


@pytest.mark.anyio
async def test_handle_post_message_missing_session_id(mock_transport: FastApiSseTransport) -> None:
    """Test handling a request with a missing session_id."""
    # Create a mock request with no session_id
    mock_request = MagicMock(spec=Request)
    mock_request.query_params = {}

    # Check that the function raises HTTPException with the correct status code
    with pytest.raises(HTTPException) as excinfo:
        await mock_transport.handle_fastapi_post_message(mock_request)

    assert excinfo.value.status_code == 400
    assert "session_id is required" in excinfo.value.detail


@pytest.mark.anyio
async def test_handle_post_message_invalid_session_id(mock_transport: FastApiSseTransport) -> None:
    """Test handling a request with an invalid session_id."""
    # Create a mock request with an invalid session_id
    mock_request = MagicMock(spec=Request)
    mock_request.query_params = {"session_id": "not-a-valid-uuid"}

    # Check that the function raises HTTPException with the correct status code
    with pytest.raises(HTTPException) as excinfo:
        await mock_transport.handle_fastapi_post_message(mock_request)

    assert excinfo.value.status_code == 400
    assert "Invalid session ID" in excinfo.value.detail


@pytest.mark.anyio
async def test_handle_post_message_session_not_found(
    mock_transport: FastApiSseTransport, valid_session_id: UUID
) -> None:
    """Test handling a request with a valid session_id that doesn't exist."""
    # Create a mock request with a valid session_id
    mock_request = MagicMock(spec=Request)
    mock_request.query_params = {"session_id": valid_session_id.hex}

    # The session_id is valid but not in the transport's writers
    with pytest.raises(HTTPException) as excinfo:
        await mock_transport.handle_fastapi_post_message(mock_request)

    assert excinfo.value.status_code == 404
    assert "Could not find session" in excinfo.value.detail


@pytest.mark.anyio
async def test_handle_post_message_validation_error(
    mock_transport: FastApiSseTransport, valid_session_id: UUID, mock_writer: AsyncMock
) -> None:
    """Test handling a request with invalid JSON that causes a ValidationError."""
    # Set up the mock transport with a valid session
    mock_transport._read_stream_writers[valid_session_id] = mock_writer

    # Create a mock request with valid session_id but invalid body
    mock_request = MagicMock(spec=Request)
    mock_request.query_params = {"session_id": valid_session_id.hex}
    mock_request.body = AsyncMock(return_value=b'{"invalid": "json"}')

    # Mock BackgroundTasks
    with patch("fastapi_mcp.transport.sse.BackgroundTasks") as MockBackgroundTasks:
        mock_background_tasks = MockBackgroundTasks.return_value

        # Call the function
        response = await mock_transport.handle_fastapi_post_message(mock_request)

        # Verify response and background task setup
        assert response.status_code == 400
        assert "error" in response.body.decode() if isinstance(response.body, bytes) else False
        assert mock_background_tasks.add_task.called
        assert response.background == mock_background_tasks


@pytest.mark.anyio
async def test_handle_post_message_general_exception(
    mock_transport: FastApiSseTransport, valid_session_id: UUID, mock_writer: AsyncMock
) -> None:
    """Test handling a request that causes a general exception during body processing."""
    # Set up the mock transport with a valid session
    mock_transport._read_stream_writers[valid_session_id] = mock_writer

    # Create a mock request that raises an exception when body is accessed
    mock_request = MagicMock(spec=Request)
    mock_request.query_params = {"session_id": valid_session_id.hex}

    # Instead of mocking the body method to raise an exception,
    # we'll patch the body method to return a normal value and then
    # patch JSONRPCMessage.model_validate_json to raise the exception
    mock_request.body = AsyncMock(return_value=b'{"jsonrpc": "2.0", "method": "test", "id": "1"}')

    # Mock the model_validate_json method to raise an Exception
    with patch("mcp.types.JSONRPCMessage.model_validate_json", side_effect=Exception("Test exception")):
        # Check that the function raises HTTPException with the correct status code
        with pytest.raises(HTTPException) as excinfo:
            await mock_transport.handle_fastapi_post_message(mock_request)

        assert excinfo.value.status_code == 400
        assert "Invalid request body" in excinfo.value.detail


@pytest.mark.anyio
async def test_send_message_safely_with_validation_error(
    mock_transport: FastApiSseTransport, mock_writer: AsyncMock
) -> None:
    """Test sending a ValidationError message safely."""
    # Create a minimal validation error manually instead of using from_exception_data
    mock_validation_error = MagicMock(spec=ValidationError)
    mock_validation_error.__str__.return_value = "Mock validation error"  # type: ignore

    # Call the function
    await mock_transport._send_message_safely(mock_writer, mock_validation_error)

    # Verify that the writer.send was called with a JSONRPCError
    assert mock_writer.send.called
    sent_message = mock_writer.send.call_args[0][0]
    assert isinstance(sent_message, SessionMessage)
    assert isinstance(sent_message.message, JSONRPCMessage)
    assert isinstance(sent_message.message.root, JSONRPCError)
    assert sent_message.message.root.error.code == -32700  # Parse error code


@pytest.mark.anyio
async def test_send_message_safely_with_jsonrpc_message(
    mock_transport: FastApiSseTransport, mock_writer: AsyncMock
) -> None:
    """Test sending a JSONRPCMessage safely."""
    # Create a JSONRPCMessage
    message = SessionMessage(
        JSONRPCMessage.model_validate({"jsonrpc": "2.0", "id": "123", "method": "test_method", "params": {}})
    )

    # Call the function
    await mock_transport._send_message_safely(mock_writer, message)

    # Verify that the writer.send was called with the message
    assert mock_writer.send.called
    sent_message = mock_writer.send.call_args[0][0]
    assert sent_message == message


@pytest.mark.anyio
async def test_send_message_safely_exception_handling(
    mock_transport: FastApiSseTransport, mock_writer: AsyncMock
) -> None:
    """Test exception handling when sending a message."""
    # Set up the writer to raise an exception
    mock_writer.send.side_effect = Exception("Test exception")

    # Create a message
    message = SessionMessage(
        JSONRPCMessage.model_validate({"jsonrpc": "2.0", "id": "123", "method": "test_method", "params": {}})
    )

    # Call the function - it should not raise an exception
    await mock_transport._send_message_safely(mock_writer, message)

    # Verify that the writer.send was called
    assert mock_writer.send.called
