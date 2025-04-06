#!/usr/bin/env python3
"""
Simple test client for the Asha Transcription Service WebSocket API.

Usage:
    poetry run python -m tests.test_client
"""

import asyncio
import json
import uuid
import base64
import sys
import os
from pathlib import Path
import websockets

# Add the parent directory to sys.path if running tests directly
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent))

# Configuration
SERVER_URL = "ws://localhost:8000/ws/"
TEST_AUDIO = "SGVsbG8gd29ybGQsIHRoaXMgaXMgYSB0ZXN0IGF1ZGlvIHNhbXBsZQ=="  # Base64 encoded dummy text


async def test_websocket():
    """Test the WebSocket API."""
    # Generate a random session ID
    session_id = str(uuid.uuid4())
    
    # Connect to WebSocket
    print(f"Connecting to session {session_id}...")
    async with websockets.connect(f"{SERVER_URL}{session_id}") as websocket:
        print("Connected!")
        
        # Send 5 audio chunks
        for i in range(1, 6):
            # Prepare the message
            message = {
                "serial": i,
                "audio_data": TEST_AUDIO,
                "provider": "dummy"  # Use dummy provider for testing
            }
            
            # Send the message
            print(f"Sending chunk {i}...")
            await websocket.send(json.dumps(message))
            
            # Receive the response
            response = await websocket.recv()
            response_data = json.loads(response)
            print(f"Received response for chunk {i}: {response_data}")
            
            # Wait a bit between messages
            await asyncio.sleep(1)
        
        print("Test completed!")


if __name__ == "__main__":
    asyncio.run(test_websocket()) 