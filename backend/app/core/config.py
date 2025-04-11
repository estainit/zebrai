import os
from typing import List
from dotenv import load_dotenv
from pydantic_settings import BaseSettings
from typing import Optional

# Load environment variables
load_dotenv()

class Settings(BaseSettings):
    # API settings
    API_V1_STR: str = "/api"
    
    # Security
    JWT_SECRET: str = os.getenv("JWT_SECRET", "your-secret-key")  # In production, use a secure secret
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/zebrai")
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL environment variable not set")
    
    # OpenAI
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY environment variable not set")
    
    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000", 
        "http://localhost:8000", 
        "https://cryptafe.io"
    ]
    
    # File storage
    TEMP_AUDIO_DIR: str = "temp_audio"
    CHUNKS_COUNT_NEED_FOR_TRANSCRIPTION: int = 2  # Number of chunks to collect before sending to OpenAI
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "DEBUG")

    # Google OAuth
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    GOOGLE_REDIRECT_URI: str = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/api/auth/google/callback")
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:3000")

    class Config:
        env_file = ".env"

# Create settings instance
settings = Settings()

# Ensure temp directory exists
os.makedirs(settings.TEMP_AUDIO_DIR, exist_ok=True) 