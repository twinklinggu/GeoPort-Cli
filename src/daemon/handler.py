"""Daemon command handler - CLI entry point for daemon mode."""

import threading
import time

from src.app.context import app_context
from src.daemon.monitor import daemon_monitor_loop
from src.utils.logging import logger


def handle_daemon(args) -> bool:
    """Handle the daemon command from CLI.

    Args:
        args: Parsed argparse arguments containing daemon parameters.

    Returns:
        bool: True if daemon completed successfully, False on error.
    """
    # Validate arguments
    if args.connection_type == "wifi" and args.wifihost is None:
        logger.error("Daemon: --wifihost is required for wifi connection type")
        return False

    # Populate app_context with daemon configuration
    app_context.daemon_mode = True
    app_context.daemon_latitude = args.lat
    app_context.daemon_longitude = args.lon
    app_context.daemon_auto_reconnect = not args.no_auto_reconnect
    app_context.connection_type = args.connection_type
    app_context.wifihost = args.wifihost
    app_context.udid = args.udid
    app_context.terminate_daemon_thread = False
    app_context.location_active = False

    # Start daemon monitor thread
    daemon_thread = threading.Thread(target=daemon_monitor_loop, daemon=True)
    app_context.daemon_thread = daemon_thread
    daemon_thread.start()

    logger.info("Daemon: Started in background, press Ctrl+C to exit")

    # Wait in main thread until termination signal
    try:
        while not app_context.terminate_daemon_thread:
            time.sleep(0.5)
    except KeyboardInterrupt:
        logger.info("\nDaemon: Received keyboard interrupt")
    finally:
        app_context.terminate_daemon_thread = True
        if daemon_thread.is_alive():
            daemon_thread.join(timeout=5.0)

    logger.info("Daemon: Shutdown complete")
    return True
