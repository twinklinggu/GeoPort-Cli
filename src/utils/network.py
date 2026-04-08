"""Network utilities - port selection, etc."""

import os

from src.utils.logging import logger


def create_geoport_folder():
    """Create GeoPort folder in user's home directory with proper permissions."""
    from src.config.settings import home_dir, platform_name

    geoport_folder = os.path.join(home_dir, "GeoPort")

    if not os.path.exists(geoport_folder):
        os.makedirs(geoport_folder)
        logger.info(f"GeoPort Home: {geoport_folder}")
        logger.info("GeoPort folder created successfully")

    # Set permissions for the GeoPort folder
    if platform_name == "Windows":
        # Windows permissions (read/write for everyone)
        os.system(f"icacls {geoport_folder} /grant Everyone:(OI)(CI)F")
        logger.info("Permissions set for GeoPort folder on Windows")
    else:  # Linux and MacOS
        # POSIX permissions (read/write for everyone)
        os.chmod(geoport_folder, 0o777)
        logger.info("Permissions set for GeoPort folder on MacOS")


def remove_ansi_escape_codes(text: str) -> str:
    """Remove ANSI escape codes from text."""
    import re

    ansi_escape = re.compile(r"\x1b[^m]*m")
    return ansi_escape.sub("", text)
