import asyncio
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse
from loguru import logger
from ..notification.sse_manager import sse_manager # Import the singleton instance
from ..notification.service import send_heartbeat

router = APIRouter(
    prefix="/notifications",
    tags=["notifications"],
)

async def event_generator(request: Request, client_id: str, queue: asyncio.Queue):
    """Yields messages from the client's queue as SSE events."""
    try:
        # Send an immediate heartbeat to confirm the connection is established
        await send_heartbeat(client_id)
        
        while True:
            # Check if client is still connected before waiting
            if await request.is_disconnected():
                logger.warning(f"Client {client_id} disconnected before message send.")
                break

            message = await queue.get()
            yield f"data: {message}\n\n" # SSE format: "data: <json_string>\n\n"
            queue.task_done() # Indicate message processing is complete
            logger.debug(f"Sent message to client {client_id}")

    except asyncio.CancelledError:
        logger.info(f"Event generator cancelled for client {client_id}.")
    finally:
        # Clean up connection on generator exit/cancellation
        await sse_manager.disconnect(client_id)


@router.get("/sse/{session_id}")
async def sse_endpoint(request: Request, session_id: str):
    """Endpoint for clients to establish SSE connections."""
    logger.info(f"SSE connection request for session_id: {session_id}")
    try:
        queue = await sse_manager.connect(session_id)
    except Exception as e:
        logger.error(f"Failed to connect SSE client {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Could not establish SSE connection")

    return StreamingResponse(
        event_generator(request, session_id, queue),
        media_type="text/event-stream",
        headers={
            'Cache-Control': 'no-cache', 
            'Connection': 'keep-alive', 
            'X-Accel-Buffering': 'no'
        } # Disable buffering
    ) 