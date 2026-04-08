"""Tunnel lifecycle and thread management."""

import asyncio
import threading

from src.app.context import app_context
from src.tunnel.base import check_rsd_data, stop_tunnel_thread
from src.tunnel.quic import start_tunnel_thread
from src.tunnel.tcp import (
    start_tcp_tunnel_thread,
    start_wifi_quic_tunnel,
    start_wifi_tcp_tunnel,
)
from src.utils.logging import logger


def run_wifi_tunnel():
    from src.devices.connection import version_check
    """Entry point for running WiFi tunnel in thread."""
    try:
        if version_check(app_context.ios_version):
            asyncio.run(start_wifi_quic_tunnel())
        else:
            asyncio.run(start_wifi_tcp_tunnel())
    except Exception as e:
        logger.error(f"Error in run_wifi_tunnel: {e}")


def start_wifi_tunnel_thread():
    """Start WiFi tunnel in a new thread."""
    app_context.terminate_tunnel_thread = False
    thread = threading.Thread(target=run_wifi_tunnel)
    thread.start()


# Re-export common functions
__all__ = [
    "check_rsd_data",
    "start_tcp_tunnel_thread",
    "start_tunnel_thread",
    "start_wifi_tunnel_thread",
    "stop_tunnel_thread",
]
