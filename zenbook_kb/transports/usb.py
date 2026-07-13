"""USB (pogo-pin) transport via pyusb HID SET_REPORT control transfer."""

from __future__ import annotations

import usb.core
import usb.util

from zenbook_kb.detect import ConnectionInfo, DeviceIds
from zenbook_kb.protocol import (
    USB_BM_REQUEST_TYPE,
    USB_B_REQUEST,
    USB_WINDEX,
    USB_WLENGTH,
    USB_WVALUE,
    build_usb_packet,
    clamp_brightness,
)
from zenbook_kb.transports.base import Transport, TransportError


class UsbTransport(Transport):
    name = "usb"

    def __init__(self, ids: DeviceIds, windex: int = USB_WINDEX) -> None:
        self.ids = ids
        self.windex = windex
        self._dev: usb.core.Device | None = None

    def is_available(self) -> bool:
        return usb.core.find(idVendor=self.ids.vendor_id, idProduct=self.ids.product_id) is not None

    def _open(self) -> usb.core.Device:
        dev = usb.core.find(idVendor=self.ids.vendor_id, idProduct=self.ids.product_id)
        if dev is None:
            raise TransportError(
                f"USB device not found ({self.ids.vendor_id:04x}:{self.ids.product_id:04x})"
            )
        return dev

    def set_brightness(self, level: int) -> None:
        level = clamp_brightness(level)
        data = build_usb_packet(level)
        dev = self._open()
        detached = False

        if dev.is_kernel_driver_active(self.windex):
            try:
                dev.detach_kernel_driver(self.windex)
                detached = True
            except usb.core.USBError as exc:
                raise TransportError(f"Could not detach kernel driver: {exc}") from exc

        try:
            ret = dev.ctrl_transfer(
                USB_BM_REQUEST_TYPE,
                USB_B_REQUEST,
                USB_WVALUE,
                self.windex,
                data,
                timeout=1000,
            )
            if ret != USB_WLENGTH:
                raise TransportError(f"Only {ret} of {USB_WLENGTH} bytes sent")
        except usb.core.USBError as exc:
            raise TransportError(f"USB control transfer failed: {exc}") from exc
        finally:
            if detached:
                try:
                    dev.attach_kernel_driver(self.windex)
                except usb.core.USBError:
                    pass


def transport_for(info: ConnectionInfo, windex: int = USB_WINDEX) -> UsbTransport:
    return UsbTransport(info.ids, windex=windex)
