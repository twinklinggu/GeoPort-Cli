"""Fuel price API integration (Australian fuel prices)."""

from typing import Dict, List, Optional

import requests

from src.config.settings import BROADCAST_FILE, CURRENT_VERSION_FILE, GITHUB_REPO
from src.utils.logging import logger


def get_github_version() -> Optional[str]:
    """Get the latest version from GitHub."""
    try:
        url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/{CURRENT_VERSION_FILE}"
        response = requests.get(url)
        response.raise_for_status()
        return response.text.strip()
    except requests.RequestException:
        return None


def get_github_broadcast() -> Optional[str]:
    """Get broadcast message from GitHub."""
    try:
        url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/{BROADCAST_FILE}"
        logger.error(f"Github URL: {url}")
        response = requests.get(url, verify=False)
        logger.error(f"github response: {response}")
        if not response.text.strip():
            return None
        github_broadcast = response.text.strip()
        logger.error("GITHUB BROADCAST MESSAGE:")
        return github_broadcast
    except requests.RequestException:
        return None


def get_fuel_data(fuel_type: str) -> Optional[Dict]:
    """Get fuel prices from the ProjectZeroThree API."""
    try:
        url = "https://projectzerothree.info/api.php?format=json"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        if fuel_type == "all":
            return data

        filtered_prices = []
        for price in data["prices"]:
            if price["type"] == fuel_type:
                filtered_prices.append(price)

        result = {
            "prices": filtered_prices,
            "title": data["title"],
            "updated": data["updated"],
        }
        return result
    except Exception as e:
        logger.error(f"Error fetching fuel data: {e}")
        return None


def get_fuel_types() -> List[str]:
    """Get list of available fuel types."""
    return ["E10", "U91", "U95", "U98", "Diesel", "LPG"]
