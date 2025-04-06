import asyncio
import base64
import sys
import os
from pathlib import Path
import httpx
from loguru import logger

# Add the parent directory to sys.path if running tests directly
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent))

# Configure logger
logger.add(Path(__file__).parent.parent / "api_test.log", rotation="1 MB")

async def test_transcription_api():
    # Load the chunked audio file
    chunk_path = Path(__file__).parent.parent / "audio_chunk_10s.wav"
    
    try:
        # Read the file and convert to base64
        with open(chunk_path, "rb") as f:
            audio_bytes = f.read()
            audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")
        
        # API endpoint
        url = "http://localhost:8000/api/transcribe"
        
        # Prepare request payload
        payload = {
            "audio_data": audio_base64,
            "provider": "deepgram"
        }
        
        logger.info("Sending audio to API endpoint for transcription...")
        
        # Send POST request to the API
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, timeout=30.0)
            
            # Log response information
            logger.info(f"Response status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                transcript = result.get("transcript", "")
                
                logger.info(f"Transcription result: {transcript}")
                print("\n" + "-"*50)
                print("API TRANSCRIPTION RESULT:")
                print(transcript)
                print("-"*50 + "\n")
                return transcript
            else:
                error_msg = f"API error: {response.status_code} - {response.text}"
                logger.error(error_msg)
                print("\n" + "-"*50)
                print("API ERROR:")
                print(error_msg)
                print("-"*50 + "\n")
                return error_msg
                
    except Exception as e:
        error_msg = f"Error testing API: {str(e)}"
        logger.exception(error_msg)
        print("\n" + "-"*50)
        print("ERROR:")
        print(error_msg)
        print("-"*50 + "\n")
        return error_msg

if __name__ == "__main__":
    # Run the async function
    result = asyncio.run(test_transcription_api()) 