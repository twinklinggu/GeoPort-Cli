"""GeoPort - iOS Location Simulation CLI

Refactored from monolithic main.py into modular structure.
"""

import argparse
import asyncio
import os
import signal
import sys

# Add the project root to path so we can import src modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psutil

# pyuac is Windows-only, conditionally import
if sys.platform == "win32":
    import pyuac

import requests
from urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

# Import from our modules
from src.app.context import app_context
from src.config.settings import APP_VERSION_NUMBER, current_platform, is_windows
from src.daemon.handler import handle_daemon
from src.devices.connection import handle_connect
from src.devices.developer_mode import handle_enable_dev_mode
from src.devices.discovery import handle_list_devices
from src.location.simulation import (
    handle_set_location,
    handle_stop_location,
    stop_set_location_thread,
)
from src.tunnel.base import stop_tunnel_thread
from src.utils.logging import logger
from src.utils.network import create_geoport_folder

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


# Check sudo on macOS
if current_platform == "darwin":
    if os.geteuid() != 0:
        logger.error("*********************** WARNING ***********************")
        logger.error("Not running as Sudo, this probably isn't going to work")
        logger.error("*********************** WARNING ***********************")
        app_context.sudo_message = (
            "Not running as Sudo, this probably isn't going to work"
        )
    else:
        logger.info("Running as Sudo")
        app_context.sudo_message = ""


def clear_geoport():
    """Clear any running GeoPort processes."""
    logger.info("clear any GeoPort instances")
    substring = "GeoPort"

    for process in psutil.process_iter(["pid", "name"]):
        if substring in process.info["name"]:
            logger.info(
                f"Found process: {process.info['pid']} - {process.info['name']}"
            )
            process.terminate()
    logger.warning("No GeoPort found")


def clear_old_geoport():
    """Clear old GeoPort processes excluding current process."""
    logger.info("clear old GeoPort instances")
    substring = "GeoPort"
    current_pid = os.getpid()

    for process in psutil.process_iter(["pid", "name"]):
        if substring in process.info["name"] and process.info["pid"] != current_pid:
            logger.info(
                f"Found process: {process.info['pid']} - {process.info['name']}"
            )
            process.terminate()


def terminate_threads():
    """Terminate all non-main threads."""
    logger.info("Terminating all threads")
    for thread in threading.enumerate():
        if thread != threading.main_thread():
            logger.info(f"thread: {thread}")
            terminate_flag = threading.Event()
            terminate_flag.set()


def list_threads():
    """List all current threads."""
    for thread in threading.enumerate():
        logger.info(f"thread: {thread}")


def cancel_async_tasks():
    """Cancel all pending async tasks."""
    try:
        tasks = asyncio.all_tasks()
        for task in tasks:
            logger.info(f"task: {task}")
            task.cancel()
    except RuntimeError as e:
        if "no running event loop" in str(e):
            logger.error("No running event loop found.")
        else:
            raise e


def shutdown_server():
    """Shutdown cleanly - stop tunnels, location, and exit."""
    logger.warning("shutdown server")
    try:
        handle_stop_location()
    except Exception:
        pass
    # Stop daemon thread if running
    if app_context.daemon_mode and app_context.daemon_thread is not None:
        app_context.terminate_daemon_thread = True
        try:
            app_context.daemon_thread.join(timeout=5.0)
        except Exception:
            pass
        # Reset daemon state
        app_context.daemon_mode = False
        app_context.daemon_thread = None
    stop_set_location_thread()
    stop_tunnel_thread()
    cancel_async_tasks()
    terminate_threads()
    clear_geoport()
    logger.error("OS Kill")
    os._exit(0)


def handle_clear():
    """Handle clear command - stop all connections and exit."""
    logger.warning("Clearing all connections and exiting GeoPort")
    shutdown_server()


def signal_handler(signum, frame):
    """Handle interrupt signals for clean shutdown."""
    logger.info("\nReceived interrupt signal, cleaning up...")
    shutdown_server()


