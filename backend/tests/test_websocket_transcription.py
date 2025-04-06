#!/usr/bin/env python3
"""
WebSocket Transcription Test Script

This script tests the end-to-end functionality of the Asha Transcription Service by:
1. Loading an audio file
2. Splitting it into 5-second chunks
3. Sending each chunk to the WebSocket endpoint
4. Tracking the transcription results
5. Verifying data in the database afterward
6. Checking for SOAP note generation after WebSocket closes

Usage:
    poetry run python -m tests.test_websocket_transcription
"""

import asyncio
import sys
import os
import json
import uuid
import base64
import time
from pathlib import Path
import sqlalchemy as sa
import websockets
from pydub import AudioSegment
from loguru import logger
import httpx

# Set environment variables for testing
os.environ["SOAP_API_KEY"] = "test-soap-api-key"
os.environ["SOAP_API_ENDPOINT"] = "https://test-api.example.com/soap"

# Add the parent directory to sys.path if running tests directly
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent))

from app.models import Transcript, SOAPNote, async_session

# Configuration
WEBSOCKET_URL = "ws://localhost:8000/ws/"
API_BASE_URL = "http://localhost:8000/api"
AUDIO_PATH = Path(__file__).parent.parent / "aws-bp-30 (1).mp3"
CHUNK_LENGTH_MS = 5000  # 5 seconds per chunk
MAX_DURATION_MS = 20000  # Process the first 20 seconds of audio
LOG_FILE = Path(__file__).parent.parent / "websocket_test.log"
# Time to wait for background SOAP note generation after WebSocket closes
SOAP_GENERATION_WAIT_TIME = 10  # seconds

# Configure logger
logger.remove()  # Remove default handlers
logger.add(LOG_FILE, rotation="1 MB", level="INFO")
logger.add(sys.stdout, level="INFO")  # Also log to console

async def chunk_audio(audio_path: Path, chunk_length_ms: int, max_duration_ms: int):
    """
    Load an audio file and split it into chunks of specified length.
    
    Args:
        audio_path: Path to the audio file
        chunk_length_ms: Length of each chunk in milliseconds
        max_duration_ms: Maximum duration to process from the start
        
    Returns:
        List of (chunk_number, base64_encoded_audio_data) tuples
    """
    logger.info(f"Loading audio file: {audio_path}")
    
    # Load the audio file
    audio = AudioSegment.from_mp3(audio_path)
    
    # Calculate the number of chunks
    duration_ms = min(len(audio), max_duration_ms)
    num_chunks = (duration_ms + chunk_length_ms - 1) // chunk_length_ms
    
    logger.info(f"Processing {duration_ms/1000:.1f} seconds of audio in {num_chunks} chunks")
    
    # Create chunks
    chunks = []
    for i in range(num_chunks):
        chunk_start = i * chunk_length_ms
        chunk_end = min(chunk_start + chunk_length_ms, duration_ms)
        
        # Extract the chunk
        audio_chunk = audio[chunk_start:chunk_end]
        
        # Export to in-memory WAV
        wav_data = audio_chunk.export(format="wav").read()
        
        # Base64 encode the WAV data
        base64_data = base64.b64encode(wav_data).decode("utf-8")
        
        # Add to list of chunks with chunk number (serial)
        chunks.append((i + 1, base64_data))
        
        logger.debug(f"Created chunk {i+1}: {chunk_start/1000:.1f}s - {chunk_end/1000:.1f}s")
    
    return chunks

async def send_chunks_to_websocket(session_id: str, chunks):
    """
    Send audio chunks to the WebSocket endpoint.
    
    Args:
        session_id: Session identifier
        chunks: List of (chunk_number, base64_encoded_audio_data) tuples
    
    Returns:
        Dictionary of transcription results by chunk number
    """
    websocket_url = f"{WEBSOCKET_URL}{session_id}"
    logger.info(f"Connecting to WebSocket: {websocket_url}")
    
    results = {}
    
    try:
        async with websockets.connect(websocket_url) as websocket:
            logger.info(f"Connected to session {session_id}")
            
            # Tell the server to use the "mock" SOAP processor for testing
            await websocket.send(json.dumps({
                "set_soap_processor": "mock"
            }))
            
            for serial, audio_data in chunks:
                # Prepare the message
                message = {
                    "serial": serial,
                    "audio_data": audio_data,
                    # Using default provider from server settings
                }
                
                # Send the chunk
                logger.info(f"Sending chunk {serial} to server...")
                await websocket.send(json.dumps(message))
                
                # Wait for the response
                response = await websocket.recv()
                response_data = json.loads(response)
                
                if response_data.get("status") == "success":
                    transcript = response_data.get("transcript", "")
                    logger.info(f"Received transcript for chunk {serial}: {transcript[:50]}...")
                    results[serial] = transcript
                else:
                    logger.error(f"Error processing chunk {serial}: {response_data}")
                
                # Brief pause to avoid overloading
                await asyncio.sleep(0.1)
        
        logger.info(f"WebSocket connection closed normally for session {session_id}")
        logger.info(f"Waiting {SOAP_GENERATION_WAIT_TIME} seconds for background SOAP note generation...")
        
        # Wait for the background SOAP note generation to complete
        await asyncio.sleep(SOAP_GENERATION_WAIT_TIME)
                
    except Exception as e:
        logger.exception(f"WebSocket error: {e}")
    
    return results

