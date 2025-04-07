from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.ext.asyncio import AsyncSession
import os
import uuid
import json
import aiofiles
from typing import Dict
import io

from app.core.config import settings
from app.core.logging import logger
from app.core.security import verify_token
from app.db.session import get_db_session
from app.models.transcription import transcription_chunks
from app.services.transcription import transcribe_audio

# Create router
router = APIRouter()

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
    
    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active_connections[session_id] = websocket
        logger.info(f"WebSocket connection established for session {session_id}")
    
    def disconnect(self, session_id: str):
        if session_id in self.active_connections:
            del self.active_connections[session_id]
            logger.info(f"WebSocket connection closed for session {session_id}")
    
    async def send_message(self, session_id: str, message: dict):
        if session_id in self.active_connections:
            await self.active_connections[session_id].send_json(message)

# Create connection manager instance
manager = ConnectionManager()

@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str, db: AsyncSession = Depends(get_db_session)):
    """Handles WebSocket connections, receives audio chunks, transcribes, saves, and returns text."""
    await manager.connect(websocket, session_id)
    
    try:
        # Wait for authentication message
        auth_message = await websocket.receive_json()
        if auth_message.get("type") != "auth":
            await websocket.close(code=4001, reason="Authentication required")
            return
        
        # Verify token
        token = auth_message.get("token")
        if not token:
            await websocket.close(code=4001, reason="Token required")
            return
        
        try:
            # Verify token and get user
            user = await verify_token(token, db)
            logger.info(f"User {user.username} authenticated for WebSocket session {session_id}")
        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            await websocket.close(code=4001, reason="Invalid token")
            return
        
        # Create a temporary file for the audio data
        temp_file_path = os.path.join(settings.TEMP_AUDIO_DIR, f"{session_id}.webm")
        async with aiofiles.open(temp_file_path, 'wb') as temp_file:
            # Create an empty file to start with
            await temp_file.write(b'')
        
        # Initialize variables
        audio_chunks = []
        chunk_count = 0
        do_transcript = user.conf.get("doTranscript", True) if user.conf else True
        
        # Process audio chunks
        while True:
            try:
                # Receive audio data
                data = await websocket.receive_bytes()
                
                # Append to audio chunks
                audio_chunks.append(data)
                chunk_count += 1
                
                # Save to temporary file
                async with aiofiles.open(temp_file_path, 'ab') as temp_file:
                    await temp_file.write(data)
                
                # Save to database and transcribe when we reach the required number of chunks
                if chunk_count % settings.CHUNKS_COUNT_NEED_FOR_TRANSCRIPTION == 0:
                    # Read the entire file so far
                    async with aiofiles.open(temp_file_path, 'rb') as temp_file:
                        audio_data = await temp_file.read()
                    
                    # Insert into database
                    insert_query = transcription_chunks.insert().values(
                        session_id=session_id,
                        audio_chunk=audio_data
                    )
                    await db.execute(insert_query)
                    await db.commit()
                    
                    # Transcribe if enabled
                    if do_transcript and len(audio_data) > 0:
                        try:
                            # Create a file-like object from the audio data
                            audio_file = io.BytesIO(audio_data)
                            
                            # Transcribe the audio
                            transcript = await transcribe_audio(audio_file)
                            
                            # Update the database with the transcript
                            update_query = (
                                transcription_chunks.update()
                                .where(transcription_chunks.c.session_id == session_id)
                                .values(transcript=transcript)
                            )
                            await db.execute(update_query)
                            await db.commit()
                            
                            # Send the transcript back to the client
                            await manager.send_message(session_id, {
                                "type": "transcript",
                                "text": transcript
                            })
                            
                            # Clear the audio chunks after successful transcription
                            audio_chunks = []
                            
                        except Exception as e:
                            logger.error(f"Transcription error: {str(e)}")
                            # Continue processing even if transcription fails
                
            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected for session {session_id}")
                break
            except Exception as e:
                logger.error(f"Error processing audio chunk: {str(e)}")
                # Continue processing even if there's an error with one chunk
        
        # Save any remaining audio data when the connection is closed
        if audio_chunks:
            try:
                # Read the entire file
                async with aiofiles.open(temp_file_path, 'rb') as temp_file:
                    audio_data = await temp_file.read()
                
                # Insert into database
                insert_query = transcription_chunks.insert().values(
                    session_id=session_id,
                    audio_chunk=audio_data
                )
                await db.execute(insert_query)
                await db.commit()
                
                # Transcribe if enabled and not already transcribed
                if do_transcript and len(audio_data) > 0:
                    try:
                        # Create a file-like object from the audio data
                        audio_file = io.BytesIO(audio_data)
                        
                        # Transcribe the audio
                        transcript = await transcribe_audio(audio_file)
                        
                        # Update the database with the transcript
                        update_query = (
                            transcription_chunks.update()
                            .where(transcription_chunks.c.session_id == session_id)
                            .values(transcript=transcript)
                        )
                        await db.execute(update_query)
                        await db.commit()
                        
                        # Send the transcript back to the client
                        await manager.send_message(session_id, {
                            "type": "transcript",
                            "text": transcript
                        })
                    except Exception as e:
                        logger.error(f"Transcription error: {str(e)}")
            except Exception as e:
                logger.error(f"Error saving final audio data: {str(e)}")
    finally:
        manager.disconnect(session_id)
        
        # Clean up temporary file
        try:
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
        except Exception as e:
            logger.error(f"Error cleaning up temporary file: {str(e)}") 