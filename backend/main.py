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
from models import transcription_chunks, users, create_tables

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

TEMP_AUDIO_DIR = "temp_audio"
os.makedirs(TEMP_AUDIO_DIR, exist_ok=True)

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

# --- Audio Transcription Function ---
async def transcribe_audio(audio_file):
    """Transcribe audio using OpenAI's Whisper API."""
    try:
        # Create a temporary file for the audio data
        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as temp_file:
            temp_file.write(audio_file.read())
            temp_file_path = temp_file.name

        # Open the file for transcription
        with open(temp_file_path, "rb") as audio_file:
            # Call OpenAI's Whisper API for transcription
            response = await openai.Audio.atranscribe("whisper-1", audio_file)
            
            # Clean up the temporary file
            os.unlink(temp_file_path)
            
            # Return the transcribed text
            return response.text
    except Exception as e:
        logger.error(f"Transcription error: {e}")
        # Clean up the temporary file if it exists
        if 'temp_file_path' in locals():
            try:
                os.unlink(temp_file_path)
            except:
                pass
        raise e

# --- WebSocket Connection Management (Simple) ---
# A more robust manager class is better for production
active_connections: dict[str, WebSocket] = {}

# --- WebSocket Endpoint ---
@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str, db: AsyncSession = Depends(get_db_session)):
    """Handles WebSocket connections, receives audio chunks, transcribes, saves, and returns text."""
    await websocket.accept()
    
    try:
        # Wait for authentication message
        auth_message = await websocket.receive_json()
        if auth_message.get("type") != "auth":
            await websocket.close(code=4001, reason="Authentication required")
            return
            
        token = auth_message.get("token")
        if not token:
            await websocket.close(code=4001, reason="No token provided")
            return
            
        try:
            # Verify token
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            username = payload.get("sub")
            if not username:
                await websocket.close(code=4002, reason="Invalid token")
                return
                
            # Get user from database
            query = select(users).where(users.c.username == username)
            result = await db.execute(query)
            user = result.fetchone()
            
            if not user:
                await websocket.close(code=4002, reason="User not found")
                return
                
            active_connections[session_id] = websocket
            logger.info(f"WebSocket connection accepted for session: {session_id}, user: {username}")
            
            # Get user's transcription preference
            do_transcript = user.conf.get("doTranscript", True)
            do_transcript = False
            logger.info(f"User {username} transcription enabled: {do_transcript}")
            
            while True:
                audio_data = await websocket.receive_bytes()
                logger.debug(f"Received {len(audio_data)} bytes for session {session_id}")

                if not audio_data:
                    continue

                # Generate a unique filename for this chunk
                chunk_filename = f"{session_id}_{uuid.uuid4()}.webm"
                temp_file_path = os.path.join(TEMP_AUDIO_DIR, chunk_filename)

                try:
                    # Save the chunk with WebM header if it's the first chunk
                    if not os.path.exists(temp_file_path):
                        # Add WebM header for the first chunk
                        webm_header = bytes([
                            0x1A, 0x45, 0xDF, 0xA3,  # EBML Header
                            0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x20,  # EBML Version
                            0x42, 0x86, 0x81, 0x01, 0x42, 0xF7, 0x81, 0x01,  # DocType
                            0x42, 0xF2, 0x81, 0x04, 0x42, 0xF3, 0x81, 0x08,  # DocTypeVersion
                            0x42, 0x82, 0x84, 0x77, 0x65, 0x62, 0x6D, 0x42, 0x87, 0x81, 0x02,  # DocTypeReadVersion
                            0x42, 0x85, 0x81, 0x02,  # DocTypeVersion
                            0x18, 0x53, 0x80, 0x67,  # Segment
                            0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,  # Segment Size
                            0x15, 0x49, 0xA9, 0x66,  # Info
                            0x16, 0x54, 0xAE, 0x6B,  # Tracks
                            0xAE, 0x8A,  # Track Entry
                            0xD7, 0x81, 0x01,  # Track Number
                            0x73, 0xC5, 0x81, 0x01,  # Track Type (Audio)
                            0x9A, 0x81, 0x01,  # Flag Default
                            0x86, 0x85, 0x6F, 0x70, 0x75, 0x73,  # Codec ID
                            0x63, 0xA2, 0x81, 0x01,  # Codec Private
                            0x9F, 0x81, 0x01,  # Flag Lacing
                            0x22, 0xB5, 0x9C,  # Track UID
                            0x83, 0x81, 0x01,  # Track Type
                            0xE0,  # Cluster
                            0xE1,  # Timecode
                            0xA3,  # Simple Block
                        ])
                        async with aiofiles.open(temp_file_path, "wb") as temp_file:
                            await temp_file.write(webm_header)
                            await temp_file.write(audio_data)
                    else:
                        # Append the chunk without header
                        async with aiofiles.open(temp_file_path, "ab") as temp_file:
                            await temp_file.write(audio_data)

                    # Save to database with proper WebM format
                    if not os.path.exists(temp_file_path):
                        # For first chunk, include header
                        with open(temp_file_path, "rb") as f:
                            audio_data = f.read()
                    else:
                        # For subsequent chunks, just use the chunk data
                        audio_data = audio_data

                    insert_query = transcription_chunks.insert().values(
                        session_id=session_id,
                        audio_chunk=audio_data,
                        transcript=None  # Will be updated after transcription
                    )
                    await db.execute(insert_query)
                    await db.commit()

                    # Transcribe if enabled
                    if do_transcript:
                        try:
                            # Create a copy of the audio file for transcription
                            with open(temp_file_path, "rb") as audio_file:
                                audio_data_for_transcription = audio_file.read()
                                
                            # Create a BytesIO object from the audio data
                            audio_io = io.BytesIO(audio_data_for_transcription)
                            
                            # Transcribe the audio
                            transcript = await transcribe_audio(audio_io)
                            
                            if transcript:
                                # Update the chunk's transcript in the database
                                update_query = transcription_chunks.update().where(
                                    transcription_chunks.c.session_id == session_id
                                ).values(transcript=transcript)
                                await db.execute(update_query)
                                await db.commit()
                                
                                # Send transcript back to client
                                await websocket.send_json({
                                    "transcript": transcript,
                                    "chunk_id": chunk_filename
                                })
                        except Exception as e:
                            logger.error(f"Transcription error: {e}")
                            await websocket.send_json({
                                "error": f"Transcription failed: {str(e)}",
                                "chunk_id": chunk_filename
                            })

                except Exception as e:
                    logger.error(f"Error processing audio chunk: {e}")
                    await websocket.send_json({
                        "error": f"Failed to process audio chunk: {str(e)}",
                        "chunk_id": chunk_filename
                    })

        except InvalidTokenError:
            await websocket.close(code=4002, reason="Invalid token")
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            await websocket.close(code=4002, reason=str(e))
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for session: {session_id}")
        if session_id in active_connections:
            del active_connections[session_id]
    except Exception as e:
        logger.error(f"Unexpected error in WebSocket endpoint: {e}")
        if session_id in active_connections:
            del active_connections[session_id]

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
    per_page: int = 20,
    db: AsyncSession = Depends(get_db_session),
    user = Depends(verify_token)  # Use token verification instead of basic auth
):
    """Get paginated transcription chunks."""
    try:
        offset = (page - 1) * per_page
        logger.info(f"Fetching transcriptions with offset={offset}, per_page={per_page}")
        
        # Get total count
        count_query = select(func.count()).select_from(transcription_chunks)
        total_count = await db.execute(count_query)
        total_count = total_count.scalar()
        logger.info(f"Total count of transcriptions: {total_count}")
        
        # Get paginated records ordered by ID in descending order
        query = select(transcription_chunks).order_by(transcription_chunks.c.id.asc()).offset(offset).limit(per_page)
        result = await db.execute(query)
        records = result.fetchall()
        logger.info(f"Retrieved {len(records)} records")
        
        # Format response
        transcriptions = [
            {
                "id": record.id,
                "transcript": record.transcript,
                "file_size": format_file_size(len(record.audio_chunk)) if record.audio_chunk else "0 B"
            }
            for record in records
        ]
        print(f".......Transcriptions: {transcriptions}")
        print(f".......Total count: {total_count}")
        print(f".......Page: {page}")
        print(f".......Per page: {per_page}")
        print(f".......Total pages: {(total_count + per_page - 1) // per_page}")

        response = {
            "items": transcriptions,
            "total": total_count,
            "page": page,
            "per_page": per_page,
            "total_pages": (total_count + per_page - 1) // per_page
        }
        logger.info(f"Final response: {response}")
        return response
    
    except Exception as e:
        logger.error(f"Error fetching transcriptions: {e}")
        logger.error(f"Error type: {type(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

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
        query = transcription_chunks.delete().where(transcription_chunks.c.id == transcription_id)
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
        query = transcription_chunks.delete().where(transcription_chunks.c.id.in_(request.ids))
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
        query = select(transcription_chunks.c.audio_chunk).where(transcription_chunks.c.id == transcription_id)
        result = await db.execute(query)
        record = result.fetchone()
        
        if not record:
            raise HTTPException(status_code=404, detail="Transcription not found")
        
        return Response(
            content=record.audio_chunk,
            media_type="audio/webm"
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