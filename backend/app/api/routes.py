from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import List

from app.core.security import verify_token
from app.db.session import get_db_session
from app.services.auth import authenticate_user, reset_password
from app.services.transcription import (
    delete_transcription,
    delete_multiple_transcriptions,
    get_transcription_audio
)
from app.core.logging import logger

# Create router
router = APIRouter()

# Pydantic models for request validation
class LoginRequest(BaseModel):
    username: str
    password: str

class PasswordResetRequest(BaseModel):
    username: str
    new_password: str

class UserProfile(BaseModel):
    username: str
    email: str
    role: str
    lang: str
    conf: dict

class BatchDeleteRequest(BaseModel):
    ids: List[int]

# Authentication routes
@router.post("/login")
async def login(login_data: LoginRequest, db: AsyncSession = Depends(get_db_session)):
    """Authenticate user and return JWT token."""
    try:
        return await authenticate_user(login_data.username, login_data.password, db)
    except HTTPException as e:
        logger.error(f"Login failed for user {login_data.username}: {e.detail}")
        raise e
    except Exception as e:
        logger.error(f"Unexpected error during login: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during login"
        )

@router.get("/user/profile")
async def get_user_profile(
    current_user = Depends(verify_token),
    db: AsyncSession = Depends(get_db_session)
):
    """Get the current user's profile."""
    try:
        # The verify_token dependency already returns the user
        return {
            "username": current_user.username,
            "email": current_user.email,
            "role": current_user.role,
            "lang": current_user.lang,
            "conf": current_user.conf
        }
    except Exception as e:
        logger.error(f"Error fetching user profile: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error fetching user profile"
        )

@router.post("/reset-password")
async def reset_password_endpoint(reset_data: PasswordResetRequest, db: AsyncSession = Depends(get_db_session)):
    """Reset a user's password."""
    success = await reset_password(reset_data.username, reset_data.new_password, db)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to reset password. User may not exist."
        )
    return {"message": "Password reset successfully"}


@router.delete("/transcriptions/{transcription_id}")
async def delete_transcription_endpoint(
    transcription_id: int,
    db: AsyncSession = Depends(get_db_session),
    user = Depends(verify_token)
):
    """Delete a transcription by ID."""
    try:
        success = await delete_transcription(db, transcription_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Transcription with ID {transcription_id} not found"
            )
        return {"message": "Transcription deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting transcription: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete transcription"
        )

@router.delete("/transcriptions")
async def delete_multiple_transcriptions_endpoint(
    request: BatchDeleteRequest,
    db: AsyncSession = Depends(get_db_session),
    user = Depends(verify_token)
):
    """Delete multiple transcriptions by IDs."""
    try:
        success = await delete_multiple_transcriptions(db, request.ids)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to delete transcriptions"
            )
        return {"message": "Transcriptions deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting transcriptions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete transcriptions"
        )

@router.get("/transcriptions/{transcription_id}/audio")
async def get_transcription_audio_endpoint(
    transcription_id: int,
    db: AsyncSession = Depends(get_db_session),
    user = Depends(verify_token)
):
    """Get audio data for a transcription."""
    try:
        audio_data, mime_type = await get_transcription_audio(db, transcription_id)
        if not audio_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Transcription with ID {transcription_id} not found"
            )
        
        # Return the audio data with appropriate headers
        return Response(
            content=audio_data,
            media_type=mime_type,
            headers={
                "Content-Disposition": f"attachment; filename=transcription_{transcription_id}.{mime_type.split('/')[-1]}",
                "Accept-Ranges": "bytes",
                "Cache-Control": "no-cache, no-store, must-revalidate"
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching audio: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch audio"
        ) 