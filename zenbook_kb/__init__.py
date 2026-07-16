"""Zenbook Duo detachable keyboard control library."""

from zenbook_kb.protocol import (
    BRIGHTNESS_MAX,
    BRIGHTNESS_MIN,
    build_brightness_report,
)
from zenbook_kb.detect import ConnectionMode, detect_connection
from zenbook_kb.limits import BrightnessLimits, get_brightness_limits

__all__ = [
    "BRIGHTNESS_MAX",
    "BRIGHTNESS_MIN",
    "BrightnessLimits",
    "ConnectionMode",
    "build_brightness_report",
    "detect_connection",
    "get_brightness_limits",
]
