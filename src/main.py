import asyncio
import argparse
import logging
import os
import psutil
import re
import requests
import signal
import subprocess
import sys
import threading
import time

# pyuac is Windows-only, conditionally import
if sys.platform == 'win32':
    import pyuac

from urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

from pymobiledevice3.usbmux import list_devices
from pymobiledevice3.cli.mounter import auto_mount
from pymobiledevice3.lockdown import create_using_usbmux, create_using_tcp, get_mobdev2_lockdowns
from pymobiledevice3.services.amfi import AmfiService
from pymobiledevice3.exceptions import DeviceHasPasscodeSetError, NoDeviceConnectedError
from pymobiledevice3.services.dvt.instruments.dvt_provider import DvtProvider
from pymobiledevice3.services.dvt.instruments.location_simulation import LocationSimulation
from pymobiledevice3.remote.remote_service_discovery import RemoteServiceDiscoveryService
from pymobiledevice3.remote.utils import stop_remoted_if_required, resume_remoted_if_required, get_rsds
from pymobiledevice3.remote.tunnel_service import create_core_device_tunnel_service_using_rsd, get_remote_pairing_tunnel_services, start_tunnel, create_core_device_tunnel_service_using_remotepairing, get_core_device_tunnel_services, CoreDeviceTunnelProxy
#from pymobiledevice3.cli.remote import install_driver_if_required
from pymobiledevice3.osu.os_utils import get_os_utils
from pymobiledevice3.bonjour import DEFAULT_BONJOUR_TIMEOUT, browse_mobdev2
from pymobiledevice3.pair_records import get_local_pairing_record, get_remote_pairing_record_filename, get_preferred_pair_record
from pymobiledevice3.common import get_home_folder
# from pymobiledevice3.cli.remote import cli_install_wetest_drivers

from pymobiledevice3.cli.remote import tunnel_task
from pymobiledevice3.lockdown import LockdownClient
from pymobiledevice3.lockdown_service_provider import LockdownServiceProvider
from pymobiledevice3.remote.common import TunnelProtocol

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
OSUTILS = get_os_utils()


import logging

# Get or create a logger instance named "GeoPort"
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)

# Create a logger named "GeoPort"
logger = logging.getLogger("GeoPort")
logging.getLogger("urllib3").setLevel(logging.WARNING)

# Define constants
# Get the home directory of the current user
home_dir = os.path.expanduser("~")
is_windows = sys.platform == 'win32'
base_directory = getattr(sys, '_MEIPASS', os.path.abspath(os.path.dirname(sys.argv[0])))
location = None
rsd_data = None
rsd_host = None
rsd_port = None
rsd_data_map = {}
wifi_address = None
wifihost = None
wifi_port = None
connection_type = None
udid = None
lockdown = None
ios_version = None
pair_record = None
error_message = None
sudo_message = ""
captured_output = None
GITHUB_REPO = 'davesc63/GeoPort'
CURRENT_VERSION_FILE = 'CURRENT_VERSION'
BROADCAST_FILE = 'BROADCAST'
APP_VERSION_NUMBER = "4.0.2"
terminate_tunnel_thread = False
terminate_location_thread = False
location_threads = []
timeout = DEFAULT_BONJOUR_TIMEOUT

# Get the current platform using sys.platform
current_platform = sys.platform

# Map the platform names to standard values
platform = {
    'win32': 'Windows',
    'linux': 'Linux',
    'darwin': 'MacOS',
}.get(current_platform, 'Unknown')

# Check if running as sudo
if current_platform == "darwin":
    if os.geteuid() != 0:
        logger.error("*********************** WARNING ***********************")
        logger.error("Not running as Sudo, this probably isn't going to work")
        logger.error("*********************** WARNING ***********************")
        sudo_message = "Not running as Sudo, this probably isn't going to work"
    else:
        logger.info("Running as Sudo")
        sudo_message = ""


def create_geoport_folder():
    # Define the path to the GeoPort folder
    geoport_folder = os.path.join(home_dir, 'GeoPort')

    # Check if the GeoPort folder exists, create it if not
    if not os.path.exists(geoport_folder):
        os.makedirs(geoport_folder)
        logger.info(f"GeoPort Home: {geoport_folder}")
        logger.info("GeoPort folder created successfully")

    # Set permissions for the GeoPort folder
    if current_platform == 'win32':
        # Windows permissions (read/write for everyone)
        os.system(f"icacls {geoport_folder} /grant Everyone:(OI)(CI)F")
        logger.info("Permissions set for GeoPort folder on Windows")
    else:  # Linux and MacOS
        # POSIX permissions (read/write for everyone)
        os.chmod(geoport_folder, 0o777)
        logger.info("Permissions set for GeoPort folder on MacOS")


# Define the function to be executed in the thread
def run_tunnel(service_provider):

    try:
        asyncio.run(start_quic_tunnel(service_provider))

        logger.info("run_tunnel completed")
        sys.exit(0)

    except Exception as e:
        error_message = str(e)

        # Handle the exception, such as logging it
        logger.error(f"Tunnel error: {error_message}", exc_info=True)
        sys.exit(1)

