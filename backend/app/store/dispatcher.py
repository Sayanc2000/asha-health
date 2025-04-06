import asyncio
import time
from typing import List, Optional, Dict, Any
from datetime import datetime
from loguru import logger
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
import json

from app.models import Transcript, async_session
from .storage import TranscriptRecord, TranscriptSegment, get_transcript_store


class TranscriptDispatcher:
    """
    A service that periodically dispatches transcripts from the in-memory store 
    to the database in batches.
    """
    
    def __init__(
        self,
        interval_seconds: int = 5,
        batch_size: int = 3,
        max_retries: int = 3,
        retry_delay_seconds: int = 1,
    ):
        self.interval_seconds = interval_seconds
        self.batch_size = batch_size
        self.max_retries = max_retries
        self.retry_delay_seconds = retry_delay_seconds
        self.running = False
        self.task = None
    
    async def start(self):
        """Start the dispatcher as a background task."""
        if self.running:
            logger.warning("Dispatcher is already running")
            return
        
        self.running = True
        self.task = asyncio.create_task(self._dispatch_loop())
        logger.info(f"Transcript dispatcher started (interval={self.interval_seconds}s, batch_size={self.batch_size})")
    
    async def stop(self):
        """Stop the dispatcher gracefully."""
        if not self.running:
            logger.warning("Dispatcher is not running")
            return
        
        self.running = False
        if self.task:
            try:
                await self.task
                self.task = None
                logger.info("Transcript dispatcher stopped gracefully")
            except asyncio.CancelledError:
                logger.warning("Transcript dispatcher was cancelled")
    
    async def _dispatch_loop(self):
        """Main loop that periodically dispatches pending transcripts."""
        try:
            while self.running:
                await self._process_batch()
                # Wait before processing the next batch
                await asyncio.sleep(self.interval_seconds)
        except Exception as e:
            logger.exception(f"Error in transcript dispatcher loop: {str(e)}")
            self.running = False
    
    async def _process_batch(self):
        """Process a batch of pending transcripts."""
        # Get the in-memory store
        store = get_transcript_store()
        
        # Retrieve pending transcripts up to batch size
        pending_transcripts = await store.get_pending_transcripts(limit=self.batch_size)
        
        if not pending_transcripts:
            return  # Nothing to process
        
        logger.info(f"Dispatching {len(pending_transcripts)} transcripts to database")
        
        # Process the batch with retries
        for retry in range(self.max_retries):
            try:
                await self._save_to_database(pending_transcripts)
                
                # Mark all transcripts as dispatched in the in-memory store
                for record in pending_transcripts:
                    await store.mark_as_dispatched(record.session_id, record.serial)
                
                logger.info(f"Successfully dispatched {len(pending_transcripts)} transcripts to database")
                break  # Success, exit retry loop
                
            except Exception as e:
                logger.error(f"Failed to dispatch transcripts (attempt {retry+1}/{self.max_retries}): {str(e)}")
                
                if retry < self.max_retries - 1:
                    # Exponential backoff for retries
                    wait_time = self.retry_delay_seconds * (2 ** retry)
                    logger.info(f"Retrying in {wait_time} seconds...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error("Max retries reached, giving up on this batch")
    
    async def _save_to_database(self, records: List[TranscriptRecord]):
        """
        Save a batch of transcript records to the database.
        
        Args:
            records: List of TranscriptRecord objects to save
        """
        async with async_session() as session:
            async with session.begin():
                # Create a list of Transcript model instances
                db_transcripts = []
                
                for record in records:
                    # Get primary speaker if multiple segments with different speakers
                    primary_speaker = "SPEAKER_00"
                    if record.segments:
                        # Count occurrences of each speaker
                        speaker_counts = {}
                        for segment in record.segments:
                            speaker_counts[segment.speaker] = speaker_counts.get(segment.speaker, 0) + 1
                        # Get the most common speaker
                        primary_speaker = max(speaker_counts.items(), key=lambda x: x[1])[0]
                    
                    # Create DB model instance
                    transcript = Transcript(
                        session_id=record.session_id,
                        serial=record.serial,
                        transcript=record.transcript,
                        speaker=primary_speaker,
                        created_at=record.created_at
                    )
                    db_transcripts.append(transcript)
                
                # Add all transcripts to the session
                session.add_all(db_transcripts)
                
                # Commit happens automatically at the end of the context manager


# Singleton instance
_dispatcher = TranscriptDispatcher()

def get_dispatcher() -> TranscriptDispatcher:
    """
    Get the global instance of the transcript dispatcher.
    """
    return _dispatcher

async def start_dispatcher():
    """Start the global transcript dispatcher."""
    dispatcher = get_dispatcher()
    await dispatcher.start()

async def stop_dispatcher():
    """Stop the global transcript dispatcher."""
    dispatcher = get_dispatcher()
    await dispatcher.stop() 