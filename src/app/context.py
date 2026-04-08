"""Application context that encapsulates all global state."""

import threading
from typing import Any, Dict, List, Optional

from pymobiledevice3.lockdown import LockdownClient


class AppContext:
    """Application state context holding all global variables."""

    def __init__(self):
        # Device and connection state
        self.udid: Optional[str] = None
        self.connection_type: Optional[str] = None
        self.ios_version: Optional[str] = None
        self.lockdown: Optional[LockdownClient] = None
        self.pair_record: Optional[Any] = None

        # RSD (Remote Service Discovery) state
        self.rsd_data: Optional[tuple] = None
        self.rsd_host: Optional[str] = None
        self.rsd_port: Optional[str] = None
        self.rsd_data_map: Dict[str, Dict[str, Dict[str, Optional[str]]]] = {}

        # WiFi specific state
        self.wifihost: Optional[str] = None
        self.wifi_address: Optional[str] = None
        self.wifi_port: Optional[int] = None

        # Location state
        self.location: Optional[str] = None
        self.terminate_location_thread: bool = False
        self.location_threads: List[threading.Thread] = []

        # Tunnel state
        self.terminate_tunnel_thread: bool = False

        # Error and message state
        self.error_message: Optional[str] = None
        self.sudo_message: str = ""
        self.captured_output: Optional[str] = None


# Global context instance for single-user application
app_context = AppContext()
