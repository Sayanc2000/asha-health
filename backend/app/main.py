import uuid
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from loguru import logger
import asyncio
import json
import sqlalchemy as sa

# Import application components
from app.transcription.factory import get_transcription_service
from app.store.storage import get_transcript_store
from app.store.dispatcher import start_dispatcher, stop_dispatcher, get_dispatcher
from app.database import init_db, async_session
from app.config import get_settings, Settings
from app.soap_service import process_and_store_soap_note, get_soap_note_for_session, schedule_soap_note_generation
from app.models import Transcript, SOAPNote, Session

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


class SessionRequest(BaseModel):
    name: Optional[str] = None


class SessionResponse(BaseModel):
    session_id: str
    name: Optional[str] = None
    created_at: str


class SessionInfo(BaseModel):
    session_id: str
    name: Optional[str] = None
    created_at: str
    chunks_count: int


class SOAPNoteRequest(BaseModel):
    provider: Optional[str] = "default"


class SOAPNoteResponse(BaseModel):
    session_id: str
    soap_text: str
    created_at: str


class SessionDetailResponse(BaseModel):
    session_id: str
    name: Optional[str] = None
    created_at: str
    transcript_count: int
    has_soap_note: bool
    last_activity: Optional[str] = None


class SessionUpdateRequest(BaseModel):
    name: str


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
    Get information about all transcription sessions.
    """
    try:
        async with async_session() as session:
            # Get all sessions from the database
            result = await session.execute(
                sa.select(Session)
                .order_by(Session.created_at.desc())
            )
            db_sessions = result.scalars().all()
            
            # For each session, count the number of transcripts
            sessions_info = []
            for db_session in db_sessions:
                # Count transcripts for this session
                transcript_count_result = await session.execute(
                    sa.select(sa.func.count()).select_from(Transcript)
                    .where(Transcript.session_id == db_session.id)
                )
                transcript_count = transcript_count_result.scalar() or 0
                
                sessions_info.append(SessionInfo(
                    session_id=str(db_session.id),
                    name=db_session.name,
                    created_at=db_session.created_at.isoformat(),
                    chunks_count=transcript_count
                ))
            
            return sessions_info
    except Exception as e:
        logger.error(f"Failed to get sessions: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving sessions: {str(e)}")


@app.get("/api/sessions/{session_id}")
async def get_session_transcripts(session_id: str):
    """
    Get all transcripts for a specific session.
    """
    try:
        # Convert string session_id to UUID
        session_uuid = uuid.UUID(session_id)
        
        async with async_session() as session:
            # First check if the session exists
            session_result = await session.execute(
                sa.select(Session)
                .where(Session.id == session_uuid)
            )
            db_session = session_result.scalar_one_or_none()
            
            if not db_session:
                raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
            
            # Get all transcripts for the session
            transcript_result = await session.execute(
                sa.select(Transcript)
                .where(Transcript.session_id == session_uuid)
                .order_by(Transcript.serial)
            )
            db_transcripts = transcript_result.scalars().all()
            
            return {
                "session_id": session_id,
                "name": db_session.name,
                "created_at": db_session.created_at.isoformat(),
                "transcripts": [
                    {
                        "serial": transcript.serial,
                        "transcript": transcript.transcript,
                        "speaker": transcript.speaker,
                        "created_at": transcript.created_at.isoformat()
                    }
                    for transcript in db_transcripts
                ]
            }
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid session ID format: {session_id}")
    except Exception as e:
        logger.error(f"Failed to get session transcripts: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving session transcripts: {str(e)}")


@app.get("/api/v2/sessions/{session_id}")
async def get_session_transcripts_v2(session_id: str):
    """
    Get all transcripts for a specific session using the new in-memory store.
    Includes detailed transcript data with segments and speaker information.
    """
    try:
        # Validate the session_id as UUID
        session_uuid = uuid.UUID(session_id)
        
        # Check if session exists
        async with async_session() as session:
            session_result = await session.execute(
                sa.select(Session)
                .where(Session.id == session_uuid)
            )
            db_session = session_result.scalar_one_or_none()
            
            if not db_session:
                raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    
        # Get the transcript store
        transcript_store = get_transcript_store()
        
        # Get all transcripts for the session
        transcripts = await transcript_store.get_transcripts_for_session(str(session_uuid))
        
        if not transcripts:
            # No transcripts in memory store, try database
            async with async_session() as session:
                result = await session.execute(
                    sa.select(Transcript)
                    .where(Transcript.session_id == session_uuid)
                    .order_by(Transcript.serial)
                )
                db_transcripts = result.scalars().all()
                
                if not db_transcripts:
                    # Return empty transcripts list instead of 404 since session exists
                    return {
                        "session_id": session_id,
                        "name": db_session.name,
                        "created_at": db_session.created_at.isoformat(),
                        "transcripts": []
                    }
                
                # Convert DB transcripts to response format
                return {
                    "session_id": session_id,
                    "name": db_session.name,
                    "created_at": db_session.created_at.isoformat(),
                    "transcripts": [
                        {
                            "serial": t.serial,
                            "text": t.transcript,
                            "segments": [],  # No segments available from DB
                            "speakers": [t.speaker] if t.speaker else ["SPEAKER_00"],
                            "status": "completed",
                            "created_at": t.created_at.isoformat()
                        }
                        for t in db_transcripts
                    ]
                }
        
        return {
            "session_id": session_id,
            "name": db_session.name,
            "created_at": db_session.created_at.isoformat(),
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
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid session ID format: {session_id}")
    except Exception as e:
        logger.error(f"Failed to get session transcripts v2: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving session transcripts: {str(e)}")


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
    
    # Get session names from database
    session_names = {}
    if sessions:
        try:
            async with async_session() as db_session:
                for session_id in sessions.keys():
                    try:
                        # Validate session_id as UUID
                        session_uuid = uuid.UUID(session_id)
                        
                        session_result = await db_session.execute(
                            sa.select(Session)
                            .where(Session.id == session_uuid)
                        )
                        session_obj = session_result.scalar_one_or_none()
                        
                        if session_obj:
                            session_names[session_id] = session_obj.name or "Unnamed Session"
                    except ValueError:
                        session_names[session_id] = "Invalid Session ID"
        except Exception as e:
            logger.error(f"Error fetching session names: {e}")
    
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
                "name": session_names.get(session_id, "Unknown"),
                "pending_serials": sorted(serials)
            }
            for session_id, serials in sessions.items()
        ]
    }


@app.post("/api/sessions", response_model=SessionResponse)
async def create_session(request: SessionRequest):
    """
    Create a new session and return the session ID.
    
    Args:
        request: Optional request body with session name
        
    Returns:
        The created session info with ID
    """
    try:
        async with async_session() as session:
            # Create a new session
            new_session = Session(
                name=request.name
            )
            session.add(new_session)
            await session.commit()
            await session.refresh(new_session)
            
            return SessionResponse(
                session_id=str(new_session.id),
                name=new_session.name,
                created_at=new_session.created_at.isoformat()
            )
    except Exception as e:
        logger.error(f"Failed to create session: {e}")
        raise HTTPException(status_code=500, detail=f"Error creating session: {str(e)}")


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
        # Validate the session_id as UUID
        session_uuid = uuid.UUID(session_id)
        
        # Check if session exists
        async with async_session() as session:
            session_result = await session.execute(
                sa.select(Session)
                .where(Session.id == session_uuid)
            )
            db_session = session_result.scalar_one_or_none()
            
            if not db_session:
                raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
        
        # Use default provider if not specified
        provider = request.provider if request and request.provider else "default"
        
        # Process and store the SOAP note
        soap_note = await process_and_store_soap_note(str(session_uuid), provider=provider)
        
        return SOAPNoteResponse(
            session_id=str(soap_note.session_id),
            soap_text=soap_note.soap_text,
            created_at=soap_note.created_at.isoformat()
        )
    except ValueError as e:
        if "invalid literal for UUID" in str(e):
            raise HTTPException(status_code=400, detail=f"Invalid session ID format: {session_id}")
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
    try:
        # Validate the session_id as UUID
        session_uuid = uuid.UUID(session_id)
        
        # Check if session exists
        async with async_session() as session:
            session_result = await session.execute(
                sa.select(Session)
                .where(Session.id == session_uuid)
            )
            db_session = session_result.scalar_one_or_none()
            
            if not db_session:
                raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
        
        soap_note = await get_soap_note_for_session(str(session_uuid))
        
        if not soap_note:
            raise HTTPException(status_code=404, detail=f"No SOAP note found for session {session_id}")
        
        return SOAPNoteResponse(
            session_id=str(soap_note.session_id),
            soap_text=soap_note.soap_text,
            created_at=soap_note.created_at.isoformat()
        )
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid session ID format: {session_id}")
    except Exception as e:
        logger.error(f"Failed to get SOAP note for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving SOAP note: {str(e)}")


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str, settings: Settings = Depends(get_settings)):
    await websocket.accept()
    logger.info(f"Session {session_id} connected.")
    
    try:
        # Validate session_id as UUID and check if session exists
        try:
            session_uuid = uuid.UUID(session_id)
            
            async with async_session() as db_session:
                # Check if the session exists
                session_result = await db_session.execute(
                    sa.select(Session)
                    .where(Session.id == session_uuid)
                )
                db_session_obj = session_result.scalar_one_or_none()
                
                if not db_session_obj:
                    logger.error(f"Session {session_id} not found in database.")
                    await websocket.send_json({
                        "status": "error",
                        "message": f"Session {session_id} not found"
                    })
                    await websocket.close()
                    return
        except ValueError:
            logger.error(f"Invalid session ID format: {session_id}")
            await websocket.send_json({
                "status": "error",
                "message": f"Invalid session ID format: {session_id}"
            })
            await websocket.close()
            return
    
        # Create a transcription service instance via the factory with configured provider
        transcription_service = get_transcription_service(provider=settings.TRANSCRIPTION_PROVIDER)
        
        # Get the in-memory transcript store
        transcript_store = get_transcript_store()
        
        # Ensure a place in the in-memory store
        interim_transcripts[session_id] = {}
        
        # Store SOAP processor type for this session (default unless specified in test)
        soap_processor_type = "default"

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


@app.get("/api/sessions/{session_id}/details", response_model=SessionDetailResponse)
async def get_session_details(session_id: str):
    """
    Get detailed information about a specific session.
    
    Args:
        session_id: The session ID to get details for
        
    Returns:
        Detailed session information including transcript count and SOAP note status
    """
    try:
        # Validate session_id as UUID
        session_uuid = uuid.UUID(session_id)
        
        async with async_session() as session:
            # Check if the session exists
            session_result = await session.execute(
                sa.select(Session)
                .where(Session.id == session_uuid)
            )
            db_session = session_result.scalar_one_or_none()
            
            if not db_session:
                raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
            
            # Count transcripts
            transcript_count_result = await session.execute(
                sa.select(sa.func.count()).select_from(Transcript)
                .where(Transcript.session_id == session_uuid)
            )
            transcript_count = transcript_count_result.scalar() or 0
            
            # Check if a SOAP note exists
            soap_result = await session.execute(
                sa.select(sa.func.count()).select_from(SOAPNote)
                .where(SOAPNote.session_id == session_uuid)
            )
            has_soap_note = (soap_result.scalar() or 0) > 0
            
            # Get the latest activity timestamp (most recent transcript or SOAP note)
            last_activity = db_session.created_at
            
            if transcript_count > 0:
                # Get the most recent transcript
                latest_transcript_result = await session.execute(
                    sa.select(Transcript.created_at)
                    .where(Transcript.session_id == session_uuid)
                    .order_by(Transcript.created_at.desc())
                    .limit(1)
                )
                latest_transcript_time = latest_transcript_result.scalar_one_or_none()
                if latest_transcript_time and latest_transcript_time > last_activity:
                    last_activity = latest_transcript_time
            
            if has_soap_note:
                # Get the most recent SOAP note
                latest_soap_result = await session.execute(
                    sa.select(SOAPNote.created_at)
                    .where(SOAPNote.session_id == session_uuid)
                    .order_by(SOAPNote.created_at.desc())
                    .limit(1)
                )
                latest_soap_time = latest_soap_result.scalar_one_or_none()
                if latest_soap_time and latest_soap_time > last_activity:
                    last_activity = latest_soap_time
            
            return SessionDetailResponse(
                session_id=session_id,
                name=db_session.name,
                created_at=db_session.created_at.isoformat(),
                transcript_count=transcript_count,
                has_soap_note=has_soap_note,
                last_activity=last_activity.isoformat() if last_activity else None
            )
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid session ID format: {session_id}")
    except Exception as e:
        logger.error(f"Failed to get session details: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving session details: {str(e)}")


@app.put("/api/sessions/{session_id}", response_model=SessionResponse)
async def update_session(session_id: str, request: SessionUpdateRequest):
    """
    Update a session's metadata.
    
    Args:
        session_id: The session ID to update
        request: The update request with new values
        
    Returns:
        The updated session
    """
    try:
        # Validate session_id as UUID
        session_uuid = uuid.UUID(session_id)
        
        async with async_session() as session:
            # Check if the session exists
            session_result = await session.execute(
                sa.select(Session)
                .where(Session.id == session_uuid)
            )
            db_session = session_result.scalar_one_or_none()
            
            if not db_session:
                raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
            
            # Update the session
            db_session.name = request.name
            session.add(db_session)
            await session.commit()
            await session.refresh(db_session)
            
            return SessionResponse(
                session_id=str(db_session.id),
                name=db_session.name,
                created_at=db_session.created_at.isoformat()
            )
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid session ID format: {session_id}")
    except Exception as e:
        logger.error(f"Failed to update session: {e}")
        raise HTTPException(status_code=500, detail=f"Error updating session: {str(e)}")
