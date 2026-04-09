"""Device connection handling and version checks."""

import sys

from pymobiledevice3.lockdown import create_using_usbmux

from src.app.context import app_context
from src.tunnel.manager import (
    check_rsd_data,
    start_tcp_tunnel_thread,
    start_tunnel_thread,
)
from src.utils.logging import logger


def is_major_version_17_or_greater(version_string: str) -> bool:
    """Check if the major version in the given version string is 17 or greater."""
    try:
        major_version = int(version_string.split(".", maxsplit=1)[0])
        return major_version >= 17
    except (ValueError, IndexError):
        return False


def is_major_version_less_than_16(version_string: str) -> bool:
    """Check if the major version in the given version string is less than 16."""
    try:
        major_version = int(version_string.split(".", maxsplit=1)[0])
        return major_version < 16
    except (ValueError, IndexError):
        logger.error(f"Error: {ValueError}, {IndexError}")
        return False


def version_check(version_string: str) -> bool:
    """Check if Windows needs WeTest driver (iOS 17.0-17.3)."""
    try:
        version_parts = version_string.split(".")
        major_version = int(version_parts[0])
        minor_version = int(version_parts[1]) if len(version_parts) > 1 else 0

        if major_version == 17 and 0 <= minor_version <= 3:
            if sys.platform == "win32":
                logger.info("Checking Windows Driver requirement")
                logger.info("Driver is required")
            return True
        else:
            if sys.platform == "win32":
                logger.info("Driver is not required")
                return False
            logger.info("MacOS - pass")
            return False

    except (ValueError, IndexError) as e:
        logger.error(f"Driver check error: {e}")
        return False


async def connect_usb() -> bool:
    """Connect to a USB device."""
    try:
        app_context.rsd_host = None
        app_context.rsd_port = None

        # Get device info to get iOS version
        temp_lockdown = await create_using_usbmux(app_context.udid, autopair=True)
        app_context.ios_version = temp_lockdown.product_version
        logger.info(f"iOS Version: {app_context.ios_version}")

        if is_major_version_17_or_greater(app_context.ios_version):
            logger.info("iOS 17+ detected")
            logger.info(f"iOS Version: {app_context.ios_version}")
            if version_check(app_context.ios_version):
                if sys.platform == "win32":
                    logger.warning("iOS is between 17.0 and 17.3.1, WHY?")
                    logger.warning("You should upgrade to 17.4+")
                    logger.error(
                        "We need to install a 3rd party driver for these versions"
                    )
                    logger.error("which may stop working at any time")
                    try:
                        from src.devices.discovery import get_devices_with_retry

                        devices = await get_devices_with_retry()
                        logger.info(f"Devices: {devices}")
                        rsd = [
                            device
                            for device in devices
                            if device.udid == app_context.udid
                        ]
                        if len(rsd) > 0:
                            rsd = rsd[0]
                        start_tunnel_thread(rsd)

                    except RuntimeError as e:
                        error_message = str(e)
                        logger.error(f"Error: {error_message}")
                        return False

            else:
                # lockdown will be created inside the tunnel thread to avoid event loop issues
                start_tcp_tunnel_thread(app_context.udid)

            if not check_rsd_data():
                logger.error("RSD Data is None, Perhaps the tunnel isn't established")
                return False
            else:
                app_context.rsd_data = (app_context.rsd_host, app_context.rsd_port)
                logger.info(f"RSD Data: {app_context.rsd_data}")

            app_context.rsd_data_map.setdefault(app_context.udid, {})[
                app_context.connection_type
            ] = {"host": app_context.rsd_host, "port": app_context.rsd_port}
            logger.info(f"Device Connection Map: {app_context.rsd_data_map}")
            logger.info("USB connection successful")
            return True

        elif not is_major_version_17_or_greater(app_context.ios_version):
            app_context.rsd_data = (app_context.ios_version, app_context.udid)
            logger.info(f"RSD Data: {app_context.rsd_data}")

            global_lockdown = await create_using_usbmux(app_context.udid, autopair=True)
            app_context.lockdown = global_lockdown
            logger.info(f"Lockdown client = {app_context.lockdown}")

            app_context.rsd_data_map.setdefault(app_context.udid, {})[
                app_context.connection_type
            ] = {"host": app_context.rsd_host, "port": app_context.rsd_port}

            logger.info("USB connection successful")
            return True

        else:
            logger.error("No iOS version present")
            return False
    finally:
        logger.warning("Connect Device function completed")


async def connect_wifi() -> bool:
    """Connect to a WiFi device."""
    from src.devices.discovery import get_wifi_with_retry
    from src.tunnel.manager import start_wifi_tunnel_thread

    try:
        app_context.rsd_host = None
        app_context.rsd_port = None

        logger.info(f"Connecting WiFi device: udid={app_context.udid}")
        logger.info(f"Wifi host: {app_context.wifihost}")

        # We already need wifihost set for this
        from src.devices.developer_mode import check_pair_record

        check_pair_record(app_context.udid)

        if app_context.pair_record is None:
            logger.error("No Pair Record Found. Please use a USB Cable to create one")
            return False

        devices = await get_wifi_with_retry()
        logger.info(f"Connect Wifi Devices: {devices}")
        logger.info(f"Wifi Address:  {app_context.wifi_address}")

        start_wifi_tunnel_thread()

        if not check_rsd_data():
            logger.error("RSD Data is None, Perhaps the tunnel isn't established")
            return False
        else:
            app_context.rsd_data = (app_context.rsd_host, app_context.rsd_port)
            logger.info(f"RSD Data: {app_context.rsd_data}")

        app_context.rsd_data_map.setdefault(app_context.udid, {})[
            app_context.connection_type
        ] = {"host": app_context.rsd_host, "port": app_context.rsd_port}
        logger.info(f"Device Connection Map: {app_context.rsd_data_map}")
        logger.info("WiFi connection successful")
        return True

    finally:
        logger.warning("Connect Device function completed")


async def handle_connect(args) -> bool:
    """Handle connect command from CLI."""
    app_context.udid = args.udid
    app_context.connection_type = args.connection_type.capitalize()
    if args.wifihost:
        app_context.wifihost = args.wifihost

    if app_context.connection_type.lower() == "wifi":
        if not app_context.wifihost:
            logger.error("--wifihost is required for wifi connection")
            return False
        return await connect_wifi()
    elif app_context.connection_type.lower() == "usb":
        return await connect_usb()
    else:
        logger.error(f"Invalid connection type: {args.connection_type}")
        return False
