import asyncio
import json
import websockets
import os
import base64
import sys
import time
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def test_streaming_transcription(session_id, audio_file_path):
    """
    Test the streaming transcription by sending audio chunks to the WebSocket server.
    
    Args:
        session_id: The session ID to use
        audio_file_path: Path to the audio file to send
    """
    # Read the audio file
    with open(audio_file_path, "rb") as f:
        audio_data = f.read()
    
    # Connect to the WebSocket server
    uri = f"ws://localhost:8000/ws/{session_id}"
    print(f"Connecting to {uri}...")
    
    async with websockets.connect(uri) as websocket:
        # Receive the initial connection message
        response = await websocket.recv()
        print(f"Connection response: {response}")
        
        # Define chunk size (e.g., 0.2 seconds of audio at 16kHz mono 16-bit = 6,400 bytes)
        # Adjust this based on your audio format and desired latency
        chunk_size = 6400
        
        # Calculate number of chunks
        num_chunks = len(audio_data) // chunk_size
        
        print(f"Sending {num_chunks} chunks from {audio_file_path} ({len(audio_data)} bytes)...")
        
        # Send audio data in chunks
        for i in range(num_chunks):
            # Extract chunk
            start = i * chunk_size
            end = start + chunk_size
            chunk = audio_data[start:end]
            
            # Send as binary if the server accepts raw PCM
            await websocket.send(chunk)
            
            # Or send as base64 in JSON (uncomment if your server expects this format)
            # chunk_base64 = base64.b64encode(chunk).decode("utf-8")
            # message = json.dumps({"audio_data": chunk_base64})
            # await websocket.send(message)
            
            # Sleep to simulate real-time audio (adjust based on your chunk size)
            await asyncio.sleep(0.1)  # 100ms between chunks
            
            # Process any incoming messages
            while websocket.messages:
                response = await websocket.recv()
                print(f"Received: {json.loads(response)}")
        
        # Wait for final results
        print("Finished sending audio, waiting for final results...")
        for _ in range(5):  # Wait for up to 5 seconds for final results
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                print(f"Received: {json.loads(response)}")
            except asyncio.TimeoutError:
                pass
            
        print("Test completed.")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python test_stream.py <session_id> <audio_file_path>")
        sys.exit(1)
    
    session_id = sys.argv[1]
    audio_file_path = sys.argv[2]
    
    # Run the test
    asyncio.run(test_streaming_transcription(session_id, audio_file_path)) 