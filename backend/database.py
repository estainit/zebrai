import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
logger.info(f"Database URL: {DATABASE_URL}")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable not set")

engine = create_async_engine(DATABASE_URL, echo=True) # echo=True for debugging SQL

# Async session maker
AsyncSessionFactory = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

async def get_db_session() -> AsyncSession:
    """Dependency to get an async database session."""
    logger.debug("Creating new database session")
    async with AsyncSessionFactory() as session:
        logger.debug("Database session created successfully")
        yield session