"""Pytest configuration for GeoPort tests."""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


def pytest_configure(config):
    """Configure pytest."""
    pass
