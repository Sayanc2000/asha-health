import asyncio
from typing import Dict, Optional, List, Any
from loguru import logger
import sqlalchemy as sa
from sqlalchemy.future import select
import uuid

from .database import async_session
from .models import Transcript, SOAPNote
from .soap_processor import get_soap_processor
from .store.storage import get_transcript_store, TranscriptRecord
from .config import get_settings

# Get application settings
settings = get_settings()

async def process_and_store_soap_note(session_id: str, provider: str = "default") -> SOAPNote:
    """
    Process transcripts for a session and generate a SOAP note.
    
    Args:
        session_id: The session ID to process
        provider: The SOAP processor provider to use
        
    Returns:
        The created SOAPNote object
        
    Raises:
        ValueError: If no transcripts are found for the session
    """
    try:
        # Convert session_id to UUID
        session_uuid = uuid.UUID(session_id)
        
        # 1. Retrieve transcript text using the in-memory store first
        transcript_store = get_transcript_store()
        transcript_records = await transcript_store.get_transcripts_for_session(session_id)
        
        # If no transcripts in memory, try the database
        if not transcript_records:
            logger.info(f"No transcripts found in memory for session {session_id}, checking database")
            async with async_session() as session:
                result = await session.execute(
                    select(Transcript)
                    .filter(Transcript.session_id == session_uuid)
                    .order_by(Transcript.serial)
                )
                db_transcripts = result.scalars().all()
                
                if not db_transcripts:
                    logger.error(f"No transcripts found for session {session_id}")
                    raise ValueError(f"No transcripts found for session {session_id}")
                
                # Convert DB transcripts to text
                transcript_text = "\n".join([t.transcript for t in db_transcripts])
        else:
            # Order transcripts by serial number and convert to text
            transcript_text = "\n".join([record.transcript for record in transcript_records])
        
        if not transcript_text:
            logger.error(f"Empty transcript text for session {session_id}")
            raise ValueError(f"Empty transcript text for session {session_id}")
            
        logger.info(f"Retrieved transcripts for session {session_id}, generating SOAP note")
        
        # 2. Generate SOAP note using the SOAP processor
        soap_processor = get_soap_processor(
            provider=provider,
            endpoint=settings.SOAP_API_ENDPOINT,
            api_key=settings.SOAP_API_KEY
        )
        try:
            soap_text = await soap_processor.process(transcript_text)
        except Exception as e:
            logger.error(f"Failed to generate SOAP note for session {session_id}: {e}")
            raise
        
        # 3. Store the SOAP note in the database
        async with async_session() as session:
            new_soap = SOAPNote(
                session_id=session_uuid,
                soap_text=soap_text
            )
            session.add(new_soap)
            await session.commit()
            await session.refresh(new_soap)
            
        logger.info(f"Stored SOAP note for session {session_id}")
        return new_soap
    except ValueError as e:
        if "invalid literal for UUID" in str(e):
            logger.error(f"Invalid session ID format: {session_id}")
        raise


async def get_soap_note_for_session(session_id: str) -> Optional[SOAPNote]:
    """
    Retrieve the SOAP note for a given session.
    
    Args:
        session_id: The session ID to retrieve the SOAP note for
        
    Returns:
        The SOAPNote object if found, None otherwise
    """
    try:
        # Convert session_id to UUID
        session_uuid = uuid.UUID(session_id)
        
        async with async_session() as session:
            result = await session.execute(
                select(SOAPNote)
                .filter(SOAPNote.session_id == session_uuid)
                .order_by(SOAPNote.created_at.desc())
            )
            soap_note = result.scalars().first()
            
        return soap_note
    except ValueError as e:
        logger.error(f"Invalid session ID format in get_soap_note_for_session: {session_id}, {e}")
        return None


async def generate_soap_note_background(session_id: str, provider: str = "default"):
    """
    Generate a SOAP note for a session in the background.
    This function is designed to be run as an asyncio task.
    
    Args:
        session_id: The session ID to generate a SOAP note for
        provider: The SOAP processor provider to use
    """
    try:
        logger.info(f"Starting background SOAP note generation for session {session_id}")
        await process_and_store_soap_note(session_id, provider=provider)
        logger.info(f"Completed background SOAP note generation for session {session_id}")
    except Exception as e:
        logger.error(f"Background SOAP note generation failed for session {session_id}: {e}")


def schedule_soap_note_generation(session_id: str, provider: str = "default"):
    """
    Schedule a SOAP note generation task to run in the background.
    
    Args:
        session_id: The session ID to generate a SOAP note for
        provider: The SOAP processor provider to use
    """
    asyncio.create_task(
        generate_soap_note_background(session_id, provider)
    ) 