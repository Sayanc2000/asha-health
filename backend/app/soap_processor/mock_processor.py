import asyncio
from loguru import logger
from .base import BaseSOAPProcessor

class MockSOAPProcessor(BaseSOAPProcessor):
    """
    A mock SOAP processor for testing purposes.
    Generates a simple SOAP note without making external API calls.
    """
    def __init__(self, endpoint: str = None, api_key: str = None):
        """
        Initialize the mock SOAP processor.
        
        Args:
            endpoint: Ignored in mock implementation
            api_key: Ignored in mock implementation
        """
        self.endpoint = endpoint
        self.api_key = api_key
    
    async def process(self, transcript_text: str) -> str:
        """
        Generate a mock SOAP note from the transcript text.
        
        Args:
            transcript_text: The transcript text to generate a SOAP note from
            
        Returns:
            A mock SOAP note
        """
        # Generate a simple mock SOAP note
        logger.info("Generating mock SOAP note")
        
        # Create a simple SOAP note with transcript snippets
        words = transcript_text.split()
        word_count = len(words)
        
        # Use a small delay to simulate API call
        await asyncio.sleep(0.5)
        
        # Generate a simple SOAP note
        soap_note = f"""
## SOAP Note

### Subjective
Patient reports: "{transcript_text[:100]}..."

### Objective
- Word count: {word_count}
- First few words: {' '.join(words[:5])}
- Last few words: {' '.join(words[-5:] if len(words) >= 5 else words)}

### Assessment
This is a mock SOAP note for testing purposes.

### Plan
1. Continue monitoring
2. Follow up in two weeks
3. Review transcript completely
"""
        
        return soap_note 