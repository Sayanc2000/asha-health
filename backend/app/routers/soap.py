import uuid
from fastapi import APIRouter, HTTPException
from loguru import logger

from app.database import async_session
from app.models import Session
from app.soap_service import process_and_store_soap_note, get_soap_note_for_session
from app.schemas import SOAPNoteRequest, SOAPNoteResponse

# Create router
router = APIRouter(
    prefix="/api/sessions",
    tags=["soap"],
)


@router.post("/{session_id}/soap", response_model=SOAPNoteResponse)
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
            import sqlalchemy as sa
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


@router.get("/{session_id}/soap", response_model=SOAPNoteResponse)
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
            import sqlalchemy as sa
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