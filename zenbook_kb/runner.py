"""Select and run the appropriate keyboard backlight transport."""

from __future__ import annotations

from zenbook_kb.detect import ConnectionInfo, ConnectionMode
from zenbook_kb.transports.base import Transport, TransportError
from zenbook_kb.transports.bluetooth import BluetoothTransport, transport_for as bt_for
from zenbook_kb.transports.usb import UsbTransport, transport_for as usb_for


def get_transport(info: ConnectionInfo, usb_windex: int = 4) -> Transport:
    if info.mode is ConnectionMode.USB:
        return usb_for(info, windex=usb_windex)
    return bt_for(info)


def set_brightness(info: ConnectionInfo, level: int, usb_windex: int = 4) -> str:
    transport = get_transport(info, usb_windex=usb_windex)
    if not transport.is_available():
        raise TransportError(f"{transport.name} transport is not available")
    transport.set_brightness(level)
    return transport.name
