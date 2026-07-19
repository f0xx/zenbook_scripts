#!/usr/bin/env python3
"""Interactive console configurator for Zenbook Duo keyboard scripts."""

from __future__ import annotations

import argparse
import configparser
import subprocess
import sys
import traceback
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from zenbook_kb.install import (
    detect_init_system,
    install_all,
    install_fan_control_support,
    install_kb_brightness_tree,
    install_sudoers_kb_brightness,
    print_install_summary,
)
from zenbook_kb.dmi import has_platform_profile, has_screenpad_sysfs, is_ux5400, product_name
from zenbook_kb.users import default_duo_config, default_hotkeys_config, resolve_config_dir

EXAMPLE_CONFIG = Path(__file__).resolve().parent / "zenbook-duo.conf.example"
EXAMPLE_HOTKEYS = Path(__file__).resolve().parent / "zenbook-hotkeys.conf.example"


def prompt(label: str, default: str) -> str:
    value = input(f"{label} [{default}]: ").strip()
    return value or default


def yes_no(question: str, default_no: bool = True, *, assume_yes: bool = False) -> bool:
    if assume_yes:
        print(f"{question} → yes (--all-yes)", flush=True)
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
    print(f"Running: {' '.join(cmd)}", flush=True)
    subprocess.run(cmd, check=False)


def ensure_hotkeys_config() -> None:
    default_hotkeys = default_hotkeys_config()
    config_dir = resolve_config_dir()
    if default_hotkeys.exists() or not EXAMPLE_HOTKEYS.exists():
        return
    config_dir.mkdir(parents=True, exist_ok=True)
    default_hotkeys.write_text(EXAMPLE_HOTKEYS.read_text())
    print(f"Created {default_hotkeys} (edit to bind unmapped Fn+ keys)", flush=True)


def resolve_fan_control_flag(args: argparse.Namespace) -> bool | None:
    """Return True/False when CLI forced; None = decide later (prompt / auto)."""
    if args.include_fan_control and args.no_include_fan_control:
        raise SystemExit("use only one of --include-fan-control / --no-include-fan-control")
    if args.include_fan_control:
        return True
    if args.no_include_fan_control:
        return False
    return None


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
    parser.add_argument(
        "--include-fan-control",
        action="store_true",
        help="Install adaptive platform-fan-control (config + OpenRC)",
    )
    parser.add_argument(
        "--no-include-fan-control",
        action="store_true",
        help="Skip adaptive fan-control install (overrides auto / --all-yes)",
    )
    args = parser.parse_args(argv)

    script_dir = SCRIPT_DIR
    default_config = default_duo_config()
    cfg = configparser.ConfigParser()
    if default_config.exists():
        cfg.read(default_config)
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
    dmi_name = product_name() or "unknown"
    screenpad = has_screenpad_sysfs() or is_ux5400()
    platform_profile = has_platform_profile()
    fan_flag = resolve_fan_control_flag(args)
    print("Zenbook Duo keyboard configurator", flush=True)
    print(f"Detected DMI product: {dmi_name}", flush=True)
    print(f"Detected connection: {detect_keyboard()}", flush=True)
    print(f"Detected ScreenPad sysfs: {'yes' if has_screenpad_sysfs() else 'no'}", flush=True)
    print(f"Detected platform_profile: {'yes' if platform_profile else 'no'}", flush=True)
    print(
        f"Detected init system: {init_system} "
        f"({'systemctl found' if init_system == 'systemd' else 'OpenRC-like'})",
        flush=True,
    )
    print(flush=True)

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

    write_config(cfg, default_config)
    ensure_hotkeys_config()
    print(f"\nSaved {default_config}", flush=True)

    if yes_no("Test brightness now?", default_no=True, assume_yes=args.all_yes):
        test_brightness(script_dir, int(kb["default_brightness"]))

    # --- collect install choices first (no side effects yet) ---
    want_screenpad = False
    want_screenpad_sync = False
    if screenpad:
        want_screenpad = yes_no(
            "Install ScreenPad + platform-profile tools (UX5400 / asus_screenpad)?",
            default_no=False,
            assume_yes=args.all_yes,
        )
        if want_screenpad:
            want_screenpad_sync = yes_no(
                "Also install ScreenPad brightness-sync service?",
                default_no=False,
                assume_yes=args.all_yes,
            )

    with_fan: bool | None = fan_flag
    if with_fan is None:
        if not platform_profile:
            with_fan = False
        elif args.all_yes:
            with_fan = True
        else:
            with_fan = yes_no(
                "Install adaptive fan-control daemon (/etc/zenbook-scripts/fan-control.json)?",
                default_no=False,
                assume_yes=False,
            )

    want_full = yes_no(
        "Install kb-brightness + tools to /usr/local?",
        default_no=True,
        assume_yes=args.all_yes,
    )
    with_hotkeys = False
    if want_full:
        with_hotkeys = yes_no(
            f"Also install udev rules + {init_system} hotkey listener service?",
            default_no=False,
            assume_yes=args.all_yes,
        )
    elif not with_fan and not want_screenpad:
        if yes_no("Install scripts only (no udev/service)?", default_no=True, assume_yes=args.all_yes):
            want_full = True
            with_hotkeys = False

    print("\n--- starting install (progress below) ---\n", flush=True)

    try:
        if want_full or want_screenpad or with_fan:
            # One path: tree + optional pieces (avoids silent mid-prompt hangs).
            if want_full or want_screenpad:
                install_all(
                    script_dir,
                    with_hotkey_service=with_hotkeys if want_full else False,
                    with_screenpad=want_screenpad,
                    with_screenpad_sync=want_screenpad_sync,
                    with_fan_control=bool(with_fan),
                    fan_control_enable=bool(with_fan),
                )
            elif with_fan:
                install_kb_brightness_tree(script_dir)
                install_sudoers_kb_brightness()
                install_fan_control_support(script_dir, enable_service=True, seed_config=True)
        else:
            print("Nothing selected to install.", flush=True)
    except subprocess.TimeoutExpired as exc:
        print(f"\nERROR: command timed out: {exc.cmd}", file=sys.stderr, flush=True)
        print("Partial install possible — see summary.", file=sys.stderr, flush=True)
        print_install_summary()
        return 1
    except Exception:
        print("\nERROR during install:", file=sys.stderr, flush=True)
        traceback.print_exc()
        print_install_summary()
        return 1

    print_install_summary()

    if with_hotkeys:
        print("\nTry: kb-brightness-hotkeys --dry-run", flush=True)
        if init_system == "openrc":
            print("Service: rc-service zenbook-kb-hotkeys status", flush=True)
    if with_fan:
        print("Fan: platform-probe && platform-fan-control check", flush=True)
        if init_system == "openrc":
            print("Service: rc-service zenbook-platform-fan-control status", flush=True)
    if want_screenpad:
        print("Try: screenpad status && kb-platform-profile list", flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
