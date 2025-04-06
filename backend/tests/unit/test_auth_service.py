import pytest
from fastapi import HTTPException, status
from sqlalchemy import select

from app.services.auth import authenticate_user, reset_password
from app.models.user import users

@pytest.mark.asyncio
async def test_authenticate_user_success(db_session, test_user):
    """Test successful user authentication."""
    # Authenticate the test user
    result = await authenticate_user("testuser", "testpassword", db_session)
    
    # Verify the result
    assert "access_token" in result
    assert result["token_type"] == "bearer"
    assert result["username"] == "testuser"
    assert result["role"] == "user"
    assert "conf" in result
    assert result["conf"]["doTranscript"] is True

@pytest.mark.asyncio
async def test_authenticate_user_wrong_password(db_session, test_user):
    """Test authentication with wrong password."""
    # Authenticate with wrong password
    with pytest.raises(HTTPException) as excinfo:
        await authenticate_user("testuser", "wrongpassword", db_session)
    
    # Verify the exception
    assert excinfo.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert excinfo.value.detail == "Invalid credentials"

@pytest.mark.asyncio
async def test_authenticate_user_nonexistent(db_session):
    """Test authentication with nonexistent user."""
    # Authenticate with nonexistent user
    with pytest.raises(HTTPException) as excinfo:
        await authenticate_user("nonexistentuser", "testpassword", db_session)
    
    # Verify the exception
    assert excinfo.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert excinfo.value.detail == "Invalid credentials"

@pytest.mark.asyncio
async def test_reset_password_success(db_session, test_user):
    """Test successful password reset."""
    # Reset the password
    success = await reset_password("testuser", "newpassword", db_session)
    
    # Verify the result
    assert success is True
    
    # Verify the password was changed
    query = select(users).where(users.c.username == "testuser")
    result = await db_session.execute(query)
    user = result.fetchone()
    
    # Verify the user exists
    assert user is not None
    
    # Verify the password was changed
    from app.core.security import verify_user
    await verify_user("testuser", "newpassword", db_session)

@pytest.mark.asyncio
async def test_reset_password_nonexistent_user(db_session):
    """Test password reset for nonexistent user."""
    # Reset password for nonexistent user
    success = await reset_password("nonexistentuser", "newpassword", db_session)
    
    # Verify the result
    assert success is False 