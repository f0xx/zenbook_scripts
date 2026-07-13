#!/usr/bin/env python3
"""Interactive console configurator for Zenbook Duo keyboard scripts."""

from __future__ import annotations

import argparse
import configparser
import os
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from zenbook_kb.install import detect_init_system, install_all, install_kb_brightness_tree

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "zenbook-scripts"
DEFAULT_CONFIG = DEFAULT_CONFIG_DIR / "zenbook-duo.conf"
DEFAULT_HOTKEYS = DEFAULT_CONFIG_DIR / "zenbook-hotkeys.conf"
EXAMPLE_CONFIG = Path(__file__).resolve().parent / "zenbook-duo.conf.example"
EXAMPLE_HOTKEYS = Path(__file__).resolve().parent / "zenbook-hotkeys.conf.example"


def prompt(label: str, default: str) -> str:
    value = input(f"{label} [{default}]: ").strip()
    return value or default


def yes_no(question: str, default_no: bool = True, *, assume_yes: bool = False) -> bool:
    if assume_yes:
        return True
    suffix = "[y/N]" if default_no else "[Y/n]"
    return input(f"{question} {suffix}: ").strip().lower().startswith("y")


def detect_keyboard() -> str:
    try:
        output = subprocess.check_output(["lsusb"], text=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"
    if "1b2c" in output.lower():
        return "usb"
    return "bluetooth-or-absent"


def write_config(cfg: configparser.ConfigParser, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as fh:
        cfg.write(fh)


def test_brightness(script_dir: Path, level: int) -> None:
    cmd = [sys.executable, str(script_dir / "brightness.py"), str(level), "--show-mode"]
    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=False)


def ensure_hotkeys_config() -> None:
    if DEFAULT_HOTKEYS.exists() or not EXAMPLE_HOTKEYS.exists():
        return
    DEFAULT_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    DEFAULT_HOTKEYS.write_text(EXAMPLE_HOTKEYS.read_text())
    print(f"Created {DEFAULT_HOTKEYS} (edit to bind unmapped Fn+ keys)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Zenbook Duo keyboard configurator + installer")
    parser.add_argument(
        "--defaults",
        action="store_true",
        help="Do not prompt; use existing ~/.config values or project defaults",
    )
    parser.add_argument(
        "--all-yes",
        action="store_true",
        help="Assume yes for all yes/no prompts (use with --defaults for semi-auto)",
    )
    args = parser.parse_args(argv)

    script_dir = SCRIPT_DIR
    cfg = configparser.ConfigParser()
    if DEFAULT_CONFIG.exists():
        cfg.read(DEFAULT_CONFIG)
    elif EXAMPLE_CONFIG.exists():
        cfg.read(EXAMPLE_CONFIG)
    else:
        cfg.read_dict(
            {
                "keyboard": {
                    "usb_vendor_id": "0b05",
                    "usb_product_id": "1b2c",
                    "bt_vendor_id": "0b05",
                    "bt_product_id": "1b2d",
                    "usb_windex": "4",
                    "default_brightness": "1",
                },
                "duo": {"default_backlight": "1", "default_scale": "1"},
            }
        )

    kb = cfg["keyboard"]
    duo = cfg.setdefault("duo", {})

    init_system = detect_init_system()
    print("Zenbook Duo keyboard configurator")
    print(f"Detected connection: {detect_keyboard()}")
    print(f"Detected init system: {init_system} ({'systemctl found' if init_system == 'systemd' else 'OpenRC-like'})")
    print()

    if not args.defaults:
        kb["usb_vendor_id"] = prompt("USB vendor ID (pogo pins)", kb.get("usb_vendor_id", "0b05"))
        kb["usb_product_id"] = prompt("USB product ID", kb.get("usb_product_id", "1b2c"))
        kb["bt_vendor_id"] = prompt("Bluetooth vendor ID", kb.get("bt_vendor_id", "0b05"))
        kb["bt_product_id"] = prompt("Bluetooth product ID", kb.get("bt_product_id", "1b2d"))
        kb["usb_windex"] = prompt("USB interface index (wIndex)", kb.get("usb_windex", "4"))
        kb["default_brightness"] = prompt("Default brightness 0-3", kb.get("default_brightness", "1"))
        duo["default_backlight"] = prompt(
            "duo.sh default backlight 0-3", duo.get("default_backlight", kb["default_brightness"])
        )
        duo["default_scale"] = prompt("duo.sh monitor scale", duo.get("default_scale", "1"))

    write_config(cfg, DEFAULT_CONFIG)
    ensure_hotkeys_config()
    print(f"\nSaved {DEFAULT_CONFIG}")

    if yes_no("Test brightness now?", default_no=True, assume_yes=args.all_yes):
        test_brightness(script_dir, int(kb["default_brightness"]))

    if yes_no(
        "Install kb-brightness + Fn+ hotkey service to /usr/local?",
        default_no=True,
        assume_yes=args.all_yes,
    ):
        with_hotkeys = yes_no(
            f"Install udev rules + {init_system} hotkey listener service?",
            default_no=False,
            assume_yes=args.all_yes,
        )
        install_all(script_dir, with_hotkey_service=with_hotkeys)
        if with_hotkeys:
            print()
            print("Try: kb-brightness-hotkeys --dry-run   (press Fn+ keys)")
            print("Map unmapped keys in ~/.config/zenbook-scripts/zenbook-hotkeys.conf")
            if init_system == "openrc":
                print("Service: rc-service zenbook-kb-hotkeys status")
            else:
                print("Service: systemctl status zenbook-kb-hotkeys.service")
    elif yes_no("Install scripts only (no udev/service)?", default_no=True, assume_yes=args.all_yes):
        install_kb_brightness_tree(script_dir)
        from zenbook_kb.install import install_sudoers_kb_brightness

        install_sudoers_kb_brightness()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
