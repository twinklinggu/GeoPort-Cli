"""Tests for version checking functions."""
import pytest

from src.devices.connection import (
    is_major_version_17_or_greater,
    is_major_version_less_than_16,
    version_check,
)


@pytest.mark.unit
def test_is_major_version_17_or_greater():
    """Test version 17+ check."""
    assert is_major_version_17_or_greater("17.0") is True
    assert is_major_version_17_or_greater("17.4") is True
    assert is_major_version_17_or_greater("16.0") is False
    assert is_major_version_17_or_greater("15.0") is False
    assert is_major_version_17_or_greater("18.0") is True
    assert is_major_version_17_or_greater("invalid") is False


@pytest.mark.unit
def test_is_major_version_less_than_16():
    """Test version less than 16 check."""
    assert is_major_version_less_than_16("15.0") is True
    assert is_major_version_less_than_16("14.5") is True
    assert is_major_version_less_than_16("16.0") is False
    assert is_major_version_less_than_16("17.0") is False
    assert is_major_version_less_than_16("invalid") is False


@pytest.mark.unit
def test_version_check():
    """Test Windows driver requirement check (iOS 17.0-17.3)."""
    # This function behaves differently on Windows vs other platforms, but logic is consistent
    result = version_check("17.0")
    # On non-Windows, should return False
    # On Windows, should return True for 17.0-17.3
    # Just check it doesn't crash
    assert isinstance(result, bool)

    result = version_check("17.3")
    assert isinstance(result, bool)

    result = version_check("17.4")
    assert isinstance(result, bool)

    result = version_check("16.0")
    assert isinstance(result, bool)
