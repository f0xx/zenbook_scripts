"""Debug where Zenbook Duo key events actually arrive (evdev + USB + hidraw)."""

from __future__ import annotations

import os
import select
import struct
import sys
import time
from pathlib import Path

INPUT_EVENT_SIZE = struct.calcsize("@llHHi")
INPUT_EVENT_FMT = "@llHHi"
EV_KEY = 0x01

KEY_NAMES: dict[int, str] = {}


def _load_key_names() -> dict[int, str]:
    names: dict[int, str] = {}
    header = Path("/usr/include/linux/input-event-codes.h")
    if not header.is_file():
        return names
    for line in header.read_text().splitlines():
        if not line.startswith("#define KEY_"):
            continue
        parts = line.split()
        if len(parts) < 3:
            continue
        try:
            names[int(parts[2], 0)] = parts[1]
        except ValueError:
            continue
    return names


def _zenbook_input_devices() -> list[Path]:
    out: list[Path] = []
    for event_dir in sorted(Path("/sys/class/input").glob("event*")):
        name_path = event_dir / "device" / "name"
        if not name_path.is_file():
            continue
        name = name_path.read_text().strip()
        if "Zenbook Duo" in name or name == "Asus WMI hotkeys":
            dev = Path("/dev/input") / event_dir.name
            if dev.exists():
                out.append(dev)
    return out


def _zenbook_hidraws() -> list[Path]:
    out: list[Path] = []
    for hidraw in sorted(Path("/sys/class/hidraw").glob("hidraw*")):
        uevent = hidraw / "device" / "uevent"
        if uevent.is_file() and "1B2C" in uevent.read_text().upper():
            dev = Path("/dev") / hidraw.name
            if dev.exists():
                out.append(dev)
    return out


def _usb_interrupt_eps():
    import usb.core
    import usb.util

    dev = usb.core.find(idVendor=0x0B05, idProduct=0x1B2C)
    if dev is None:
        return []
    eps = []
    cfg = dev.get_active_configuration()
    for intf in cfg:
        inum = intf.bInterfaceNumber
        try:
            if dev.is_kernel_driver_active(inum):
                dev.detach_kernel_driver(inum)
            usb.util.claim_interface(dev, inum)
        except Exception:
            continue
        for ep in intf:
            if usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_IN:
                eps.append((dev, inum, ep))
    return eps


def sniff_all(duration_s: float = 30.0, out_path: Path | None = None) -> int:
    global KEY_NAMES
    KEY_NAMES = _load_key_names()

    log_lines: list[str] = []

    def emit(msg: str) -> None:
        line = f"{time.strftime('%H:%M:%S')} {msg}"
        log_lines.append(line)
        print(line, flush=True)

    emit("=== Zenbook key sniff (press Fn+F4 and other Fn+ keys) ===")
    emit("Tip: run with service stopped: sudo rc-service zenbook-kb-hotkeys stop")
    emit("")

    evdev_fds: dict[int, Path] = {}
    for dev in _zenbook_input_devices():
        try:
            fd = os.open(dev, os.O_RDONLY | os.O_NONBLOCK)
            evdev_fds[fd] = dev
            emit(f"evdev watch: {dev}")
        except OSError as exc:
            emit(f"evdev skip {dev}: {exc}")

    hidraw_fds: dict[int, Path] = {}
    for dev in _zenbook_hidraws():
        try:
            fd = os.open(dev, os.O_RDONLY | os.O_NONBLOCK)
            hidraw_fds[fd] = dev
            emit(f"hidraw watch: {dev}")
        except OSError as exc:
            emit(f"hidraw skip {dev}: {exc}")

    usb_eps = []
    try:
        usb_eps = _usb_interrupt_eps()
        for _dev, inum, ep in usb_eps:
            emit(f"usb watch: interface {inum} ep {ep.bEndpointAddress:#x}")
    except Exception as exc:
        emit(f"usb setup failed: {exc}")

    if not evdev_fds and not hidraw_fds and not usb_eps:
        emit("Nothing to watch.")
        return 1

    emit(f"Sniffing for {duration_s:.0f}s…")
    emit("")

    end = time.monotonic() + duration_s
    usb_dev = usb_eps[0][0] if usb_eps else None

    try:
        while time.monotonic() < end:
            wait_fds = list(evdev_fds) + list(hidraw_fds)
            if wait_fds:
                readable, _, _ = select.select(wait_fds, [], [], 0.05)
            else:
                readable = []

            for fd in readable:
                if fd in evdev_fds:
                    while True:
                        try:
                            data = os.read(fd, INPUT_EVENT_SIZE * 16)
                        except BlockingIOError:
                            break
                        if not data:
                            break
                        for off in range(0, len(data), INPUT_EVENT_SIZE):
                            chunk = data[off : off + INPUT_EVENT_SIZE]
                            if len(chunk) != INPUT_EVENT_SIZE:
                                continue
                            _t1, _t2, etype, code, val = struct.unpack(INPUT_EVENT_FMT, chunk)
                            if etype != EV_KEY:
                                continue
                            name = KEY_NAMES.get(code, f"KEY_{code}")
                            emit(
                                f"evdev {evdev_fds[fd].name}: {name} ({code}) value={val}"
                            )
                elif fd in hidraw_fds:
                    while True:
                        try:
                            data = os.read(fd, 64)
                        except BlockingIOError:
                            break
                        if not data:
                            break
                        emit(f"hidraw {hidraw_fds[fd].name}: raw={data.hex()}")

            for dev, inum, ep in usb_eps:
                try:
                    data = bytes(
                        dev.read(ep.bEndpointAddress, ep.wMaxPacketSize, timeout=10)
                    )
                except Exception:
                    continue
                if data:
                    emit(f"usb if{inum} ep{ep.bEndpointAddress:#x}: raw={data.hex()}")
    except KeyboardInterrupt:
        pass
    finally:
        if usb_dev is not None:
            import usb.util

            for _d, inum, _ep in usb_eps:
                try:
                    usb.util.release_interface(usb_dev, inum)
                except Exception:
                    pass
        for fd in list(evdev_fds) + list(hidraw_fds):
            os.close(fd)

    if out_path:
        out_path.write_text("\n".join(log_lines) + "\n")
        emit(f"Wrote {out_path}")

    return 0
