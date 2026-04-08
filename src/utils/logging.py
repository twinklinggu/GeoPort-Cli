"""Logging configuration for GeoPort."""

import logging


def setup_logging() -> logging.Logger:
    """Configure and return the GeoPort logger."""
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler()],
    )

    # Create a logger named "GeoPort"
    logger = logging.getLogger("GeoPort")
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    return logger


# Global logger instance
logger = setup_logging()
