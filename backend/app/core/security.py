import bcrypt
import jwt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.core.logging import logger
from app.db.session import get_db_session
from app.models.user import users

# Security scheme for JWT
security = HTTPBearer()

def hash_password(plain_password: str) -> str:
    """Hash a password using bcrypt."""
    # Convert password to bytes
    password_bytes = plain_password.strip().encode('utf-8')
    
    # Generate salt and hash the password
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    
    # Return the hash as a string
    return hashed.decode('utf-8')

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt

async def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security), 
    db: AsyncSession = Depends(get_db_session)
):
    """Verify a JWT token and return the associated user."""
    try:
        payload = jwt.decode(credentials.credentials, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, 
                detail="Invalid authentication credentials"
            )
    except jwt.exceptions.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Invalid authentication credentials"
        )
    
    query = select(users).where(users.c.username == username)
    result = await db.execute(query)
    user = result.fetchone()
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="User not found"
        )
    return user

async def verify_user(username: str, password: str, db: AsyncSession):
    """Verify a user's credentials."""
    logger.debug(f"Verifying user: {username}")
    query = select(users).where(users.c.username == username)
    result = await db.execute(query)
    user = result.fetchone()
    
    logger.debug(f"Database query result: {user}")
    
    if not user:
        logger.debug("User not found in database")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    logger.debug(f"Found user: {user.username}, role: {user.role}")
    
    # Convert password to bytes for bcrypt
    password_bytes = password.strip().encode('utf-8')
    stored_hash_bytes = user.password_hash.encode('utf-8')
    
    try:
        # Compare the hashes
        is_valid = bcrypt.checkpw(password_bytes, stored_hash_bytes)
        logger.debug(f"Password check result: {is_valid}")
        
        if not is_valid:
            logger.debug("Invalid password")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
            
        return user
        
    except Exception as e:
        logger.error(f"Error during password check: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        ) 