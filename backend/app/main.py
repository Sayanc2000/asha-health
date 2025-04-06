import uuid
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from loguru import logger
import asyncio
import json

# Import application components
from app.transcription.factory import get_transcription_service
from app.store.storage import get_transcript_store
from app.store.dispatcher import start_dispatcher, stop_dispatcher, get_dispatcher
from app.models import init_db, Transcript, SOAPNote, async_session
from app.config import get_settings, Settings
from app.soap_service import process_and_store_soap_note, get_soap_note_for_session, schedule_soap_note_generation

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

# In-memory store for interim transcripts: {session_uuid: {serial_number: transcript}}
interim_transcripts: Dict[str, Dict[int, str]] = {}

# Models for API endpoints
class TranscriptionRequest(BaseModel):
    audio_data: str
    provider: Optional[str] = None


class TranscriptionResponse(BaseModel):
    text: str
    segments: List[Dict[str, Any]] = []
    speakers: List[str] = []


class SessionInfo(BaseModel):
    session_id: str
    chunks_count: int


class SOAPNoteRequest(BaseModel):
    provider: Optional[str] = "default"


class SOAPNoteResponse(BaseModel):
    session_id: str
    soap_text: str
    created_at: str


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
            "/api/sessions",
            "/api/sessions/{session_id}",
            "/api/sessions/{session_id}/soap",
        ],
        "configured_provider": settings.TRANSCRIPTION_PROVIDER
    }


