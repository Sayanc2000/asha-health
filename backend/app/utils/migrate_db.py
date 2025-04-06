"""
Script to upgrade database schema for transcript table
"""
import asyncio
import argparse
import json
from loguru import logger
import sqlalchemy as sa
from sqlalchemy.future import select
import uuid
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import engine, Base, async_session
from app.models import Transcript

async def migrate_transcript_table():
    """Upgrade the transcript table schema to add speaker column and UUID id"""
    
    # Check if we need to run the migration
    async with engine.begin() as conn:
        # Check for columns in transcript table
        has_speaker_column = False
        is_id_uuid = False
        
        try:
            # First check if transcripts table exists
            result = await conn.execute(sa.text(
                "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'transcripts')"
            ))
            table_exists = result.scalar()
            
            if not table_exists:
                logger.info("Transcripts table does not exist yet. No migration needed.")
                return
            
            # Check for speaker column
            result = await conn.execute(sa.text(
                "SELECT EXISTS (SELECT FROM information_schema.columns WHERE table_name = 'transcripts' AND column_name = 'speaker')"
            ))
            has_speaker_column = result.scalar()
            
            # Check id column type
            result = await conn.execute(sa.text(
                "SELECT data_type FROM information_schema.columns WHERE table_name = 'transcripts' AND column_name = 'id'"
            ))
            id_type = result.scalar()
            is_id_uuid = id_type and "uuid" in id_type.lower()
            
        except Exception as e:
            logger.error(f"Error checking schema: {str(e)}")
            return
    
    # Run appropriate migrations
    if not has_speaker_column:
        logger.info("Adding speaker column to transcripts table")
        async with engine.begin() as conn:
            await conn.execute(sa.text(
                "ALTER TABLE transcripts ADD COLUMN speaker VARCHAR DEFAULT 'SPEAKER_00'"
            ))
    
    if not is_id_uuid:
        logger.info("Converting id column to UUID (this will create a new table and transfer data)")
        
        # This is complex - need to create a new table and migrate data
        async with engine.begin() as conn:
            # Create a temporary new table with UUID id
            await conn.execute(sa.text("""
                CREATE TABLE transcripts_new (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    session_id VARCHAR,
                    serial INTEGER,
                    transcript TEXT,
                    speaker VARCHAR DEFAULT 'SPEAKER_00',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            
            # Create index on session_id
            await conn.execute(sa.text(
                "CREATE INDEX idx_transcripts_new_session_id ON transcripts_new (session_id)"
            ))
            
            # Copy data from old table to new table
            await conn.execute(sa.text("""
                INSERT INTO transcripts_new (session_id, serial, transcript, speaker, created_at)
                SELECT session_id, serial, transcript, 
                       COALESCE(speaker, 'SPEAKER_00') as speaker, 
                       created_at 
                FROM transcripts
            """))
            
            # Drop old table
            await conn.execute(sa.text("DROP TABLE transcripts"))
            
            # Rename new table to transcripts
            await conn.execute(sa.text("ALTER TABLE transcripts_new RENAME TO transcripts"))
    
    logger.info("Migration completed successfully")

async def main():
    logger.info("Starting database migration")
    try:
        await migrate_transcript_table()
        logger.info("Migration finished")
    except Exception as e:
        logger.error(f"Migration failed: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main()) 