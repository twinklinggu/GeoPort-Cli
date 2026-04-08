"""Base tunnel interface and common functionality."""

import time



from src.app.context import app_context
from src.utils.logging import logger


def stop_tunnel_thread():
    """Stop the current tunnel thread."""
    logger.info("stop tunnel thread")
    app_context.terminate_tunnel_thread = True
    logger.info("Tunnel stopped")


def check_rsd_data() -> bool:
    """Check if RSD data is available."""
    max_attempts = 30
    attempts = 0
    while attempts < max_attempts:
        if app_context.rsd_host is not None and app_context.rsd_port is not None:
            return True

        time.sleep(1)
        attempts += 1
    logger.error("RSD Data is still None after multiple attempts")
    return False