# Define a function to start the tunnel thread
def start_tunnel_thread(service_provider):
    global terminate_tunnel_thread  # Declare the global variable
    terminate_tunnel_thread = False  # Set the value of the global variable
    thread = threading.Thread(target=run_tunnel, args=(service_provider,))
    thread.start()
    return

async def start_quic_tunnel(service_provider: RemoteServiceDiscoveryService) -> None:

    logger.warning("Start USB QUIC tunnel")

    global terminate_tunnel_thread
    stop_remoted_if_required()
    #install_driver_if_required()

    # if sys.platform == 'win32':
    #     logger.info("Windows System - Driver Check Required")
    #     if version_check(ios_version):
    #         logger.warning("Installing WeTest Driver - QUIC Tunnel")
    #         cli_install_wetest_drivers()

    service = await create_core_device_tunnel_service_using_rsd(service_provider, autopair=True)

    async with service.start_quic_tunnel() as tunnel_result:
        resume_remoted_if_required()

        logger.info(f"QUIC Address: {tunnel_result.address}")
        logger.info(f"QUIC Port: {tunnel_result.port}")
        global rsd_port
        global rsd_host
        rsd_host = tunnel_result.address

        rsd_port = str(tunnel_result.port)


        while True:
            if terminate_tunnel_thread is True:
                return
            # wait user input while the asyncio tasks execute
            await asyncio.sleep(.5)


# Define the function to be executed in the thread
def run_tcp_tunnel(service_provider):

    try:
        asyncio.run(start_tcp_tunnel(service_provider))

        logger.info("run_tcp_tunnel completed")
        return

    except Exception as e:
        error_message = str(e)
        logger.error(f"TCP tunnel error: {error_message}", exc_info=True)

        # Handle the exception, such as logging it or returning an error response
        return

# Define a function to start the tunnel thread
def start_tcp_tunnel_thread(target_udid):
    global terminate_tunnel_thread  # Declare the global variable
    terminate_tunnel_thread = False  # Set the value of the global variable
    thread = threading.Thread(target=run_tcp_tunnel, args=(target_udid,))
    thread.start()
    return

async def start_tcp_tunnel(target_udid: str) -> None:

    logger.warning("Start USB TCP tunnel")

    global terminate_tunnel_thread
    stop_remoted_if_required()
    #install_driver_if_required()

    #service = await create_core_device_tunnel_service_using_rsd(service_provider, autopair=True)

    # Create lockdown inside this async context to avoid event loop conflicts
    lockdown = await create_using_usbmux(target_udid, autopair=True)
    logger.info(f"Created lockdown in tunnel thread: {lockdown}")
    # New API: use create factory method
    service = await CoreDeviceTunnelProxy.create(lockdown)
    #asyncio.run(tunnel_task(service, secrets=None, protocol=TunnelProtocol.TCP), debug=True)
    async with service.start_tcp_tunnel() as tunnel_result:
        logger.info(f"TCP Address: {tunnel_result.address}")
        logger.info(f"TCP Port: {tunnel_result.port}")
        global rsd_port
        global rsd_host
        rsd_host = tunnel_result.address

        rsd_port = str(tunnel_result.port)

        while True:
            if terminate_tunnel_thread is True:
                return
            # wait user input while the asyncio tasks execute
            await asyncio.sleep(.5)



def is_major_version_17_or_greater(version_string):
    # Check if the major version in the given version string is 17 or greater.
    try:
        major_version = int(version_string.split('.')[0])
        return major_version >= 17
    except (ValueError, IndexError):
        # Handle invalid version string or missing major version
        return False

def is_major_version_less_than_16(version_string):
    # Check if the major version in the given version string is 17 or greater.
    try:
        major_version = int(version_string.split('.')[0])
        return major_version < 16
    except (ValueError, IndexError):
        # Handle invalid version string or missing major version
        logger.error(f"Error: {ValueError}, {IndexError}")
        return False


def version_check(version_string):
    try:
        # Split the version string into major and minor version parts
        version_parts = version_string.split('.')

        # Extract the major and minor version parts
        major_version = int(version_parts[0])
        minor_version = int(version_parts[1]) if len(version_parts) > 1 else 0

        # Check if the version string satisfies the condition
        if major_version == 17 and 0 <= minor_version <= 3:
            if sys.platform == 'win32':
                logger.info("Checking Windows Driver requirement")
                logger.info("Driver is required")
            return True
        else:
            if sys.platform == 'win32':
                logger.info("Driver is not required")
                return False
            logger.info("MacOS - pass")
            return False


    except (ValueError, IndexError) as e:
        logger.error(f"Driver check error: {e}")
        # Handle invalid version string or missing major/minor version
        return False

