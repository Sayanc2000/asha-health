import uuid
import json
from typing import Dict
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from loguru import logger
import sqlalchemy as sa

from app.config import get_settings, Settings
from app.database import async_session
from app.models import Session
from app.transcription.factory import get_transcription_service
from app.store.storage import get_transcript_store
from app.soap_service import schedule_soap_note_generation

# Create router
router = APIRouter(tags=["websocket"])

# In-memory store for interim transcripts: {session_uuid: {serial_number: transcript}}
interim_transcripts: Dict[str, Dict[int, str]] = {}


@router.websocket("/ws/{session_id}")
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