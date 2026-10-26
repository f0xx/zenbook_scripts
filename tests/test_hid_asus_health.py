"""Unit tests for vendor if4 health checks."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from zenbook_kb import hid_asus_health as health  # noqa: E402


class TestVendorIf4Health(unittest.TestCase):
    def setUp(self) -> None:
        health._last_ensure_mono = 0.0

    def test_vendor_if4_on_asus_true_for_if4_asus_node(self) -> None:
        node = mock.Mock()
        node.name = "0003:0B05:1B2C.000C"
        rdesc = mock.Mock()
        rdesc.is_file.return_value = True
        rdesc.read_bytes.return_value = b"\x00" * 100
        driver = mock.Mock()
        driver.is_symlink.return_value = True
        node.__truediv__ = lambda self, key: {
            "report_descriptor": rdesc,
            "driver": driver,
        }[key]

        with mock.patch.object(Path, "is_dir", return_value=True), mock.patch.object(
            Path, "iterdir", return_value=[node]
        ), mock.patch(
            "zenbook_kb.hid_asus_health.os.path.realpath",
            return_value="/devices/pci/usb3/3-6/3-6:1.4/0003:0B05:1B2C.000C",
        ), mock.patch(
            "zenbook_kb.hid_asus_health.os.readlink",
            return_value="../../../bus/hid/drivers/asus",
        ):
            self.assertTrue(health.vendor_if4_on_asus())

    def test_ensure_skips_when_healthy(self) -> None:
        with mock.patch.object(health, "usb_pogo_docked", return_value=True), mock.patch.object(
            health, "vendor_if4_on_asus", return_value=True
        ), mock.patch.object(health, "run_root") as run_root:
            self.assertTrue(health.ensure_vendor_if4())
            run_root.assert_not_called()

    def test_ensure_respects_cooldown(self) -> None:
        health._last_ensure_mono = health.time.monotonic()
        with mock.patch.object(health, "usb_pogo_docked", return_value=True), mock.patch.object(
            health, "vendor_if4_on_asus", return_value=False
        ), mock.patch.object(health, "sideload_hid_asus_loaded", return_value=True), mock.patch.object(
            health, "find_hid_asus_switch", return_value=Path("/usr/libexec/zenbook-hid-asus-switch")
        ), mock.patch.object(health, "run_root") as run_root:
            self.assertFalse(health.ensure_vendor_if4())
            run_root.assert_not_called()


if __name__ == "__main__":
    unittest.main()