def get_devices_with_retry(max_attempts=10):
    if sys.platform == 'win32' and ios_version is not None:
        logger.info(f"iOS Version: {ios_version}")
        if version_check(ios_version):
            logger.info("Windows Driver Install Required")
            # cli_install_wetest_drivers()  # Removed in pymobiledevice3 9.9.0
    for attempt in range(1, max_attempts + 1):
        try:
            devices = asyncio.run(get_rsds(timeout))
            #dev1 = asyncio.run(get_rsds(timeout))
            #devices = asyncio.run(get_core_device_tunnel_services(timeout))
            #print("devices: ", devices)
            #print("dev1: ", dev1)
            if devices:
                return devices  # Return devices if the list is not empty
            else:
                logger.warning(f"Attempt {attempt}: No devices found")
        except Exception as e:
            logger.warning(f"Attempt {attempt}: Error occurred - {e}")
        time.sleep(1)  # Add a delay between attempts if needed
    raise RuntimeError("No devices found after multiple attempts.\n Ensure you are running GeoPort as sudo / Administrator \n Please see the FAQ: https://github.com/davesc63/GeoPort/blob/main/FAQ.md \n If you still have the error please raise an issue on github: https://github.com/davesc63/GeoPort/issues ")


def get_wifi_with_retry(max_attempts=10):
    global udid, wifi_address, wifi_port

    for attempt in range(1, max_attempts + 1):
        try:
            logger.info("Discovering Wifi Devices - This may take a while...")
            devices = asyncio.run(get_remote_pairing_tunnel_services(timeout))
            #devices = get_remote_pairing_tunnel_services(timeout)


            if devices:
                if udid:
                    for device in devices:
                        if device.remote_identifier == udid:
                            logger.info(f"Device found with udid: {udid}.")
                            wifi_address = device.hostname
                            wifi_port = device.port
                            return device
                else:
                    return devices
            else:
                logger.warning(f"Attempt {attempt}: No devices found")
        except Exception as e:
            logger.warning(f"Attempt {attempt}: Error occurred - {e}")

        # Add a delay between attempts
        time.sleep(1)

    raise RuntimeError("No devices found after multiple attempts. Please see the FAQ.")

def stop_tunnel_thread():
    global terminate_tunnel_thread
    logger.info("stop tunnel thread")
    # Set the terminate flag to True to stop the thread
    terminate_tunnel_thread = True
    logger.info("Tunnel stopped")

def check_pair_record(udid):
    global pair_record
    logger.info(f"Connection Type: {connection_type}")
    logger.info("Enable Developer Mode")

    home = get_home_folder()
    logger.info(f"Pair Record Home: {home}")

    filename = get_remote_pairing_record_filename(udid)
    logger.info(f"Pair Record File: {filename}")

    # pair_record = get_local_pairing_record(filename, home)
    pair_record = get_preferred_pair_record(udid, home)
    #logger.info(f"Pair Record: {pair_record}")
    return pair_record

def check_developer_mode(udid, connection_type):
    try:

        logger.warning("Check Developer Mode")

        async def check():
            lockdown = await create_using_usbmux(udid, connection_type=connection_type, autopair=True)
            result = await lockdown.get_developer_mode_status()
            return result

        result = asyncio.run(check())
        logger.info(f"Developer Mode Check result:  {result}")

        # Check if developer mode is enabled
        if result:
            logger.info("Developer Mode is true")
            return True
        else:
            logger.warning("Developer Mode is false")
            return False

    except subprocess.CalledProcessError:
        return False


def enable_developer_mode(udid, connection_type):
    check_pair_record(udid)

    logger.info(f"Connection Type: {connection_type}")
    logger.info("Enable Developer Mode")

    home = get_home_folder()
    logger.info(f"Pair Record Home: {home}")
    #
    # filename = get_remote_pairing_record_filename(udid)
    # logger.info(f"Pair Record File: {filename}")
    #
    # pair_record = get_local_pairing_record(filename, home)
    # logger.info(f"Pair Record: {pair_record}")
    if connection_type == "Network":
        if pair_record is None:
            logger.error("Network: No Pair Record Found. Please use a USB cable first to create a pair record")
            return False, "No Pair Record Found. Please use a USB cable first to create a pair record"
    else:
        logger.error("No Pair Record Found. USB cable detected. Creating a pair record")
        pass
        #return False, "No Pair Record Found. Please use a USB cable first to create a pair record"

    async def enable():
        lockdown = await create_using_usbmux(
            udid,
            connection_type=connection_type,
            autopair=True,
            pairing_records_cache_folder=home)
        await AmfiService(lockdown).enable_developer_mode()

    try:
        asyncio.run(enable())
        logger.info("Enable complete, mount developer image...")
        mount_developer_image()

    except DeviceHasPasscodeSetError:
        error_message = "Error: Device has a passcode set\n \n Please temporarily remove the passcode and run GeoPort again to enable Developer Mode \n \n Go to \"Settings - Face ID & Passcode\"\n"
        logger.error(f"{error_message}")
        return False, error_message

    # except Exception as e:  # Catch any other exception
    #     logger.error(f"An error occurred: {str(e)}")
    #     return False, f"An error occurred: {str(e)}"

    return True, None

