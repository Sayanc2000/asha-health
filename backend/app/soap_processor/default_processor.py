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
            "The SOAP note must include exactly the following sections:\n\n"
            "- **Subjective:** Patient-reported information extracted from the transcript.\n"
            "- **Objective:** Observable and measurable data mentioned in the transcript.\n"
            "- **Assessment:** Analysis or diagnosis based solely on the provided transcript.\n"
            "- **Plan:** Recommended actions or treatment derived from the transcript.\n\n"
            "Do not include any part of the transcript in your output. "
            "Use only the information in the transcript to generate the SOAP note. "
            "Return only the SOAP note in plain text using Markdown formatting, without any extra commentary. "
            "Output exactly in the following format:\n\n"
            "```\n"
            "Subjective:\n[Your content here]\n\n"
            "Objective:\n[Your content here]\n\n"
            "Assessment:\n[Your content here]\n\n"
            "Plan:\n[Your content here]\n"
            "```\n\n"
            "Transcript for context (do not include in your response):\n"
            f"{transcript_text}\n\n"
            "SOAP Note:"
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