async def verify_database_records(session_id: str, expected_chunk_count: int):
    """
    Verify that transcripts were properly stored in the database.
    
    Args:
        session_id: Session identifier
        expected_chunk_count: Expected number of chunks
        
    Returns:
        Dictionary of database records by serial number
    """
    logger.info(f"Verifying database records for session {session_id}...")
    
    # Wait a moment to allow dispatcher to finish processing
    await asyncio.sleep(6)  # Giving the dispatcher time to process
    
    try:
        async with async_session() as session:
            # Query the database for transcripts from this session
            result = await session.execute(
                sa.select(Transcript)
                .where(Transcript.session_id == session_id)
                .order_by(Transcript.serial)
            )
            db_records = result.scalars().all()
            
        logger.info(f"Found {len(db_records)} records in database out of {expected_chunk_count} expected")
        
        # Convert to dictionary by serial number
        db_transcripts = {record.serial: record.transcript for record in db_records}
        
        # Check if we got all the expected records
        missing_serials = [i for i in range(1, expected_chunk_count + 1) if i not in db_transcripts]
        if missing_serials:
            logger.warning(f"Missing {len(missing_serials)} records in database: {missing_serials}")
        
        return db_transcripts
    
    except Exception as e:
        logger.exception(f"Database verification error: {e}")
        return {}

async def check_soap_note_generation(session_id: str):
    """
    Check if a SOAP note was generated for the session.
    
    This function uses both the REST API and direct database access to check.
    
    Args:
        session_id: Session identifier
        
    Returns:
        Tuple of (soap_note_exists, soap_note_text)
    """
    logger.info(f"Checking for SOAP note generation for session {session_id}...")
    
    # First try the REST API
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{API_BASE_URL}/sessions/{session_id}/soap")
            
            if response.status_code == 200:
                soap_data = response.json()
                logger.info(f"SOAP note found via API for session {session_id}")
                return True, soap_data.get("soap_text", "")
            else:
                logger.warning(f"No SOAP note found via API for session {session_id}: {response.status_code}")
    except Exception as e:
        logger.error(f"Error checking SOAP note via API: {e}")
    
    # If API check failed, try direct database access
    try:
        async with async_session() as session:
            result = await session.execute(
                sa.select(SOAPNote)
                .where(SOAPNote.session_id == session_id)
                .order_by(SOAPNote.created_at.desc())
            )
            soap_note = result.scalars().first()
            
            if soap_note:
                logger.info(f"SOAP note found in database for session {session_id}")
                return True, soap_note.soap_text
            else:
                logger.warning(f"No SOAP note found in database for session {session_id}")
                return False, ""
    except Exception as e:
        logger.exception(f"Database SOAP note check error: {e}")
        return False, ""

async def main():
    """Main test function."""
    logger.info("Starting WebSocket transcription test")
    
    # Generate a unique session ID
    session_id = str(uuid.uuid4())
    logger.info(f"Test session ID: {session_id}")
    
    try:
        # Step 1: Split the audio into chunks
        chunks = await chunk_audio(AUDIO_PATH, CHUNK_LENGTH_MS, MAX_DURATION_MS)
        
        # Step 2: Send chunks to the WebSocket
        start_time = time.time()
        websocket_results = await send_chunks_to_websocket(session_id, chunks)
        elapsed_time = time.time() - start_time
        logger.info(f"WebSocket processing completed in {elapsed_time:.2f} seconds")
        
        # Step 3: Verify database records
        db_transcripts = await verify_database_records(session_id, len(chunks))
        
        # Step 4: Check for SOAP note generation
        soap_generated, soap_text = await check_soap_note_generation(session_id)
        
        # Step 5: Report results
        logger.info("\n" + "="*50)
        logger.info(f"TEST SUMMARY for session {session_id}")
        logger.info("="*50)
        logger.info(f"Total chunks processed: {len(chunks)}")
        logger.info(f"WebSocket responses received: {len(websocket_results)}")
        logger.info(f"Database records found: {len(db_transcripts)}")
        logger.info(f"SOAP note generated: {soap_generated}")
        
        if len(db_transcripts) == len(chunks):
            logger.info("SUCCESS: All transcripts were successfully stored in the database")
        else:
            logger.warning(f"PARTIAL SUCCESS: {len(db_transcripts)}/{len(chunks)} transcripts stored in database")
        
        if soap_generated:
            logger.info("SUCCESS: SOAP note was generated after WebSocket closed")
            # Display a snippet of the SOAP note
            logger.info(f"SOAP note preview: {soap_text[:200]}...")
        else:
            logger.warning("FAILURE: No SOAP note was generated after WebSocket closed")
        
        # Display a few example transcripts
        sample_count = min(3, len(db_transcripts))
        if sample_count > 0:
            logger.info("\nSample transcripts from database:")
            for serial in sorted(list(db_transcripts.keys()))[:sample_count]:
                logger.info(f"Chunk {serial}: {db_transcripts[serial][:100]}...")
        
        logger.info("="*50)
        logger.info("Test completed")
        
    except Exception as e:
        logger.exception(f"Test failed: {e}")

if __name__ == "__main__":
    asyncio.run(main()) 