def mount_developer_image():
    try:

        global lockdown
        lockdown = asyncio.run(create_using_usbmux(udid, autopair=True))
        logger.info(f"mount lockdown: {lockdown}")

        auto_mount(lockdown)

        logger.info("Developer image mounted successfully")
    except Exception as e:
        error_message = str(e)
        logger.error(f"Mount developer image error: {error_message}")
        return False, error_message
    return True, None

async def set_location_thread(latitude, longitude):
    global terminate_location_thread

    try:
        global rsd_host, rsd_port, udid, ios_version, connection_type

        if udid in rsd_data_map:
            if connection_type in rsd_data_map[udid]:
                rsd_data = rsd_data_map[udid][connection_type]
                rsd_host = rsd_data['host']
                rsd_port = rsd_data['port']

                logger.info(f"RSD in udid mapping is: {rsd_data}")
                logger.info("RSD already created. Reusing connection")
                logger.info(f"RSD Data: {rsd_data}")


                if ios_version is not None and is_major_version_17_or_greater(ios_version):
                    async with RemoteServiceDiscoveryService((rsd_host, int(rsd_port))) as sp_rsd:
                        async with DvtProvider(sp_rsd) as dvt:
                            async with LocationSimulation(dvt) as location_simulation:
                                await location_simulation.set(latitude, longitude)
                                logger.warning("Location Set Successfully")
                                #OSUTILS.wait_return()
                                while not terminate_location_thread:
                                    time.sleep(0.5)


                elif ios_version is not None and not is_major_version_17_or_greater(ios_version):
                    async with DvtProvider(lockdown) as dvt:
                        async with LocationSimulation(dvt) as location_simulation:
                            await location_simulation.clear()
                            await location_simulation.set(latitude, longitude)
                            logger.warning("Location Set Successfully")
                            #await asyncio.wait_for(OSUTILS.wait_return(), timeout=1)  # Adjust timeout as needed
                            while not terminate_location_thread:
                                time.sleep(0.5)

                await asyncio.sleep(1)  # Adjust sleep time according to your requirements

    except asyncio.CancelledError:
        # Handle cancellation gracefully
        pass
    except ConnectionResetError as cre:
        if "[Errno 54] Connection reset by peer" in str(cre):
            logger.error("The Set Location buffer is full. Try to 'Stop Location' to clear old connections")
    except Exception as e:
        logger.error(f"Error setting location: {e}")


# Function to start the set_location_thread in a separate thread
def start_set_location_thread(latitude, longitude):
    global terminate_location_thread
    # Stop existing threads
    stop_set_location_thread()

    # Reset the terminate flag before starting the thread
    terminate_location_thread = False


    # Define a helper function to run the async function in the thread
    async def run_async_function():
        await set_location_thread(latitude, longitude)

    # Create a new thread and start it
    location_thread = threading.Thread(target=lambda: asyncio.run(run_async_function()))
    location_thread.start()


# Function to stop the location thread
def stop_set_location_thread():
    # Set the flag to indicate that the thread should stop
    global terminate_location_thread
    terminate_location_thread = True


def handle_stop_location():
    try:
        stop_set_location_thread()
        global rsd_data
        global rsd_host
        global rsd_port
        global lockdown
        global ios_version, udid, connection_type
        logger.info(f"stop set location data:  {rsd_data}")

        async def clear_location():
            global rsd_data, rsd_host, rsd_port
            if udid in rsd_data_map:
                if connection_type in rsd_data_map[udid]:
                    rsd_data = rsd_data_map[udid][connection_type]

                    rsd_host = rsd_data['host']
                    rsd_port = rsd_data['port']

                if ios_version is not None and is_major_version_17_or_greater(ios_version):
                    async with RemoteServiceDiscoveryService((rsd_host, int(rsd_port))) as sp_rsd:
                        async with DvtProvider(sp_rsd) as dvt:
                            async with LocationSimulation(dvt) as location_simulation:
                                await location_simulation.clear()
                                logger.warning("Location Cleared Successfully")
                        return "Location cleared successfully"

                elif ios_version is not None and not is_major_version_17_or_greater(ios_version):
                    async with DvtProvider(lockdown) as dvt:
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

def get_github_version():
    try:
        # Make a request to the GitHub API to get the content of CURRENT_VERSION file
        url = f'https://raw.githubusercontent.com/{GITHUB_REPO}/main/{CURRENT_VERSION_FILE}'
        response = requests.get(url)

        response.raise_for_status()

        # Parse the content of the file
        github_version = response.text.strip()

        return github_version
    except requests.RequestException as e:

        return None


def get_github_broadcast():
    try:
        # Make a request to the GitHub API to get the content of CURRENT_VERSION file
        url = f'https://raw.githubusercontent.com/{GITHUB_REPO}/main/{BROADCAST_FILE}'
        logger.error(f"Github URL: {url}")

        response = requests.get(url, verify=False)
        logger.error(f"github response: {response}")
        #response.raise_for_status()

        # Parse the content of the file
        github_broadcast = response.text.strip()
        logger.error(f"GITHUB BROADCAST MESSAGE:")

        return github_broadcast
    except requests.RequestException as e:

        return None


