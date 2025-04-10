import os
import uuid
import logging
import bcrypt
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert # Use dialect specific insert for potential ON CONFLICT later
import aiofiles # For async file operations
import openai
from sqlalchemy import select, func
from typing import List, Optional
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
import tempfile
from datetime import datetime, timedelta
import jwt
from jwt.exceptions import InvalidTokenError
import io

from database import engine, get_db_session
from app.models import voice_records, users, create_tables, User
from app.core.config import settings
from app.services.transcription import transcribe_audio
from app import create_app
from app.services.websocket_service import WebSocketService

# --- Configuration & Setup ---
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
if not openai.api_key:
    raise ValueError("OPENAI_API_KEY environment variable not set")

# Configure logging to show all levels and use a simple format
logging.basicConfig(
    level=logging.DEBUG,  # Set to DEBUG to see all logs
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()  # This ensures logs go to stdout
    ]
)
logger = logging.getLogger(__name__)

# Add a test log message to verify logging is working
logger.info("Backend server starting up...")
logger.debug("Debug logging is enabled")

# Constants
CHUNKS_COUNT_NEED_FOR_TRANSCRIPTION = 3  # Number of chunks to process for transcription
TEMP_AUDIO_DIR = "temp_audio"
os.makedirs(TEMP_AUDIO_DIR, exist_ok=True)

app = FastAPI()
security = HTTPBearer()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8000", "https://cryptafe.io"],  # Frontend URLs
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "Accept", "Origin", "X-Requested-With"],
    expose_headers=["*"],
    max_age=3600  # Cache preflight requests for 1 hour
)

# --- Database Initialization ---
@app.on_event("startup")
async def startup_event():
    logger.info("Starting up...")
    await create_tables(engine) # Create DB tables if they don't exist
    logger.info("Database tables checked/created.")

# Add after the imports
class LoginRequest(BaseModel):
    username: str
    password: str

class PasswordResetRequest(BaseModel):
    username: str
    new_password: str

class BatchDeleteRequest(BaseModel):
    ids: List[int] 

# Add JWT configuration
JWT_SECRET = os.getenv("JWT_SECRET", "your-secret-key")  # In production, use a secure secret
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440  # 24 hours

# Add JWT token functions
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return encoded_jwt

async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security), db: AsyncSession = Depends(get_db_session)):
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    
    query = select(users).where(users.c.username == username)
    result = await db.execute(query)
    user = result.fetchone()
    
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user

# --- Authentication ---
async def verify_user(username: str, password: str, db: AsyncSession):
    print(f"........Verifying user: {username}")
    query = select(users).where(users.c.username == username)
    result = await db.execute(query)
    user = result.fetchone()
    
    print(f"Database query result: {user}")
    
    if not user:
        print(".......User not found in database")
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials"
        )
    
    print(f".......Found user: {user.username}, role: {user.role}")
    print(f".......Stored hash: {user.password_hash}")
    print(f".......Input password: {password}")
    
    # Convert password to bytes for bcrypt
    password_bytes = password.strip().encode('utf-8')
    stored_hash_bytes = user.password_hash.encode('utf-8')
    
    print(f".......Password bytes: {password_bytes}")
    print(f".......Stored hash bytes: {stored_hash_bytes}")
    print(f".......Stored hash type: {type(user.password_hash)}")
    print(f".......Stored hash length: {len(user.password_hash)}")
    
    try:
        # First, try to hash the input password to ensure it's in the correct format
        hashed_input = hash_password(password)
        print(f".......Hashed input password: {hashed_input}")
        
        # Then compare the hashes
        is_valid = bcrypt.checkpw(password_bytes, stored_hash_bytes)
        print(f".......Password check result: {is_valid}")
        
        if not is_valid:
            print(".......Invalid password")
            raise HTTPException(
                status_code=401,
                detail="Invalid credentials"
            )
            
        return user
        
    except Exception as e:
        print(f".......Error during password check: {str(e)}")
        print(f".......Error type: {type(e)}")
        import traceback
        print(f".......Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials"
        )

# Replace the login endpoint
@app.post("/api/login")
async def login(login_data: LoginRequest, db: AsyncSession = Depends(get_db_session)):
    """Authenticate user and return JWT token."""
    try:
        print(f".......Login data: {login_data}")
        user = await verify_user(login_data.username, login_data.password, db)
        print(f".......User: {user}")
        
        # Create access token
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.username, "role": user.role},
            expires_delta=access_token_expires
        )
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "username": user.username,
            "role": user.role,
            "conf": user.conf
        }
    except HTTPException as e:
        logger.error(f"Login failed for user {login_data.username}: {e.detail}")
        raise e
    except Exception as e:
        logger.error(f"Unexpected error during login: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred during login"
        )

