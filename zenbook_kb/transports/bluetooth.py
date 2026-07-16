"""Bluetooth transport via hidraw HIDIOCSFEATURE ioctl."""

from __future__ import annotations

import fcntl
import os
import struct
from pathlib import Path

from zenbook_kb.detect import ConnectionInfo
from zenbook_kb.protocol import build_brightness_report, clamp_brightness
from zenbook_kb.transports.base import Transport, TransportError

# HIDIOCSFEATURE(len) for a 64-byte buffer on Linux x86_64.
_HIDIOCSFEATURE_64 = 0xC0094806


class BluetoothTransport(Transport):
    name = "bluetooth"

    def __init__(self, hidraw_path: Path | None) -> None:
        self.hidraw_path = hidraw_path

    def is_available(self) -> bool:
        return self.hidraw_path is not None and self.hidraw_path.exists()

    def set_brightness(self, level: int) -> None:
        if not self.hidraw_path:
            raise TransportError("Bluetooth hidraw device path is not set")

        level = clamp_brightness(level)
        report = build_brightness_report(level)
        buf = bytearray(64)
        buf[: len(report)] = report

        try:
            fd = os.open(self.hidraw_path, os.O_RDWR)
        except OSError as exc:
            if exc.errno == 13:
                raise TransportError(
                    f"Cannot open {self.hidraw_path}: permission denied (try sudo)"
                ) from exc
            raise TransportError(f"Cannot open {self.hidraw_path}: {exc}") from exc

        try:
            fcntl.ioctl(fd, _HIDIOCSFEATURE_64, buf)
        except OSError as exc:
            raise TransportError(
                f"HID feature report failed on {self.hidraw_path}: {exc}"
            ) from exc
        finally:
            os.close(fd)


def transport_for(info: ConnectionInfo) -> BluetoothTransport:
    return BluetoothTransport(info.hidraw_path)
