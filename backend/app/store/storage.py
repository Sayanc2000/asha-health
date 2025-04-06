import asyncio
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from loguru import logger
import json

@dataclass
class TranscriptSegment:
    """Data class to hold segment information from transcript."""
    id: int
    start: float
    end: float
    text: str
    speaker: str = "SPEAKER_00"

@dataclass
class TranscriptRecord:
    """Data class to hold transcript information."""
    session_id: str
    serial: int
    transcript: str  # Full text
    segments: List[TranscriptSegment] = field(default_factory=list)
    speakers: List[str] = field(default_factory=lambda: ["SPEAKER_00"])
    created_at: datetime = None
    status: str = "pending"
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()


class InMemoryTranscriptionStore:
    """
    A thread-safe in-memory store for transcriptions.
    Provides operations to add, query, and mark transcripts as dispatched.
    """
    
    def __init__(self):
        # Main storage: {session_id: {serial: TranscriptRecord}}
        self._transcripts: Dict[str, Dict[int, TranscriptRecord]] = {}
        self._lock = asyncio.Lock()
        
    async def add_transcript(
        self, 
        session_id: str, 
        serial: int, 
        transcript_data: Dict[str, Any]
    ) -> TranscriptRecord:
        """
        Add a transcript to the in-memory store.
        
        Args:
            session_id: Unique identifier for the transcription session
            serial: Sequential number for the transcript within the session
            transcript_data: Dictionary containing transcript text, segments and speakers
            
        Returns:
            The created TranscriptRecord
        """
        # Extract text from transcript data
        text = transcript_data.get("text", "")
        
        # Extract and convert segments to TranscriptSegment objects
        segments = []
        for segment_data in transcript_data.get("segments", []):
            segment = TranscriptSegment(
                id=segment_data.get("id", 0),
                start=segment_data.get("start", 0.0),
                end=segment_data.get("end", 0.0),
                text=segment_data.get("text", ""),
                speaker=segment_data.get("speaker", "SPEAKER_00")
            )
            segments.append(segment)
        
        # Extract speakers
        speakers = transcript_data.get("speakers", ["SPEAKER_00"])
        
        # Create the record
        record = TranscriptRecord(
            session_id=session_id,
            serial=serial,
            transcript=text,
            segments=segments,
            speakers=speakers
        )
        
        async with self._lock:
            # Create session dict if it doesn't exist
            if session_id not in self._transcripts:
                self._transcripts[session_id] = {}
            
            # Add the transcript to the session
            self._transcripts[session_id][serial] = record
            
        logger.debug(f"Added transcript to in-memory store: session={session_id}, serial={serial}")
        return record
    
    async def get_pending_transcripts(self, limit: int = 100) -> List[TranscriptRecord]:
        """
        Retrieve all transcripts with 'pending' status, up to the specified limit.
        
        Args:
            limit: Maximum number of transcripts to return
            
        Returns:
            List of pending TranscriptRecord objects
        """
        pending_records = []
        
        async with self._lock:
            for session_dict in self._transcripts.values():
                for record in session_dict.values():
                    if record.status == "pending":
                        pending_records.append(record)
                        if len(pending_records) >= limit:
                            break
                if len(pending_records) >= limit:
                    break
                    
        return pending_records
    
    async def mark_as_dispatched(self, session_id: str, serial: int) -> bool:
        """
        Mark a transcript as dispatched.
        
        Args:
            session_id: Session identifier
            serial: Serial number of the transcript
            
        Returns:
            True if the transcript was found and marked, False otherwise
        """
        async with self._lock:
            if session_id in self._transcripts and serial in self._transcripts[session_id]:
                self._transcripts[session_id][serial].status = "dispatched"
                logger.debug(f"Marked transcript as dispatched: session={session_id}, serial={serial}")
                return True
            return False
    
    async def remove_transcript(self, session_id: str, serial: int) -> bool:
        """
        Remove a transcript from the store.
        
        Args:
            session_id: Session identifier
            serial: Serial number of the transcript
            
        Returns:
            True if the transcript was found and removed, False otherwise
        """
        async with self._lock:
            if session_id in self._transcripts and serial in self._transcripts[session_id]:
                del self._transcripts[session_id][serial]
                # Clean up empty session
                if not self._transcripts[session_id]:
                    del self._transcripts[session_id]
                logger.debug(f"Removed transcript from store: session={session_id}, serial={serial}")
                return True
            return False
    
    async def get_transcripts_for_session(self, session_id: str) -> List[TranscriptRecord]:
        """
        Get all transcripts for a specific session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            List of TranscriptRecord objects for the session
        """
        async with self._lock:
            if session_id not in self._transcripts:
                return []
            
            # Return a sorted list of transcripts by serial number
            return sorted(
                list(self._transcripts[session_id].values()),
                key=lambda record: record.serial
            )
    
    async def purge_old_transcripts(self, max_age_seconds: int = 3600) -> int:
        """
        Remove transcripts older than the specified age.
        
        Args:
            max_age_seconds: Maximum age in seconds for transcripts to keep
            
        Returns:
            Number of transcripts removed
        """
        now = datetime.utcnow()
        removed_count = 0
        
        async with self._lock:
            for session_id in list(self._transcripts.keys()):
                for serial in list(self._transcripts[session_id].keys()):
                    record = self._transcripts[session_id][serial]
                    age = (now - record.created_at).total_seconds()
                    
                    if age > max_age_seconds:
                        del self._transcripts[session_id][serial]
                        removed_count += 1
                
                # Clean up empty session
                if not self._transcripts[session_id]:
                    del self._transcripts[session_id]
                    
        if removed_count > 0:
            logger.info(f"Purged {removed_count} old transcripts from in-memory store")
            
        return removed_count


# Singleton instance for global access
_transcript_store = InMemoryTranscriptionStore()

def get_transcript_store() -> InMemoryTranscriptionStore:
    """
    Get the global instance of the in-memory transcript store.
    """
    return _transcript_store 