from sqlalchemy import Table, Column, Integer, ForeignKey, LargeBinary, Text, DateTime, JSON, String
from datetime import datetime

from app.models.base import metadata

# Transcription chunks table
voice_records = Table(
    "voice_records",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("user_id", Integer, ForeignKey("users.id")),
    Column("audio_byte", LargeBinary),
    Column("transcript", Text),
    Column("created_at", DateTime, default=datetime.utcnow),
    Column("client_info", JSON, nullable=True),  # Store client information as JSON
    Column("session_id", String, nullable=True),
    Column("client_type", String(20))  # Regular VARCHAR column for client type
) 