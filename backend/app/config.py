import os
from typing import Dict, Any, Optional
from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database settings
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./test.db",
        description="Database connection string"
    )

    # Transcription service settings
    TRANSCRIPTION_PROVIDER: str = Field(
        default="dummy",
        description="Provider for transcription service (dummy, deepgram, whisper)"
    )
    USE_STREAMING_TRANSCRIPTION: bool = Field(
        default=False,
        description="Use streaming transcription for real-time results"
    )
    DEEPGRAM_API_KEY: Optional[str] = Field(
        default=None,
        description="API key for Deepgram"
    )
    OPENAI_API_KEY: Optional[str] = Field(
        default=None,
        description="API key for OpenAI Whisper"
    )

    # SOAP service settings
    SOAP_API_KEY: Optional[str] = Field(
        default="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",
        description="API key for SOAP note generation service",
    )
    SOAP_API_ENDPOINT: Optional[str] = Field(
        default="https://openrouter.ai/api/v1/completions",
        description="Endpoint URL for SOAP note generation service",
    )

    # Logging settings
    LOG_LEVEL: str = Field(
        default="INFO",
        description="Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
    )
    LOG_FILE: str = Field(
        default="app.log",
        description="Log file path"
    )
    LOG_ROTATION: str = Field(
        default="500 MB",
        description="Log rotation size"
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """
    Get application settings, cached for performance.
    
    Returns:
        Application settings
    """
    return Settings() 
