# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**GeoPort** is a desktop application for iOS location spoofing. It's a Flask-based web application that provides a GUI interface to simulate device location on iOS devices via USB or WiFi connections. The application uses `pymobiledevice3` library to communicate with iOS devices through various tunnel protocols (QUIC/TCP).

**Tech Stack:**
- Python 3.9+ with Flask web framework
- pymobiledevice3 for iOS device communication
- HTML/CSS/JavaScript frontend (Leaflet-based maps)
- PyInstaller for packaging into standalone executables

**Current Version:** 4.0.2

## Development Commands

### Dependency Management (uv)

This project uses **uv** for fast Python package management and virtual environments.

**Create virtual environment and install dependencies:**
```bash
uv sync
```

**Install with development dependencies:**
```bash
uv sync --extra dev
```

**Add a new dependency:**
```bash
uv add <package-name>
```

**Add a development dependency:**
```bash
uv add --dev <package-name>
```

**Run Python in the virtual environment:**
```bash
uv run python <script>
```

**Activate the virtual environment shell:**
```bash
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

**List installed packages:**
```bash
uv pip list
```

### Running the Application

**Development mode (with auto-browser):**
```bash
uv run src/main.py
```

**Disable auto-browser opening:**
```bash
uv run src/main.py --no-browser
```

**Specify custom port (default: random port 49215-65535, or 54321 if available):**
```bash
uv run src/main.py --port 8080
```

**Connect to specific device via WiFi:**
```bash
uv run src/main.py --wifihost <device-ip> --udid <device-udid>
```

**Administrator privileges required:**
- **macOS/Linux:** Run with `sudo`
- **Windows:** Run as Administrator

Example:
```bash
sudo uv run src/main.py --no-browser
```

### Packaging/Building

The application is packaged with PyInstaller. Build artifacts are typically generated for:
- macOS (ARM and Intel)
- Windows (64-bit)
- Linux (Ubuntu 22.04)

Build configuration (`.spec` files) may be located in the repository or generated on demand. When building, ensure pymobiledevice3 and all dependencies are correctly bundled.

### Dependencies

All dependencies are managed in `pyproject.toml` using uv. Key runtime dependencies:
- **flask** - Web framework
- **pymobiledevice3** - iOS device communication (must support iOS 17+ location simulation APIs)
- **psutil** - Process management
- **requests** - HTTP requests (fuel API)
- **pycountry** - Country lookup
- **pyuac** (Windows only) - UAC elevation

**Install everything (including dev tools):**
```bash
uv sync --extra dev
```

**Install only runtime dependencies:**
```bash
uv sync
```

## Architecture

### High-Level Structure

```
GeoPort/
├── src/
│   ├── main.py              # Flask app + all backend logic (monolithic)
│   └── templates/
│       ├── map.html         # Primary UI (map interface)
│       └── map2.html        # Alternative UI variant
├── images/                  # Documentation images
├── README.md                # User-facing documentation
├── FAQ.md                   # Troubleshooting guide
├── CURRENT_VERSION          # Current app version
├── BROADCAST                # Broadcast message file
├── pyproject.toml           # Dependency management (uv)
└── CLAUDE.md                # This file
```

### Backend (src/main.py)

The entire backend is a single Flask application file (~1,500 lines) that handles:

1. **Device Management**
   - USB device discovery via `list_devices()` from pymobiledevice3
   - WiFi device discovery via `get_remote_pairing_tunnel_services()`
   - Connection type handling: USB, Network (WiFi), Manual WiFi
   - Developer mode checking and enabling via `AmfiService`

2. **Tunnel Management**
   - QUIC tunnels for iOS 17+ (Windows 17.0-17.3.1 special handling)
   - TCP tunnels for older iOS versions
   - Separate tunnel threads with async lifecycle management
   - Global connection mapping: `rsd_data_map[udid][connection_type]`

3. **Location Simulation**
   - `set_location()` endpoint receives lat/lng from UI
   - Uses `LocationSimulation` service from pymobiledevice3
   - Maintains location thread that continuously sets location
   - `stop_location()` clears simulation

4. **Fuel Mode** (Australian-specific)
   - Fetches fuel prices from external API: `https://projectzerothree.info/api.php?format=json`
   - Endpoints: `/api/data/<fuel_type>`, `/api/fuel_types`

5. **Global State**
   - The app uses many module-level global variables (e.g., `udid`, `lockdown`, `rsd_host`, `rsd_port`, `location`, `connection_type`)
   - This is a **single-user desktop app** pattern, acceptable but not thread-safe for multi-user scenarios

### Frontend (templates/map.html)

Leaflet-based interactive map with:
- Device listing and connection UI
- Map click-to-set location functionality
- Track creation (draw routes)
- GPX/GeoJSON import/export
- Playback speed control (walk/run/ride/drive/custom)
- Fuel mode interface (Australia)

### iOS Version Handling

Critical branching logic:
- **iOS 17+**: Uses Remote Service Discovery (RSD) + QUIC/TCP tunneling
- **iOS <17**: Direct Lockdown connection with DVT proxy
- **iOS 17.0-17.3.1 on Windows**: Requires third-party WeTest driver

Check functions:
- `is_major_version_17_or_greater(version_string)`
- `is_major_version_less_than_16(version_string)`
- `version_check(version_string)` (Windows driver requirement)

## Code Quality Tools

