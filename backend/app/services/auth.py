from datetime import timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.core.logging import logger
from app.core.security import verify_user, create_access_token, hash_password
from app.models.user import users

async def authenticate_user(username: str, password: str, db: AsyncSession):
    """Authenticate a user and return a JWT token."""
    try:
        logger.debug(f"Login attempt for user: {username}")
        user = await verify_user(username, password, db)
        logger.debug(f"User authenticated: {user.username}")
        
        # Create access token
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.username, "role": user.role},
            expires_delta=access_token_expires
        )
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "username": user.username,
            "role": user.role,
            "lang": user.lang,
            "conf": user.conf
        }
    except Exception as e:
        logger.error(f"Authentication error: {str(e)}")
        raise

async def reset_password(username: str, new_password: str, db: AsyncSession):
    """Reset a user's password."""
    try:
        # Check if user exists
        query = select(users).where(users.c.username == username)
        result = await db.execute(query)
        user = result.fetchone()
        
        if not user:
            return False
        
        # Hash the new password
        hashed_password = hash_password(new_password)
        
        # Update the user's password
        update_query = (
            users.update()
            .where(users.c.username == username)
            .values(password_hash=hashed_password)
        )
        
        await db.execute(update_query)
        await db.commit()
        
        return True
    except Exception as e:
        logger.error(f"Password reset error: {str(e)}")
        return False 