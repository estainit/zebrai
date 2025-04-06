import asyncio
import asyncpg
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def add_user_id_column():
    # Get database connection details from environment variables
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL environment variable is not set")
    
    # Connect to the database
    conn = await asyncpg.connect(db_url)
    
    try:
        # Check if the column already exists
        column_exists = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'transcription_chunks'
                AND column_name = 'user_id'
            );
            """
        )
        
        if not column_exists:
            # Add the user_id column
            await conn.execute(
                """
                ALTER TABLE transcription_chunks
                ADD COLUMN user_id INTEGER NOT NULL DEFAULT 1;
                """
            )
            print("Added user_id column to transcription_chunks table")
        else:
            print("user_id column already exists in transcription_chunks table")
    
    finally:
        # Close the connection
        await conn.close()

if __name__ == "__main__":
    asyncio.run(add_user_id_column()) 