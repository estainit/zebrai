import pytest
import io
from unittest.mock import patch, MagicMock
from sqlalchemy import select, func

from app.services.transcription import (
    transcribe_audio,
    delete_transcription,
    delete_multiple_transcriptions,
    get_transcription_audio,
    format_file_size
)
from app.models.transcription import voice_records

@pytest.mark.asyncio
async def test_transcribe_audio():
    """Test audio transcription."""
    # Create a mock audio file
    audio_file = io.BytesIO(b"mock audio data")
    
    # Mock the OpenAI API response
    mock_response = MagicMock()
    mock_response.text = "This is a test transcription."
    
    # Patch the OpenAI API call
    with patch("openai.Audio.atranscribe", return_value=mock_response):
        # Transcribe the audio
        result = await transcribe_audio(audio_file)
        
        # Verify the result
        assert result == "This is a test transcription."

@pytest.mark.asyncio
async def test_transcribe_audio_error():
    """Test audio transcription error handling."""
    # Create a mock audio file
    audio_file = io.BytesIO(b"mock audio data")
    
    # Mock the OpenAI API call to raise an exception
    with patch("openai.Audio.atranscribe", side_effect=Exception("API error")):
        # Transcribe the audio
        with pytest.raises(Exception) as excinfo:
            await transcribe_audio(audio_file)
        
        # Verify the exception
        assert str(excinfo.value) == "API error"

@pytest.mark.asyncio
async def test_delete_transcription_success(db_session):
    """Test successful transcription deletion."""
    # Insert test data
    test_data = {
        "session_id": "test-session",
        "audio_byte": b"test audio data",
        "transcript": "Test transcription"
    }
    
    query = voice_records.insert().values(**test_data)
    result = await db_session.execute(query)
    await db_session.commit()
    
    # Get the inserted ID
    query = select(voice_records).where(voice_records.c.session_id == "test-session")
    result = await db_session.execute(query)
    transcription = result.fetchone()
    transcription_id = transcription.id
    
    # Delete the transcription
    success = await delete_transcription(db_session, transcription_id)
    
    # Verify the result
    assert success is True
    
    # Verify the transcription was deleted
    query = select(voice_records).where(voice_records.c.id == transcription_id)
    result = await db_session.execute(query)
    transcription = result.fetchone()
    
    assert transcription is None

@pytest.mark.asyncio
async def test_delete_transcription_nonexistent(db_session):
    """Test deletion of nonexistent transcription."""
    # Delete a nonexistent transcription
    success = await delete_transcription(db_session, 999)
    
    # Verify the result
    assert success is False

@pytest.mark.asyncio
async def test_delete_multiple_transcriptions_success(db_session):
    """Test successful deletion of multiple transcriptions."""
    # Insert test data
    test_data = [
        {
            "session_id": "test-session-1",
            "audio_byte": b"test audio data 1",
            "transcript": "Test transcription 1"
        },
        {
            "session_id": "test-session-2",
            "audio_byte": b"test audio data 2",
            "transcript": "Test transcription 2"
        },
        {
            "session_id": "test-session-3",
            "audio_byte": b"test audio data 3",
            "transcript": "Test transcription 3"
        }
    ]
    
    for data in test_data:
        query = voice_records.insert().values(**data)
        await db_session.execute(query)
    
    await db_session.commit()
    
    # Get the inserted IDs
    query = select(voice_records).where(voice_records.c.session_id.in_(["test-session-1", "test-session-2"]))
    result = await db_session.execute(query)
    transcriptions = result.fetchall()
    transcription_ids = [t.id for t in transcriptions]
    
    # Delete the transcriptions
    success = await delete_multiple_transcriptions(db_session, transcription_ids)
    
    # Verify the result
    assert success is True
    
    # Verify the transcriptions were deleted
    query = select(voice_records).where(voice_records.c.id.in_(transcription_ids))
    result = await db_session.execute(query)
    transcriptions = result.fetchall()
    
    assert len(transcriptions) == 0
    
    # Verify the remaining transcription
    query = select(voice_records).where(voice_records.c.session_id == "test-session-3")
    result = await db_session.execute(query)
    transcription = result.fetchone()
    
    assert transcription is not None

@pytest.mark.asyncio
async def test_delete_multiple_transcriptions_empty(db_session):
    """Test deletion of multiple transcriptions with empty list."""
    # Delete with empty list
    success = await delete_multiple_transcriptions(db_session, [])
    
    # Verify the result
    assert success is False

@pytest.mark.asyncio
async def test_get_transcription_audio_success(db_session):
    """Test successful retrieval of transcription audio."""
    # Insert test data
    test_data = {
        "session_id": "test-session",
        "audio_byte": b"test audio data",
        "transcript": "Test transcription"
    }
    
    query = voice_records.insert().values(**test_data)
    result = await db_session.execute(query)
    await db_session.commit()
    
    # Get the inserted ID
    query = select(voice_records).where(voice_records.c.session_id == "test-session")
    result = await db_session.execute(query)
    transcription = result.fetchone()
    transcription_id = transcription.id
    
    # Get the audio
    audio_data = await get_transcription_audio(db_session, transcription_id)
    
    # Verify the result
    assert audio_data == b"test audio data"

@pytest.mark.asyncio
async def test_get_transcription_audio_nonexistent(db_session):
    """Test retrieval of audio for nonexistent transcription."""
    # Get audio for nonexistent transcription
    audio_data = await get_transcription_audio(db_session, 999)
    
    # Verify the result
    assert audio_data is None

def test_format_file_size():
    """Test file size formatting."""
    # Test bytes
    assert format_file_size(500) == "500 B"
    
    # Test kilobytes
    assert format_file_size(1024) == "1.00 KB"
    assert format_file_size(2048) == "2.00 KB"
    
    # Test megabytes
    assert format_file_size(1024 * 1024) == "1.00 MB"
    assert format_file_size(2 * 1024 * 1024) == "2.00 MB"
    
    # Test gigabytes
    assert format_file_size(1024 * 1024 * 1024) == "1.00 GB"
    assert format_file_size(2 * 1024 * 1024 * 1024) == "2.00 GB" 