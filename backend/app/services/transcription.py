import os
import tempfile
import openai
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Optional, Union
from io import BytesIO
import subprocess
import io
import logging

from app.core.config import settings
from app.core.logging import logger
from app.models.transcription import transcription_chunks

# Set OpenAI API key
openai.api_key = settings.OPENAI_API_KEY

logger = logging.getLogger(__name__)

def convert_to_ios_compatible(audio_data: bytes) -> bytes:
    """Convert audio to iOS-compatible format (AAC in MP4 container)"""
    try:
        logger.info("Starting iOS audio conversion")
        # Create temporary files
        with tempfile.NamedTemporaryFile(suffix='.webm', delete=False) as input_file, \
             tempfile.NamedTemporaryFile(suffix='.m4a', delete=False) as output_file:
            
            input_path = input_file.name
            output_path = output_file.name
            
            # Write input data
            input_file.write(audio_data)
            input_file.flush()
            
            logger.info(f"Input file size: {len(audio_data)} bytes")
            
            # First try direct conversion to AAC
            try:
                logger.info("Attempting primary conversion method")
                cmd = [
                    'ffmpeg', '-y',
                    '-i', input_path,
                    '-c:a', 'aac',
                    '-b:a', '128k',
                    '-ar', '44100',
                    '-ac', '2',
                    '-f', 'mp4',
                    output_path
                ]
                logger.info(f"Running FFmpeg command: {' '.join(cmd)}")
                convert_result = subprocess.run(cmd, capture_output=True, text=True)
                
                if convert_result.returncode != 0:
                    logger.error(f"Primary conversion failed: {convert_result.stderr}")
                    raise Exception("Primary conversion failed")
                
                # Read the converted file
                with open(output_path, 'rb') as f:
                    converted_data = f.read()
                
                logger.info(f"Successfully converted audio. Output size: {len(converted_data)} bytes")
                return converted_data
                
            except Exception as e:
                logger.error(f"Primary conversion failed: {str(e)}")
                logger.info("Attempting fallback conversion method")
                
                # Fallback: Convert to WAV first, then to AAC
                try:
                    # First convert to WAV
                    wav_path = input_path + '.wav'
                    wav_cmd = [
                        'ffmpeg', '-y',
                        '-i', input_path,
                        '-acodec', 'pcm_s16le',
                        '-ar', '44100',
                        '-ac', '2',
                        wav_path
                    ]
                    logger.info(f"Running WAV conversion: {' '.join(wav_cmd)}")
                    subprocess.run(wav_cmd, check=True, capture_output=True)
                    
                    # Then convert WAV to AAC
                    aac_cmd = [
                        'ffmpeg', '-y',
                        '-i', wav_path,
                        '-c:a', 'aac',
                        '-b:a', '128k',
                        '-ar', '44100',
                        '-ac', '2',
                        '-f', 'mp4',
                        output_path
                    ]
                    logger.info(f"Running AAC conversion: {' '.join(aac_cmd)}")
                    subprocess.run(aac_cmd, check=True, capture_output=True)
                    
                    # Read the converted file
                    with open(output_path, 'rb') as f:
                        converted_data = f.read()
                    
                    logger.info(f"Fallback conversion successful. Output size: {len(converted_data)} bytes")
                    return converted_data
                    
                except Exception as e2:
                    logger.error(f"Fallback conversion failed: {str(e2)}")
                    raise
                    
    except Exception as e:
        logger.error(f"Audio conversion failed: {str(e)}")
        raise
    finally:
        # Clean up temporary files
        try:
            if 'input_path' in locals():
                os.unlink(input_path)
            if 'output_path' in locals():
                os.unlink(output_path)
            if 'wav_path' in locals():
                os.unlink(wav_path)
        except Exception as e:
            logger.error(f"Error cleaning up temporary files: {str(e)}")


# --- Audio Transcription Function ---
async def transcribe_audio(audio_data: Union[bytes, BytesIO]) -> Optional[str]:
    """
    Transcribe audio data using OpenAI's Whisper API.
    
    Args:
        audio_data: Raw audio bytes in WebM format or BytesIO object
        
    Returns:
        Transcribed text or None if transcription fails
    """
    try:
        # Convert BytesIO to bytes if necessary
        if isinstance(audio_data, BytesIO):
            audio_data = audio_data.getvalue()
            
        # Create a temporary file for the audio data
        with tempfile.NamedTemporaryFile(suffix='.webm', delete=False) as temp_file:
            temp_file.write(audio_data)
            temp_file_path = temp_file.name
            
        try:
            # Open the audio file
            with open(temp_file_path, "rb") as audio_file:
                # Call OpenAI's Whisper API without language parameter to enable auto-detection
                transcript = openai.Audio.transcribe(
                    "whisper-1",
                    audio_file
                )
                
            return transcript.text
            
        except Exception as e:
            logger.error(f"Error in transcription: {str(e)}")
            return None
            
    except Exception as e:
        logger.error(f"Error processing audio: {str(e)}")
        return None
        
    finally:
        # Clean up temporary file
        try:
            if 'temp_file_path' in locals():
                os.unlink(temp_file_path)
        except Exception as e:
            logger.error(f"Error cleaning up temporary file: {str(e)}")

async def delete_transcription(
    db: AsyncSession,
    transcription_id: int
):
    """Delete a transcription by ID."""
    query = select(transcription_chunks).where(transcription_chunks.c.id == transcription_id)
    result = await db.execute(query)
    transcription = result.fetchone()
    
    if not transcription:
        return False
    
    delete_query = transcription_chunks.delete().where(transcription_chunks.c.id == transcription_id)
    await db.execute(delete_query)
    await db.commit()
    
    return True

async def delete_multiple_transcriptions(
    db: AsyncSession,
    ids: List[int]
):
    """Delete multiple transcriptions by IDs."""
    if not ids:
        return False
    
    delete_query = transcription_chunks.delete().where(transcription_chunks.c.id.in_(ids))
    await db.execute(delete_query)
    await db.commit()
    
    return True

async def get_transcription_audio(
    db: AsyncSession,
    transcription_id: int
):
    """Get audio data for a transcription."""
    query = select(transcription_chunks).where(transcription_chunks.c.id == transcription_id)
    result = await db.execute(query)
    transcription = result.fetchone()
    
    if not transcription:
        return None, None
    
    # Convert the audio to iOS-compatible format
    audio_data = convert_to_ios_compatible(transcription.audio_chunk)
    return audio_data, "audio/mp4"

def format_file_size(size_bytes):
    """Format file size in bytes to human-readable format."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.2f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB" 