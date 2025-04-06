from fastapi import APIRouter, HTTPException, Depends
from loguru import logger

from app.config import get_settings, Settings
from app.transcription.factory import get_transcription_service
from app.store.storage import get_transcript_store
from app.schemas import TranscriptionRequest, TranscriptionResponse

# Create router
router = APIRouter(
    prefix="/api",
    tags=["transcription"],
)


@router.post("/transcribe", response_model=TranscriptionResponse)
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


@router.get("/v2/sessions/{session_id}")
async def get_session_transcripts_v2(session_id: str):
    """
    Get all transcripts for a specific session using the new in-memory store.
    Includes detailed transcript data with segments and speaker information.
    """
    import uuid
    import sqlalchemy as sa
    from app.database import async_session
    from app.models import Session, Transcript
    
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


@router.get("/v2/dispatcher/status")
async def get_dispatcher_status():
    """
    Get the status of the dispatcher and information about pending transcripts.
    """
    import uuid
    import sqlalchemy as sa
    from app.database import async_session
    from app.models import Session
    from app.store.dispatcher import get_dispatcher
    
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