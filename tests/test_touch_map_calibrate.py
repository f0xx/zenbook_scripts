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
    MapRule,
    UX8406_PRESET,
    auto_rules,
    preset_rules_for_machine,
)
from zenbook_kb.touchpad_calibrate import (  # noqa: E402
    analyze_capture_jsonl,
    detect_transport,
    suggest_knobs,
)


class TestTouchpadCalibrate(unittest.TestCase):
    def test_detect_transport(self) -> None:
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


if __name__ == "__main__":
    unittest.main()
