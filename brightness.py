#!/usr/bin/env python3
"""Set Zenbook Duo detachable keyboard backlight brightness."""

from __future__ import annotations

import argparse
import configparser
import sys
from pathlib import Path

from zenbook_kb.detect import detect_connection
from zenbook_kb.protocol import (
    DEFAULT_BT_PRODUCT_ID,
    DEFAULT_USB_PRODUCT_ID,
    DEFAULT_USB_VENDOR_ID,
)
from zenbook_kb.limits import get_brightness_limits
from zenbook_kb.runner import set_brightness
from zenbook_kb.snapshot import restore_snapshot, save_snapshot
from zenbook_kb.state import _user_home, read_brightness, write_brightness
from zenbook_kb.transports.base import TransportError

DEFAULT_CONFIG = _user_home() / ".config" / "zenbook-scripts" / "zenbook-duo.conf"


def _parse_hex(value: str) -> int:
    return int(value, 16)


def load_config(path: Path | None) -> configparser.ConfigParser:
    cfg = configparser.ConfigParser()
    cfg.read_dict(
        {
            "keyboard": {
                "usb_vendor_id": f"{DEFAULT_USB_VENDOR_ID:04x}",
                "usb_product_id": f"{DEFAULT_USB_PRODUCT_ID:04x}",
                "bt_vendor_id": f"{DEFAULT_USB_VENDOR_ID:04x}",
                "bt_product_id": f"{DEFAULT_BT_PRODUCT_ID:04x}",
                "usb_windex": "4",
                "default_brightness": "1",
            }
        }
    )
    if path and path.exists():
        cfg.read(path)
    return cfg


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Control ASUS Zenbook Duo detachable keyboard backlight."
    )
    parser.add_argument(
        "level",
        nargs="?",
        help=(
            "Brightness level, or command: get, get_min, get_max, limits, "
            "save, restore, load"
        ),
    )
    parser.add_argument(
        "snapshot_path",
        nargs="?",
        type=Path,
        help="Snapshot file for save/restore/load (default: ~/.config/zenbook-scripts/zenbook_duo.save)",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help=f"Config file (default: {DEFAULT_CONFIG})",
    )
    parser.add_argument(
        "--vendor-id",
        type=_parse_hex,
        help="USB vendor ID (overrides config, pogo-pin mode)",
    )
    parser.add_argument(
        "--product-id",
        type=_parse_hex,
        help="USB product ID (overrides config, pogo-pin mode)",
    )
    parser.add_argument(
        "--bt-vendor-id",
        type=_parse_hex,
        help="Bluetooth vendor ID (overrides config)",
    )
    parser.add_argument(
        "--bt-product-id",
        type=_parse_hex,
        help="Bluetooth product ID (overrides config)",
    )
    parser.add_argument(
        "--mode",
        choices=("auto", "usb", "bluetooth"),
        default="auto",
        help="Force transport mode (default: auto-detect)",
    )
    parser.add_argument(
        "--usb-windex",
        type=int,
        help="USB interface index for HID SET_REPORT (default: 4)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Only print errors",
    )
    parser.add_argument(
        "--show-mode",
        action="store_true",
        help="Print active transport mode after setting brightness",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    cfg = load_config(args.config)

    usb_vendor = args.vendor_id or _parse_hex(cfg["keyboard"]["usb_vendor_id"])
    usb_product = args.product_id or _parse_hex(cfg["keyboard"]["usb_product_id"])
    bt_vendor = args.bt_vendor_id or _parse_hex(cfg["keyboard"]["bt_vendor_id"])
    bt_product = args.bt_product_id or _parse_hex(cfg["keyboard"]["bt_product_id"])
    usb_windex = args.usb_windex or int(cfg["keyboard"]["usb_windex"])
    default_level = int(cfg["keyboard"]["default_brightness"])

    if args.level is None:
        parser.error("brightness level or command is required")

    snapshot_path = args.snapshot_path
    mode = None if args.mode == "auto" else args.mode
    info = None
    keyboard_optional = args.level in {"get_min", "get_max", "limits", "save"}

    if not keyboard_optional or args.level in {"restore", "load"}:
        try:
            info = detect_connection(
                usb_vendor_id=usb_vendor,
                usb_product_id=usb_product,
                bt_vendor_id=bt_vendor,
                bt_product_id=bt_product,
                mode=mode,
            )
        except RuntimeError as exc:
            if args.level in {"get_min", "get_max", "limits", "save"}:
                info = None
            else:
                print(exc, file=sys.stderr)
                return 1

    limits = get_brightness_limits(info, cfg)

    if args.level == "get":
        print(read_brightness(default_level))
        return 0
    if args.level == "get_min":
        print(limits.minimum)
        return 0
    if args.level == "get_max":
        print(limits.maximum)
        return 0
    if args.level == "limits":
        print(f"{limits.minimum} {limits.maximum} {limits.source}")
        return 0
    if args.level == "save":
        try:
            path = save_snapshot(snapshot_path, cfg, limits=limits)
        except OSError as exc:
            print(exc, file=sys.stderr)
            return 1
        if not args.quiet:
            print(path)
        return 0
    if args.level in {"restore", "load"}:
        try:
            level = restore_snapshot(snapshot_path, cfg, args.config)
            cfg = load_config(args.config)
            usb_vendor = args.vendor_id or _parse_hex(cfg["keyboard"]["usb_vendor_id"])
            usb_product = args.product_id or _parse_hex(cfg["keyboard"]["usb_product_id"])
            bt_vendor = args.bt_vendor_id or _parse_hex(cfg["keyboard"]["bt_vendor_id"])
            bt_product = args.bt_product_id or _parse_hex(cfg["keyboard"]["bt_product_id"])
            usb_windex = args.usb_windex or int(cfg["keyboard"]["usb_windex"])
            info = detect_connection(
                usb_vendor_id=usb_vendor,
                usb_product_id=usb_product,
                bt_vendor_id=bt_vendor,
                bt_product_id=bt_product,
                mode=mode,
            )
            limits = get_brightness_limits(info, cfg)
            if level < limits.minimum or level > limits.maximum:
                parser.error(
                    f"snapshot brightness {level} outside limits "
                    f"{limits.minimum}-{limits.maximum}"
                )
            active = set_brightness(info, level, usb_windex=usb_windex)
        except (RuntimeError, TransportError, FileNotFoundError, ValueError) as exc:
            print(exc, file=sys.stderr)
            return 1
        if not args.quiet:
            print(f"Keyboard backlight restored to {level}")
        if args.show_mode:
            print(active)
        return 0

    try:
        level = int(args.level)
    except ValueError:
        parser.error(
            f"unknown command or invalid level: {args.level!r}"
        )

    if level < limits.minimum or level > limits.maximum:
        parser.error(
            f"level must be an integer between {limits.minimum} and {limits.maximum}"
        )

    try:
        if info is None:
            raise RuntimeError("Zenbook Duo keyboard not found")
        active = set_brightness(info, level, usb_windex=usb_windex)
        write_brightness(level)
    except (RuntimeError, TransportError) as exc:
        print(exc, file=sys.stderr)
        return 1

    if not args.quiet:
        print(f"Keyboard backlight set to {level}")
    if args.show_mode:
        print(active)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
