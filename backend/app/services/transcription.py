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
    # Create temporary files
    temp_webm = None
    temp_wav = None
    
    try:
        # Convert BytesIO to bytes if necessary
        if isinstance(audio_data, BytesIO):
            audio_data = audio_data.getvalue()
        
        # Create a temporary file for the WebM data
        with tempfile.NamedTemporaryFile(suffix='.webm', delete=False) as temp_webm:
            temp_webm.write(audio_data)
            temp_webm_path = temp_webm.name
        
        # Create a temporary file for the converted WAV
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_wav:
            temp_wav_path = temp_wav.name
        
        # First, try to validate the WebM file
        try:
            validate_cmd = [
                'ffmpeg', '-v', 'error',
                '-i', temp_webm_path,
                '-f', 'null', '-'
            ]
            subprocess.run(validate_cmd, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"WebM validation failed: {e.stderr}")
            # If validation fails, try to repair the WebM file
            repair_cmd = [
                'ffmpeg', '-y',
                '-i', temp_webm_path,
                '-c', 'copy',
                '-f', 'webm',
                f'{temp_webm_path}.repaired'
            ]
            try:
                subprocess.run(repair_cmd, check=True, capture_output=True, text=True)
                os.replace(f'{temp_webm_path}.repaired', temp_webm_path)
                logger.info("Successfully repaired WebM file")
            except subprocess.CalledProcessError as repair_e:
                logger.error(f"WebM repair failed: {repair_e.stderr}")
                raise ValueError(f"Failed to repair WebM file: {repair_e.stderr}")
        
        # Convert to WAV format with specific parameters
        convert_cmd = [
            'ffmpeg', '-y',
            '-i', temp_webm_path,
            '-acodec', 'pcm_s16le',  # 16-bit PCM
            '-ar', '16000',          # 16kHz sample rate
            '-ac', '1',              # Mono audio
            '-f', 'wav',
            temp_wav_path
        ]
        
        try:
            subprocess.run(convert_cmd, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg conversion failed: {e.stderr}")
            # Try alternative conversion method
            alt_convert_cmd = [
                'ffmpeg', '-y',
                '-f', 'webm',
                '-i', temp_webm_path,
                '-acodec', 'pcm_s16le',
                '-ar', '16000',
                '-ac', '1',
                '-f', 'wav',
                temp_wav_path
            ]
            try:
                subprocess.run(alt_convert_cmd, check=True, capture_output=True, text=True)
            except subprocess.CalledProcessError as alt_e:
                logger.error(f"Alternative FFmpeg conversion failed: {alt_e.stderr}")
                raise ValueError(f"Failed to convert audio format: {alt_e.stderr}")
        
        # Verify the converted file exists and has content
        if not os.path.exists(temp_wav_path) or os.path.getsize(temp_wav_path) == 0:
            raise ValueError("Converted audio file does not exist or is empty")
        
        # Transcribe using OpenAI's Whisper API
        with open(temp_wav_path, 'rb') as audio_file:
            try:
                response = await openai.Audio.atranscribe(
                    "whisper-1",
                    audio_file,
                    api_key=settings.OPENAI_API_KEY
                )
                return response['text']
            except Exception as e:
                logger.error(f"OpenAI transcription failed: {str(e)}")
                raise ValueError(f"Transcription failed: {str(e)}")
                
    except Exception as e:
        logger.error(f"Error in transcribe_audio: {str(e)}")
        raise
        
    finally:
        # Clean up temporary files
        try:
            if temp_webm and os.path.exists(temp_webm_path):
                os.unlink(temp_webm_path)
            if temp_wav and os.path.exists(temp_wav_path):
                os.unlink(temp_wav_path)
            if os.path.exists(f'{temp_webm_path}.repaired'):
                os.unlink(f'{temp_webm_path}.repaired')
        except Exception as e:
            logger.error(f"Error cleaning up temporary files: {str(e)}")


async def get_transcriptionsZZ(
    db: AsyncSession,
    page: int = 1,
    per_page: int = 20
):
    """Get transcriptions with pagination."""
    # Calculate offset
    offset = (page - 1) * per_page
    
    # Get total count
    count_query = select(func.count()).select_from(transcription_chunks)
    total_count = await db.scalar(count_query)
    
    # Get transcriptions
    query = (
        select(transcription_chunks)
        .order_by(transcription_chunks.c.created_at.desc())
        .offset(offset)
        .limit(per_page)
    )
    
    result = await db.execute(query)
    items = result.fetchall()
    
    # Format file sizes and add row numbers
    formatted_items = []
    for index, item in enumerate(items):
        formatted_item = dict(item)
        formatted_item["file_size"] = format_file_size(len(item.audio_chunk))
        # Add row number that continues across pages
        formatted_item["row_number"] = total_count - offset - index
        formatted_items.append(formatted_item)
    
    return {
        "items": formatted_items,
        "total": total_count,
        "page": page,
        "per_page": per_page,
        "has_more": offset + per_page < total_count
    }

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