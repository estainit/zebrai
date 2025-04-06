from sqlalchemy import Table, Column, Integer, String, LargeBinary, DateTime, Text
from sqlalchemy.sql import func

from app.models.base import metadata

# Transcription chunks table
transcription_chunks = Table(
    "transcription_chunks",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("session_id", String(100), index=True),  # To group chunks by recording session
    Column("audio_chunk", LargeBinary, nullable=False),  # Store raw audio bytes
    Column("transcript", Text, nullable=True),  # Store transcribed text
    Column("created_at", DateTime(timezone=True), server_default=func.now())
) 