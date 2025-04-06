import os
import sys
import pytest
import asyncio
from pathlib import Path
from typing import AsyncGenerator, Generator
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Add the backend directory to the Python path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app import create_app
from app.db.session import get_db_session
from app.models import create_tables, metadata
from app.core.security import hash_password
from app.models.user import users

# Test database URL
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# Create test engine
test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

# Test session factory
TestSessionFactory = sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False
)

@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
async def test_app():
    """Create a test FastAPI application."""
    app = create_app()
    
    # Override the database session dependency
    async def override_get_db_session():
        async with TestSessionFactory() as session:
            yield session
    
    app.dependency_overrides[get_db_session] = override_get_db_session
    
    yield app

@pytest.fixture(scope="session")
def client(test_app):
    """Create a test client for the FastAPI application."""
    return TestClient(test_app)

@pytest.fixture(autouse=True)
async def setup_database():
    """Create database tables before each test and drop them after."""
    async with test_engine.begin() as conn:
        await conn.run_sync(metadata.drop_all)
        await conn.run_sync(metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(metadata.drop_all)

@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh database session for a test."""
    async with TestSessionFactory() as session:
        yield session

@pytest.fixture
async def test_user(db_session: AsyncSession):
    """Create a test user in the database."""
    # Create a test user
    hashed_password = hash_password("testpassword")
    user_data = {
        "username": "testuser",
        "password_hash": hashed_password,
        "role": "user",
        "conf": {"doTranscript": True}
    }
    
    # Insert the user
    query = users.insert().values(**user_data)
    await db_session.execute(query)
    await db_session.commit()
    
    # Get the user
    query = users.select().where(users.c.username == "testuser")
    result = await db_session.execute(query)
    user = result.fetchone()
    
    return user

@pytest.fixture
async def test_admin(db_session: AsyncSession):
    """Create a test admin user in the database."""
    # Create a test admin
    hashed_password = hash_password("adminpassword")
    admin_data = {
        "username": "testadmin",
        "password_hash": hashed_password,
        "role": "admin",
        "conf": {"doTranscript": True}
    }
    
    # Insert the admin
    query = users.insert().values(**admin_data)
    await db_session.execute(query)
    await db_session.commit()
    
    # Get the admin
    query = users.select().where(users.c.username == "testadmin")
    result = await db_session.execute(query)
    admin = result.fetchone()
    
    return admin

@pytest.fixture
def test_user_token(test_user):
    """Create a JWT token for the test user."""
    from app.core.security import create_access_token
    from datetime import timedelta
    from app.core.config import settings
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": test_user.username, "role": test_user.role},
        expires_delta=access_token_expires
    )
    
    return access_token

@pytest.fixture
def test_admin_token(test_admin):
    """Create a JWT token for the test admin."""
    from app.core.security import create_access_token
    from datetime import timedelta
    from app.core.config import settings
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": test_admin.username, "role": test_admin.role},
        expires_delta=access_token_expires
    )
    
    return access_token 