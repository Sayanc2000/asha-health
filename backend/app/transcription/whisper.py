import base64
import tempfile
import os
import httpx
from typing import Dict, Any, Optional, List
from .base import BaseTranscriptionService
from loguru import logger

class WhisperTranscriptionService(BaseTranscriptionService):
    """
    A transcription service that uses OpenAI's Whisper API.
    """
    def __init__(self, api_key: str = None):
        """
        Initialize the Whisper transcription service.
        
        Args:
            api_key: The OpenAI API key
        """
        self.api_key = api_key or "YOUR_OPENAI_API_KEY"
        self.base_url = "https://api.openai.com/v1/audio/transcriptions"
        
    async def transcribe(self, audio_data: str) -> Dict[str, Any]:
        """
        Transcribe audio data using OpenAI's Whisper API.
        
        Args:
            audio_data: Base64 encoded audio data
            
        Returns:
            Dictionary containing transcription data including text, segments, and speakers
        """
        try:
            # Decode base64 data
            decoded_audio = base64.b64decode(audio_data)
            
            # Create a temporary file to store the audio data
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp:
                temp.write(decoded_audio)
                temp_path = temp.name
                
            try:
                # Prepare headers with authentication
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                }
                
                # Prepare the form data with the audio file
                files = {
                    "file": ("audio.wav", open(temp_path, "rb"), "audio/wav"),
                }
                
                # Form data for API parameters - request verbose JSON response
                data = {
                    "model": "whisper-1",
                    "language": "en",
                    "response_format": "verbose_json"
                }
                
                # Make async request to OpenAI
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        self.base_url,
                        headers=headers,
                        files=files,
                        data=data,
                        timeout=30.0
                    )
                    
                    if response.status_code == 200:
                        # Parse and extract detailed transcript data from response
                        result = response.json()
                        
                        # Extract full transcript text
                        text = result.get("text", "")
                        
                        # Process segments and assign default speaker
                        segments = result.get("segments", [])
                        for segment in segments:
                            # OpenAI Whisper doesn't do speaker diarization
                            # Assign default speaker for all segments
                            segment["speaker"] = "SPEAKER_00"
                        
                        # Create structured response
                        response_data = {
                            "text": text,
                            "segments": segments,
                            "speakers": ["SPEAKER_00"]
                        }
                        
                        return response_data
                    else:
                        logger.error(f"Whisper API error: {response.status_code} - {response.text}")
                        return {
                            "text": f"Transcription error: {response.status_code}",
                            "segments": [],
                            "speakers": []
                        }
            
            finally:
                # Clean up the temporary file
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
        
        except Exception as e:
            logger.exception(f"Error in WhisperTranscriptionService: {str(e)}")
            return {
                "text": f"Transcription failed: {str(e)}",
                "segments": [],
                "speakers": []
            } 