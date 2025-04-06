from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from .config import get_settings
from .models import Base

# Get application settings
settings = get_settings()

# Create async engine with settings
engine = create_async_engine(settings.DATABASE_URL)
async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

# Function to create DB tables asynchronously
async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all) 