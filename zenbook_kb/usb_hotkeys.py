"""USB interface 4 vendor hotkey reports for Zenbook Duo (0b05:1b2c).

hid-generic does not bind interface 4. Vendor hotkeys use interrupt IN on ep 0x85
after the ASUS HID handshake (hid-asus.c: asus_kbd_init).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

try:
    from zenbook_kb.protocol import USB_BM_REQUEST_TYPE, USB_B_REQUEST, USB_WINDEX
except ImportError:
    USB_BM_REQUEST_TYPE = 0x21
    USB_B_REQUEST = 0x09
    USB_WINDEX = 4

VENDOR_REPORT_ID = 0x5A
USB_VENDOR_ID = 0x0B05
USB_PRODUCT_ID = 0x1B2C
USB_INTERFACE = USB_WINDEX

# ASUS vendor usage codes (hid-asus.c / asus-wmi notify codes)
VENDOR_KBD_BRT_UP = 0xC4
VENDOR_KBD_BRT_DOWN = 0xC5
VENDOR_KBD_BRT_TOGGLE = 0xC7
VENDOR_FNLOCK = 0x4E
VENDOR_PROFILE_CYCLE = 0x9D

ASUS_HANDSHAKE = bytes(
    [
        VENDOR_REPORT_ID,
        0x41,
        0x53,
        0x55,
        0x53,
        0x20,
        0x54,
        0x65,
        0x63,
        0x68,
        0x2E,
        0x49,
        0x6E,
        0x63,
        0x2E,
        0x00,
    ]
)

ASUS_INIT_PACKETS = (
    bytes([VENDOR_REPORT_ID, 0x05, 0x20, 0x31, 0x00, 0x08]),
    bytes([VENDOR_REPORT_ID, 0xBA, 0xC5, 0xC4]),
    bytes([VENDOR_REPORT_ID, 0xD0, 0x8F, 0x01]),
    bytes([VENDOR_REPORT_ID, 0xD0, 0x85, 0xFF]),
)


@dataclass
class UsbVendorEvent:
    code: int
    raw: bytes
    pressed: bool = True


def _usb_set_feature(dev, payload: bytes, interface: int = USB_INTERFACE) -> None:
    """HID SET_REPORT (feature) on the vendor interface."""
    buf = bytearray(16)
    buf[: len(payload)] = payload
    dev.ctrl_transfer(
        USB_BM_REQUEST_TYPE,
        USB_B_REQUEST,
        (0x03 << 8) | payload[0],
        interface,
        bytes(buf),
        timeout=1000,
    )


def _usb_init_vendor(dev, interface: int = USB_INTERFACE) -> None:
    """ASUS handshake + OOBE/init (hid-asus asus_kbd_init / asus_kbd_disable_oobe)."""
    _usb_set_feature(dev, ASUS_HANDSHAKE, interface)
    for packet in ASUS_INIT_PACKETS:
        _usb_set_feature(dev, packet, interface)


def _import_usb():
    try:
        import usb.core
        import usb.util
    except ImportError as exc:
        raise RuntimeError("pyusb is required for USB hotkey monitoring") from exc
    return usb.core, usb.util


class UsbVendorHotkeys:
    """Poll interrupt IN on Zenbook Duo USB vendor interface."""

    def __init__(
        self,
        vendor_id: int = USB_VENDOR_ID,
        product_id: int = USB_PRODUCT_ID,
        interface: int = USB_INTERFACE,
    ) -> None:
        self.vendor_id = vendor_id
        self.product_id = product_id
        self.interface = interface
        self._usb = None
        self._dev = None
        self._endpoint = None
        self._detached = False

    @property
    def available(self) -> bool:
        usb_core, _ = _import_usb()
        return usb_core.find(idVendor=self.vendor_id, idProduct=self.product_id) is not None

    def open(self) -> None:
        usb_core, usb_util = _import_usb()
        self._usb = (usb_core, usb_util)
        dev = usb_core.find(idVendor=self.vendor_id, idProduct=self.product_id)
        if dev is None:
            raise RuntimeError(
                f"USB keyboard not found ({self.vendor_id:04x}:{self.product_id:04x})"
            )
        self._dev = dev
        try:
            if dev.is_kernel_driver_active(self.interface):
                dev.detach_kernel_driver(self.interface)
                self._detached = True
            usb_util.claim_interface(dev, self.interface)
        except usb_core.USBError as exc:
            if getattr(exc, "errno", None) == 16:
                raise RuntimeError(
                    "USB interface 4 is busy (is zenbook-kb-hotkeys already running?). "
                    "Run: sudo rc-service zenbook-kb-hotkeys stop"
                ) from exc
            raise
        try:
            _usb_init_vendor(dev, self.interface)
            print("USB vendor init: ASUS handshake sent", file=sys.stderr, flush=True)
        except Exception as exc:
            print(f"USB vendor init warning: {exc}", file=sys.stderr, flush=True)
        cfg = dev.get_active_configuration()
        intf = cfg[(self.interface, 0)]
        ep = usb_util.find_descriptor(
            intf,
            custom_match=lambda e: usb_util.endpoint_direction(e.bEndpointAddress)
            == usb_util.ENDPOINT_IN,
        )
        if ep is None:
            raise RuntimeError(f"No interrupt IN endpoint on interface {self.interface}")
        self._endpoint = ep

    def close(self) -> None:
        if self._dev is None or self._usb is None:
            return
        _, usb_util = self._usb
        try:
            usb_util.release_interface(self._dev, self.interface)
        except Exception:
            pass
        if self._detached:
            try:
                self._dev.attach_kernel_driver(self.interface)
            except Exception:
                pass
        self._dev = None
        self._endpoint = None
        self._usb = None
        self._detached = False

    def poll(self, timeout_ms: int = 100) -> UsbVendorEvent | None:
        if self._dev is None or self._endpoint is None:
            return None
        usb_core, _ = self._usb
        try:
            data = bytes(
                self._dev.read(
                    self._endpoint.bEndpointAddress,
                    self._endpoint.wMaxPacketSize,
                    timeout=timeout_ms,
                )
            )
        except usb_core.USBTimeoutError:
            return None
        except usb_core.USBError as exc:
            print(f"usb-hotkeys: read error: {exc}", file=sys.stderr)
            return None
        return parse_vendor_report(data)


def parse_vendor_report(data: bytes) -> UsbVendorEvent | None:
    """Parse 0x5a vendor input report from interface 4."""
    if len(data) < 2 or data[0] != VENDOR_REPORT_ID:
        return None
    code = data[1]
    # Byte 2 is often 1 on press, 0 on release (observed on UX8406).
    pressed = True if len(data) < 3 else data[2] != 0
    if not pressed:
        return None
    return UsbVendorEvent(code=code, raw=data, pressed=pressed)


def builtin_usb_vendor_actions() -> dict[int, str]:
    """Map vendor byte → action string (same format as zenbook-hotkeys.conf)."""
    return {
        VENDOR_KBD_BRT_UP: "kb-brightness:+1",
        VENDOR_KBD_BRT_DOWN: "kb-brightness:-1",
        VENDOR_KBD_BRT_TOGGLE: "kb-brightness:toggle",
        VENDOR_PROFILE_CYCLE: "shell:asusctl profile -n 2>/dev/null || true",
        0x99: "shell:asusctl profile -n 2>/dev/null || true",
        0xAE: "shell:asusctl profile -n 2>/dev/null || true",
        0x10: "display-brightness:down",
        0x20: "display-brightness:up",
        0x7C: "audio:mic-mute",
        0x88: "rfkill:bluetooth",
        0x9C: "shell:platform-screen-swap",
        # Observed on UX8406 during debug; bind manually once confirmed.
        0x3D: "log",
        VENDOR_FNLOCK: "log",  # toggles in kernel with hid-asus; log for now
    }


def sniff_usb(duration_s: float = 30.0) -> int:
    """Print raw USB vendor reports (press Fn+ keys during this window)."""
    mon = UsbVendorHotkeys()
    if not mon.available:
        print("USB Zenbook keyboard (0b05:1b2c) not found", file=sys.stderr)
        return 1
    mon.open()
    print(
        f"Sniffing USB interface {USB_INTERFACE} for {duration_s:.0f}s — press Fn+F4 etc.",
        flush=True,
    )
    print("(Ignore terminal garbage like ^[OS — look for lines starting with usb:)", flush=True)
    import time

    end = time.monotonic() + duration_s
    try:
        while time.monotonic() < end:
            if mon._dev is None or mon._endpoint is None:
                break
            usb_core, _ = mon._usb
            try:
                data = bytes(
                    mon._dev.read(
                        mon._endpoint.bEndpointAddress,
                        mon._endpoint.wMaxPacketSize,
                        timeout=200,
                    )
                )
            except usb_core.USBTimeoutError:
                continue
            except usb_core.USBError as exc:
                print(f"usb read error: {exc}", flush=True)
                continue
            if not data:
                continue
            ev = parse_vendor_report(data)
            if ev is not None:
                print(f"usb vendor 0x{ev.code:02x}  raw={data.hex()}", flush=True)
            else:
                print(f"usb raw (unparsed)  raw={data.hex()}", flush=True)
    except KeyboardInterrupt:
        pass
    finally:
        mon.close()
    return 0
