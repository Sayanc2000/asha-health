"""
Pydantic models for API schemas
"""
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime


# Transcription models
class TranscriptionRequest(BaseModel):
    audio_data: str
    provider: Optional[str] = None


class TranscriptionResponse(BaseModel):
    text: str
    segments: List[Dict[str, Any]] = []
    speakers: List[str] = []


# Session models
class SessionRequest(BaseModel):
    name: Optional[str] = None


class SessionResponse(BaseModel):
    session_id: str
    name: Optional[str] = None
    created_at: str


class SessionInfo(BaseModel):
    session_id: str
    name: Optional[str] = None
    created_at: str
    chunks_count: int


class SessionDetailResponse(BaseModel):
    session_id: str
    name: Optional[str] = None
    created_at: str
    transcript_count: int
    has_soap_note: bool
    last_activity: Optional[str] = None


class SessionUpdateRequest(BaseModel):
    name: str


# SOAP note models
class SOAPNoteRequest(BaseModel):
    provider: Optional[str] = "default"


class SOAPNoteResponse(BaseModel):
    session_id: str
    soap_text: str
    created_at: str


class TranscriptSchema(BaseModel):
    id: Optional[int] = None
    session_id: UUID
    serial: int
    transcript: str
    speaker: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)