# --- WebSocket Connection Management (Simple) ---
# A more robust manager class is better for production
active_connections: dict[str, WebSocket] = {}

# --- WebSocket Endpoint ---
@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str, db: AsyncSession = Depends(get_db_session)):
    """Handles WebSocket connections for audio recording with real-time transcription."""
    logger.info(f"New WebSocket connection request for session: {session_id}")
    
    try:
        # Create WebSocket service instance
        websocket_service = WebSocketService(db)
        
        # Handle the connection
        await websocket_service.handle_connection(websocket, session_id)
    except Exception as e:
        logger.error(f"Error in WebSocket endpoint: {e}")
        try:
            await websocket.close(code=1011, reason=str(e))
        except:
            pass
    finally:
        logger.info(f"WebSocket connection closed for session: {session_id}")

# --- Basic HTTP Endpoint (Optional) ---
@app.get("/")
async def read_root():
    """Root endpoint to verify the server is running."""
    logger.info("Root endpoint called")
    return JSONResponse(
        content={"message": "Assistant Backend Running", "status": "ok"},
        status_code=200
    )

@app.get("/api/transcriptions")
async def get_transcriptions(
    page: int = 1,
    per_page: int = 10,
    time_filter: str = "all",
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(verify_token)
):
    """
    Get paginated transcriptions for the current user with optional time filtering.
    
    Args:
        page: Page number (1-based)
        per_page: Number of items per page
        time_filter: Filter by time period ('all', 'today', 'week', 'month')
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        Paginated transcriptions with metadata
    """
    # Calculate offset
    offset = (page - 1) * per_page
    
    # Base query
    query = select(voice_records)
    
    # Check if user_id column exists
    try:
        # Try to filter by user_id if the column exists
        query = query.where(voice_records.c.user_id == current_user.id)
    except AttributeError:
        # If user_id column doesn't exist, return all transcriptions (for backward compatibility)
        logger.warning("user_id column not found in voice_records table. Returning all transcriptions.")
    
    # Apply time filter
    now = datetime.utcnow()
    if time_filter == "today":
        # Last 24 hours
        start_time = now - timedelta(days=1)
        query = query.where(voice_records.c.created_at >= start_time)
    elif time_filter == "week":
        # Last 7 days
        start_time = now - timedelta(days=7)
        query = query.where(voice_records.c.created_at >= start_time)
    elif time_filter == "month":
        # Last 30 days
        start_time = now - timedelta(days=30)
        query = query.where(voice_records.c.created_at >= start_time)
    
    # Get total count after applying filters
    count_query = select(func.count()).select_from(query.subquery())
    total_count_result = await db.execute(count_query)
    total_count = total_count_result.scalar()
    
    # Calculate total pages
    total_pages = (total_count + per_page - 1) // per_page
    
    # Get paginated results
    query = query.order_by(voice_records.c.id.desc()).offset(offset).limit(per_page)
    result = await db.execute(query)
    transcriptions = result.fetchall()
    
    # Calculate row numbers (1-based)
    start_row = offset + 1
    items = []
    for i, transcription in enumerate(transcriptions):
        items.append({
            "id": transcription.id,
            "transcript": transcription.transcript,
            "file_size": format_file_size(len(transcription.audio_byte)) if transcription.audio_byte else "0 B",
            "created_at": transcription.created_at.isoformat() if transcription.created_at else None,
            "row_number": start_row + i
        })
    
    # Prepare response
    response = {
        "items": items,
        "total": total_count,
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages,
        "has_more": page < total_pages
    }
    
    return response

