"""
Test script for the in-memory transcription store and dispatcher.
"""
import asyncio
import sys
import os
from pathlib import Path

# Add the parent directory to sys.path if running tests directly
# This ensures imports work correctly when running the test file directly
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent))

from app.store.storage import get_transcript_store
from app.store.dispatcher import get_dispatcher

async def test_in_memory_store():
    """Test the in-memory transcript store functionality."""
    print("\n=== Testing In-Memory Transcript Store ===")
    
    # Get the store instance
    store = get_transcript_store()
    
    # Add some test transcripts
    await store.add_transcript('test_session', 1, 'Test transcript 1')
    await store.add_transcript('test_session', 2, 'Test transcript 2')
    await store.add_transcript('another_session', 1, 'Another session transcript')
    
    # Get pending transcripts
    pending = await store.get_pending_transcripts()
    print(f'Added {len(pending)} transcripts: {[r.transcript for r in pending]}')
    
    # Get session transcripts
    session_transcripts = await store.get_transcripts_for_session('test_session')
    print(f'Session transcripts: {[r.transcript for r in session_transcripts]}')
    
    # Mark one as dispatched
    await store.mark_as_dispatched('test_session', 1)
    
    # Check pending again
    pending = await store.get_pending_transcripts()
    print(f'After marking as dispatched: {len(pending)} pending transcripts remaining')
    
    # Get all transcripts for the session (including dispatched)
    session_transcripts = await store.get_transcripts_for_session('test_session')
    for record in session_transcripts:
        print(f'Serial: {record.serial}, Status: {record.status}, Text: {record.transcript}')
    
    return True

async def test_dispatcher():
    """Test the transcript dispatcher functionality."""
    print("\n=== Testing Transcript Dispatcher ===")
    
    # Get the dispatcher instance
    dispatcher = get_dispatcher()
    
    # Configure it for faster testing
    dispatcher.interval_seconds = 2
    dispatcher.batch_size = 5
    
    # Start the dispatcher
    print("Starting dispatcher...")
    await dispatcher.start()
    
    # Wait a moment for the dispatcher to process
    print("Waiting for dispatcher to process...")
    await asyncio.sleep(3)
    
    # Check if any transcripts were dispatched
    store = get_transcript_store()
    pending = await store.get_pending_transcripts()
    print(f'Pending transcripts after dispatcher run: {len(pending)}')
    
    # Stop the dispatcher
    print("Stopping dispatcher...")
    await dispatcher.stop()
    
    return True

async def main():
    """Run all tests."""
    await test_in_memory_store()
    await test_dispatcher()
    print("\nAll tests completed!")

if __name__ == "__main__":
    asyncio.run(main()) 