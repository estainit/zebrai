import os
import io
import logging
import jwt
from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Dict, Optional
from app.models import users, transcription_chunks
from app.services.transcription import transcribe_audio
from app.core.config import settings
import aiofiles
from datetime import datetime

logger = logging.getLogger(__name__)

class WebSocketService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.active_connections: Dict[str, WebSocket] = {}
        self.audio_chunks: List[bytes] = []
        self.chunk_count = 0
        self.temp_file_path: Optional[str] = None
        self.user = None
        self.session_id = None
        self.is_first_chunk = True

    async def handle_connection(self, websocket: WebSocket, session_id: str):
        """Handle the WebSocket connection lifecycle."""
        logger.info(f"New WebSocket connection request for session: {session_id}")
        await websocket.accept()
        self.session_id = session_id
        
        try:
            logger.info("Starting authentication...")
            auth_success = await self._authenticate(websocket)
            if not auth_success:
                logger.error("Authentication failed")
                return
                
            logger.info("Authentication successful, starting audio processing...")
            await self._process_audio_stream(websocket)
        except Exception as e:
            logger.error(f"Error in WebSocket connection: {e}")
            if "Invalid token" in str(e):
                await websocket.close(code=4002, reason=str(e))
        finally:
            logger.info("Cleaning up WebSocket connection...")
            await self._cleanup(websocket)

    async def _authenticate(self, websocket: WebSocket):
        """Authenticate the WebSocket connection."""
        auth_message = await websocket.receive_json()
        if auth_message.get("type") != "auth":
            await websocket.close(code=4001, reason="Authentication required")
            return False
            
        token = auth_message.get("token")
        if not token:
            await websocket.close(code=4001, reason="No token provided")
            return False
            
        try:
            payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
            username = payload.get("sub")
            if not username:
                await websocket.close(code=4002, reason="Invalid token")
                return False
                
            query = select(users).where(users.c.username == username)
            result = await self.db.execute(query)
            self.user = result.fetchone()
            
            if not self.user:
                await websocket.close(code=4002, reason="User not found")
                return False
                
            self.active_connections[self.session_id] = websocket
            logger.info(f"WebSocket connection accepted for session: {self.session_id}, user: {username}")
            return True
            
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            raise

    async def _process_audio_stream(self, websocket: WebSocket):
        """Process the incoming audio stream."""
        self.temp_file_path = os.path.join(settings.TEMP_AUDIO_DIR, f"{self.session_id}.webm")
        logger.info("Starting recording...")
        
        try:
            while True:
                try:
                    # Check if WebSocket is still connected
                    if websocket.client_state.value != 1:  # 1 is CONNECTED state
                        logger.warning("WebSocket disconnected")
                        break
                        
                    await self._process_audio_chunk(websocket)
                except WebSocketDisconnect:
                    logger.info("WebSocket disconnected normally")
                    break
                except Exception as e:
                    logger.error(f"Error in recording loop: {e}")
                    continue
        except Exception as e:
            logger.error(f"Error in recording session: {e}")
            if "Invalid token" in str(e):
                await websocket.close(code=4002, reason=str(e))

    async def _process_audio_chunk(self, websocket: WebSocket):
        """Process a single audio chunk."""
        try:
            audio_chunk = await websocket.receive_bytes()
            if not audio_chunk:
                logger.warning("Received empty audio chunk")
                return
                
            self.audio_chunks.append(audio_chunk)
            self.chunk_count += 1
            logger.info(f"Received chunk {self.chunk_count}, size: {len(audio_chunk)} bytes")
            
            # Save chunk to temporary file
            async with aiofiles.open(self.temp_file_path, "ab") as temp_file:
                if self.is_first_chunk:
                    # Write WebM header for the first chunk
                    await temp_file.write(b'\x1A\x45\xDF\xA3')  # EBML header
                    await temp_file.write(b'\x42\x86')  # DocType
                    await temp_file.write(b'\x81\x01')  # DocTypeVersion
                    await temp_file.write(b'\x42\xF7\x81\x01')  # DocTypeReadVersion
                    self.is_first_chunk = False
                await temp_file.write(audio_chunk)
            
            if self.chunk_count % settings.CHUNKS_COUNT_NEED_FOR_TRANSCRIPTION == 0:
                await self._transcribe_and_save_chunks()
        except Exception as e:
            logger.error(f"Error processing audio chunk: {e}")
            raise

    async def _transcribe_and_save_chunks(self):
        """Transcribe and save the recent audio chunks."""
        try:
            if not self.audio_chunks:
                logger.warning("No audio chunks to process")
                return
                
            recent_chunks = self.audio_chunks[-settings.CHUNKS_COUNT_NEED_FOR_TRANSCRIPTION:]
            combined_audio = b''.join(recent_chunks)
            
            if not combined_audio:
                logger.warning("Combined audio is empty")
                return
                
            logger.info(f"Processing {len(recent_chunks)} chunks for transcription")
            
            # Transcribe the audio
            transcript = await transcribe_audio(combined_audio)
            logger.info(f"Transcription result: {transcript}")
            
            # Save to database
            insert_query = transcription_chunks.insert().values(
                session_id=self.session_id,
                user_id=self.user.id,
                audio_chunk=combined_audio,
                transcript=transcript,
                created_at=datetime.utcnow()
            )
            await self.db.execute(insert_query)
            await self.db.commit()
            logger.info(f"Successfully saved chunk {self.chunk_count} to database")
            
            # Send transcript to client
            if transcript and self.session_id in self.active_connections:
                try:
                    await self.active_connections[self.session_id].send_json({
                        "type": "transcript",
                        "text": transcript,
                        "chunk_number": self.chunk_count
                    })
                    logger.info(f"Successfully sent transcript for chunk {self.chunk_count}")
                except Exception as e:
                    logger.error(f"Failed to send transcript to client: {e}")
        except Exception as e:
            logger.error(f"Error in _transcribe_and_save_chunks: {e}")
            raise

    async def _save_final_recording(self):
        """Save the complete recording to the database."""
        try:
            if not self.audio_chunks:
                logger.warning("No audio chunks to save as final recording")
                return
                
            complete_audio = b''.join(self.audio_chunks)
            
            if not complete_audio:
                logger.warning("Complete audio is empty")
                return
                
            logger.info("Processing final recording")
            
            # Transcribe the complete audio
            transcript = await transcribe_audio(complete_audio)
            logger.info(f"Final transcription result: {transcript}")
            
            # Save to database
            insert_query = transcription_chunks.insert().values(
                session_id=self.session_id,
                user_id=self.user.id,
                audio_chunk=complete_audio,
                transcript=transcript,
                created_at=datetime.utcnow()
            )
            await self.db.execute(insert_query)
            await self.db.commit()
            logger.info("Successfully saved final recording to database")
            
            # Send final transcript to client
            if transcript and self.session_id in self.active_connections:
                try:
                    await self.active_connections[self.session_id].send_json({
                        "type": "final_transcript",
                        "text": transcript,
                        "total_chunks": self.chunk_count
                    })
                    logger.info("Successfully sent final transcript to client")
                except Exception as e:
                    logger.error(f"Failed to send final transcript to client: {e}")
        except Exception as e:
            logger.error(f"Error in _save_final_recording: {e}")
            raise

    async def _cleanup(self, websocket: WebSocket):
        """Clean up resources and save final recording."""
        try:
            if self.audio_chunks:
                await self._save_final_recording()
                
                # Send a completion message to the client
                if self.session_id in self.active_connections:
                    try:
                        await self.active_connections[self.session_id].send_json({
                            "type": "recording_complete",
                            "message": "Recording session completed"
                        })
                        logger.info("Sent recording completion message to client")
                    except Exception as e:
                        logger.error(f"Failed to send completion message: {e}")
        except Exception as e:
            logger.error(f"Error saving final recording: {e}")
            
        try:
            if self.temp_file_path and os.path.exists(self.temp_file_path):
                os.unlink(self.temp_file_path)
        except Exception as e:
            logger.error(f"Error cleaning up temporary file: {e}")
        
        if self.session_id in self.active_connections:
            del self.active_connections[self.session_id] 