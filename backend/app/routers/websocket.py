import uuid
import json
import time
from typing import Dict, Any
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from loguru import logger
import sqlalchemy as sa

from app.config import get_settings, Settings
from app.database import async_session
from app.models import Session
from app.transcription.factory import get_transcription_service
from app.transcription.deepgram_streaming import DeepgramStreamingService
from app.store.storage import get_transcript_store
from app.soap_service import schedule_soap_note_generation

# Create router
router = APIRouter(tags=["websocket"])

# In-memory store for interim transcripts: {session_uuid: {serial_number: transcript}}
interim_transcripts: Dict[str, Dict[int, str]] = {}

# In-memory store for active streaming connections
active_streams: Dict[str, DeepgramStreamingService] = {}


@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str, settings: Settings = Depends(get_settings)):
    await websocket.accept()
    logger.info(f"Session {session_id} connected.")
    
    # Variables for tracking streaming state
    stream_service = None
    
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
        
        # Determine if we should use streaming mode
        use_streaming = settings.USE_STREAMING_TRANSCRIPTION and settings.TRANSCRIPTION_PROVIDER == "deepgram"
        
        # Get the transcript store for storing results
        transcript_store = get_transcript_store()
        
        # Store SOAP processor type for this session (default unless specified in test)
        soap_processor_type = "default"
        
        if use_streaming:
            logger.info(f"Session {session_id}: Using streaming transcription with Deepgram")
            
            # Define the callback function to process streaming results
            async def result_callback(
                session_id: str, 
                transcript_data: Dict[str, Any], 
                is_final: bool,
                serial: int = None
            ):
                logger.debug(f"Session {session_id}: Received {'final' if is_final else 'interim'} transcript from Deepgram")
                
                # Send the result back to the client
                await websocket.send_json({
                    "status": "transcript_update",
                    "session_id": session_id,
                    "data": transcript_data,
                    "is_final": is_final,
                    "serial": serial
                })
                
                # Only store final results in the transcript store
                if is_final and serial is not None:
                    # Store in the new thread-safe in-memory store
                    await transcript_store.add_transcript(
                        session_id=session_id,
                        serial=serial,
                        transcript_data=transcript_data
                    )
                    
                    # Also store in legacy format for backward compatibility
                    if session_id not in interim_transcripts:
                        interim_transcripts[session_id] = {}
                    interim_transcripts[session_id][serial] = transcript_data.get("text", "")
            
            try:
                # Create and connect the streaming service
                stream_service = DeepgramStreamingService(
                    api_key=settings.DEEPGRAM_API_KEY,
                    session_id=session_id,
                    client_websocket=websocket,
                    result_callback=result_callback
                )
                
                await stream_service.connect()
                
                # Keep track of active streams
                active_streams[session_id] = stream_service
                
                logger.info(f"Session {session_id}: Started Deepgram streaming transcription")
                
                # Inform client that streaming is ready
                await websocket.send_json({
                    "status": "connected",
                    "message": "Connected to streaming transcription service",
                    "streaming": True
                })
                
            except Exception as e:
                logger.error(f"Session {session_id}: Failed to start Deepgram streaming: {e}")
                use_streaming = False  # Fall back to batch mode
                await websocket.send_json({
                    "status": "warning",
                    "message": f"Failed to connect to streaming service, falling back to batch mode: {str(e)}"
                })
        
        # If not using streaming, set up batch transcription
        if not use_streaming:
            # Create a transcription service instance via the factory with configured provider
            transcription_service = get_transcription_service(provider=settings.TRANSCRIPTION_PROVIDER)
            
            # Ensure a place in the in-memory store
            interim_transcripts[session_id] = {}
            
            # Inform client that batch mode is ready
            await websocket.send_json({
                "status": "connected",
                "message": "Connected to batch transcription service",
                "streaming": False
            })

        # Main WebSocket processing loop
        while True:
            # Receive message from client
            try:
                message = await websocket.receive()
                
                # Check if this is text or binary message
                if "text" in message:
                    # It's a JSON message
                    message_raw = message["text"]
                    try:
                        data = json.loads(message_raw)
                        
                        # Check if this is a test control message to set the SOAP processor type
                        if "set_soap_processor" in data:
                            soap_processor_type = data["set_soap_processor"]
                            logger.info(f"Session {session_id}: Setting SOAP processor to {soap_processor_type}")
                            await websocket.send_json({
                                "status": "success", 
                                "message": f"SOAP processor set to {soap_processor_type}"
                            })
                            continue
                        
                        # For streaming mode, check if we received a base64 encoded audio
                        if use_streaming and "audio_data" in data:
                            import base64
                            audio_data = data.get("audio_data")
                            audio_bytes = base64.b64decode(audio_data)
                            
                            # Send to the streaming service
                            if stream_service:
                                await stream_service.send_audio(audio_bytes)
                            
                            # Acknowledge receipt (client may or may not need this)
                            await websocket.send_json({
                                "status": "audio_received",
                                "message": "Audio chunk received and processed"
                            })
                            continue
                        
                        # Process as a normal transcription message for batch mode
                        if not use_streaming:
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
                            
                            # Store the interim result with its serial number in legacy in-memory dict
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
                            
                    except json.JSONDecodeError as e:
                        logger.error(f"Session {session_id}: Failed to parse JSON message: {e}")
                        continue
                        
                elif "bytes" in message and use_streaming:
                    # It's binary data for streaming mode
                    audio_bytes = message["bytes"]
                    
                    # Send to the streaming service
                    if stream_service:
                        await stream_service.send_audio(audio_bytes)
                
            except Exception as e:
                logger.error(f"Session {session_id}: Error processing message: {e}")
                await websocket.send_json({
                    "status": "error",
                    "message": f"Error processing message: {str(e)}"
                })

    except WebSocketDisconnect:
        logger.info(f"Session {session_id} disconnected.")
        
        # Clean up streaming resources if necessary
        if session_id in active_streams:
            logger.info(f"Session {session_id}: Cleaning up streaming resources")
            await active_streams[session_id].close()
            del active_streams[session_id]
        
        # Schedule SOAP note generation to run in the background 
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
        
        # Clean up streaming resources if necessary
        if session_id in active_streams:
            try:
                await active_streams[session_id].close()
                del active_streams[session_id]
            except Exception as cleanup_error:
                logger.error(f"Session {session_id}: Error cleaning up streaming resources: {cleanup_error}")
        
        # Also schedule SOAP note generation on error cases
        schedule_soap_note_generation(session_id, provider=soap_processor_type) 