def remove_ansi_escape_codes(text):
    ansi_escape = re.compile(r'\x1b[^m]*m')
    return ansi_escape.sub('', text)

async def get_network_devices():
# you can also query network lockdown instances using the following:
    async for ip, lockdown in get_mobdev2_lockdowns():
        print(ip, lockdown.short_info)

def handle_list_devices():
    try:
        connected_devices = {}

        # Retrieve all devices
        all_devices = asyncio.run(list_devices())
        #wifi_devices = None
        #wifi_devices = asyncio.run(get_network_devices())
        logger.info(f"\n\nRaw Devices:  {all_devices}\n")
        #logger.info(f"\n\nWifi Devices:  {wifi_devices}\n")

        if wifihost:
            udid_parsed = udid
            logger.warning(f"Wifi requested to {wifihost}")
            logger.warning(f"udid: {udid_parsed}")
            lockdown = asyncio.run(create_using_tcp(hostname=wifihost, identifier=udid_parsed))

            # udid = lockdown.udid
            # print("wifi udid", udid)
            info = lockdown.short_info
            logger.warning(f"Wifi Short Info: {info}")
            # enable_wifi_connections属性已在新版本pymobiledevice3中移除
            wifi_connection_state = True
            info['wifiState'] = wifi_connection_state

            info['ConnectionType'] = 'Network'

            # Substitute "Network" with "Wifi" in the connection_type
            connection_type = "Manual Wifi"
            # if connection_type == "Network":
            #     connection_type = "Wifi"

            # If the serial already exists in the connected_devices dictionary
            if udid_parsed in connected_devices:
                # If the connection_type already exists under the serial, append the device to the list
                if connection_type in connected_devices[udid_parsed]:
                    connected_devices[udid_parsed][connection_type].append(info)
                # If the connection_type doesn't exist under the serial, create a new list with the device
                else:
                    connected_devices[udid_parsed][connection_type] = [info]
            # If the serial is new, create a new dictionary entry with the connection_type as a list
            else:
                connected_devices[udid_parsed] = {connection_type: [info]}

        # Iterate through all devices
        for device in all_devices:
            device_udid = device.serial
            device_connection_type = device.connection_type

            # Create lockdown and info variables
            #global lockdown
            device_lockdown = asyncio.run(create_using_usbmux(device_udid, connection_type=device_connection_type, autopair=True))
            info = device_lockdown.short_info

            # enable_wifi_connections属性已在新版本pymobiledevice3中移除
            wifi_connection_state = True

            # Modify the info dictionary to include wifiConState
            info['wifiState'] = wifi_connection_state

            # Substitute "Network" with "Wifi" in the connection_type
            if device_connection_type == "Network":
                device_connection_type = "Wifi"

            # If the serial already exists in the connected_devices dictionary
            if device_udid in connected_devices:
                # If the connection_type already exists under the serial, append the device to the list
                if device_connection_type in connected_devices[device_udid]:
                    connected_devices[device_udid][device_connection_type].append(info)
                # If the connection_type doesn't exist under the serial, create a new list with the device
                else:
                    connected_devices[device_udid][device_connection_type] = [info]
            # If the serial is new, create a new dictionary entry with the connection_type as a list
            else:
                connected_devices[device_udid] = {device_connection_type: [info]}

        logger.info(f"\n=== Connected Devices ===\n")
        for device_udid, connections in connected_devices.items():
            logger.info(f"\nUDID: {device_udid}")
            for conn_type, devices_info in connections.items():
                for info in devices_info:
                    logger.info(f"  {conn_type}: {info}")
        logger.info(f"\n====================\n")

        # Check if running as sudo
        if current_platform == "darwin":
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

def check_rsd_data():
    max_attempts = 30
    attempts = 0
    while attempts < max_attempts:
        if rsd_host is not None and rsd_port is not None:
            return True  # Data is available
        time.sleep(1)
        attempts += 1
    logger.error("RSD Data is still None after multiple attempts")
    return False  # Data is still None after all attempts

