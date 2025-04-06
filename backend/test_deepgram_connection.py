import asyncio
import json
import websockets
import os
import ssl
from dotenv import load_dotenv

# Load environment variables 
load_dotenv()

DEEPGRAM_API_KEY = os.environ.get("DEEPGRAM_API_KEY")

async def test_deepgram_connection():
    """Test direct connection to Deepgram WebSocket API"""
    if not DEEPGRAM_API_KEY:
        print("No Deepgram API key found in environment variables.")
        return
    
    print(f"Testing connection to Deepgram WebSocket API...")
    
    # Construct the WebSocket URL with query parameters
    params = {
        "encoding": "linear16",
        "sample_rate": 16000,
        "channels": 1,
        "language": "en",
        "model": "nova-2",
        "punctuate": True,
        "diarize": True,
        "smart_format": True,
        "interim_results": True,
    }
    
    query_string = "&".join([f"{k}={v}" for k, v in params.items() if not isinstance(v, bool)] + 
                           [f"{k}=true" for k, v in params.items() if v is True])
    uri = f"wss://api.deepgram.com/v1/listen?{query_string}"
    
    print(f"Connecting to: {uri}")
    
    try:
        # Create an SSL context
        ssl_context = ssl.create_default_context()
        
        # Connect using websockets 15.0.1 method
        print("Connecting with websockets 15.0.1 method...")
        connection = await websockets.connect(
            uri,
            additional_headers={"Authorization": f"Token {DEEPGRAM_API_KEY}"},
            ssl=ssl_context
        )
        print("Connection successful!")
        
        # Send a small audio chunk (silent)
        print("Sending a silent audio chunk...")
        silent_chunk = bytes(6400)  # 6400 bytes of zeros (200ms of silence at 16kHz, 16-bit)
        await connection.send(silent_chunk)
        
        # Wait for a response
        print("Waiting for a response...")
        response = await asyncio.wait_for(connection.recv(), timeout=5.0)
        print(f"Received response: {response}")
        
        # Close the connection
        await connection.close()
        print("Connection closed successfully")
        
    except Exception as e:
        print(f"Error connecting to Deepgram: {e}")

if __name__ == "__main__":
    asyncio.run(test_deepgram_connection()) 