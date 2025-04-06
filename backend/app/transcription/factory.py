import os
from typing import Dict, Any, Optional
from .deepgram import DeepgramTranscriptionService
from .whisper import WhisperTranscriptionService
from .base import BaseTranscriptionService
from loguru import logger
from dotenv import load_dotenv, find_dotenv

find_dotenv()
load_dotenv()


class DummyTranscriptionService(BaseTranscriptionService):
    """
    A dummy transcription service that returns placeholder text.
    Useful for testing without making API calls.
    """
    def __init__(self, *args, **kwargs):
        logger.warning("Using dummy transcription service - will return placeholder text")
    
    async def transcribe(self, audio_data: str) -> Dict[str, Any]:
        """
        Return a placeholder transcription with structured data.
        
        Args:
            audio_data: Base64 encoded audio data (ignored)
            
        Returns:
            A dictionary with placeholder transcription data
        """
        placeholder_text = "This is a placeholder transcription from the dummy service."
        
        # Create a dummy structured response with segments and speaker info
        return {
            "text": placeholder_text,
            "segments": [
                {
                    "id": 0,
                    "start": 0.0,
                    "end": 2.5,
                    "text": "This is a placeholder",
                    "speaker": "SPEAKER_00"
                },
                {
                    "id": 1,
                    "start": 2.5,
                    "end": 5.0,
                    "text": "transcription from the dummy service.",
                    "speaker": "SPEAKER_00"
                }
            ],
            "speakers": ["SPEAKER_00"]
        }


# Cache for service instances
_service_instances: Dict[str, BaseTranscriptionService] = {}

def get_transcription_service(
    provider: str = "dummy", 
    api_key: Optional[str] = None,
    **kwargs: Any
) -> BaseTranscriptionService:
    """
    Factory method to get an instance of a transcription service.
    Change provider easily by passing a different string.
    
    Args:
        provider: The name of the transcription provider to use
        api_key: API key for the service (optional)
        **kwargs: Additional configuration options for the service
        
    Returns:
        An instance of a transcription service
        
    Raises:
        ValueError: If the provider is unknown
    """
    # Check if we already have an instance of this provider
    if provider in _service_instances:
        logger.debug(f"Returning cached {provider} transcription service")
        return _service_instances[provider]
    
    # Create a new instance based on the provider
    if provider == "deepgram":
        # Try to get API key from environment if not provided
        deepgram_api_key = api_key or os.environ.get("DEEPGRAM_API_KEY")
        if not deepgram_api_key:
            logger.warning("No Deepgram API key provided, using placeholder")
        
        service = DeepgramTranscriptionService(api_key=deepgram_api_key)
        
        # Note: For streaming with Deepgram, use the DeepgramStreamingService directly
        # This factory only returns batch transcription services
        logger.info("Created Deepgram batch transcription service. For streaming, configure USE_STREAMING_TRANSCRIPTION=True")
        
    elif provider == "whisper":
        # Try to get API key from environment if not provided
        openai_api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not openai_api_key:
            logger.warning("No OpenAI API key provided, using placeholder")
        
        service = WhisperTranscriptionService(api_key=openai_api_key)
    elif provider == "dummy":
        # Create a dummy service for testing
        service = DummyTranscriptionService()
    else:
        raise ValueError(f"Unknown transcription provider: {provider}")
    
    # Cache the instance
    _service_instances[provider] = service
    
    return service