from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.logging import logger

# Create async engine
engine = create_async_engine(settings.DATABASE_URL, echo=True)  # echo=True for debugging SQL

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