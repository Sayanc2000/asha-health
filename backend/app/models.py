import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid
from .config import get_settings

# Get application settings
settings = get_settings()

# Create async engine with settings
engine = create_async_engine(settings.DATABASE_URL, echo=True)
Base = declarative_base()
async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

class Transcript(Base):
    __tablename__ = "transcripts"
    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = sa.Column(sa.String, index=True)  # UUID stored as a string
    serial = sa.Column(sa.Integer)
    transcript = sa.Column(sa.Text)
    speaker = sa.Column(sa.String, default="SPEAKER_00")
    created_at = sa.Column(sa.DateTime, default=datetime.utcnow)

class SOAPNote(Base):
    __tablename__ = "soap_notes"
    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = sa.Column(sa.String, index=True)
    soap_text = sa.Column(sa.Text)
    created_at = sa.Column(sa.DateTime, default=datetime.utcnow)

# Function to create DB tables asynchronously
async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)