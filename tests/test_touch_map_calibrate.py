"""Unit tests for touchpad calibrate analyzer and touch-map presets."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from zenbook_kb.touch_map import (  # noqa: E402
    KWinInputDevice,
    MapRule,
    UX8406_PRESET,
    activate_kwin_live_filter,
    auto_rules,
    preset_rules_for_machine,
    restore_all_compositor_touchpads,
    restore_kwin_touchpad_after_filter,
)
from zenbook_kb.touchpad_calibrate import (  # noqa: E402
    analyze_capture_jsonl,
    detect_transport,
    suggest_knobs,
)


class TestTouchpadCalibrate(unittest.TestCase):
    def test_pointer_touchpad_name(self) -> None:
        from zenbook_kb.touch_map import _is_pointer_touchpad_name

        self.assertTrue(
            _is_pointer_touchpad_name(
                "Primax Electronics Ltd. ASUS Zenbook Duo Keyboard Touchpad"
            )
        )
        self.assertFalse(
            _is_pointer_touchpad_name(
                "Primax Electronics Ltd. ASUS Zenbook Duo Keyboard Touchpad (filter)"
            )
        )
        self.assertFalse(_is_pointer_touchpad_name("ELAN9009:00 04F3:425A"))

        self.assertEqual(
            detect_transport(phys="usb-0000:00:14.0-6/input5"),
            "usb",
        )
        self.assertEqual(
            detect_transport(name="BlueZ Touchpad", phys=""),
            "bluetooth",
        )
        self.assertEqual(detect_transport(phys="i2c-ELAN9009:00"), "i2c")

    def test_analyze_and_suggest(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "cap.jsonl"
            rows = [
                {"kind": "meta", "sequence": "mixed", "transport": "usb"},
                {"passed": False, "dropped_by": "outlier_reject", "typing_armed": False},
                {"passed": False, "dropped_by": "outlier_reject", "typing_armed": False},
                {"passed": False, "dropped_by": "outlier_reject", "typing_armed": False},
                {"passed": False, "dropped_by": "outlier_reject", "typing_armed": False},
                {"passed": False, "dropped_by": "outlier_reject", "typing_armed": False},
                {"passed": True, "typing_armed": True},
            ]
            path.write_text(
                "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8"
            )
            stats = analyze_capture_jsonl(path)
            self.assertEqual(stats.frames, 6)
            self.assertEqual(stats.outlier, 5)
            sug = suggest_knobs(stats, max_delta=1200, delay_ms=25, typing_window_ms=350)
            self.assertGreater(sug.max_delta, 1200)


class TestTouchMapPreset(unittest.TestCase):
    def test_ux8406_preset(self) -> None:
        with mock.patch(
            "zenbook_kb.touch_map._dmi_product",
            return_value="ASUS Zenbook Duo UX8406MA_UX8406MA",
        ):
            rules = preset_rules_for_machine()
        self.assertEqual([(r.match, r.output) for r in rules], list(UX8406_PRESET))
        with mock.patch(
            "zenbook_kb.touch_map._dmi_product",
            return_value="ASUS Zenbook Duo UX8406MA_UX8406MA",
        ):
            auto = auto_rules(devices=[], outputs=[])
        self.assertEqual(len(auto), 2)
        self.assertIsInstance(auto[0], MapRule)


class TestKWinLiveFilterActivate(unittest.TestCase):
    def test_activate_enables_filter_disables_physical(self) -> None:
        with mock.patch("zenbook_kb.touch_map.kwin_available", return_value=True), mock.patch(
            "zenbook_kb.touch_map.find_kwin_filter_sysname",
            return_value="event15",
        ), mock.patch(
            "zenbook_kb.touch_map.set_device_enabled"
        ) as set_en:
            ok = activate_kwin_live_filter(
                touchpad_path=Path("/dev/input/event6"),
                name_hint="GDX1515:00 27C6:01F4 Touchpad",
                filter_sysname="event15",
            )
        self.assertTrue(ok)
        calls = [c.args for c in set_en.call_args_list]
        self.assertIn(("event15", True), calls)
        self.assertIn(("event6", False), calls)


class TestKWinTouchpadRestore(unittest.TestCase):
    def test_restore_nudges_physical_touchpad(self) -> None:
        dev_physical = mock.Mock(
            name="GDX1515:00 27C6:01F4 Touchpad",
            enabled=True,
        )
        dev_filter = mock.Mock(
            name="GDX1515:00 27C6:01F4 Touchpad (filter)",
            enabled=True,
        )
        dev_physical.name = "GDX1515:00 27C6:01F4 Touchpad"
        dev_filter.name = "GDX1515:00 27C6:01F4 Touchpad (filter)"

        def _get(sysname: str):
            return {"event6": dev_physical, "event14": dev_filter}.get(sysname)

        with mock.patch("zenbook_kb.touch_map.kwin_available", return_value=True), mock.patch(
            "zenbook_kb.touch_map.find_kwin_filter_sysname",
            return_value="event14",
        ), mock.patch(
            "zenbook_kb.touch_map.set_device_enabled"
        ) as set_en:
            ok = restore_kwin_touchpad_after_filter(
                touchpad_path=Path("/dev/input/event6"),
                name_hint=dev_physical.name,
            )
        self.assertTrue(ok)
        calls = [c.args for c in set_en.call_args_list]
        self.assertIn(("event14", False), calls)
        self.assertIn(("event6", False), calls)
        self.assertIn(("event6", True), calls)

    def test_restore_finalizes_pointer_pad_seen_as_touch_device(self) -> None:
        """USB Primax can appear in list_touch_devices (touch=true) before finalize."""
        primax = KWinInputDevice(
            sysname="event10",
            name="Primax Electronics Ltd. ASUS Zenbook Duo Keyboard Touchpad",
            enabled=True,
            touch=True,
            tablet_tool=False,
            output_name="",
        )
        with mock.patch("zenbook_kb.touch_map.kwin_available", return_value=True), mock.patch(
            "zenbook_kb.touch_map.list_touch_devices",
            return_value=[primax],
        ), mock.patch(
            "zenbook_kb.touch_map.list_pointer_touchpads",
            return_value=[primax],
        ), mock.patch(
            "zenbook_kb.touch_map._finalize_kwin_touchpad",
            return_value=1,
        ) as finalize:
            n = restore_all_compositor_touchpads()
        self.assertGreaterEqual(n, 1)
        finalize.assert_called_once_with(primax)


if __name__ == "__main__":
    unittest.main()