def connect_usb():
    try:
        global udid, connection_type
        global ios_version
        global rsd_data, rsd_host, rsd_port

        logger.info(f"Connecting USB device: udid={udid}")

        rsd_host = None
        rsd_port = None

        # Get device info to get iOS version
        temp_lockdown = asyncio.run(create_using_usbmux(udid, autopair=True))
        ios_version = temp_lockdown.product_version
        logger.info(f"iOS Version: {ios_version}")

        if is_major_version_17_or_greater(ios_version):
            logger.info("iOS 17+ detected")

            logger.info(f"iOS Version: {ios_version}")
            if version_check(ios_version):
                if sys.platform == 'win32':
                    logger.warning("iOS is between 17.0 and 17.3.1, WHY?")
                    logger.warning("You should upgrade to 17.4+")
                    logger.error("We need to install a 3rd party driver for these versions")
                    logger.error("which may stop working at any time")
                    try:
                        devices = get_devices_with_retry()
                        logger.info(f"Devices: {devices}")
                        rsd = [device for device in devices if device.udid == udid]
                        if len(rsd) > 0:
                            rsd = rsd[0]
                        start_tunnel_thread(rsd)

                    except RuntimeError as e:
                        error_message = str(e)
                        logger.error(f"Error: {error_message}")
                        return False

            else:
                # lockdown will be created inside the tunnel thread to avoid event loop issues
                start_tcp_tunnel_thread(udid)

            #time.sleep(3)
            if not check_rsd_data():
                logger.error("RSD Data is None, Perhaps the tunnel isn't established")
                return False
            else:
                rsd_data = rsd_host, rsd_port
                logger.info(f"RSD Data: {rsd_data}")

            rsd_data_map.setdefault(udid, {})[connection_type] = {"host": rsd_host, "port": rsd_port}
            logger.info(f"Device Connection Map: {rsd_data_map}")
            logger.info("USB connection successful")
            return True

        elif not is_major_version_17_or_greater(ios_version):
            rsd_data = ios_version, udid
            logger.info(f"RSD Data: {rsd_data}")

            # # Check if developer mode is enabled, and enable it if not
            # if not check_developer_mode(udid, connection_type):
            #     # Display modal to inform the user and give options
            #     return jsonify({'developer_mode_required': 'True'})

            # create LockdownServiceProvider
            #global lockdown
            global lockdown
            lockdown = asyncio.run(create_using_usbmux(udid, autopair=True))
            logger.info(f"Lockdown client = {lockdown}")
            #rsd_data = rsd_host, rsd_port
            rsd_host, rsd_port = rsd_data

            rsd_data_map.setdefault(udid, {})[connection_type] = {"host": rsd_host, "port": rsd_port}

            logger.info("USB connection successful")
            return True

        else:
            # Invalid ios_version
            logger.error("No iOS version present")
            return False
    finally:
        logger.warning("Connect Device function completed")

def connect_wifi():
    try:
        global udid, wifi_address, connection_type, wifi_port
        global ios_version
        global rsd_data, rsd_host, rsd_port

        logger.info(f"Connecting WiFi device: udid={udid}")

        rsd_host = None
        rsd_port = None

        # We already need wifihost set for this
        logger.info(f"Wifi host: {wifihost}")

        # Get device info to get iOS version
        # We need to establish connection first
        check_pair_record(udid)

        if pair_record is None:
            logger.error("No Pair Record Found. Please use a USB Cable to create one")
            return False

        devices = get_wifi_with_retry()
        logger.info(f"Connect Wifi Devices: {devices}")
        logger.info(f"Wifi Address:  {wifi_address}")

        # Run tun(devices) as a background task
        #asyncio.create_task(tun(devices))
        #await tun(devices)
        #start_wifi_tunnel_thread(devices)
        start_wifi_tunnel_thread()

        if not check_rsd_data():
            logger.error("RSD Data is None, Perhaps the tunnel isn't established")
            return False
        else:
            rsd_data = rsd_host, rsd_port
            logger.info(f"RSD Data: {rsd_data}")

        rsd_data_map.setdefault(udid, {})[connection_type] = {"host": rsd_host, "port": rsd_port}
        logger.info(f"Device Connection Map: {rsd_data_map}")
        logger.info("WiFi connection successful")
        return True

    finally:
        logger.warning("Connect Device function completed")


async def start_wifi_tcp_tunnel() -> None:

    logger.warning(f"Start Wifi TCP Tunnel")

    global terminate_tunnel_thread
    stop_remoted_if_required()
    #install_driver_if_required()

    # if sys.platform == 'win32':
    #     if is_driver_required:
    #         logger.warning("Installing WeTest Driver")
    #         cli_install_wetest_drivers()

    #service = await create_core_device_tunnel_service_using_remotepairing(udid, wifi_address, wifi_port)
    lockdown = await create_using_usbmux(udid)
    service = await CoreDeviceTunnelProxy.create(lockdown)

    async with service.start_tcp_tunnel() as tunnel_result:
        resume_remoted_if_required()

        logger.info(f'Identifier: {service.remote_identifier}')
        logger.info(f'Interface: {tunnel_result.interface}')
        logger.info(f'RSD Address: {tunnel_result.address}')
        logger.info(f'RSD Port: {tunnel_result.port}')
        global rsd_port
        global rsd_host
        rsd_host = tunnel_result.address

        rsd_port = str(tunnel_result.port)


        while True:
            if terminate_tunnel_thread is True:
                return
            # wait user input while the asyncio tasks execute
            await asyncio.sleep(.5)

