"""Vendor USB if4 health checks and recovery (UX8406 hid-asus sideload).

When interface 4 loses its HID node (usbhid bound but no ``0003:0B05:1B2C.*``
on ``asus``), Fn-row / vendor hotkeys stop working until ``ensure-if4`` or
``rebind-hid-asus.sh`` runs.  ``zenbook-kb-hotkeys`` calls this module on
hotplug churn and on a periodic timer while the docked keyboard is present.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path

from zenbook_kb.priv import run_root

log = logging.getLogger("zenbook.hid_asus_health")

VENDOR_IF4_RDESC_MIN = 90
VENDOR_IF4_RDESC_MAX = 120
DEFAULT_ENSURE_COOLDOWN_S = 120.0
DEFAULT_PERIODIC_CHECK_S = 60.0

HID_ASUS_READY = Path("/run/zenbook-hid-asus/ready")

_last_ensure_mono: float = 0.0


def find_hid_asus_switch() -> Path | None:
    for cand in (
        Path("/usr/libexec/zenbook-hid-asus-switch"),
        Path("/usr/local/libexec/zenbook-hid-asus-switch"),
    ):
        if cand.is_file() and os.access(cand, os.X_OK):
            return cand
    return None


def usb_pogo_docked() -> bool:
    hid_root = Path("/sys/bus/usb/devices")
    if not hid_root.is_dir():
        return False
    for node in hid_root.iterdir():
        try:
            vendor = (node / "idVendor").read_text(encoding="ascii").strip().lower()
            product = (node / "idProduct").read_text(encoding="ascii").strip().lower()
        except OSError:
            continue
        if vendor == "0b05" and product == "1b2c":
            return True
    return False


def sideload_hid_asus_loaded() -> bool:
    return Path("/sys/module/hid_asus").is_dir()


def _report_descriptor_bytes(path: Path) -> int:
    """Byte length of HID report descriptor (sysfs stat.st_size is often 4096)."""
    try:
        return len(path.read_bytes())
    except OSError:
        return 0


def vendor_if4_on_asus() -> bool:
    """True when USB if4 has an ``asus`` HID node (90–120 byte vendor rdesc)."""
    hid_root = Path("/sys/bus/hid/devices")
    if not hid_root.is_dir():
        return False
    for node in hid_root.iterdir():
        name = node.name.upper()
        if "0B05" not in name or "1B2C" not in name:
            continue
        try:
            path = os.path.realpath(node)
        except OSError:
            continue
        if ":1.4/" not in path:
            continue
        rdesc = node / "report_descriptor"
        if rdesc.is_file():
            size = _report_descriptor_bytes(rdesc)
            if size and not (VENDOR_IF4_RDESC_MIN <= size <= VENDOR_IF4_RDESC_MAX):
                continue
        driver = node / "driver"
        if not driver.is_symlink():
            continue
        try:
            target = os.readlink(driver)
        except OSError:
            continue
        if "asus" not in os.fsdecode(target).lower():
            continue
        return True
    return False


@dataclass(frozen=True)
class VendorIf4Status:
    docked: bool
    sideload: bool
    healthy: bool
    switch: str | None

    def summary(self) -> str:
        parts = [
            f"docked={'yes' if self.docked else 'no'}",
            f"sideload={'yes' if self.sideload else 'no'}",
            f"if4_asus={'yes' if self.healthy else 'NO'}",
        ]
        if self.switch:
            parts.append(f"switch={self.switch}")
        return " ".join(parts)


def vendor_if4_status() -> VendorIf4Status:
    sw = find_hid_asus_switch()
    return VendorIf4Status(
        docked=usb_pogo_docked(),
        sideload=sideload_hid_asus_loaded(),
        healthy=vendor_if4_on_asus(),
        switch=str(sw) if sw else None,
    )


def ensure_vendor_if4(*, force: bool = False, cooldown_s: float = DEFAULT_ENSURE_COOLDOWN_S) -> bool:
    """Run ``zenbook-hid-asus-switch ensure-if4`` (root). Returns True if if4 is healthy after."""
    global _last_ensure_mono

    if not usb_pogo_docked():
        return False
    if vendor_if4_on_asus():
        return True
    if not sideload_hid_asus_loaded():
        log.debug("ensure-if4 skipped: hid_asus module not loaded")
        return False

    now = time.monotonic()
    if not force and (now - _last_ensure_mono) < cooldown_s:
        log.debug("ensure-if4 skipped: cooldown %.0fs", cooldown_s - (now - _last_ensure_mono))
        return False

    switch = find_hid_asus_switch()
    if switch is None:
        log.warning("ensure-if4 skipped: zenbook-hid-asus-switch not found")
        return False

    _last_ensure_mono = now
    log.info("ensure-if4: invoking %s (force=%s)", switch, force)
    try:
        proc = run_root(
            [str(switch), "ensure-if4"],
            timeout=120,
            capture=True,
        )
    except OSError as exc:
        log.warning("ensure-if4 failed to run: %s", exc)
        return False

    out = (proc.stdout or b"").decode(errors="replace").strip()
    err = (proc.stderr or b"").decode(errors="replace").strip()
    if out:
        log.info("ensure-if4: %s", out.replace("\n", " | "))
    if proc.returncode != 0:
        log.warning("ensure-if4 exit %s: %s", proc.returncode, err or out)
        return vendor_if4_on_asus()

    ok = vendor_if4_on_asus()
    if ok:
        log.info("ensure-if4: vendor if4 restored")
    else:
        log.warning("ensure-if4: finished but if4 still missing")
    return ok


def maybe_ensure_vendor_if4(*, reason: str, force: bool = False) -> bool:
    """Recover if4 when docked + sideload active; log *reason*."""
    if not usb_pogo_docked() or not sideload_hid_asus_loaded():
        return False
    if vendor_if4_on_asus():
        return True
    log.warning("vendor if4 unhealthy (%s)", reason)
    return ensure_vendor_if4(force=force)


def touch_hid_asus_ready() -> None:
    """Signal OpenRC hotkeys that boot sideload + ensure-if4 finished."""
    try:
        HID_ASUS_READY.parent.mkdir(parents=True, exist_ok=True)
        HID_ASUS_READY.touch()
    except OSError as exc:
        log.debug("could not write %s: %s", HID_ASUS_READY, exc)
