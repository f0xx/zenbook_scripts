"""UX581 / UX582 front lightbar (ALED0217 / HID 0b05:0124) protocol helpers.

No hardware required to import or unit-test. Live HID writes are opt-in
(``--apply``) and never touch register index 6 (known brick).

Feature report ``0x20`` is 32 payload bytes (33 with report-id). Community map:

| Index | Role (partial) |
|-------|----------------|
| 0 | report id ``0x20`` when sending |
| 1 | animation / mode (1–20 observed) |
| 2 | loop flag (``2`` = infinite in some trials) |
| 3 | repeat count |
| 4 | brightness |
| 5 | LED count |
| 6 | **DO NOT WRITE** — bricks device |
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path

LIGHTBAR_VID = 0x0B05
LIGHTBAR_PID = 0x0124
REPORT_ID_COLOR = 0x20
REPORT_LEN_COLOR = 32  # payload after report id
BRICK_REGISTER = 6

# hidraw ioctl (linux/hidraw.h) — HIDIOCSFEATURE(len) / HIDIOCGFEATURE(len)
_IOC_WRITE = 1
_IOC_READ = 2
_IOC_NRBITS = 8
_IOC_TYPEBITS = 8
_IOC_SIZEBITS = 14
_IOC_NRSHIFT = 0
_IOC_TYPESHIFT = _IOC_NRSHIFT + _IOC_NRBITS
_IOC_SIZESHIFT = _IOC_TYPESHIFT + _IOC_TYPEBITS
_IOC_DIRSHIFT = _IOC_SIZESHIFT + _IOC_SIZEBITS


def _ioc(direction: int, typ: int, nr: int, size: int) -> int:
    return (
        (direction << _IOC_DIRSHIFT)
        | (typ << _IOC_TYPESHIFT)
        | (nr << _IOC_NRSHIFT)
        | (size << _IOC_SIZESHIFT)
    )


def HIDIOCGFEATURE(length: int) -> int:
    return _ioc(_IOC_WRITE | _IOC_READ, ord("H"), 0x07, length)


def HIDIOCSFEATURE(length: int) -> int:
    return _ioc(_IOC_WRITE | _IOC_READ, ord("H"), 0x06, length)


@dataclass(frozen=True)
class LightbarDevice:
    hidraw: Path
    sysfs: Path
    name: str


def is_ux581_family(product: str = "", board: str = "") -> bool:
    blob = f"{product} {board}".upper()
    return "UX581" in blob or "UX582" in blob


def build_report_0x20(
    *,
    anim: int = 1,
    loop: int = 2,
    repeat: int = 0,
    brightness: int = 128,
    led_count: int = 7,
    extra: bytes | None = None,
) -> bytes:
    """Build feature report id 0x20 + 32-byte payload.

    Index 6 is forced to 0 and must stay unused.
    """
    buf = bytearray(1 + REPORT_LEN_COLOR)
    buf[0] = REPORT_ID_COLOR
    buf[1] = anim & 0xFF
    buf[2] = loop & 0xFF
    buf[3] = repeat & 0xFF
    buf[4] = brightness & 0xFF
    buf[5] = led_count & 0xFF
    buf[BRICK_REGISTER] = 0  # never set
    if extra:
        # extra overlays from index 7 onward only
        for i, b in enumerate(extra):
            idx = 7 + i
            if idx >= len(buf):
                break
            if idx == BRICK_REGISTER:
                continue
            buf[idx] = b
    return bytes(buf)


def assert_report_safe(report: bytes) -> None:
    if not report or report[0] != REPORT_ID_COLOR:
        raise ValueError("expected feature report id 0x20")
    if len(report) < 1 + REPORT_LEN_COLOR:
        raise ValueError(f"report too short: {len(report)}")
    if len(report) > BRICK_REGISTER and report[BRICK_REGISTER] != 0:
        raise ValueError(
            f"refusing report: byte[{BRICK_REGISTER}]={report[BRICK_REGISTER]} "
            "(known to brick UX581 lightbar)"
        )


def format_report_hex(report: bytes) -> str:
    return ",".join(f"{b:02x}" for b in report)


def _read_text(path: Path) -> str:
    try:
        return path.read_text().strip()
    except OSError:
        return ""


def find_lightbar_devices() -> list[LightbarDevice]:
    """Locate hidraw nodes for VID:PID 0b05:0124 via sysfs."""
    found: list[LightbarDevice] = []
    for raw in sorted(Path("/sys/class/hidraw").glob("hidraw*")):
        device = raw / "device"
        # Walk up to HID device with uevent / id
        hid = device.resolve() if device.exists() else None
        if hid is None:
            continue
        # Prefer ../uevent MODALIAS=hid:b0003g0001v00000B05p00000124
        uevent = _read_text(hid / "uevent")
        if not uevent:
            # sometimes device is the hidraw's parent
            uevent = _read_text(hid.parent / "uevent")
        modalias = ""
        for line in uevent.splitlines():
            if line.startswith("MODALIAS="):
                modalias = line.split("=", 1)[1].upper()
                break
        if "V00000B05" not in modalias or "P00000124" not in modalias:
            # fallback: idVendor/idProduct on USB parent
            usb = hid
            ok = False
            for _ in range(6):
                vid = _read_text(usb / "idVendor").lower()
                pid = _read_text(usb / "idProduct").lower()
                if vid == "0b05" and pid == "0124":
                    ok = True
                    break
                parent = usb.parent
                if parent == usb:
                    break
                usb = parent
            if not ok:
                continue
        name = _read_text(hid / "name") or modalias or "0b05:0124"
        node = Path("/dev") / raw.name
        found.append(LightbarDevice(hidraw=node, sysfs=raw, name=name))
    return found


def send_feature_report(hidraw: Path, report: bytes) -> None:
    assert_report_safe(report)
    import fcntl

    fd = os.open(hidraw, os.O_RDWR)
    try:
        buf = bytearray(report)
        # Some kernels want exact length; pad if needed
        fcntl.ioctl(fd, HIDIOCSFEATURE(len(buf)), buf, True)
    finally:
        os.close(fd)


def get_feature_report(hidraw: Path, report_id: int = REPORT_ID_COLOR, length: int = 33) -> bytes:
    import fcntl

    fd = os.open(hidraw, os.O_RDWR)
    try:
        buf = bytearray(length)
        buf[0] = report_id & 0xFF
        fcntl.ioctl(fd, HIDIOCGFEATURE(length), buf, True)
        return bytes(buf)
    finally:
        os.close(fd)


def hidapitester_cmdline(report: bytes) -> str:
    """Equivalent hidapitester invocation for operators without this CLI."""
    assert_report_safe(report)
    payload = format_report_hex(report)
    return (
        f"sudo hidapitester --vidpid 0B05/0124 -l {len(report)} "
        f"--open --send-feature {payload}"
    )


def _resolve_device(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit)
    devs = find_lightbar_devices()
    if not devs:
        raise FileNotFoundError("no 0b05:0124 hidraw found")
    return devs[0].hidraw


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="UX581 lightbar helper (0b05:0124 feature report 0x20). "
        "Default is dry-run; pass --apply to write HID (never writes reg6)."
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="List matching hidraw devices")
    sub.add_parser("status", help="DMI hint + device presence (no HID write)")

    g = sub.add_parser("get", help="Read feature report 0x20 (needs device)")
    g.add_argument("--device", help="hidraw path (default: first match)")

    s = sub.add_parser("set", help="Build/send report 0x20")
    s.add_argument("--anim", type=int, default=1, help="mode / animation (1–20)")
    s.add_argument("--loop", type=int, default=2, help="loop flag (2≈infinite)")
    s.add_argument("--repeat", type=int, default=0)
    s.add_argument("--brightness", type=int, default=128)
    s.add_argument("--leds", type=int, default=7, dest="led_count")
    s.add_argument("--apply", action="store_true", help="Write to device (else print only)")
    s.add_argument("--device", help="hidraw path (default: first match)")

    raw = sub.add_parser("raw", help="Send hex bytes (report id first); blocks non-zero byte[6]")
    raw.add_argument("hex", help="comma or space separated hex, e.g. 20,01,02,...")
    raw.add_argument("--apply", action="store_true")
    raw.add_argument("--device", help="hidraw path")

    args = p.parse_args(argv)

    if args.cmd == "list":
        devs = find_lightbar_devices()
        if not devs:
            print("no 0b05:0124 hidraw found (BIOS Fast Boot off?)")
            return 1
        for d in devs:
            print(f"{d.hidraw}  {d.name}")
        return 0

    if args.cmd == "status":
        from zenbook_kb.dmi import board_name, product_name

        prod, board = product_name(), board_name()
        print(f"DMI product: {prod}")
        print(f"DMI board:   {board}")
        print(f"UX581 family: {is_ux581_family(prod, board)}")
        devs = find_lightbar_devices()
        print(f"lightbar HID: {'yes' if devs else 'no'} ({len(devs)} node(s))")
        for d in devs:
            print(f"  {d.hidraw}  {d.name}")
        print("WMI asus::lightbar is on/off only — not used for colour.")
        return 0

    if args.cmd == "get":
        try:
            path = _resolve_device(args.device)
        except FileNotFoundError as exc:
            print(exc, file=sys.stderr)
            return 1
        data = get_feature_report(path)
        print(format_report_hex(data))
        return 0

    if args.cmd == "set":
        report = build_report_0x20(
            anim=args.anim,
            loop=args.loop,
            repeat=args.repeat,
            brightness=args.brightness,
            led_count=args.led_count,
        )
        assert_report_safe(report)
        print(f"report: {format_report_hex(report)}")
        print(f"hidapitester: {hidapitester_cmdline(report)}")
        if not args.apply:
            print("dry-run (pass --apply to write)")
            return 0
        try:
            path = _resolve_device(args.device)
        except FileNotFoundError as exc:
            print(exc, file=sys.stderr)
            return 1
        send_feature_report(path, report)
        print(f"wrote {path}")
        return 0

    if args.cmd == "raw":
        parts = args.hex.replace(",", " ").split()
        report = bytes(int(x, 16) for x in parts)
        assert_report_safe(report)
        print(f"report: {format_report_hex(report)}")
        print(f"hidapitester: {hidapitester_cmdline(report)}")
        if not args.apply:
            print("dry-run (pass --apply to write)")
            return 0
        try:
            path = _resolve_device(args.device)
        except FileNotFoundError as exc:
            print(exc, file=sys.stderr)
            return 1
        send_feature_report(path, report)
        print(f"wrote {path}")
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
