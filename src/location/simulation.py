"""Location simulation functionality."""

import asyncio
import threading
import time

from pymobiledevice3.remote.remote_service_discovery import (
    RemoteServiceDiscoveryService,
)
from pymobiledevice3.services.dvt.instruments.dvt_provider import DvtProvider
from pymobiledevice3.services.dvt.instruments.location_simulation import (
    LocationSimulation,
)

from src.app.context import app_context
from src.devices.connection import is_major_version_17_or_greater
from src.utils.logging import logger


async def set_location_thread(latitude: float, longitude: float):
    """Background thread that continuously maintains the location simulation."""
    app_context.terminate_location_thread = False

    try:
        if app_context.udid in app_context.rsd_data_map:
            if (
                app_context.connection_type
                in app_context.rsd_data_map[app_context.udid]
            ):
                rsd_data = app_context.rsd_data_map[app_context.udid][
                    app_context.connection_type
                ]
                app_context.rsd_host = rsd_data["host"]
                app_context.rsd_port = rsd_data["port"]

                logger.info(f"RSD in udid mapping is: {rsd_data}")
                logger.info("RSD already created. Reusing connection")
                logger.info(f"RSD Data: {rsd_data}")

                if (
                    app_context.ios_version is not None
                    and is_major_version_17_or_greater(app_context.ios_version)
                ):
                    async with RemoteServiceDiscoveryService(
                        (app_context.rsd_host, int(app_context.rsd_port))
                    ) as sp_rsd:
                        async with DvtProvider(sp_rsd) as dvt:
                            async with LocationSimulation(dvt) as location_simulation:
                                await location_simulation.set(latitude, longitude)
                                logger.warning("Location Set Successfully")
                                while not app_context.terminate_location_thread:
                                    time.sleep(0.5)

                elif (
                    app_context.ios_version is not None
                    and not is_major_version_17_or_greater(app_context.ios_version)
                ):
                    async with DvtProvider(app_context.lockdown) as dvt:
                        async with LocationSimulation(dvt) as location_simulation:
                            await location_simulation.clear()
                            await location_simulation.set(latitude, longitude)
                            logger.warning("Location Set Successfully")
                            while not app_context.terminate_location_thread:
                                time.sleep(0.5)

                await asyncio.sleep(1)

    except asyncio.CancelledError:
        pass
    except ConnectionResetError as cre:
        if "[Errno 54] Connection reset by peer" in str(cre):
            logger.error(
                "The Set Location buffer is full. Try to 'Stop Location' to clear old connections"
            )
    except Exception as e:
        logger.error(f"Error setting location: {e}")


def start_set_location_thread(latitude: float, longitude: float):
    """Start the location simulation in a separate thread."""
    stop_set_location_thread()
    app_context.terminate_location_thread = False

    async def run_async_function():
        await set_location_thread(latitude, longitude)

    location_thread = threading.Thread(target=lambda: asyncio.run(run_async_function()))
    location_thread.start()
    app_context.location_threads.append(location_thread)


def stop_set_location_thread():
    """Stop the location simulation thread."""
    app_context.terminate_location_thread = True


def handle_stop_location() -> bool:
    """Handle stop-location command from CLI."""
    try:
        stop_set_location_thread()
        logger.info(f"stop set location data:  {app_context.rsd_data}")

        async def clear_location():
            if app_context.udid in app_context.rsd_data_map:
                if (
                    app_context.connection_type
                    in app_context.rsd_data_map[app_context.udid]
                ):
                    rsd_data = app_context.rsd_data_map[app_context.udid][
                        app_context.connection_type
                    ]
                    app_context.rsd_host = rsd_data["host"]
                    app_context.rsd_port = rsd_data["port"]

                if (
                    app_context.ios_version is not None
                    and is_major_version_17_or_greater(app_context.ios_version)
                ):
                    async with RemoteServiceDiscoveryService(
                        (app_context.rsd_host, int(app_context.rsd_port))
                    ) as sp_rsd:
                        async with DvtProvider(sp_rsd) as dvt:
                            async with LocationSimulation(dvt) as location_simulation:
                                await location_simulation.clear()
                                logger.warning("Location Cleared Successfully")
                        return "Location cleared successfully"

                elif (
                    app_context.ios_version is not None
                    and not is_major_version_17_or_greater(app_context.ios_version)
                ):
                    async with DvtProvider(app_context.lockdown) as dvt:
                        async with LocationSimulation(dvt) as location_simulation:
                            await location_simulation.clear()
                            logger.warning("Location Cleared Successfully")
                        return "Location cleared successfully"
            return "Location cleared successfully"

        result = asyncio.run(clear_location())
        logger.info(result)
        return True
    except Exception as e:
        error_message = str(e)
        logger.error(f"Error stopping location: {error_message}")
        return False


def handle_set_location(args) -> bool:
    """Handle set-location command from CLI."""
    latitude = args.lat
    longitude = args.lon

    # If udid is provided, connect the device first
    if args.udid is not None:
        if args.connection_type is None:
            logger.error("--connection-type is required when --udid is provided")
            return False
        if args.connection_type == "wifi" and args.wifihost is None:
            logger.error("--wifihost is required for wifi connection")
            return False

        app_context.udid = args.udid
        app_context.connection_type = args.connection_type.capitalize()
        if args.wifihost:
            app_context.wifihost = args.wifihost

        if app_context.connection_type.lower() == "wifi":
            from src.devices.connection import connect_wifi

            connected = connect_wifi()
        else:
            from src.devices.connection import connect_usb

            connected = connect_usb()
        if not connected:
            logger.error("Failed to connect to device")
            return False

    if app_context.ios_version is None:
        logger.error(
            "No device connected. Please connect a device first using 'connect' command or provide --udid and --connection-type with set-location"
        )
        return False

    app_context.location = f"{latitude} {longitude}"

    if is_major_version_17_or_greater(app_context.ios_version):
        start_set_location_thread(latitude, longitude)
        logger.info(f"Location set successfully: {latitude}, {longitude}")
        logger.info("Press Ctrl+C to stop")
        try:
            while not app_context.terminate_location_thread:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("\nReceived interrupt, stopping location...")
            handle_stop_location()
        return True

    elif not is_major_version_17_or_greater(app_context.ios_version):
        from src.devices.developer_mode import mount_developer_image

        mount_developer_image()

        latitude, longitude = map(float, app_context.location.split())
        start_set_location_thread(latitude, longitude)
        logger.info(f"Location set successfully: {latitude}, {longitude}")
        logger.info("Press Ctrl+C to stop")
        try:
            while not app_context.terminate_location_thread:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("\nReceived interrupt, stopping location...")
            handle_stop_location()
        return True

    else:
        logger.error("No iOS version present")
        return False
