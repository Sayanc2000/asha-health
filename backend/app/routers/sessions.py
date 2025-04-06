import uuid
from typing import List
from fastapi import APIRouter, HTTPException
from loguru import logger
import sqlalchemy as sa

from app.database import async_session
from app.models import Session, Transcript, SOAPNote
from app.schemas import (
    SessionRequest, 
    SessionResponse, 
    SessionInfo, 
    SessionDetailResponse, 
    SessionUpdateRequest
)

# Create router
router = APIRouter(
    prefix="/api/sessions",
    tags=["sessions"],
)


@router.get("", response_model=List[SessionInfo])
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


@router.get("/{session_id}")
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


@router.post("", response_model=SessionResponse)
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


@router.get("/{session_id}/details", response_model=SessionDetailResponse)
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


@router.put("/{session_id}", response_model=SessionResponse)
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