"""Daemon monitor loop - continuously checks for device connections."""

import asyncio
import time
from typing import Optional

from pymobiledevice3.usbmux import list_devices

from src.app.context import app_context
from src.devices.connection import connect_usb, connect_wifi
from src.location.simulation import start_set_location_thread, stop_set_location_thread
from src.tunnel.base import stop_tunnel_thread
from src.utils.logging import logger


def _list_devices_sync():
    """Helper to get list of devices synchronously."""
    return asyncio.run(list_devices())


POLL_INTERVAL = 2  # seconds between device checks


def find_matching_device() -> Optional[str]:
    """Find a device matching the current connection type and optional UDID."""
    target_udid = app_context.udid
    connection_type = app_context.connection_type

    try:
        if connection_type == "usb":
            devices = _list_devices_sync()
            if not devices:
                return None

            # If specific UDID requested
            if target_udid is not None:
                for device in devices:
                    if device.serial == target_udid:
                        return device.serial
                return None

            # Return first device found
            return devices[0].serial

        elif connection_type == "wifi":
            # For WiFi, we need the wifihost already set
            if app_context.wifihost is None:
                return None
            return target_udid

    except Exception as e:
        logger.error(f"Error looking for devices: {e}")
        return None

    return None


def handle_device_connected() -> bool:
    """Handle a newly connected device - connect and start location simulation."""
    logger.info("Daemon: Device detected, connecting...")

    # Find the matching device UDID if not specified
    if app_context.udid is None:
        found_udid = find_matching_device()
        if found_udid is None:
            logger.warning("Daemon: No matching device found")
            return False
        app_context.udid = found_udid

    # Connect based on connection type
    connection_type = app_context.connection_type
    try:
        if connection_type == "usb":
            success = asyncio.run(connect_usb())
        elif connection_type == "wifi":
            success = asyncio.run(connect_wifi())
        else:
            logger.error(f"Daemon: Unknown connection type {connection_type}")
            return False

        if not success:
            logger.error("Daemon: Failed to connect to device")
            return False

        logger.info(f"Daemon: Connected to device {app_context.udid} successfully")

        # Start location simulation
        lat = app_context.daemon_latitude
        lon = app_context.daemon_longitude

        if lat is None or lon is None:
            logger.error("Daemon: Latitude/longitude not configured")
            return False

        start_set_location_thread(lat, lon)
        logger.info(f"Daemon: Location set to {lat}, {lon}")
        return True

    except Exception as e:
        logger.error(f"Daemon: Error connecting to device: {e}")
        return False


def handle_device_disconnected() -> None:
    """Handle device disconnection - stop location simulation and cleanup."""
    logger.warning("Daemon: Device disconnected")
    current_udid = app_context.udid
    try:
        stop_set_location_thread()
        stop_tunnel_thread()
        # Clean up stale rsd_data_map entry
        if current_udid and current_udid in app_context.rsd_data_map:
            del app_context.rsd_data_map[current_udid]
    except Exception as e:
        logger.error(f"Daemon: Error during disconnect cleanup: {e}")
    finally:
        # Clear current UDID so we'll find it again on reconnect
        app_context.udid = None


def check_connection_alive() -> bool:
    """Check if the current device connection is still alive."""
    if app_context.udid is None:
        return False

    try:
        # Try to list devices and see if our UDID is still present
        devices = _list_devices_sync()
        for device in devices:
            if device.serial == app_context.udid:
                return True
        return False
    except Exception:
        return False


def daemon_monitor_loop() -> None:
    """Main daemon monitor loop - runs in a background thread."""
    logger.info("Daemon: Starting device monitor")
    lat = app_context.daemon_latitude
    lon = app_context.daemon_longitude
    logger.info(f"Daemon: Target location - lat={lat}, lon={lon}")
    logger.info(f"Daemon: Connection type - {app_context.connection_type}")
    if app_context.udid:
        logger.info(f"Daemon: Target UDID - {app_context.udid}")
    else:
        logger.info("Daemon: Target UDID - any first matching device")
    auto_reconnect = "enabled" if app_context.daemon_auto_reconnect else "disabled"
    logger.info(f"Daemon: Auto-reconnect - {auto_reconnect}")

    while not app_context.terminate_daemon_thread:
        if not app_context.location_active:
            # Waiting for device to connect
            udid = find_matching_device()

            if udid is not None:
                # Device found, connect and start location
                if udid:
                    app_context.udid = udid
                success = handle_device_connected()
                if success:
                    app_context.location_active = True
            # If no device found, just continue to sleep

        elif not check_connection_alive():
            # Location is active, check if connection is still alive
            handle_device_disconnected()
            app_context.location_active = False
            if not app_context.daemon_auto_reconnect:
                logger.info("Daemon: Auto-reconnect disabled, exiting monitor")
                app_context.terminate_daemon_thread = True
                break

        # Sleep before next check
        for _ in range(int(POLL_INTERVAL * 10)):
            if app_context.terminate_daemon_thread:
                break
            time.sleep(0.1)

    logger.info("Daemon: Monitor thread exiting")
