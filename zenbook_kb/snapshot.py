"""Save and restore keyboard backlight settings snapshots."""

from __future__ import annotations

import configparser
from datetime import datetime, timezone
from pathlib import Path

from zenbook_kb.limits import BrightnessLimits, get_brightness_limits
from zenbook_kb.state import DEFAULT_STATE_DIR, read_brightness, write_brightness

DEFAULT_SNAPSHOT = DEFAULT_STATE_DIR / "zenbook_duo.save"
SNAPSHOT_VERSION = "1"


def _keyboard_section(
    cfg: configparser.ConfigParser,
    brightness: int,
    limits: BrightnessLimits,
) -> dict[str, str]:
    kb = cfg["keyboard"]
    return {
        "version": SNAPSHOT_VERSION,
        "saved_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "brightness": str(brightness),
        "usb_vendor_id": kb.get("usb_vendor_id", "0b05"),
        "usb_product_id": kb.get("usb_product_id", "1b2c"),
        "bt_vendor_id": kb.get("bt_vendor_id", "0b05"),
        "bt_product_id": kb.get("bt_product_id", "1b2d"),
        "usb_windex": kb.get("usb_windex", "4"),
        "default_brightness": kb.get("default_brightness", str(brightness)),
        "brightness_min": str(limits.minimum),
        "brightness_max": str(limits.maximum),
    }


def save_snapshot(
    path: Path | None,
    cfg: configparser.ConfigParser,
    brightness: int | None = None,
    limits: BrightnessLimits | None = None,
) -> Path:
    """Write current settings to a snapshot file."""
    target = path or DEFAULT_SNAPSHOT
    level = brightness if brightness is not None else read_brightness(
        int(cfg["keyboard"].get("default_brightness", "1"))
    )
    resolved_limits = limits or get_brightness_limits(None, cfg)

    out = configparser.ConfigParser()
    out["keyboard"] = _keyboard_section(cfg, level, resolved_limits)

    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w") as fh:
        out.write(fh)
    return target


def load_snapshot(path: Path | None) -> configparser.ConfigParser:
    """Read a snapshot file."""
    target = path or DEFAULT_SNAPSHOT
    if not target.exists():
        raise FileNotFoundError(f"Snapshot not found: {target}")

    cfg = configparser.ConfigParser()
    with target.open() as fh:
        cfg.read_file(fh)
    if "keyboard" not in cfg:
        raise ValueError(f"Invalid snapshot (missing [keyboard] section): {target}")
    return cfg


def snapshot_brightness(cfg: configparser.ConfigParser) -> int:
    return int(cfg["keyboard"]["brightness"])


def merge_snapshot_config(
    snapshot: configparser.ConfigParser,
    cfg: configparser.ConfigParser,
) -> None:
    """Merge snapshot [keyboard] values into the live config object."""
    if "keyboard" not in cfg:
        cfg["keyboard"] = {}
    for key, value in snapshot["keyboard"].items():
        if key in {"version", "saved_at"}:
            continue
        cfg["keyboard"][key] = value


def write_config(cfg: configparser.ConfigParser, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as fh:
        cfg.write(fh)


def restore_snapshot(
    path: Path | None,
    cfg: configparser.ConfigParser,
    config_path: Path,
    *,
    update_config: bool = True,
) -> int:
    """Load snapshot, optionally update config file, return brightness level."""
    snapshot = load_snapshot(path)
    level = snapshot_brightness(snapshot)

    if update_config:
        merge_snapshot_config(snapshot, cfg)
        write_config(cfg, config_path)

    write_brightness(level)
    return level
