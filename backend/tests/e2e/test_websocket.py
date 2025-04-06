import pytest
import asyncio
import json
from fastapi import WebSocket
from unittest.mock import patch, MagicMock

from app.websockets.handlers import handle_websocket_connection

@pytest.mark.asyncio
async def test_websocket_connection_success():
    """Test successful WebSocket connection."""
    # Create a mock WebSocket
    mock_websocket = MagicMock(spec=WebSocket)
    mock_websocket.accept = MagicMock()
    mock_websocket.receive_text = MagicMock(return_value=json.dumps({
        "type": "auth",
        "token": "test_token"
    }))
    mock_websocket.send_text = MagicMock()
    mock_websocket.close = MagicMock()
    
    # Mock the token verification
    with patch("app.core.security.verify_token", return_value={"sub": "testuser"}):
        # Handle the WebSocket connection
        await handle_websocket_connection(mock_websocket)
        
        # Verify the connection was accepted
        mock_websocket.accept.assert_called_once()
        
        # Verify the authentication response
        mock_websocket.send_text.assert_called_with(json.dumps({
            "type": "auth",
            "status": "success"
        }))

@pytest.mark.asyncio
async def test_websocket_connection_invalid_token():
    """Test WebSocket connection with invalid token."""
    # Create a mock WebSocket
    mock_websocket = MagicMock(spec=WebSocket)
    mock_websocket.accept = MagicMock()
    mock_websocket.receive_text = MagicMock(return_value=json.dumps({
        "type": "auth",
        "token": "invalid_token"
    }))
    mock_websocket.send_text = MagicMock()
    mock_websocket.close = MagicMock()
    
    # Mock the token verification to raise an exception
    with patch("app.core.security.verify_token", side_effect=Exception("Invalid token")):
        # Handle the WebSocket connection
        await handle_websocket_connection(mock_websocket)
        
        # Verify the connection was accepted
        mock_websocket.accept.assert_called_once()
        
        # Verify the authentication response
        mock_websocket.send_text.assert_called_with(json.dumps({
            "type": "auth",
            "status": "error",
            "message": "Invalid token"
        }))
        
        # Verify the connection was closed
        mock_websocket.close.assert_called_once()

@pytest.mark.asyncio
async def test_websocket_transcription_success():
    """Test successful audio transcription over WebSocket."""
    # Create a mock WebSocket
    mock_websocket = MagicMock(spec=WebSocket)
    mock_websocket.accept = MagicMock()
    mock_websocket.receive_text = MagicMock(side_effect=[
        json.dumps({
            "type": "auth",
            "token": "test_token"
        }),
        json.dumps({
            "type": "transcribe",
            "audio": "base64_encoded_audio_data",
            "session_id": "test_session"
        })
    ])
    mock_websocket.send_text = MagicMock()
    mock_websocket.close = MagicMock()
    
    # Mock the token verification
    with patch("app.core.security.verify_token", return_value={"sub": "testuser"}):
        # Mock the transcription service
        with patch("app.services.transcription.transcribe_audio", return_value="Test transcription"):
            # Handle the WebSocket connection
            await handle_websocket_connection(mock_websocket)
            
            # Verify the connection was accepted
            mock_websocket.accept.assert_called_once()
            
            # Verify the authentication response
            mock_websocket.send_text.assert_any_call(json.dumps({
                "type": "auth",
                "status": "success"
            }))
            
            # Verify the transcription response
            mock_websocket.send_text.assert_any_call(json.dumps({
                "type": "transcribe",
                "status": "success",
                "session_id": "test_session",
                "transcript": "Test transcription"
            }))

@pytest.mark.asyncio
async def test_websocket_transcription_error():
    """Test audio transcription error over WebSocket."""
    # Create a mock WebSocket
    mock_websocket = MagicMock(spec=WebSocket)
    mock_websocket.accept = MagicMock()
    mock_websocket.receive_text = MagicMock(side_effect=[
        json.dumps({
            "type": "auth",
            "token": "test_token"
        }),
        json.dumps({
            "type": "transcribe",
            "audio": "invalid_base64_data",
            "session_id": "test_session"
        })
    ])
    mock_websocket.send_text = MagicMock()
    mock_websocket.close = MagicMock()
    
    # Mock the token verification
    with patch("app.core.security.verify_token", return_value={"sub": "testuser"}):
        # Mock the transcription service to raise an exception
        with patch("app.services.transcription.transcribe_audio", side_effect=Exception("Transcription error")):
            # Handle the WebSocket connection
            await handle_websocket_connection(mock_websocket)
            
            # Verify the connection was accepted
            mock_websocket.accept.assert_called_once()
            
            # Verify the authentication response
            mock_websocket.send_text.assert_any_call(json.dumps({
                "type": "auth",
                "status": "success"
            }))
            
            # Verify the transcription error response
            mock_websocket.send_text.assert_any_call(json.dumps({
                "type": "transcribe",
                "status": "error",
                "session_id": "test_session",
                "message": "Transcription error"
            }))

@pytest.mark.asyncio
async def test_websocket_invalid_message_format():
    """Test WebSocket connection with invalid message format."""
    # Create a mock WebSocket
    mock_websocket = MagicMock(spec=WebSocket)
    mock_websocket.accept = MagicMock()
    mock_websocket.receive_text = MagicMock(return_value="invalid_json")
    mock_websocket.send_text = MagicMock()
    mock_websocket.close = MagicMock()
    
    # Handle the WebSocket connection
    await handle_websocket_connection(mock_websocket)
    
    # Verify the connection was accepted
    mock_websocket.accept.assert_called_once()
    
    # Verify the error response
    mock_websocket.send_text.assert_called_with(json.dumps({
        "type": "error",
        "message": "Invalid message format"
    }))
    
    # Verify the connection was closed
    mock_websocket.close.assert_called_once()

@pytest.mark.asyncio
async def test_websocket_unknown_message_type():
    """Test WebSocket connection with unknown message type."""
    # Create a mock WebSocket
    mock_websocket = MagicMock(spec=WebSocket)
    mock_websocket.accept = MagicMock()
    mock_websocket.receive_text = MagicMock(return_value=json.dumps({
        "type": "unknown",
        "data": "test_data"
    }))
    mock_websocket.send_text = MagicMock()
    mock_websocket.close = MagicMock()
    
    # Handle the WebSocket connection
    await handle_websocket_connection(mock_websocket)
    
    # Verify the connection was accepted
    mock_websocket.accept.assert_called_once()
    
    # Verify the error response
    mock_websocket.send_text.assert_called_with(json.dumps({
        "type": "error",
        "message": "Unknown message type: unknown"
    }))
    
    # Verify the connection was closed
    mock_websocket.close.assert_called_once()

@pytest.mark.asyncio
async def test_websocket_connection_closed():
    """Test WebSocket connection when client disconnects."""
    # Create a mock WebSocket
    mock_websocket = MagicMock(spec=WebSocket)
    mock_websocket.accept = MagicMock()
    mock_websocket.receive_text = MagicMock(side_effect=Exception("Connection closed"))
    mock_websocket.send_text = MagicMock()
    mock_websocket.close = MagicMock()
    
    # Handle the WebSocket connection
    await handle_websocket_connection(mock_websocket)
    
    # Verify the connection was accepted
    mock_websocket.accept.assert_called_once()
    
    # Verify no messages were sent
    mock_websocket.send_text.assert_not_called()
    
    # Verify the connection was closed
    mock_websocket.close.assert_called_once() 