"""Developer mode enabling and checking."""

import asyncio
import subprocess
from typing import Optional, Tuple

from pymobiledevice3.common import get_home_folder
from pymobiledevice3.exceptions import DeviceHasPasscodeSetError
from pymobiledevice3.lockdown import create_using_usbmux
from pymobiledevice3.pair_records import (
    get_preferred_pair_record,
    get_remote_pairing_record_filename,
)
from pymobiledevice3.services.amfi import AmfiService

from src.app.context import app_context
from src.utils.logging import logger


def check_pair_record(udid: str):
    """Check and retrieve pairing record for the device."""
    logger.info(f"Connection Type: {app_context.connection_type}")
    logger.info("Enable Developer Mode")

    home = get_home_folder()
    logger.info(f"Pair Record Home: {home}")

    filename = get_remote_pairing_record_filename(udid)
    logger.info(f"Pair Record File: {filename}")

    pair_record = get_preferred_pair_record(udid, home)
    app_context.pair_record = pair_record
    return pair_record


async def check_developer_mode(udid: str, connection_type: str) -> bool:
    """Check if developer mode is enabled on the device."""
    try:
        logger.warning("Check Developer Mode")

        lockdown = await create_using_usbmux(
            udid, connection_type=connection_type, autopair=True
        )
        result = await lockdown.get_developer_mode_status()
        logger.info(f"Developer Mode Check result:  {result}")

        if result:
            logger.info("Developer Mode is true")
            return True
        else:
            logger.warning("Developer Mode is false")
            return False

    except subprocess.CalledProcessError:
        return False


async def enable_developer_mode(
    udid: str, connection_type: str
) -> Tuple[bool, Optional[str]]:
    """Enable developer mode on the device."""
    check_pair_record(udid)

    logger.info(f"Connection Type: {connection_type}")
    logger.info("Enable Developer Mode")

    home = get_home_folder()
    logger.info(f"Pair Record Home: {home}")

    if connection_type == "Network":
        if app_context.pair_record is None:
            logger.error(
                "Network: No Pair Record Found. Please use a USB cable first to create a pair record"
            )
            return (
                False,
                "No Pair Record Found. Please use a USB cable first to create a pair record",
            )
    else:
        logger.error("No Pair Record Found. USB cable detected. Creating a pair record")
        pass

    lockdown = await create_using_usbmux(
        udid,
        connection_type=connection_type,
        autopair=True,
        pairing_records_cache_folder=home,
    )
    await AmfiService(lockdown).enable_developer_mode()

    try:
        logger.info("Enable complete, mount developer image...")
        from src.devices.connection import mount_developer_image

        success, error_msg = await mount_developer_image()
        if not success:
            return False, error_msg

    except DeviceHasPasscodeSetError:
        error_message = (
            "Error: Device has a passcode set\n"
            " Please temporarily remove the passcode and run GeoPort again to enable Developer Mode\n"
            ' \n Go to "Settings - Face ID & Passcode"\n'
        )
        logger.error(f"{error_message}")
        return False, error_message

    return True, None


async def mount_developer_image() -> Tuple[bool, Optional[str]]:
    """Mount the developer image after enabling developer mode."""
    from pymobiledevice3.cli.mounter import auto_mount

    try:
        global_lockdown = await create_using_usbmux(app_context.udid, autopair=True)
        app_context.lockdown = global_lockdown
        logger.info(f"mount lockdown: {app_context.lockdown}")

        auto_mount(app_context.lockdown)

        logger.info("Developer image mounted successfully")
        return True, None
    except Exception as e:
        error_message = str(e)
        logger.error(f"Mount developer image error: {error_message}")
        return False, error_message


async def handle_enable_dev_mode(args) -> bool:
    """Handle enable-dev-mode command from CLI."""
    app_context.udid = args.udid
    app_context.connection_type = args.connection_type.capitalize()
    if args.wifihost:
        app_context.wifihost = args.wifihost

    success, error_msg = await enable_developer_mode(
        app_context.udid, app_context.connection_type
    )
    if success:
        logger.info("Developer mode enabled successfully")
        if error_msg:
            logger.warning(error_msg)
    else:
        logger.error(f"Failed to enable developer mode: {error_msg}")
    return success
