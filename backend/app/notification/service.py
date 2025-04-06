import json
from loguru import logger
from .sse_manager import sse_manager # Import the singleton instance

async def send_soap_notification(session_id: str, status: str, message: str):
    """Formats and sends a SOAP processing status notification."""
    payload = {
        "type": "soap_update",
        "session_id": session_id,
        "status": status, # e.g., "processing", "completed", "failed"
        "message": message
    }
    json_payload = json.dumps(payload)
    logger.info(f"Sending SOAP notification for session {session_id}: Status - {status}")
    # Use session_id as the client_id for targeting specific frontend instances
    await sse_manager.send(session_id, json_payload)

async def send_heartbeat(session_id: str):
    """Sends a heartbeat notification to confirm the connection is active."""
    payload = {
        "type": "heartbeat",
        "session_id": session_id,
        "status": "connected",
        "message": "Connection established"
    }
    json_payload = json.dumps(payload)
    logger.info(f"Sending heartbeat notification for session {session_id}")
    await sse_manager.send(session_id, json_payload)

# Add other notification functions here if needed in the future
# async def send_transcription_notification(...) 