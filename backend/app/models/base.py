import datetime
from sqlalchemy import (
    MetaData, Table, Column, Integer, String, LargeBinary, DateTime, Text, JSON
)
from sqlalchemy.sql import func  # For default timestamp

# Create metadata object
metadata = MetaData()

# Function to create tables (call this once on startup)
async def create_tables(engine):
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all) 