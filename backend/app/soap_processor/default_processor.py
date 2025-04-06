import httpx
import asyncio
from loguru import logger
from .base import BaseSOAPProcessor

class DefaultSOAPProcessor(BaseSOAPProcessor):
    def __init__(self, endpoint: str, api_key: str):
        self.endpoint = endpoint
        self.api_key = api_key

    async def process(self, transcript_text: str) -> str:
        # Build a generic prompt for SOAP note generation
        prompt = (
            "Generate a structured clinical SOAP note from the following transcript. "
            "The note should include the sections: Subjective, Objective, Assessment, and Plan.\n\n"
            "Make sure you only pick data from the transcript that is provided, please do not create new information. "
            "Your job is to understand given information and organize it into a SOAP note."
            "You can use special md type characters to properly format the note."
            "Please just return only the SOAP note, do not include any other text or comments, you also do not need to specify the type of file in the response"
            f"Transcript:\n{transcript_text}\n\nSOAP Note:"
        )
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "gpt-4o",  # Generic model reference
            "prompt": prompt,
            "max_tokens": 500,  # Adjust as needed
        }
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(self.endpoint, json=data, headers=headers)
                response.raise_for_status()
                result = response.json()
                # Assume the SOAP note is returned in result["choices"][0]["text"]
                soap_text = result["choices"][0]["text"].strip()
                logger.info("SOAP note generated successfully.")
                return soap_text
        except Exception as e:
            logger.error(f"Error generating SOAP note: {e}")
            raise e 
