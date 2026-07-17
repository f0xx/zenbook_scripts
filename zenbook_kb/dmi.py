#!/usr/bin/env python3
"""DMI helpers for model-specific install paths."""

from __future__ import annotations

from pathlib import Path


def read_dmi(name: str) -> str:
    path = Path(f"/sys/class/dmi/id/{name}")
    try:
        return path.read_text().strip()
    except OSError:
        return ""


def product_name() -> str:
    return read_dmi("product_name")


def board_name() -> str:
    return read_dmi("board_name")


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