async def start_wifi_quic_tunnel() -> None:

    logger.warning(f"Start Wifi QUIC Tunnel")

    global terminate_tunnel_thread
    stop_remoted_if_required()
    #install_driver_if_required()

    # if sys.platform == 'win32':
    #     if is_driver_required:
    #         logger.warning("Installing WeTest Driver")
    #         cli_install_wetest_drivers()
    #get_wifi_with_retry()
    service = await create_core_device_tunnel_service_using_remotepairing(udid, wifi_address, wifi_port)
    # lockdown = create_using_usbmux(udid)
    # service = CoreDeviceTunnelProxy(lockdown)

    async with service.start_quic_tunnel() as tunnel_result:
        resume_remoted_if_required()

        logger.info(f'Identifier: {service.remote_identifier}')
        logger.info(f'Interface: {tunnel_result.interface}')
        logger.info(f'RSD Address: {tunnel_result.address}')
        logger.info(f'RSD Port: {tunnel_result.port}')
        global rsd_port
        global rsd_host
        rsd_host = tunnel_result.address

        rsd_port = str(tunnel_result.port)


        while True:
            if terminate_tunnel_thread is True:
                return
            # wait user input while the asyncio tasks execute
            await asyncio.sleep(.5)

# Define a function to start the tunnel thread
def start_wifi_tunnel_thread():
    global terminate_tunnel_thread
    terminate_tunnel_thread = False  # Set the value of the global variable
    thread = threading.Thread(target=run_wifi_tunnel)
    thread.start()
    return

# Entry point for running the tunnel async function
def run_wifi_tunnel():
    try:
        if version_check(ios_version):
            asyncio.run(start_wifi_quic_tunnel())
        #TODO: or win32 / 17.0-17.3 special tunnel

        else:
            asyncio.run(start_wifi_tcp_tunnel())
        #await tun(devices)
    except Exception as e:
        logger.error(f"Error in run_wifi_tunnel: {e}")

def handle_connect(args):
    global udid, connection_type, wifihost
    udid = args.udid
    connection_type = args.connection_type.capitalize()
    if args.wifihost:
        wifihost = args.wifihost

    if connection_type.lower() == 'wifi':
        if not wifihost:
            logger.error("--wifihost is required for wifi connection")
            return False
        return connect_wifi()
    elif connection_type.lower() == 'usb':
        return connect_usb()
    else:
        logger.error(f"Invalid connection type: {args.connection_type}")
        return False

def handle_enable_dev_mode(args):
    global udid, connection_type, wifihost
    udid = args.udid
    connection_type = args.connection_type.capitalize()
    if args.wifihost:
        wifihost = args.wifihost

    success, error_msg = enable_developer_mode(udid, connection_type)
    if success:
        logger.info("Developer mode enabled successfully")
        if error_msg:
            logger.warning(error_msg)
    else:
        logger.error(f"Failed to enable developer mode: {error_msg}")
    return success

def handle_set_location(args):
    global location
    global ios_version
    global udid, connection_type, wifihost

    latitude = args.lat
    longitude = args.lon

    # If udid is provided, connect the device first
    if args.udid is not None:
        if args.connection_type is None:
            logger.error("--connection-type is required when --udid is provided")
            return False
        if args.connection_type == 'wifi' and args.wifihost is None:
            logger.error("--wifihost is required for wifi connection")
            return False
        # Set globals and connect
        udid = args.udid
        connection_type = args.connection_type.capitalize()
        if args.wifihost:
            wifihost = args.wifihost
        # Connect
        if connection_type.lower() == 'wifi':
            connected = connect_wifi()
        else:
            connected = connect_usb()
        if not connected:
            logger.error("Failed to connect to device")
            return False

    if ios_version is None:
        logger.error("No device connected. Please connect a device first using 'connect' command or provide --udid and --connection-type with set-location")
        return False

    location = f"{latitude} {longitude}"

    # Split the location string into latitude and longitude
    latitude, longitude = location.split()
    latitude = float(latitude)
    longitude = float(longitude)

    if is_major_version_17_or_greater(ios_version):
        #asyncio.run(set_location_thread(latitude, longitude))
        start_set_location_thread(latitude, longitude)
        logger.info(f"Location set successfully: {latitude}, {longitude}")
        logger.info("Press Ctrl+C to stop")
        # Keep the process running
        try:
            while not terminate_location_thread:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("\nReceived interrupt, stopping location...")
            handle_stop_location()
        return True

    elif not is_major_version_17_or_greater(ios_version):
        global lockdown
        # Split the location string into latitude and longitude
        latitude, longitude = location.split()
        latitude = float(latitude)
        longitude = float(longitude)

        mount_developer_image()
        #asyncio.run(set_location_thread(latitude, longitude))
        start_set_location_thread(latitude, longitude)
        logger.info(f"Location set successfully: {latitude}, {longitude}")
        logger.info("Press Ctrl+C to stop")
        # Keep the process running
        try:
            while not terminate_location_thread:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("\nReceived interrupt, stopping location...")
            handle_stop_location()
        return True

    else:
        # Invalid ios_version
        logger.error("No iOS version present")
        return False

def clear_geoport():
    logger.info("clear any GeoPort instances")
    substring = "GeoPort"

    for process in psutil.process_iter(['pid', 'name']):
        if substring in process.info['name']:
            logger.info(f"Found process: {process.info['pid']} - {process.info['name']}")

            # Terminate the process
            process.terminate()
    else:
        logger.warning("No GeoPort found")