@app.post("/api/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio(request: TranscriptionRequest, settings: Settings = Depends(get_settings)):
    """
    Transcribe audio using the configured provider or the requested provider.
    """
    provider = request.provider or settings.TRANSCRIPTION_PROVIDER
    
    try:
        # Get the transcription service
        transcription_service = get_transcription_service(provider=provider)
        
        # Transcribe the audio
        transcript_data = await transcription_service.transcribe(request.audio_data)
        
        return TranscriptionResponse(
            text=transcript_data.get("text", ""),
            segments=transcript_data.get("segments", []),
            speakers=transcript_data.get("speakers", ["SPEAKER_00"])
        )
    
    except Exception as e:
        logger.exception(f"Error transcribing audio: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")


@app.get("/api/sessions", response_model=List[SessionInfo])
async def get_sessions():
    """
    Get information about all active transcription sessions.
    """
    return [
        SessionInfo(
            session_id=session_id,
            chunks_count=len(chunks)
        )
        for session_id, chunks in interim_transcripts.items()
    ]


@app.get("/api/sessions/{session_id}")
async def get_session_transcripts(session_id: str):
    """
    Get all transcripts for a specific session.
    """
    if session_id not in interim_transcripts:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    
    # Return transcripts ordered by serial number
    session_data = interim_transcripts[session_id]
    sorted_serials = sorted(session_data.keys())
    
    return {
        "session_id": session_id,
        "transcripts": [
            {
                "serial": serial,
                "transcript": session_data[serial]
            }
            for serial in sorted_serials
        ]
    }


@app.get("/api/v2/sessions/{session_id}")
async def get_session_transcripts_v2(session_id: str):
    """
    Get all transcripts for a specific session using the new in-memory store.
    Includes detailed transcript data with segments and speaker information.
    """
    # Get the transcript store
    transcript_store = get_transcript_store()
    
    # Get all transcripts for the session
    transcripts = await transcript_store.get_transcripts_for_session(session_id)
    
    if not transcripts:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    
    return {
        "session_id": session_id,
        "transcripts": [
            {
                "serial": record.serial,
                "text": record.transcript,
                "segments": [
                    {
                        "id": segment.id,
                        "start": segment.start,
                        "end": segment.end,
                        "text": segment.text,
                        "speaker": segment.speaker
                    }
                    for segment in record.segments
                ],
                "speakers": record.speakers,
                "status": record.status,
                "created_at": record.created_at.isoformat()
            }
            for record in transcripts
        ]
    }


@app.get("/api/v2/dispatcher/status")
async def get_dispatcher_status():
    """
    Get the status of the dispatcher and information about pending transcripts.
    """
    # Get the dispatcher instance
    dispatcher = get_dispatcher()
    
    # Get the in-memory store
    transcript_store = get_transcript_store()
    
    # Get all pending transcripts (with a large limit to get all)
    pending_transcripts = await transcript_store.get_pending_transcripts(limit=1000)
    
    # Group pending transcripts by session
    sessions = {}
    for record in pending_transcripts:
        if record.session_id not in sessions:
            sessions[record.session_id] = []
        sessions[record.session_id].append(record.serial)
    
    return {
        "dispatcher_running": dispatcher.running,
        "dispatcher_settings": {
            "interval_seconds": dispatcher.interval_seconds,
            "batch_size": dispatcher.batch_size,
            "max_retries": dispatcher.max_retries,
            "retry_delay_seconds": dispatcher.retry_delay_seconds,
        },
        "pending_transcripts_count": len(pending_transcripts),
        "sessions_with_pending_transcripts": len(sessions),
        "sessions": [
            {
                "session_id": session_id,
                "pending_serials": sorted(serials)
            }
            for session_id, serials in sessions.items()
        ]
    }


@app.post("/api/sessions/{session_id}/soap", response_model=SOAPNoteResponse)
async def create_soap_note(session_id: str, request: SOAPNoteRequest = None):
    """
    Generate a SOAP note for a specific session.
    
    Args:
        session_id: The session ID to generate a SOAP note for
        request: Optional request body with SOAP processor provider
        
    Returns:
        The generated SOAP note
    """
    try:
        # Use default provider if not specified
        provider = request.provider if request and request.provider else "default"
        
        # Process and store the SOAP note
        soap_note = await process_and_store_soap_note(session_id, provider=provider)
        
        return SOAPNoteResponse(
            session_id=soap_note.session_id,
            soap_text=soap_note.soap_text,
            created_at=soap_note.created_at.isoformat()
        )
    except ValueError as e:
        logger.error(f"Failed to create SOAP note for session {session_id}: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create SOAP note for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error creating SOAP note: {str(e)}")


@app.get("/api/sessions/{session_id}/soap", response_model=SOAPNoteResponse)
async def get_soap_note(session_id: str):
    """
    Get the SOAP note for a specific session.
    
    Args:
        session_id: The session ID to get the SOAP note for
        
    Returns:
        The SOAP note if found
    """
    soap_note = await get_soap_note_for_session(session_id)
    
    if not soap_note:
        raise HTTPException(status_code=404, detail=f"No SOAP note found for session {session_id}")
    
    return SOAPNoteResponse(
        session_id=soap_note.session_id,
        soap_text=soap_note.soap_text,
        created_at=soap_note.created_at.isoformat()
    )


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str, settings: Settings = Depends(get_settings)):
    await websocket.accept()
    logger.info(f"Session {session_id} connected.")
    
    # Create a transcription service instance via the factory with configured provider
    transcription_service = get_transcription_service(provider=settings.TRANSCRIPTION_PROVIDER)
    
    # Get the in-memory transcript store
    transcript_store = get_transcript_store()
    
    # Ensure a place in the in-memory store
    interim_transcripts[session_id] = {}
    
    # Store SOAP processor type for this session (default unless specified in test)
    soap_processor_type = "default"

    try:
        while True:
            # Receive message from client
            message_raw = await websocket.receive_text()
            data = json.loads(message_raw)
            
            # Check if this is a test control message to set the SOAP processor type
            if "set_soap_processor" in data:
                soap_processor_type = data["set_soap_processor"]
                logger.info(f"Session {session_id}: Setting SOAP processor to {soap_processor_type}")
                await websocket.send_json({"status": "success", "message": f"SOAP processor set to {soap_processor_type}"})
                continue
            
            # Normal transcription message processing
            serial = data.get("serial")
            audio_data = data.get("audio_data")  # audio data might be base64 encoded
            provider = data.get("provider", settings.TRANSCRIPTION_PROVIDER)

            logger.info(f"Session {session_id}: Received chunk {serial}.")
            
            # Use the requested provider if specified
            if provider != settings.TRANSCRIPTION_PROVIDER:
                try:
                    transcription_service = get_transcription_service(provider=provider)
                except ValueError as e:
                    logger.error(f"Invalid provider requested: {provider}, using default")
            
            # Process the transcription asynchronously
            transcript_data = await transcription_service.transcribe(audio_data)
            logger.info(f"Session {session_id}: Transcribed chunk {serial}: {transcript_data}")
            
            # Store the interim result with its serial number in legacy in-memory dict (for backward compatibility)
            interim_transcripts[session_id][serial] = transcript_data.get("text", "")
            
            # Store in the new thread-safe in-memory store
            await transcript_store.add_transcript(
                session_id=session_id,
                serial=serial,
                transcript_data=transcript_data
            )
            
            # Send acknowledgment back to client
            await websocket.send_json({
                "status": "success",
                "serial": serial,
                "transcript": transcript_data.get("text", "")
            })

    except WebSocketDisconnect:
        logger.info(f"Session {session_id} disconnected.")
        
        # Schedule SOAP note generation to run in the background 
        # using the refactored function from soap_service
        # Use the SOAP processor type that was set for this session
        schedule_soap_note_generation(session_id, provider=soap_processor_type)
        
    except Exception as e:
        logger.error(f"Error in session {session_id}: {e}")
        try:
            await websocket.send_json({
                "status": "error",
                "message": str(e)
            })
        except:
            # Might already be disconnected
            pass
        
        # Also schedule SOAP note generation on error cases
        schedule_soap_note_generation(session_id, provider=soap_processor_type)
