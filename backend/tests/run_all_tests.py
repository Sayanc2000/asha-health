#!/usr/bin/env python3
"""
Main test runner for the Asha Transcription API.
This script runs all the tests in the tests directory.
"""

import asyncio
import sys
import os
from pathlib import Path

# Add the parent directory to sys.path if running tests directly
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.test_store import test_in_memory_store, test_dispatcher
from tests.test_client import test_websocket
# Optional: we don't run these by default as they require audio files and API keys
# from tests.test_api_endpoint import test_transcription_api
# from tests.chunk_and_test import chunk_audio_and_test

async def run_all_tests():
    """Run all the tests sequentially."""
    print("\n" + "="*50)
    print("RUNNING ALL TESTS")
    print("="*50)
    
    # Test the in-memory store
    print("\nRunning in-memory store tests...")
    await test_in_memory_store()
    
    # Test the dispatcher
    print("\nRunning dispatcher tests...")
    await test_dispatcher()
    
    # Test the WebSocket API (uncomment if you have the server running)
    try:
        print("\nRunning WebSocket API tests...")
        print("(This test requires the server to be running)")
        print("If you don't have the server running, press Ctrl+C to skip")
        await asyncio.wait_for(test_websocket(), timeout=15)
    except (asyncio.TimeoutError, KeyboardInterrupt, ConnectionRefusedError):
        print("WebSocket test skipped or timed out.")
    
    # These tests are optional and not run by default as they require audio files and API keys
    # print("\nRunning API transcription test...")
    # await test_transcription_api()
    
    # print("\nRunning audio chunking and transcription test...")
    # await chunk_audio_and_test()
    
    print("\n" + "="*50)
    print("ALL TESTS COMPLETED")
    print("="*50 + "\n")

if __name__ == "__main__":
    asyncio.run(run_all_tests()) 