import logging
import sys
from core.config import settings

def setup_logging():
    """Centralized logging configuration."""
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
        format=settings.LOG_FORMAT,
        handlers=[
            logging.StreamHandler(sys.stdout)
        ],
        force=True  # Ensure that the root logger is reset and configured correctly
    )
