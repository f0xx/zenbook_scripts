"""ASUS Aura Core keyboard backlight protocol.

Protocol reference:
https://openrgb-wiki.readthedocs.io/en/latest/asus/ASUS-Aura-Core/
"""

from __future__ import annotations

REPORT_ID_BRIGHTNESS = 0x5A
BRIGHTNESS_CMD = (0xBA, 0xC5, 0xC4)
BRIGHTNESS_MIN = 0
BRIGHTNESS_MAX = 3

# Default USB IDs for Zenbook Duo UX8406 Primax keyboard (pogo pins).
DEFAULT_USB_VENDOR_ID = 0x0B05
DEFAULT_USB_PRODUCT_ID = 0x1B2C

# Bluetooth HID product ID when keyboard is detached.
DEFAULT_BT_PRODUCT_ID = 0x1B2D

# USB control transfer parameters used by the pogo-pin transport.
USB_WVALUE = 0x035A
USB_WINDEX = 4
USB_WLENGTH = 16
USB_BM_REQUEST_TYPE = 0x21
USB_B_REQUEST = 0x09


def clamp_brightness(level: int) -> int:
    return max(BRIGHTNESS_MIN, min(BRIGHTNESS_MAX, level))


def build_brightness_report(level: int) -> list[int]:
    level = clamp_brightness(level)
    return [REPORT_ID_BRIGHTNESS, *BRIGHTNESS_CMD, level]


def build_usb_packet(level: int) -> list[int]:
    """Build the 16-byte USB HID SET_REPORT payload."""
    packet = [0] * USB_WLENGTH
    report = build_brightness_report(level)
    packet[: len(report)] = report
    return packet
