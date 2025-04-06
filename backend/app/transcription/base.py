from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseTranscriptionService(ABC):
    @abstractmethod
    async def transcribe(self, audio_data: str) -> Dict[str, Any]:
        """
        Transcribe the given audio data and return structured transcript data.
        
        Args:
            audio_data: Audio data, possibly base64 encoded
            
        Returns:
            A dictionary containing transcription data including:
            - text: The full transcribed text
            - segments: List of individual segments with timing and speaker info
            - speakers: List of detected speakers
        """
        pass