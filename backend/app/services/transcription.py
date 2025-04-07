import os
import tempfile
import openai
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Optional
import subprocess
import io

from app.core.config import settings
from app.core.logging import logger
from app.models.transcription import transcription_chunks

# Set OpenAI API key
openai.api_key = settings.OPENAI_API_KEY

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
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode != 0:
                    logger.error(f"Primary conversion failed: {result.stderr}")
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

async def transcribe_audio(audio_file):
    """Transcribe audio using OpenAI's Whisper API."""
    temp_file_path = None
    converted_file_path = None
    try:
        # Create a temporary file for the input audio data
        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as temp_file:
            temp_file.write(audio_file.read())
            temp_file_path = temp_file.name

        # Create a path for the converted audio file
        converted_file_path = temp_file_path.replace(".webm", ".wav")

        # Convert audio to WAV using ffmpeg with more flexible input format handling
        try:
            subprocess.run([
                "ffmpeg", "-y",
                "-f", "auto",  # Let ffmpeg detect the input format
                "-i", temp_file_path,
                "-acodec", "pcm_s16le",  # Convert to PCM 16-bit
                "-ar", "16000",  # Set sample rate to 16kHz
                "-ac", "1",  # Convert to mono
                "-f", "wav",  # Force WAV output format
                converted_file_path
            ], check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg conversion error: {e.stderr.decode()}")
            raise ValueError("Failed to convert audio format")

        # Verify the converted file exists and has content
        if not os.path.exists(converted_file_path):
            raise ValueError("Failed to create converted audio file")

        # Open the converted file for transcription
        with open(converted_file_path, "rb") as audio_file:
            # Call OpenAI's Whisper API for transcription
            response = await openai.Audio.atranscribe("whisper-1", audio_file)
            
            # Return the transcribed text
            return response.text
            
    except Exception as e:
        logger.error(f"Transcription error: {e}")
        raise e
        
    finally:
        # Clean up temporary files
        for file_path in [temp_file_path, converted_file_path]:
            if file_path and os.path.exists(file_path):
                try:
                    os.unlink(file_path)
                except Exception as e:
                    logger.error(f"Failed to cleanup temp file {file_path}: {e}")

async def get_transcriptions(
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