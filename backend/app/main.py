import uuid
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from loguru import logger
import asyncio

# Import application components
from app.store.dispatcher import start_dispatcher, stop_dispatcher
from app.database import init_db
from app.config import get_settings, Settings

# Import routers
from app.routers import sessions, transcription, soap, websocket

# Get application settings
settings = get_settings()

app = FastAPI(
    title="Asha Transcription API",
    description="WebSocket-based service for real-time audio transcription",
    version="0.1.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Include routers
app.include_router(sessions.router)
app.include_router(transcription.router)
app.include_router(soap.router)
app.include_router(websocket.router)

# In-memory store for interim transcripts: {session_uuid: {serial_number: transcript}}
# Kept for backward compatibility
interim_transcripts: Dict[str, Dict[int, str]] = {}


@app.on_event("startup")
async def startup_event():
    logger.info("Initializing database...")
    await init_db()
    logger.info("Database initialized!")
    
    # Start the transcript dispatcher
    logger.info("Starting transcript dispatcher...")
    await start_dispatcher()
    logger.info("Transcript dispatcher started!")


@app.on_event("shutdown")
async def shutdown_event():
    # Stop the transcript dispatcher
    logger.info("Stopping transcript dispatcher...")
    await stop_dispatcher()
    logger.info("Transcript dispatcher stopped!")


@app.get("/")
async def root():
    return {
        "message": "Welcome to Asha Transcription API",
        "websocket_endpoint": "/ws/{session_id}",
        "rest_endpoints": [
            "/api/transcribe",
            "/api/sessions [GET] - List all sessions",
            "/api/sessions [POST] - Create a new session",
            "/api/sessions/{session_id} [GET] - Get transcripts for a session",
            "/api/sessions/{session_id} [PUT] - Update a session",
            "/api/sessions/{session_id}/details - Get detailed session information",
            "/api/sessions/{session_id}/soap - Get or create a SOAP note",
            "/api/v2/sessions/{session_id} - Get detailed transcripts with segments",
            "/api/v2/dispatcher/status - Get dispatcher status",
        ],
        "workflow": "1. Create a session with POST /api/sessions, 2. Connect to WebSocket with the returned session_id, 3. Send audio chunks via WebSocket",
        "configured_provider": settings.TRANSCRIPTION_PROVIDER,
        "streaming_enabled": settings.USE_STREAMING_TRANSCRIPTION
    }

print("FastAPI app created and configured. To run the server use: uvicorn app.main:app --reload")
