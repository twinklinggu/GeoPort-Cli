"""Application configuration and constants."""

import os
import sys

from pymobiledevice3.bonjour import DEFAULT_BONJOUR_TIMEOUT

# GitHub repository information
GITHUB_REPO = "davesc63/GeoPort"
CURRENT_VERSION_FILE = "CURRENT_VERSION"
BROADCAST_FILE = "BROADCAST"
APP_VERSION_NUMBER = "4.0.2"

# Default network settings
DEFAULT_BONJOUR_TIMEOUT = DEFAULT_BONJOUR_TIMEOUT
MIN_RANDOM_PORT = 49215
MAX_RANDOM_PORT = 65535
FALLBACK_PORT = 54321

# Platform detection
current_platform = sys.platform
is_windows = sys.platform == "win32"
platform_name = {
    "win32": "Windows",
    "linux": "Linux",
    "darwin": "MacOS",
}.get(current_platform, "Unknown")

# File paths
home_dir = os.path.expanduser("~")
base_directory = getattr(
    sys, "_MEIPASS", os.path.abspath(os.path.dirname(os.path.dirname(sys.argv[0])))
)
