"""QUIC tunnel implementation for iOS 17+."""

import asyncio
import sys
import threading

from pymobiledevice3.remote.remote_service_discovery import (
    RemoteServiceDiscoveryService,
)
from pymobiledevice3.remote.tunnel_service import (
    create_core_device_tunnel_service_using_rsd,
)
from pymobiledevice3.remote.utils import stop_remoted_if_required, resume_remoted_if_required

from src.app.context import app_context
from src.utils.logging import logger


async def start_quic_tunnel(service_provider: RemoteServiceDiscoveryService) -> None:
    """Start QUIC tunnel for USB connection."""
    logger.warning("Start USB QUIC tunnel")

    stop_remoted_if_required()

    service = await create_core_device_tunnel_service_using_rsd(
        service_provider, autopair=True
    )

    async with service.start_quic_tunnel() as tunnel_result:
        resume_remoted_if_required()

        logger.info(f"QUIC Address: {tunnel_result.address}")
        logger.info(f"QUIC Port: {tunnel_result.port}")
        app_context.rsd_host = tunnel_result.address
        app_context.rsd_port = str(tunnel_result.port)

        while True:
            if app_context.terminate_tunnel_thread is True:
                return
            await asyncio.sleep(0.5)


def run_tunnel(service_provider):
    """Run QUIC tunnel in thread."""
    try:
        asyncio.run(start_quic_tunnel(service_provider))

        logger.info("run_tunnel completed")
        sys.exit(0)

    except Exception as e:
        error_message = str(e)
        logger.error(f"Tunnel error: {error_message}", exc_info=True)
        sys.exit(1)


def start_tunnel_thread(service_provider):
    """Start the tunnel in a new thread."""
    app_context.terminate_tunnel_thread = False
    thread = threading.Thread(target=run_tunnel, args=(service_provider,))
    thread.start()
