from sqlalchemy import Table, Column, Integer, String, DateTime, JSON
from sqlalchemy.sql import func

from app.models.base import metadata

# Users table
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