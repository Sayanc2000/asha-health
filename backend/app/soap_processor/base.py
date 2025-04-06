from abc import ABC, abstractmethod

class BaseSOAPProcessor(ABC):
    @abstractmethod
    async def process(self, transcript_text: str) -> str:
        """
        Given a full transcript text, generate and return a structured clinical SOAP note.
        """
        pass 