def main():
    """Main entry point - parse arguments and dispatch commands."""
    parser = argparse.ArgumentParser(
        description="GeoPort - iOS Location Simulation CLI",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True, help="Command")

    # list-devices
    subparsers.add_parser(
        "list-devices", help="List all connected iOS devices (USB + WiFi)"
    )

    # connect
    parser_connect = subparsers.add_parser(
        "connect", help="Connect to a specified device"
    )
    parser_connect.add_argument("--udid", required=True, help="Device UDID")
    parser_connect.add_argument(
        "--connection-type",
        required=True,
        choices=["usb", "wifi"],
        help="Connection type",
    )
    parser_connect.add_argument(
        "--wifihost", help="WiFi IP address (required for wifi connection type)"
    )

    # enable-dev-mode
    parser_enable = subparsers.add_parser(
        "enable-dev-mode", help="Enable developer mode on device"
    )
    parser_enable.add_argument("--udid", required=True, help="Device UDID")
    parser_enable.add_argument(
        "--connection-type",
        required=True,
        choices=["usb", "wifi"],
        help="Connection type",
    )
    parser_enable.add_argument(
        "--wifihost", help="WiFi IP address (for wifi connection)"
    )

    # set-location
    parser_set = subparsers.add_parser(
        "set-location", help="Start continuous location simulation"
    )
    parser_set.add_argument("--lat", type=float, required=True, help="Latitude")
    parser_set.add_argument("--lon", type=float, required=True, help="Longitude")
    parser_set.add_argument(
        "--udid", help="Device UDID (connect this device before setting location)"
    )
    parser_set.add_argument(
        "--connection-type",
        choices=["usb", "wifi"],
        help="Connection type (required if --udid provided)",
    )
    parser_set.add_argument(
        "--wifihost", help="WiFi IP address (required for wifi connection type)"
    )

    # stop-location
    subparsers.add_parser("stop-location", help="Stop location simulation")

    # daemon
    parser_daemon = subparsers.add_parser(
        "daemon",
        help="Daemon mode - continuously monitor and auto-set location on device connection",
    )
    parser_daemon.add_argument("--lat", type=float, required=True, help="Latitude")
    parser_daemon.add_argument("--lon", type=float, required=True, help="Longitude")
    parser_daemon.add_argument(
        "--connection-type",
        required=True,
        choices=["usb", "wifi"],
        help="Connection type",
    )
    parser_daemon.add_argument(
        "--wifihost", help="WiFi IP address (required for wifi connection type)"
    )
    parser_daemon.add_argument(
        "--udid", help="Specific device UDID (if not provided, uses first device found)"
    )
    parser_daemon.add_argument(
        "--no-auto-reconnect",
        action="store_true",
        help="Disable auto-reconnect on device disconnect",
    )

    # clear
    subparsers.add_parser("clear", help="Stop all tunnels/threads and clean up exit")

    # version
    subparsers.add_parser("version", help="Show application version")

    args = parser.parse_args()

    # Add signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Create GeoPort folder
    create_geoport_folder()

    # Windows: check admin and relaunch if needed
    if is_windows:
        try:
            import pyi_splash

            pyi_splash.update_text("CLI Loaded ...")
            logger.info("clear splash")
            pyi_splash.close()
        except:
            pass
        if not pyuac.isUserAdmin():
            print("Relaunching as Admin")
            pyuac.runAsAdmin()
            sys.exit(0)

    # Dispatch based on command
    if args.command == "list-devices":
        success = handle_list_devices()
        sys.exit(0 if success else 1)
    elif args.command == "connect":
        success = handle_connect(args)
        sys.exit(0 if success else 1)
    elif args.command == "enable-dev-mode":
        success = handle_enable_dev_mode(args)
        sys.exit(0 if success else 1)
    elif args.command == "set-location":
        success = handle_set_location(args)
        sys.exit(0 if success else 1)
    elif args.command == "stop-location":
        success = handle_stop_location()
        sys.exit(0 if success else 1)
    elif args.command == "daemon":
        success = handle_daemon(args)
        sys.exit(0 if success else 1)
    elif args.command == "clear":
        handle_clear()
        sys.exit(0)
    elif args.command == "version":
        print(f"GeoPort version {APP_VERSION_NUMBER}")
        sys.exit(0)


if __name__ == "__main__":
    import threading

    main()
