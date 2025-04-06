import sys
from loguru import logger
from ..config import get_settings

# Get application settings
settings = get_settings()

# Remove default logger
logger.remove()

# Add console logger
logger.add(
    sys.stderr,
    level=settings.LOG_LEVEL,
    format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
)

# Add file logger with rotation
logger.add(
    settings.LOG_FILE,
    rotation=settings.LOG_ROTATION,
    level=settings.LOG_LEVEL,
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}"
)