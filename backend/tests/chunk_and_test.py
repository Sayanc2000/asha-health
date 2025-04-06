import os
import base64
import json
import sys
from pathlib import Path
from pydub import AudioSegment
import httpx
import asyncio
from loguru import logger

# Add the parent directory to sys.path if running tests directly
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent))

from app.transcription.factory import get_transcription_service
from app.config import get_settings

# Configure logger
logger.add(Path(__file__).parent.parent / "chunk_test.log", rotation="1 MB")

async def chunk_audio_and_test():
    # Load the audio file
    audio_path = Path(__file__).parent.parent / "aws-bp-30 (1).mp3"
    logger.info(f"Loading audio file: {audio_path}")
    
    try:
        # Load the MP3 file
        audio = AudioSegment.from_mp3(audio_path)
        
        # Extract a 10-second chunk (start at 5 seconds to avoid any initial silence)
        chunk_start_ms = 5000  # 5 seconds
        chunk_end_ms = chunk_start_ms + 10000  # 10 seconds duration
        audio_chunk = audio[chunk_start_ms:chunk_end_ms]
        
        # Save the chunk as WAV (better for transcription)
        chunk_path = Path(__file__).parent.parent / "audio_chunk_10s.wav"
        audio_chunk.export(chunk_path, format="wav")
        logger.info(f"Exported 10-second chunk to {chunk_path}")
        
        # Read the file and convert to base64
        with open(chunk_path, "rb") as f:
            audio_bytes = f.read()
            audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")
        
        # Get settings
        settings = get_settings()
        
        # Test transcription with Deepgram API
        transcription_service = get_transcription_service(provider="deepgram")
        logger.info("Sending audio to Deepgram for transcription...")
        
        # Call the transcription service
        transcript = await transcription_service.transcribe(audio_base64)
        
        logger.info(f"Transcription result: {transcript}")
        print("\n" + "-"*50)
        print("TRANSCRIPTION RESULT:")
        print(transcript)
        print("-"*50 + "\n")
        
        return transcript
        
    except Exception as e:
        logger.exception(f"Error processing audio: {str(e)}")
        return f"Error: {str(e)}"

if __name__ == "__main__":
    # Check if pydub is installed
    try:
        import pydub
    except ImportError:
        print("pydub not found. Installing...")
        import subprocess
        subprocess.check_call(["pip", "install", "pydub"])
        print("pydub installed.")
    
    # Run the async function
    result = asyncio.run(chunk_audio_and_test()) 