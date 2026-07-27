#!/usr/bin/env python3
"""DMI helpers for model-specific install paths."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path


def read_dmi(name: str) -> str:
    path = Path(f"/sys/class/dmi/id/{name}")
    try:
        return path.read_text().strip()
    except OSError:
        return ""


def product_name() -> str:
    value = read_dmi("product_name")
    if value:
        return value
    return _dmidecode_string("system-product-name")


def board_name() -> str:
    value = read_dmi("board_name")
    if value:
        return value
    return _dmidecode_string("baseboard-product-name")


def _dmidecode_string(key: str) -> str:
    """Fallback when /sys/class/dmi/id is missing (needs sys-apps/dmidecode)."""
    if not shutil.which("dmidecode"):
        return ""
    try:
        out = subprocess.check_output(
            ["dmidecode", "-s", key],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
    except (subprocess.SubprocessError, OSError):
        return ""
    return out.strip()


def _dmi_blob() -> str:
    return f"{product_name()} {board_name()}".upper()


def is_ux5400() -> bool:
    return "UX5400" in _dmi_blob()


def is_ux8406() -> bool:
    return "UX8406" in _dmi_blob()


def is_duo_chassis() -> bool:
    """True for Zenbook Duo dual-eDP chassis (detachable KB + lower panel).

    ScreenPad-only models (e.g. UX5400) are *not* Duo chassis — they use
    ``asus_screenpad`` backlight, not ``platform-duo-dock`` / eDP-2 restack.
    """
    blob = _dmi_blob()
    # UX8406 sold as Duo; UX581/UX582 Pro Duo; UX8402 earlier Duo.
    return any(tag in blob for tag in ("UX8406", "UX8402", "UX581", "UX582"))


def has_screenpad_sysfs() -> bool:
    return Path("/sys/class/backlight/asus_screenpad").is_dir()


def has_duo_pogo_usb() -> bool:
    """USB pogo dock keyboard present (0b05:1b2c)."""
    base = Path("/sys/bus/usb/devices")
    if not base.is_dir():
        return False
    for d in base.iterdir():
        try:
            vid = (d / "idVendor").read_text().strip().lower()
            pid = (d / "idProduct").read_text().strip().lower()
        except OSError:
            continue
        if vid == "0b05" and pid == "1b2c":
            return True
    return False


def has_platform_profile() -> bool:
    return Path("/sys/firmware/acpi/platform_profile").is_file()


def ensure_conf_assignment(text: str, key: str, value: str) -> tuple[str, bool]:
    """Return (new_text, changed) for OpenRC-style ``key=value``."""
    line = f"{key}={value}"
    pattern = re.compile(rf"^{re.escape(key)}=.*$", re.M)
    if pattern.search(text):
        new = pattern.sub(line, text)
    else:
        new = text.rstrip() + ("" if not text else "\n") + line + "\n"
    return new, new != text
