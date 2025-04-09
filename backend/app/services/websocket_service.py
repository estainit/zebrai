import logging
import jwt
from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.models import users, transcription_chunks
from app.services.transcription import transcribe_audio
from app.core.config import settings
from datetime import datetime

logger = logging.getLogger(__name__)

class WebSocketService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.user = None
        self.session_id = None
        self.current_transcription_id = None

    async def handle_connection(self, websocket: WebSocket, session_id: str):
        """Handle the WebSocket connection lifecycle."""
        await websocket.accept()
        self.session_id = session_id
        
        try:
            # Authenticate
            auth_message = await websocket.receive_json()
            if auth_message.get("type") != "auth":
                await websocket.close(code=4001, reason="Authentication required")
                return
                
            token = auth_message.get("token")
            if not token:
                await websocket.close(code=4001, reason="No token provided")
                return
                
            payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
            username = payload.get("sub")
            if not username:
                await websocket.close(code=4002, reason="Invalid token")
                return
                
            query = select(users).where(users.c.username == username)
            result = await self.db.execute(query)
            self.user = result.fetchone()
            
            if not self.user:
                await websocket.close(code=4002, reason="User not found")
                return
                
            logger.info(f"WebSocket connection accepted for user: {username}")
            
            # Process audio stream
            while True:
                message = await websocket.receive()
                
                if message["type"] == "websocket.receive" and "bytes" in message:
                    audio_chunk = message["bytes"]
                    if audio_chunk:
                        await self._process_audio_chunk(websocket, audio_chunk)
                        
        except WebSocketDisconnect:
            logger.info("WebSocket disconnected")
        except Exception as e:
            logger.error(f"Error in WebSocket connection: {e}")
            await websocket.close(code=1011, reason=str(e))

    async def _process_audio_chunk(self, websocket: WebSocket, audio_chunk: bytes):
        """Process a single audio chunk and update the database."""
        try:
            if self.current_transcription_id is None:
                # First chunk - create new record
                insert_query = transcription_chunks.insert().values(
                    session_id=self.session_id,
                    user_id=self.user.id,
                    audio_chunk=audio_chunk,
                    transcript="",
                    created_at=datetime.utcnow()
                )
                result = await self.db.execute(insert_query)
                await self.db.commit()
                self.current_transcription_id = result.inserted_primary_key[0]
                logger.info(f".........Created new transcription record: {self.current_transcription_id}")
            else:
                # Append to existing record
                update_query = (
                    update(transcription_chunks)
                    .where(transcription_chunks.c.id == self.current_transcription_id)
                    .values(
                        audio_chunk=transcription_chunks.c.audio_chunk + audio_chunk
                    )
                )
                #await self.db.execute(update_query)
                #await self.db.commit()
                logger.info(f"...........Appended chunk to transcription: {self.current_transcription_id}")

            # Transcribe the current audio chunk directly
            new_transcript = await transcribe_audio(audio_chunk)
            
            if new_transcript:
                # Get the current transcript
                query = select(transcription_chunks.c.transcript).where(
                    transcription_chunks.c.id == self.current_transcription_id
                )
                result = await self.db.execute(query)
                prev_transcript = result.scalar_one() or ""
                
                # Append the new transcript
                combined_transcript = f"{prev_transcript} {new_transcript}".strip()
                
                # Update the transcript
                update_query = (
                    update(transcription_chunks)
                    .where(transcription_chunks.c.id == self.current_transcription_id)
                    .values(
                        transcript=combined_transcript
                    )
                )
                await self.db.execute(update_query)
                await self.db.commit()
                
                # Send transcript to client
                await websocket.send_json({
                    "type": "transcript",
                    "text": new_transcript
                })
                logger.info(f"Updated transcript for transcription: {self.current_transcription_id}")

        except Exception as e:
            logger.error(f"Error processing audio chunk: {e}")
            # Don't raise the exception to keep the connection alive 