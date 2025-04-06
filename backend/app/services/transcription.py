import os
import tempfile
import openai
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Optional

from app.core.config import settings
from app.core.logging import logger
from app.models.transcription import transcription_chunks

# Set OpenAI API key
openai.api_key = settings.OPENAI_API_KEY

async def transcribe_audio(audio_file):
    """Transcribe audio using OpenAI's Whisper API."""
    try:
        # Create a temporary file for the audio data
        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as temp_file:
            temp_file.write(audio_file.read())
            temp_file_path = temp_file.name

        # Open the file for transcription
        with open(temp_file_path, "rb") as audio_file:
            # Call OpenAI's Whisper API for transcription
            response = await openai.Audio.atranscribe("whisper-1", audio_file)
            
            # Clean up the temporary file
            os.unlink(temp_file_path)
            
            # Return the transcribed text
            return response.text
    except Exception as e:
        logger.error(f"Transcription error: {e}")
        # Clean up the temporary file if it exists
        if 'temp_file_path' in locals():
            try:
                os.unlink(temp_file_path)
            except:
                pass
        raise e

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
        return None
    
    return transcription.audio_chunk

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