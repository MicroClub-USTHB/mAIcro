"""Application logging configuration."""

import logging


def configure_logging() -> None:
    """Configure a simple, consistent log format for the service."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
