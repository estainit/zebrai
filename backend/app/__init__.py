from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.routes import router as api_router
from app.websockets.routes import router as websocket_router

def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application
    """
    app = FastAPI(
        title="Audio Transcription API",
        description="API for audio transcription and management",
        version="1.0.0"
    )
    
    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "Accept", "Origin", "X-Requested-With"],
        expose_headers=["*"],
        max_age=3600  # Cache preflight requests for 1 hour
    )
    
    # Include routers
    app.include_router(api_router, prefix="/api")
    app.include_router(websocket_router)
    
    # Add health check endpoint
    @app.get("/health")
    async def health_check():
        return {"status": "ok"}
    
    return app 