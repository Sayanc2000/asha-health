from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import Optional

class TranscriptSchema(BaseModel):
    id: Optional[int] = Field(default=None)
    session_id: UUID
    serial: int
    transcript: str
    created_at: datetime = Field(default_factory=datetime.utcnow)