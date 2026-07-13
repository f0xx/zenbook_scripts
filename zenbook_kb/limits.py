"""Keyboard backlight limit discovery."""

from __future__ import annotations

import configparser
from dataclasses import dataclass
from pathlib import Path

from zenbook_kb.detect import ConnectionInfo
from zenbook_kb.protocol import BRIGHTNESS_MAX, BRIGHTNESS_MIN

SYSFS_KBD_BACKLIGHT = Path("/sys/class/leds/asus::kbd_backlight")


@dataclass(frozen=True)
class BrightnessLimits:
    minimum: int
    maximum: int
    source: str


def _config_limits(cfg: configparser.ConfigParser | None) -> BrightnessLimits | None:
    if cfg is None or "keyboard" not in cfg:
        return None
    kb = cfg["keyboard"]
    if "brightness_min" not in kb and "brightness_max" not in kb:
        return None
    minimum = int(kb.get("brightness_min", str(BRIGHTNESS_MIN)))
    maximum = int(kb.get("brightness_max", str(BRIGHTNESS_MAX)))
    return BrightnessLimits(minimum=minimum, maximum=maximum, source="config")


def _sysfs_limits(_cfg: configparser.ConfigParser | None = None) -> BrightnessLimits | None:
    max_path = SYSFS_KBD_BACKLIGHT / "max_brightness"
    if not max_path.exists():
        return None
    try:
        maximum = int(max_path.read_text().strip())
    except (OSError, ValueError):
        return None
    return BrightnessLimits(minimum=0, maximum=maximum, source="sysfs")


def get_brightness_limits(
    info: ConnectionInfo | None = None,
    cfg: configparser.ConfigParser | None = None,
) -> BrightnessLimits:
    """Return backlight limits for the active or requested connection."""
    for resolver in (_config_limits, _sysfs_limits):
        limits = resolver(cfg)
        if limits is not None:
            return limits

    # UX8406 Zenbook Duo detachable keyboard: 4 levels 0-3 on USB and Bluetooth.
    # HID feature reports expose the current level but not a separate max field.
    _ = info
    return BrightnessLimits(
        minimum=BRIGHTNESS_MIN,
        maximum=BRIGHTNESS_MAX,
        source="protocol",
    )