def clear_old_geoport():
    logger.info("clear old GeoPort instances")
    substring = "GeoPort"

    current_pid = os.getpid()

    for process in psutil.process_iter(['pid', 'name']):
        if substring in process.info['name'] and process.info['pid'] != current_pid:
            logger.info(f"Found process: {process.info['pid']} - {process.info['name']}")

            # Terminate the process
            process.terminate()


def shutdown_server():
    logger.warning("shutdown server")
    try:
        handle_stop_location()
    except Exception:
        pass
    stop_set_location_thread()
    stop_tunnel_thread()
    cancel_async_tasks()
    terminate_threads()

    # Terminate the current process
    clear_geoport()

    logger.error("OS Kill")
    os._exit(0)


def terminate_threads():
    """
    Terminate all threads.
    """
    for thread in threading.enumerate():
        if thread != threading.main_thread():
            logger.info(f"thread: {thread}")
            terminate_flag = threading.Event()
            terminate_flag.set()
            #thread.terminate()  # Terminate the thread

def list_threads():
    """
    Terminate all threads.
    """
    for thread in threading.enumerate():
        logger.info(f"thread: {thread}")
def cancel_async_tasks():
    try:
        #loop = asyncio.get_running_loop()
        tasks = asyncio.all_tasks()
        for task in tasks:
            logger.info(f"task: {task}")
            task.cancel()
    except RuntimeError as e:
        if "no running event loop" in str(e):
            logger.error("No running event loop found.")
        else:
            raise e  # Re-raise the error if it's not related to the event loop

def handle_clear():
    logger.warning("Clearing all connections and exiting GeoPort")
    shutdown_server()

def signal_handler(signum, frame):
    logger.info("\nReceived interrupt signal, cleaning up...")
    shutdown_server()

def main():
    #========= Arg Parser ========
    parser = argparse.ArgumentParser(description='GeoPort - iOS Location Simulation CLI')
    subparsers = parser.add_subparsers(dest='command', required=True, help='Command')

    # list-devices
    parser_list = subparsers.add_parser('list-devices', help='List all connected iOS devices (USB + WiFi)')

    # connect
    parser_connect = subparsers.add_parser('connect', help='Connect to a specified device')
    parser_connect.add_argument('--udid', required=True, help='Device UDID')
    parser_connect.add_argument('--connection-type', required=True, choices=['usb', 'wifi'], help='Connection type')
    parser_connect.add_argument('--wifihost', help='WiFi IP address (required for wifi connection type)')

    # enable-dev-mode
    parser_enable = subparsers.add_parser('enable-dev-mode', help='Enable developer mode on device')
    parser_enable.add_argument('--udid', required=True, help='Device UDID')
    parser_enable.add_argument('--connection-type', required=True, choices=['usb', 'wifi'], help='Connection type')
    parser_enable.add_argument('--wifihost', help='WiFi IP address (for wifi connection)')

    # set-location
    parser_set = subparsers.add_parser('set-location', help='Start continuous location simulation')
    parser_set.add_argument('--lat', type=float, required=True, help='Latitude')
    parser_set.add_argument('--lon', type=float, required=True, help='Longitude')
    parser_set.add_argument('--udid', help='Device UDID (connect this device before setting location)')
    parser_set.add_argument('--connection-type', choices=['usb', 'wifi'], help='Connection type (required if --udid provided)')
    parser_set.add_argument('--wifihost', help='WiFi IP address (required for wifi connection type)')

    # stop-location
    parser_stop = subparsers.add_parser('stop-location', help='Stop location simulation')

    # clear
    parser_clear = subparsers.add_parser('clear', help='Stop all tunnels/threads and clean up exit')

    args = parser.parse_args()
    #========= Arg Parser ========

    # Add signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    create_geoport_folder()

    # Windows: check admin and relaunch if needed
    if is_windows:
        try:
            import pyi_splash
            pyi_splash.update_text('CLI Loaded ...')
            logger.info("clear splash")
            pyi_splash.close()
        except:
            pass
        if not pyuac.isUserAdmin():
            print("Relaunching as Admin")
            pyuac.runAsAdmin()
            sys.exit(0)

    # Dispatch based on command
    if args.command == 'list-devices':
        success = handle_list_devices()
        sys.exit(0 if success else 1)
    elif args.command == 'connect':
        success = handle_connect(args)
        sys.exit(0 if success else 1)
    elif args.command == 'enable-dev-mode':
        success = handle_enable_dev_mode(args)
        sys.exit(0 if success else 1)
    elif args.command == 'set-location':
        success = handle_set_location(args)
        sys.exit(0 if success else 1)
    elif args.command == 'stop-location':
        success = handle_stop_location()
        sys.exit(0 if success else 1)
    elif args.command == 'clear':
        handle_clear()
        sys.exit(0)

if __name__ == '__main__':
    main()