All tool configurations are in `pyproject.toml`:

- **black** - Code formatting (line-length: 88)
- **ruff** - Fast Python linter (replaces flake8, isort, etc.)
- **mypy** - Static type checking (currently disabled for `pymobiledevice3.*` and `pyuac.*`)
- **pytest** - Testing framework

**Manual usage:**

```bash
# Format code
uv run black src tests

# Lint code
uv run ruff check src tests

# Type check
uv run mypy src

# Run all checks
uv run black src tests && uv run ruff check src tests && uv run mypy src
```

## Testing

The project is configured for testing but **no test suite currently exists**. To add tests:

1. Create tests for:
   - Device discovery mocking
   - Connection type logic (USB/WiFi branching)
   - Location setting/stopping
   - API endpoints (`/connect_device`, `/set_location`, etc.)
   - Version check functions
   - Fuel API handling

2. Recommended approach:
   - Use `pytest` for test framework (already configured in `pyproject.toml`)
   - Mock `pymobiledevice3` calls (unittest.mock or pytest-mock)
   - Test Flask endpoints with Flask's test client
   - Aim for 80%+ coverage

3. Test command:
```bash
uv run pytest tests/ -v
```

4. Coverage report:
```bash
uv run pytest tests/ --cov=src --cov-report=html
# Open htmlcov/index.html in browser
```

## Code Style and Conventions

- **Python style**: PEP 8 (enforced by black and ruff)
- **Line length**: 88 characters (configured for black/ruff)
- **Logging**: Uses Python `logging` module with logger named "GeoPort"
- **Error handling**: Comprehensive try/except with user-friendly messages
- **Threading**: Uses `threading.Thread` for tunnel and location operations
- **Async/await**: Mixed with threading (asyncio.run in threads)
- **Globals**: Extensive use of module-level globals (acceptable for single-user desktop app)
- **MyPy**: Type checking is configured but `src/main.py` currently has no type annotations

**Note:** `src/main.py` is explicitly excluded from ruff's line length checks (`E501`) in `pyproject.toml`.

## Important Files to Understand

1. **src/main.py** - Start here. Read it fully; it's the entire backend.
2. **templates/map.html** - Frontend JavaScript interacts with Flask endpoints via fetch API
3. **FAQ.md** - Common issues, especially Windows firewall configuration and driver requirements
4. **README.md** - User perspective, feature overview
5. **pyproject.toml** - All dependency and tool configuration

## Known Issues and Quirks

1. **Windows Firewall**: First run requires allowing both Public and Private networks for the tunnel adapter
2. **iOS 17.0-17.3.1 on Windows**: Requires WeTest driver which may break anytime
3. **WiFi limitations**: Device must be unlocked; same LAN/subnet required; not guaranteed
4. **Admin privileges**: Required on all platforms for USB communication
5. **Passcode handling**: Device with passcode cannot enable developer mode; user must temporarily remove passcode
6. **Connection mapping**: Uses global map `rsd_data_map` to cache RSD connections per UDID+connection type
7. **Errno 54**: "Connection reset by peer" indicates too many open connections; requires "Stop Location" and possibly app restart

## Adding Features

When modifying this codebase:

1. **Understand the connection lifecycle**:
   - `list_devices` → `connect_device` → tunnel setup → `set_location` → `stop_location`
   - Connection reuse via `rsd_data_map`

2. **iOS version checks**: Any location-related changes must account for iOS 17+ vs older versions.

3. **Thread safety**: The app is single-user but uses threads. Be careful modifying global state from multiple threads.

4. **Tunnel management**: Tunnels run in infinite loops until `terminate_tunnel_thread = True`. Proper cleanup on exit.

5. **Permissions**: Need admin rights for USB driver access. Don't hardcode any credentials.

6. **UI changes**: Edit `templates/map.html`. It's a single-page app using Leaflet and vanilla JavaScript.

7. **Type annotations**: `src/main.py` is untyped. When adding type hints, add them gradually to avoid breaking mypy.

## Development Workflow

Since there's no formal test suite:

1. Make changes to `src/main.py`
2. Run the app locally with a test device (or simulator if available)
3. Verify all connection types (USB, WiFi) work
4. Check logs for unhandled exceptions
5. Test location setting, clearing, and re-setting
6. For Windows users: Test firewall prompts
7. Run linting: `uv run ruff check src tests`
8. Format code: `uv run black src tests`

## Deployment Notes

- Release builds are PyInstaller executables
- Version sources: `CURRENT_VERSION` file (committed to repo)
- Broadcast messages: `BROADCAST` file (displayed on UI)
- GitHub repository: `davesc63/GeoPort`
- App displays update check against GitHub CURRENT_VERSION

## Future Improvements (Technical Debt)

1. **No tests**: High-priority; critical device interaction logic needs coverage
2. **Monolithic main.py**: Should be split into modules (device_manager, tunnel_manager, location_service, routes, etc.)
3. **Global state**: Should encapsulate in application context or class
4. **Async/threading mix**: Could unify to asyncio for cleaner concurrency
5. **No input validation**: Some endpoints trust client data; add validation (especially lat/lng)
6. **Logging configuration**: Hardcoded DEBUG level; should be configurable
7. **Error handling**: Some exceptions may leak information; review for user-facing messages
8. **Type annotations**: Add type hints to `src/main.py` gradually
