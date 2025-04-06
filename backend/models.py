import datetime
from sqlalchemy import (
    MetaData, Table, Column, Integer, String, LargeBinary, DateTime, Text, JSON
)
from sqlalchemy.sql import func # For default timestamp
from pydantic import BaseModel
from typing import Optional, Dict, Any

metadata = MetaData()

# SQLAlchemy Tables
transcription_chunks = Table(
    "transcription_chunks",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("session_id", String(100), index=True), # To group chunks by recording session
    Column("user_id", Integer, nullable=False), # Add user_id column
    Column("audio_chunk", LargeBinary, nullable=False), # Store raw audio bytes
    Column("transcript", Text, nullable=True),       # Store transcribed text
    Column("created_at", DateTime(timezone=True), server_default=func.now())
)

users = Table(
    "users",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("username", String(50), unique=True, nullable=False),
    Column("password_hash", String(255), nullable=False),
    Column("role", String(20), nullable=False),
    Column("conf", JSON, nullable=True, server_default='{"doTranscript": true}'),
    Column("created_at", DateTime(timezone=True), server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
)

# Pydantic Models
class User(BaseModel):
    id: int
    username: str
    role: str
    conf: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime.datetime] = None
    updated_at: Optional[datetime.datetime] = None
    
    class Config:
        orm_mode = True

# You might want a separate 'sessions' table later

# Function to create tables (call this once on startup)
async def create_tables(engine):
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)