# Helper function to format file size
def format_file_size(size_bytes):
    """Convert bytes to human readable format."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.2f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"

@app.delete("/api/transcriptions/{transcription_id}")
async def delete_transcription(
    transcription_id: int,
    db: AsyncSession = Depends(get_db_session),
    user = Depends(verify_token)  # Use token verification instead of basic auth
):
    """Delete a single transcription chunk."""
    try:
        query = voice_records.delete().where(voice_records.c.id == transcription_id)
        await db.execute(query)
        await db.commit()
        return {"message": "Transcription deleted successfully"}
    except Exception as e:
        await db.rollback()
        logger.error(f"Error deleting transcription: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/transcriptions")
async def delete_multiple_transcriptions(
    request: BatchDeleteRequest,
    db: AsyncSession = Depends(get_db_session),
    user = Depends(verify_token)  # Use token verification instead of basic auth
):
    """Delete multiple transcription chunks."""
    try:
        query = voice_records.delete().where(voice_records.c.id.in_(request.ids))
        await db.execute(query)
        await db.commit()
        return {"message": "Transcriptions deleted successfully"}
    except Exception as e:
        await db.rollback()
        logger.error(f"Error deleting transcriptions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/transcriptions/{transcription_id}/audio")
async def get_transcription_audio(
    transcription_id: int,
    db: AsyncSession = Depends(get_db_session),
    user = Depends(verify_token)  # Use token verification instead of basic auth
):
    """Get the audio chunk for a transcription."""
    try:
        query = select(voice_records.c.audio_byte).where(voice_records.c.id == transcription_id)
        result = await db.execute(query)
        record = result.fetchone()
        
        if not record:
            raise HTTPException(status_code=404, detail="Transcription not found")
        
        # Return the audio data with proper headers
        return Response(
            content=record.audio_byte,
            media_type="audio/webm;codecs=opus",
            headers={
                "Content-Disposition": f"attachment; filename=transcription_{transcription_id}.webm",
                "Accept-Ranges": "bytes",
                "Cache-Control": "no-cache, no-store, must-revalidate"
            }
        )
    except Exception as e:
        logger.error(f"Error fetching audio: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/test-logging")
async def test_logging():
    """Test endpoint to verify logging is working."""
    logger.debug("This is a DEBUG message")
    logger.info("This is an INFO message")
    logger.warning("This is a WARNING message")
    logger.error("This is an ERROR message")
    return {"message": "Logging test complete. Check your terminal for logs."}

# --- Password Hashing Function ---
def hash_password(plain_password: str) -> str:
    """
    Hashes a plain-text password using bcrypt and logs the plain text (FOR DEBUGGING ONLY).

    Args:
        plain_password: The password string to hash.

    Returns:
        The bcrypt hash string (typically 60 characters).

    Raises:
        ValueError: If the input password is not a string or is empty.
        TypeError: If encoding fails (very unlikely with strings).
    """
    if not isinstance(plain_password, str) or not plain_password:
        raise ValueError("Password must be a non-empty string.")

    # !!! SECURITY WARNING !!!
    # Logging plain-text passwords is a SIGNIFICANT security risk.
    # Only enable this during temporary debugging in a secure development environment.
    # Ensure this log statement is REMOVED or heavily guarded in production.
    logging.warning(f"Hashing plain-text password (DEBUG ONLY): '{plain_password}'") # Use WARNING to make it visible

    try:
        # 1. Encode the password string to bytes (bcrypt requires bytes)
        password_bytes = plain_password.encode('utf-8')

        # 2. Generate a salt. bcrypt.gensalt() creates a unique salt with a
        #    configurable cost factor (work factor). Higher factor = slower but more secure.
        #    Default is usually 12.
        salt = bcrypt.gensalt()
        logging.debug(f"Generated salt (prefix includes cost factor): {salt.decode('utf-8')[:29]}...") # Log only prefix for brevity/security

        # 3. Hash the password bytes using the generated salt
        hashed_password_bytes = bcrypt.hashpw(password_bytes, salt)

        # 4. Decode the resulting hash bytes back to a string (usually UTF-8)
        #    for storage in databases (e.g., VARCHAR/TEXT columns)
        hashed_password_string = hashed_password_bytes.decode('utf-8')

        logging.info(f"Password successfully hashed (length: {len(hashed_password_string)}).")
        # Avoid logging the full hash unless absolutely necessary for debugging specific storage issues.
        # logging.debug(f"Generated hash: {hashed_password_string}")

        return hashed_password_string

    except Exception as e:
        logging.error(f"Error during password hashing: {e}", exc_info=True)
        # Re-raise or handle appropriately depending on your application's flow
        raise RuntimeError(f"Failed to hash password: {e}") from e

# --- Health Check Endpoint ---
@app.get("/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

# --- Reset Password Endpoint ---
@app.post("/api/reset-password")
async def reset_password(reset_data: PasswordResetRequest, db: AsyncSession = Depends(get_db_session)):
    """Reset a user's password."""
    try:
        # Find the user
        query = select(users).where(users.c.username == reset_data.username)
        result = await db.execute(query)
        user = result.fetchone()
        
        if not user:
            raise HTTPException(
                status_code=404,
                detail="User not found"
            )
        
        # Hash the new password
        hashed_password = hash_password(reset_data.new_password)
        
        # Update the user's password
        update_query = users.update().where(users.c.username == reset_data.username).values(
            password_hash=hashed_password
        )
        await db.execute(update_query)
        await db.commit()
        
        return {"message": "Password reset successfully"}
    except Exception as e:
        await db.rollback()
        logger.error(f"Error resetting password: {e}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

# --- Run the server (for local development) ---
# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8000)
# You'll typically run with: uvicorn main:app --host 0.0.0.0 --port 8000 --reload