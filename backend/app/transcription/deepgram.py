import asyncio
import base64
import json
import httpx
from typing import Dict, Any, List
from .base import BaseTranscriptionService
from loguru import logger
import os
from dotenv import load_dotenv, find_dotenv

find_dotenv()
load_dotenv()



class DeepgramTranscriptionService(BaseTranscriptionService):
    """
    A transcription service that uses the Deepgram API.
    """
    def __init__(self, api_key: str = None):
        """
        Initialize the Deepgram transcription service.
        
        Args:
            api_key: The Deepgram API key
        """
        self.api_key = (
            api_key or os.environ.get("DEEPGRAM_API_KEY")
        )  # Replace with environment variable
        self.base_url = "https://api.deepgram.com/v1/listen"

    async def transcribe(self, audio_data: str) -> Dict[str, Any]:
        """
        Transcribe audio data using the Deepgram API.
        
        Args:
            audio_data: Base64 encoded audio data
            
        Returns:
            Dictionary containing transcription data including text, segments, and speakers
        """
        try:
            # Decode base64 data
            decoded_audio = base64.b64decode(audio_data)

            # Prepare headers with authentication and content type
            headers = {
                "Authorization": f"Token {self.api_key}",
                "Content-Type": "audio/wav",  # Assuming WAV format, adjust if needed
            }

            # Parameters for Deepgram API - enable speaker diarization and word timing
            params = {
                "punctuate": "true",
                "model": "general",
                "language": "en-US",
                "diarize": "true",  # Enable speaker diarization
                "utterances": "true"  # Get utterances by speaker
            }

            # Make async request to Deepgram
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.base_url,
                    headers=headers,
                    params=params,
                    content=decoded_audio,
                    timeout=10.0
                )

                if response.status_code == 200:
                    # Parse and extract detailed transcript data from response
                    result = response.json()
                    
                    # Extract full transcript text from results
                    channel_results = result.get("results", {}).get("channels", [{}])
                    if not channel_results:
                        return self._create_error_response("No channel results found")
                    
                    channel = channel_results[0]
                    alternatives = channel.get("alternatives", [{}])
                    if not alternatives:
                        return self._create_error_response("No alternatives found")
                    
                    # Get the transcript text
                    text = alternatives[0].get("transcript", "")
                    
                    # Process segments (words with timing info)
                    words = alternatives[0].get("words", [])
                    
                    # Process utterances (speaker segments)
                    utterances = channel.get("utterances", [])
                    
                    # Extract unique speakers
                    speakers = list(set(u.get("speaker", f"SPEAKER_{i}") 
                                       for i, u in enumerate(utterances)))
                    
                    # If no speakers detected, use default
                    if not speakers:
                        speakers = ["SPEAKER_00"]
                    
                    # Create segments from utterances
                    segments = []
                    for i, utterance in enumerate(utterances):
                        speaker = utterance.get("speaker", f"SPEAKER_{i % len(speakers) if speakers else 0}")
                        segment = {
                            "id": i,
                            "start": utterance.get("start", 0),
                            "end": utterance.get("end", 0),
                            "text": utterance.get("transcript", ""),
                            "speaker": speaker
                        }
                        segments.append(segment)
                    
                    # If no segments/utterances available, create a single segment
                    if not segments and text:
                        segments = [{
                            "id": 0,
                            "start": 0,
                            "end": 0 if not words else words[-1].get("end", 0),
                            "text": text,
                            "speaker": "SPEAKER_00"
                        }]
                    
                    # Create structured response
                    response_data = {
                        "text": text,
                        "segments": segments,
                        "speakers": speakers
                    }
                    
                    return response_data
                else:
                    logger.error(f"Deepgram API error: {response.status_code} - {response.text}")
                    return self._create_error_response(f"Transcription error: {response.status_code}")

        except Exception as e:
            logger.exception(f"Error in DeepgramTranscriptionService: {str(e)}")
            return self._create_error_response(f"Transcription failed: {str(e)}")
    
    def _create_error_response(self, error_message: str) -> Dict[str, Any]:
        """Helper method to create error response structure"""
        return {
            "text": error_message,
            "segments": [],
            "speakers": []
        }
