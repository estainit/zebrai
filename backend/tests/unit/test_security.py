import pytest
import bcrypt
import jwt
from datetime import datetime, timedelta
from fastapi import HTTPException, status

from app.core.security import (
    hash_password,
    create_access_token,
    verify_token,
    verify_user
)
from app.core.config import settings

def test_hash_password():
    """Test password hashing."""
    # Test with a simple password
    password = "testpassword"
    hashed = hash_password(password)
    
    # Verify the hash is different from the original password
    assert hashed != password
    
    # Verify the hash can be used to check the password
    assert bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    
    # Test with a complex password
    complex_password = "Complex!@#$%^&*()_+Password123"
    complex_hashed = hash_password(complex_password)
    
    # Verify the hash is different from the original password
    assert complex_hashed != complex_password
    
    # Verify the hash can be used to check the password
    assert bcrypt.checkpw(complex_password.encode('utf-8'), complex_hashed.encode('utf-8'))

def test_create_access_token():
    """Test JWT token creation."""
    # Test with default expiration
    data = {"sub": "testuser", "role": "user"}
    token = create_access_token(data)
    
    # Verify the token is a string
    assert isinstance(token, str)
    
    # Verify the token can be decoded
    decoded = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    
    # Verify the token contains the correct data
    assert decoded["sub"] == "testuser"
    assert decoded["role"] == "user"
    assert "exp" in decoded
    
    # Test with custom expiration
    custom_expires = timedelta(minutes=30)
    custom_token = create_access_token(data, expires_delta=custom_expires)
    
    # Verify the token can be decoded
    custom_decoded = jwt.decode(custom_token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    
    # Verify the token contains the correct data
    assert custom_decoded["sub"] == "testuser"
    assert custom_decoded["role"] == "user"
    assert "exp" in custom_decoded

@pytest.mark.asyncio
async def test_verify_user_success(db_session, test_user):
    """Test successful user verification."""
    # Verify the test user
    user = await verify_user("testuser", "testpassword", db_session)
    
    # Verify the user is correct
    assert user.username == "testuser"
    assert user.role == "user"

@pytest.mark.asyncio
async def test_verify_user_wrong_password(db_session, test_user):
    """Test user verification with wrong password."""
    # Verify with wrong password
    with pytest.raises(HTTPException) as excinfo:
        await verify_user("testuser", "wrongpassword", db_session)
    
    # Verify the exception
    assert excinfo.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert excinfo.value.detail == "Invalid credentials"

@pytest.mark.asyncio
async def test_verify_user_nonexistent(db_session):
    """Test user verification with nonexistent user."""
    # Verify with nonexistent user
    with pytest.raises(HTTPException) as excinfo:
        await verify_user("nonexistentuser", "testpassword", db_session)
    
    # Verify the exception
    assert excinfo.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert excinfo.value.detail == "Invalid credentials"

@pytest.mark.asyncio
async def test_verify_token_success(db_session, test_user, test_user_token):
    """Test successful token verification."""
    # Create a mock credentials object
    class MockCredentials:
        def __init__(self, token):
            self.credentials = token
    
    # Verify the token
    user = await verify_token(MockCredentials(test_user_token), db_session)
    
    # Verify the user is correct
    assert user.username == "testuser"
    assert user.role == "user"

@pytest.mark.asyncio
async def test_verify_token_invalid(db_session):
    """Test token verification with invalid token."""
    # Create a mock credentials object with invalid token
    class MockCredentials:
        def __init__(self, token):
            self.credentials = token
    
    # Verify with invalid token
    with pytest.raises(HTTPException) as excinfo:
        await verify_token(MockCredentials("invalid_token"), db_session)
    
    # Verify the exception
    assert excinfo.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert excinfo.value.detail == "Invalid authentication credentials"

@pytest.mark.asyncio
async def test_verify_token_nonexistent_user(db_session):
    """Test token verification with token for nonexistent user."""
    # Create a token for a nonexistent user
    from app.core.security import create_access_token
    
    nonexistent_token = create_access_token({"sub": "nonexistentuser", "role": "user"})
    
    # Create a mock credentials object
    class MockCredentials:
        def __init__(self, token):
            self.credentials = token
    
    # Verify with token for nonexistent user
    with pytest.raises(HTTPException) as excinfo:
        await verify_token(MockCredentials(nonexistent_token), db_session)
    
    # Verify the exception
    assert excinfo.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert excinfo.value.detail == "User not found" 