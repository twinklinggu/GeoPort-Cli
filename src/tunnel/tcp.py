"""TCP tunnel implementation for older iOS versions."""

import asyncio
import threading

from pymobiledevice3.lockdown import create_using_usbmux
from pymobiledevice3.remote.tunnel_service import CoreDeviceTunnelProxy
from pymobiledevice3.remote.utils import (
    resume_remoted_if_required,
    stop_remoted_if_required,
)

from src.app.context import app_context
from src.utils.logging import logger


async def start_tcp_tunnel(target_udid: str) -> None:
    """Start TCP tunnel for USB connection."""
    logger.warning("Start USB TCP tunnel")

    app_context.terminate_tunnel_thread = False
    stop_remoted_if_required()

    # Create lockdown inside this async context to avoid event loop conflicts
    lockdown = await create_using_usbmux(target_udid, autopair=True)
    logger.info(f"Created lockdown in tunnel thread: {lockdown}")
    service = await CoreDeviceTunnelProxy.create(lockdown)

    async with service.start_tcp_tunnel() as tunnel_result:
        resume_remoted_if_required()

        logger.info(f"TCP Address: {tunnel_result.address}")
        logger.info(f"TCP Port: {tunnel_result.port}")
        app_context.rsd_host = tunnel_result.address
        app_context.rsd_port = str(tunnel_result.port)

        while True:
            if app_context.terminate_tunnel_thread is True:
                return
            await asyncio.sleep(0.5)


def run_tcp_tunnel(service_provider):
    """Run TCP tunnel in thread."""
    try:
        asyncio.run(start_tcp_tunnel(service_provider))
        logger.info("run_tcp_tunnel completed")
        return

    except Exception as e:
        error_message = str(e)
        logger.error(f"TCP tunnel error: {error_message}", exc_info=True)
        return


def start_tcp_tunnel_thread(target_udid: str):
    """Start TCP tunnel in a new thread."""
    app_context.terminate_tunnel_thread = False
    thread = threading.Thread(target=run_tcp_tunnel, args=(target_udid,))
    thread.start()


async def start_wifi_tcp_tunnel() -> None:
    """Start TCP tunnel for WiFi connection."""
    logger.warning("Start Wifi TCP Tunnel")

    stop_remoted_if_required()

    lockdown = await create_using_usbmux(app_context.udid)
    service = await CoreDeviceTunnelProxy.create(lockdown)

    async with service.start_tcp_tunnel() as tunnel_result:
        resume_remoted_if_required()

        logger.info(f"Identifier: {service.remote_identifier}")
        logger.info(f"Interface: {tunnel_result.interface}")
        logger.info(f"RSD Address: {tunnel_result.address}")
        logger.info(f"RSD Port: {tunnel_result.port}")
        app_context.rsd_host = tunnel_result.address
        app_context.rsd_port = str(tunnel_result.port)

        while True:
            if app_context.terminate_tunnel_thread is True:
                return
            await asyncio.sleep(0.5)


async def start_wifi_quic_tunnel() -> None:
    """Start QUIC tunnel for WiFi connection."""
    from pymobiledevice3.remote.tunnel_service import (
        create_core_device_tunnel_service_using_remotepairing,
    )

    logger.warning("Start Wifi QUIC Tunnel")

    stop_remoted_if_required()

    service = await create_core_device_tunnel_service_using_remotepairing(
        app_context.udid, app_context.wifi_address, app_context.wifi_port
    )

    async with service.start_quic_tunnel() as tunnel_result:
        resume_remoted_if_required()

        logger.info(f"Identifier: {service.remote_identifier}")
        logger.info(f"Interface: {tunnel_result.interface}")
        logger.info(f"RSD Address: {tunnel_result.address}")
        logger.info(f"RSD Port: {tunnel_result.port}")
        app_context.rsd_host = tunnel_result.address
        app_context.rsd_port = str(tunnel_result.port)

        while True:
            if app_context.terminate_tunnel_thread is True:
                return
            await asyncio.sleep(0.5)
