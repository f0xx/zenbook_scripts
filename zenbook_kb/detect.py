"""Detect whether the Zenbook Duo keyboard is on pogo pins (USB) or Bluetooth."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from zenbook_kb.protocol import (
    DEFAULT_BT_PRODUCT_ID,
    DEFAULT_USB_PRODUCT_ID,
    DEFAULT_USB_VENDOR_ID,
)


class ConnectionMode(Enum):
    USB = "usb"
    BLUETOOTH = "bluetooth"


@dataclass(frozen=True)
class DeviceIds:
    vendor_id: int
    product_id: int


@dataclass(frozen=True)
class ConnectionInfo:
    mode: ConnectionMode
    ids: DeviceIds
    hidraw_path: Path | None = None
    report_descriptor_size: int | None = None


_HID_ID_RE = re.compile(
    r"^HID_ID=(\d+):([0-9A-Fa-f]+):([0-9A-Fa-f]+)$", re.MULTILINE
)


def _parse_hid_id(uevent_text: str) -> tuple[int, int, int] | None:
    match = _HID_ID_RE.search(uevent_text)
    if not match:
        return None
    bus, vendor, product = match.groups()
    return int(bus), int(vendor, 16), int(product, 16)


def _hidraw_candidates() -> list[Path]:
    return sorted(Path("/sys/class/hidraw").glob("hidraw*"))


def _report_descriptor_size(hidraw_sysfs: Path) -> int | None:
    report = hidraw_sysfs / "device" / "report_descriptor"
    try:
        return len(report.read_bytes())
    except OSError:
        return None


def _find_hidraw_by_product(
    vendor_id: int,
    product_id: int,
    descriptor_size: int | None = None,
) -> Path | None:
    for hidraw in _hidraw_candidates():
        uevent = hidraw / "device" / "uevent"
        try:
            parsed = _parse_hid_id(uevent.read_text())
        except OSError:
            continue
        if not parsed:
            continue
        _bus, vendor, product = parsed
        if vendor != vendor_id or product != product_id:
            continue
        size = _report_descriptor_size(hidraw)
        if descriptor_size is not None and size != descriptor_size:
            continue
        return Path("/dev") / hidraw.name
    return None


def usb_device_present(vendor_id: int, product_id: int) -> bool:
    try:
        output = subprocess.check_output(["lsusb"], text=True, stderr=subprocess.DEVNULL)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False
    needle = f"{vendor_id:04x}:{product_id:04x}"
    return needle in output.lower()


def detect_connection(
    usb_vendor_id: int = DEFAULT_USB_VENDOR_ID,
    usb_product_id: int = DEFAULT_USB_PRODUCT_ID,
    bt_vendor_id: int = DEFAULT_USB_VENDOR_ID,
    bt_product_id: int = DEFAULT_BT_PRODUCT_ID,
    mode: str | None = None,
) -> ConnectionInfo:
    """Return active connection info. USB (pogo) takes priority when both exist."""
    if mode == "usb":
        return ConnectionInfo(
            mode=ConnectionMode.USB,
            ids=DeviceIds(usb_vendor_id, usb_product_id),
            hidraw_path=_find_hidraw_by_product(usb_vendor_id, usb_product_id, 90),
            report_descriptor_size=90,
        )
    if mode == "bluetooth":
        return ConnectionInfo(
            mode=ConnectionMode.BLUETOOTH,
            ids=DeviceIds(bt_vendor_id, bt_product_id),
            hidraw_path=_find_hidraw_by_product(bt_vendor_id, bt_product_id, 257),
            report_descriptor_size=257,
        )

    if usb_device_present(usb_vendor_id, usb_product_id):
        return ConnectionInfo(
            mode=ConnectionMode.USB,
            ids=DeviceIds(usb_vendor_id, usb_product_id),
            hidraw_path=_find_hidraw_by_product(usb_vendor_id, usb_product_id, 90),
            report_descriptor_size=90,
        )

    hidraw = _find_hidraw_by_product(bt_vendor_id, bt_product_id, 257)
    if hidraw:
        return ConnectionInfo(
            mode=ConnectionMode.BLUETOOTH,
            ids=DeviceIds(bt_vendor_id, bt_product_id),
            hidraw_path=hidraw,
            report_descriptor_size=257,
        )

    raise RuntimeError(
        "Zenbook Duo keyboard not found. "
        f"Expected USB {usb_vendor_id:04x}:{usb_product_id:04x} "
        f"or Bluetooth {bt_vendor_id:04x}:{bt_product_id:04x}."
    )
