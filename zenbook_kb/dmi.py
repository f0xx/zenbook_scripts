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


def is_ux5400() -> bool:
    blob = f"{product_name()} {board_name()}".upper()
    return "UX5400" in blob


def is_ux8406() -> bool:
    blob = f"{product_name()} {board_name()}".upper()
    return "UX8406" in blob


def has_screenpad_sysfs() -> bool:
    return Path("/sys/class/backlight/asus_screenpad").is_dir()


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
