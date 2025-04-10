import logging
import jwt
import tempfile
import os
import subprocess
from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.models import users, voice_records
from app.services.transcription import transcribe_audio
from app.core.config import settings
from datetime import datetime

logger = logging.getLogger(__name__)

# Constants for chunk processing
LOW_CHUNK_COUNT = 2  # Number of chunks to accumulate before quick transcription
HI_CHUNK_COUNT = 4  # Number of chunks to accumulate before database update

class WebSocketService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.user = None
        self.session_id = None
        self.current_transcription_id = None
        self.temp_dir = tempfile.mkdtemp()
        self.chunk_files = []
        self.accumulated_chunks = []  # Store chunks in memory
        self.chunk_count = 0
        self.webm_header = None  # Store WebM header from first chunk
        self.client_type = "unknown"  # Initialize client type

    async def handle_connection(self, websocket: WebSocket, session_id: str):
        """Handle the WebSocket connection lifecycle."""
        await websocket.accept()
        self.session_id = session_id
        
        try:
            # Get client type from query parameters
            self.client_type = websocket.query_params.get("client_type", "unknown")
            
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
                    audio_byte = message["bytes"]
                    if audio_byte:
                        await self._process_audio_byte(websocket, audio_byte)
                        
        except WebSocketDisconnect:
            logger.info("WebSocket disconnected")
            # Save final transcription if there are remaining chunks
            if self.accumulated_chunks:
                await self._process_hi_chunk_count(websocket)
        except Exception as e:
            logger.error(f"Error in WebSocket connection: {e}")
            await websocket.close(code=1011, reason=str(e))
        finally:
            await self.cleanup()

    async def _process_audio_byte(self, websocket: WebSocket, audio_byte: bytes):
        """Process a single audio chunk and update the database."""
        try:
            # For the first chunk
            if self.chunk_count == 0:
                logger.info(f"First chunk received, size: {len(audio_byte)} bytes")
                logger.info(f"First chunk header: {audio_byte[:8].hex()}")
                
                # Store the WebM header from the first chunk
                self.webm_header = audio_byte[:4]
                logger.info(f"Extracted WebM header: {self.webm_header.hex()}")
                
                try:
                    # Create new record with the first chunk
                    insert_query = voice_records.insert().values(
                        session_id=self.session_id,
                        user_id=self.user.id,
                        audio_byte=audio_byte,
                        transcript="",
                        created_at=datetime.utcnow(),
                        client_type=self.client_type
                    )
                    result = await self.db.execute(insert_query)
                    await self.db.commit()
                    self.current_transcription_id = result.inserted_primary_key[0]
                    logger.info(f"Created new transcription record with first chunk: {self.current_transcription_id}")
                except Exception as e:
                    await self.db.rollback()
                    logger.error(f"Failed to create transcription record: {e}")
                    return
                
                # Try to transcribe the first chunk directly
                try:
                    new_transcript = await transcribe_audio(audio_byte, self.client_type)
                    if new_transcript:
                        await websocket.send_json({
                            "type": "transcript",
                            "text": new_transcript
                        })
                        logger.info(f"Sent first chunk transcript: {new_transcript}")
                except Exception as e:
                    logger.error(f"Failed to transcribe first chunk: {e}")
                    # Continue even if transcription fails
                
                self.accumulated_chunks.append(audio_byte)
                self.chunk_count += 1
                return

            # For subsequent chunks
            try:
                # For iOS devices, we need to handle the chunks differently
                if self.client_type.lower() == 'ios':
                    # For iOS, we'll process each chunk individually for transcription
                    # First, save the chunk to a temporary file with .m4a extension
                    temp_file = os.path.join(self.temp_dir, f"ios_chunk_{self.chunk_count}.m4a")
                    with open(temp_file, 'wb') as f:
                        f.write(audio_byte)
                    
                    # Try multiple conversion approaches
                    wav_file = temp_file + '.wav'
                    success = False
                    
                    # Approach 1: Try direct transcription without conversion
                    try:
                        logger.info("Trying direct transcription without conversion")
                        new_transcript = await transcribe_audio(audio_byte, self.client_type)
                        if new_transcript:
                            await websocket.send_json({
                                "type": "transcript",
                                "text": new_transcript
                            })
                            logger.info(f"Direct transcription successful: {new_transcript}")
                            success = True
                    except Exception as e:
                        logger.error(f"Direct transcription failed: {e}")
                    
                    # Approach 2: Try converting from M4A to WAV with fragmented MP4 handling
                    if not success:
                        try:
                            wav_cmd = [
                                'ffmpeg', '-y',
                                '-f', 'mp4',  # Force input format
                                '-movflags', '+frag_keyframe+empty_moov',  # Handle fragmented MP4
                                '-i', temp_file,
                                '-acodec', 'pcm_s16le',
                                '-ar', '44100',
                                '-ac', '1',
                                '-f', 'wav',
                                wav_file
                            ]
                            logger.info(f"Trying M4A to WAV conversion with fragmented MP4 handling: {' '.join(wav_cmd)}")
                            result = subprocess.run(wav_cmd, capture_output=True, text=True)
                            if result.returncode == 0:
                                with open(wav_file, 'rb') as f:
                                    wav_data = f.read()
                                new_transcript = await transcribe_audio(wav_data, self.client_type)
                                if new_transcript:
                                    await websocket.send_json({
                                        "type": "transcript",
                                        "text": new_transcript
                                    })
                                    logger.info(f"M4A to WAV conversion successful: {new_transcript}")
                                    success = True
                            else:
                                logger.error(f"M4A to WAV conversion failed: {result.stderr}")
                        except Exception as e:
                            logger.error(f"M4A to WAV conversion failed: {e}")
                    
                    # Approach 3: Try extracting raw audio with fragmented MP4 handling
                    if not success:
                        try:
                            raw_file = temp_file + '.raw'
                            raw_cmd = [
                                'ffmpeg', '-y',
                                '-f', 'mp4',  # Force input format
                                '-movflags', '+frag_keyframe+empty_moov',  # Handle fragmented MP4
                                '-i', temp_file,
                                '-f', 's16le',
                                '-ar', '44100',
                                '-ac', '1',
                                raw_file
                            ]
                            logger.info(f"Trying raw audio extraction with fragmented MP4 handling: {' '.join(raw_cmd)}")
                            result = subprocess.run(raw_cmd, capture_output=True, text=True)
                            if result.returncode == 0:
                                with open(raw_file, 'rb') as f:
                                    raw_data = f.read()
                                new_transcript = await transcribe_audio(raw_data, self.client_type)
                                if new_transcript:
                                    await websocket.send_json({
                                        "type": "transcript",
                                        "text": new_transcript
                                    })
                                    logger.info(f"Raw audio extraction successful: {new_transcript}")
                                    success = True
                            else:
                                logger.error(f"Raw audio extraction failed: {result.stderr}")
                        except Exception as e:
                            logger.error(f"Raw audio extraction failed: {e}")
                    
                    # Approach 4: Try with AAC format and fragmented MP4 handling
                    if not success:
                        try:
                            aac_file = temp_file + '.aac'
                            aac_cmd = [
                                'ffmpeg', '-y',
                                '-f', 'mp4',  # Force input format
                                '-movflags', '+frag_keyframe+empty_moov',  # Handle fragmented MP4
                                '-i', temp_file,
                                '-c:a', 'aac',
                                '-b:a', '128k',
                                '-ar', '44100',
                                '-ac', '1',
                                aac_file
                            ]
                            logger.info(f"Trying AAC conversion with fragmented MP4 handling: {' '.join(aac_cmd)}")
                            result = subprocess.run(aac_cmd, capture_output=True, text=True)
                            if result.returncode == 0:
                                with open(aac_file, 'rb') as f:
                                    aac_data = f.read()
                                new_transcript = await transcribe_audio(aac_data, self.client_type)
                                if new_transcript:
                                    await websocket.send_json({
                                        "type": "transcript",
                                        "text": new_transcript
                                    })
                                    logger.info(f"AAC conversion successful: {new_transcript}")
                                    success = True
                            else:
                                logger.error(f"AAC conversion failed: {result.stderr}")
                        except Exception as e:
                            logger.error(f"AAC conversion failed: {e}")
                    
                    if not success:
                        logger.error("All iOS audio processing approaches failed")
                        # Log the audio chunk details for debugging
                        logger.error(f"Audio chunk size: {len(audio_byte)}")
                        logger.error(f"Audio chunk header: {audio_byte[:8].hex()}")
                    
                    # Clean up temporary files
                    try:
                        if os.path.exists(temp_file):
                            os.unlink(temp_file)
                        if os.path.exists(wav_file):
                            os.unlink(wav_file)
                        if os.path.exists(raw_file):
                            os.unlink(raw_file)
                        if os.path.exists(aac_file):
                            os.unlink(aac_file)
                    except Exception as e:
                        logger.error(f"Error cleaning up iOS temporary files: {e}")
                
                # Save the chunk to a temporary file
                chunk_file = os.path.join(self.temp_dir, f"chunk_{len(self.chunk_files)}.webm")
                with open(chunk_file, 'wb') as f:
                    f.write(audio_byte)
                self.chunk_files.append(chunk_file)
                self.accumulated_chunks.append(audio_byte)
                self.chunk_count += 1

                # Get the current audio data from the database
                query = select(voice_records.c.audio_byte).where(
                    voice_records.c.id == self.current_transcription_id
                )
                result = await self.db.execute(query)
                current_audio = result.scalar_one()

                # Combine the audio data
                combined_audio = current_audio + audio_byte

                # Update the database with the combined audio
                update_query = (
                    update(voice_records)
                    .where(voice_records.c.id == self.current_transcription_id)
                    .values(
                        audio_byte=combined_audio
                    )
                )
                await self.db.execute(update_query)
                await self.db.commit()
                logger.info(f"Appended chunk to transcription: {self.current_transcription_id}")

                # Process chunks based on count (only for non-iOS devices)
                if self.client_type.lower() != 'ios':
                    if self.chunk_count % LOW_CHUNK_COUNT == 0:
                        await self._process_low_chunk_count(websocket)
                    
                    if self.chunk_count % HI_CHUNK_COUNT == 0:
                        await self._process_hi_chunk_count(websocket)

            except Exception as e:
                await self.db.rollback()
                logger.error(f"Database error processing chunk: {e}")
                # Continue processing even if database update fails
                self.accumulated_chunks.append(audio_byte)
                self.chunk_count += 1

        except Exception as e:
            logger.error(f"Error processing audio chunk: {e}")
            logger.error(f"Chunk count: {self.chunk_count}")
            logger.error(f"Chunk size: {len(audio_byte)}")
            logger.error(f"Chunk header: {audio_byte[:8].hex() if audio_byte else 'None'}")
            # Continue processing even if there's an error
            self.accumulated_chunks.append(audio_byte)
            self.chunk_count += 1

    async def _process_low_chunk_count(self, websocket: WebSocket):
        """Process accumulated chunks for database transcription update."""
        try:
            # Create a properly formatted WebM file
            input_file = os.path.join(self.temp_dir, f"temp_input_low_{self.chunk_count}.webm")
            output_file = os.path.join(self.temp_dir, f"temp_output_low_{self.chunk_count}.webm")
            
            # Write the combined chunks with proper header
            with open(input_file, 'wb') as f:
                f.write(self.webm_header)  # Write header first
                for chunk in self.accumulated_chunks:
                    f.write(chunk[4:] if chunk.startswith(self.webm_header) else chunk)

            # Use a simpler FFmpeg command that preserves the original format
            ffmpeg_cmd = [
                'ffmpeg', '-i', input_file,
                '-c:a', 'copy',  # Copy the audio stream without re-encoding
                output_file
            ]

            try:
                subprocess.run(ffmpeg_cmd, check=True, capture_output=True, text=True)
            except subprocess.CalledProcessError as e:
                logger.error(f"FFmpeg processing failed: {e.stderr}")
                return

            # Read the processed file
            with open(output_file, 'rb') as f:
                processed_audio = f.read()

            # Transcribe the processed audio
            new_transcript = await transcribe_audio(processed_audio, self.client_type)
            
            if new_transcript:
                # Send transcript to client without updating database
                await websocket.send_json({
                    "type": "transcript",
                    "text": new_transcript
                })
                logger.info(f"Sent quick transcript for chunks {self.chunk_count - LOW_CHUNK_COUNT + 1} to {self.chunk_count}")

        except Exception as e:
            logger.error(f"Error in low chunk transcription update: {e}")


    async def _process_hi_chunk_count(self, websocket: WebSocket):
        """Process accumulated chunks for database transcription update."""
        try:
            # Create a properly formatted WebM file
            input_file = os.path.join(self.temp_dir, f"temp_input_hi_{self.chunk_count}.webm")
            output_file = os.path.join(self.temp_dir, f"temp_output_hi_{self.chunk_count}.webm")
            
            # Write the combined chunks with proper header
            with open(input_file, 'wb') as f:
                f.write(self.webm_header)  # Write header first
                for chunk in self.accumulated_chunks:
                    f.write(chunk[4:] if chunk.startswith(self.webm_header) else chunk)

            # Use a simpler FFmpeg command that preserves the original format
            ffmpeg_cmd = [
                'ffmpeg', '-i', input_file,
                '-c:a', 'copy',  # Copy the audio stream without re-encoding
                output_file
            ]

            try:
                subprocess.run(ffmpeg_cmd, check=True, capture_output=True, text=True)
            except subprocess.CalledProcessError as e:
                logger.error(f"FFmpeg processing failed: {e.stderr}")
                return

            # Read the processed file
            with open(output_file, 'rb') as f:
                processed_audio = f.read()

            # Transcribe the processed audio
            new_transcript = await transcribe_audio(processed_audio, self.client_type)
            
            if new_transcript:
                # Get the current transcript
                query = select(voice_records.c.transcript).where(
                    voice_records.c.id == self.current_transcription_id
                )
                result = await self.db.execute(query)
                prev_transcript = result.scalar_one() or ""
                
                # Append the new transcript
                combined_transcript = f"{prev_transcript} {new_transcript}".strip()
                
                # Update the transcript in database
                update_query = (
                    update(voice_records)
                    .where(voice_records.c.id == self.current_transcription_id)
                    .values(
                        transcript=combined_transcript
                    )
                )
                await self.db.execute(update_query)
                await self.db.commit()
                
                logger.info(f"Updated database transcript for chunks 1 to {self.chunk_count}")

        except Exception as e:
            logger.error(f"Error in database transcription update: {e}")

    async def cleanup(self):
        """Clean up temporary files."""
        try:
            for file in self.chunk_files:
                if os.path.exists(file):
                    os.remove(file)
            if os.path.exists(self.temp_dir):
                os.rmdir(self.temp_dir)
        except Exception as e:
            logger.error(f"Error during cleanup: {e}") 
        

    async def ZZ_process_low_chunk_countZZ(self, websocket: WebSocket):
        """Process accumulated chunks for quick transcription without database update."""
        try:
            # Combine recent chunks for transcription
            recent_chunks = self.accumulated_chunks[-LOW_CHUNK_COUNT:]
            
            # Create a properly formatted WebM file
            input_file = os.path.join(self.temp_dir, f"temp_input_{self.chunk_count}.webm")
            output_file = os.path.join(self.temp_dir, f"temp_output_{self.chunk_count}.webm")
            
            # Write the combined chunks with proper header
            with open(input_file, 'wb') as f:
                # Write header only once
                f.write(self.webm_header)
                # For each chunk, skip the header if it exists
                for chunk in recent_chunks:
                    if chunk[:4] == self.webm_header:
                        f.write(chunk[4:])
                    else:
                        f.write(chunk)

            # Use a simpler FFmpeg command that preserves the original format
            ffmpeg_cmd = [
                'ffmpeg', '-i', input_file,
                '-c:a', 'copy',  # Copy the audio stream without re-encoding
                output_file
            ]

            try:
                subprocess.run(ffmpeg_cmd, check=True, capture_output=True, text=True)
            except subprocess.CalledProcessError as e:
                logger.error(f"FFmpeg processing failed: {e.stderr}")
                return

            # Read the processed file
            with open(output_file, 'rb') as f:
                processed_audio = f.read()

            # Transcribe the processed audio
            new_transcript = await transcribe_audio(processed_audio, self.client_type)
            
            if new_transcript:
                # Send transcript to client without updating database
                await websocket.send_json({
                    "type": "transcript",
                    "text": new_transcript
                })
                logger.info(f"Sent quick transcript for chunks {self.chunk_count - LOW_CHUNK_COUNT + 1} to {self.chunk_count}")

        except Exception as e:
            logger.error(f"Error in quick transcription: {e}")
            logger.error(f"Chunk count: {self.chunk_count}")
            logger.error(f"Recent chunks: {len(recent_chunks)}")
            logger.error(f"WebM header: {self.webm_header.hex() if self.webm_header else 'None'}")
