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
        prompt = f"""
        You are a large language model trained to generate clinical notes. Your task is to **create a structured SOAP note in HTML format** based on the following transcript of a patient encounter. The SOAP note must adhere to these requirements:

        - **Sections:** Include exactly **four sections**: **Subjective, Objective, Assessment,** and **Plan**. Use these as section headings (for example, as `<h2>` or `<h3>` tags in HTML). Each section should appear in the note even if the transcript has no information for that section (in such a case, include a placeholder bullet like "No relevant information.").  
        - **Bullet Points:** Under each section, provide the content as bullet points. Use an unordered list (`<ul>`) for each section’s bullet points, and each individual point should be in an `<li>` element. Each bullet point should capture a single relevant piece of information from the transcript for that section. Keep bullet point statements **concise** and **factual**.  
        - **Use of Transcript Evidence:** For **each bullet point**, include a `<span>` tag around the bullet text. In that `<span>`, add a **`title` attribute** that contains the exact excerpt(s) from the transcript which support that bullet point. This will serve as a tooltip showing evidence from the transcript. Follow these rules for the excerpts in the `title` attribute:  
        - Use **one or more short excerpts** from the transcript that are relevant to the bullet point’s content. (If the bullet is derived from multiple separate parts of the conversation, you may include more than one excerpt in the title attribute, separated by a space or semicolon.)  
        - **Limit each excerpt to 50 characters or fewer.** If an excerpt is longer than 50 characters, truncate it at a natural break within 80 characters and end it with an ellipsis (`…`).  
        - **Accuracy:** Use the exact words from the transcript for each excerpt (verbatim, aside from truncation). Do not paraphrase inside the `title` attribute – it should reflect the transcript exactly. However, feel free to paraphrase or summarize in the visible bullet text outside the title attribute.  
        - **No Transcript in Output:** Do not include the full transcript or any large portion of it in the output. Use the transcript only to extract the necessary details. The only place transcript text should appear in the output is within the `title` attributes of the spans as evidence snippets.  
        - **Output Format:** **Return only the HTML content** of the SOAP note, with no additional commentary, explanation, or markdown formatting. The output should begin with the first section’s heading (e.g., `<h2>Subjective</h2>`) and end with the closing tag of the last section’s list. Do not include any preliminary text, and do not wrap the HTML in a markdown code block. Ensure that all HTML tags are properly closed and nested.

        **Transcript:**  
        ```{transcript_text}```  

        *Use that transcript to inform the SOAP note. Remember: only output the formatted HTML SOAP note as the final answer.*
                
        """
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
