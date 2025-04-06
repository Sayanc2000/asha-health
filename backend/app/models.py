import sqlalchemy as sa
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid

Base = declarative_base()


class Session(Base):
    __tablename__ = "sessions"
    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = sa.Column(sa.String, nullable=True)
    created_at = sa.Column(sa.DateTime, default=datetime.now())

class Transcript(Base):
    __tablename__ = "transcripts"
    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = sa.Column(UUID(as_uuid=True), sa.ForeignKey("sessions.id"), index=True)
    serial = sa.Column(sa.Integer)
    transcript = sa.Column(sa.Text)
    speaker = sa.Column(sa.String, default="SPEAKER_00")
    created_at = sa.Column(sa.DateTime, default=datetime.now())


class SOAPNote(Base):
    __tablename__ = "soap_notes"
    id = sa.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = sa.Column(UUID(as_uuid=True), sa.ForeignKey("sessions.id"), index=True)
    soap_text = sa.Column(sa.Text)
    created_at = sa.Column(sa.DateTime, default=datetime.now())