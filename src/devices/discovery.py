"""Device discovery functionality for USB and WiFi."""

import asyncio
import time
from typing import List

from pymobiledevice3.lockdown import create_using_tcp, create_using_usbmux
from pymobiledevice3.remote.tunnel_service import get_remote_pairing_tunnel_services
from pymobiledevice3.remote.utils import get_rsds
from pymobiledevice3.usbmux import list_devices

from src.app.context import app_context
from src.config.settings import DEFAULT_BONJOUR_TIMEOUT
from src.utils.logging import logger


def get_devices_with_retry(max_attempts: int = 10) -> List:
    """Retry device discovery multiple times."""
    from src.devices.connection import version_check

    if app_context.is_windows and app_context.ios_version is not None:
        logger.info(f"iOS Version: {app_context.ios_version}")
        if version_check(app_context.ios_version):
            logger.info("Windows Driver Install Required")

    for attempt in range(1, max_attempts + 1):
        try:
            devices = asyncio.run(get_rsds(DEFAULT_BONJOUR_TIMEOUT))
            if devices:
                return devices
            else:
                logger.warning(f"Attempt {attempt}: No devices found")
        except Exception as e:
            logger.warning(f"Attempt {attempt}: Error occurred - {e}")
        time.sleep(1)

    raise RuntimeError(
        "No devices found after multiple attempts.\n"
        " Ensure you are running GeoPort as sudo / Administrator\n"
        " Please see the FAQ: https://github.com/davesc63/GeoPort/blob/main/FAQ.md\n"
        " If you still have the error please raise an issue on github: https://github.com/davesc63/GeoPort/issues "
    )


def get_wifi_with_retry(max_attempts: int = 10):
    """Retry WiFi device discovery multiple times."""
    for attempt in range(1, max_attempts + 1):
        try:
            logger.info("Discovering Wifi Devices - This may take a while...")
            devices = asyncio.run(
                get_remote_pairing_tunnel_services(DEFAULT_BONJOUR_TIMEOUT)
            )

            if devices:
                if app_context.udid:
                    for device in devices:
                        if device.remote_identifier == app_context.udid:
                            logger.info(f"Device found with udid: {app_context.udid}.")
                            app_context.wifi_address = device.hostname
                            app_context.wifi_port = device.port
                            return device
                else:
                    return devices
            else:
                logger.warning(f"Attempt {attempt}: No devices found")
        except Exception as e:
            logger.warning(f"Attempt {attempt}: Error occurred - {e}")

        time.sleep(1)

    raise RuntimeError("No devices found after multiple attempts. Please see the FAQ.")


def handle_list_devices() -> bool:
    """List all connected devices (USB + WiFi)."""
    try:
        connected_devices = {}

        # Retrieve all devices
        all_devices = asyncio.run(list_devices())
        logger.info(f"\n\nRaw Devices:  {all_devices}\n")

        if app_context.wifihost:
            udid_parsed = app_context.udid
            logger.warning(f"Wifi requested to {app_context.wifihost}")
            logger.warning(f"udid: {udid_parsed}")
            lockdown = asyncio.run(
                create_using_tcp(hostname=app_context.wifihost, identifier=udid_parsed)
            )

            info = lockdown.short_info
            logger.warning(f"Wifi Short Info: {info}")
            wifi_connection_state = True
            info["wifiState"] = wifi_connection_state
            info["ConnectionType"] = "Network"
            app_context.connection_type = "Manual Wifi"

            if udid_parsed in connected_devices:
                if app_context.connection_type in connected_devices[udid_parsed]:
                    connected_devices[udid_parsed][app_context.connection_type].append(
                        info
                    )
                else:
                    connected_devices[udid_parsed][app_context.connection_type] = [info]
            else:
                connected_devices[udid_parsed] = {app_context.connection_type: [info]}

        # Iterate through all devices
        for device in all_devices:
            device_udid = device.serial
            device_connection_type = device.connection_type

            device_lockdown = asyncio.run(
                create_using_usbmux(
                    device_udid, connection_type=device_connection_type, autopair=True
                )
            )
            info = device_lockdown.short_info

            wifi_connection_state = True
            info["wifiState"] = wifi_connection_state

            if device_connection_type == "Network":
                device_connection_type = "Wifi"

            if device_udid in connected_devices:
                if device_connection_type in connected_devices[device_udid]:
                    connected_devices[device_udid][device_connection_type].append(info)
                else:
                    connected_devices[device_udid][device_connection_type] = [info]
            else:
                connected_devices[device_udid] = {device_connection_type: [info]}

        logger.info("\n=== Connected Devices ===\n")
        for device_udid, connections in connected_devices.items():
            logger.info(f"\nUDID: {device_udid}")
            for conn_type, devices_info in connections.items():
                for info in devices_info:
                    logger.info(f"  {conn_type}: {info}")
        logger.info("\n====================\n")

        from src.config.settings import current_platform

        if current_platform == "darwin":
            import os

            if os.geteuid() != 0:
                logger.error("*********************** WARNING ***********************")
                logger.error("Not running as Sudo, this probably isn't going to work")
                logger.error("*********************** WARNING ***********************")

        return True

    except ConnectionAbortedError as e:
        logger.error(f"ConnectionAbortedError occurred: {e}")
        return False

    except Exception as e:
        error_message = str(e)
        logger.error(f"Error listing devices: {error_message}", exc_info=True)
        return False
