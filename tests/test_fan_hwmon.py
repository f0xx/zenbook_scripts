"""Unit tests for generic fan hwmon backend detection."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from zenbook_kb import fan_hwmon


class TestFanHwmon(unittest.TestCase):
    def test_score_thinkpad(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            d = Path(td) / "hwmon0"
            d.mkdir()
            (d / "name").write_text("thinkpad\n")
            (d / "fan1_input").write_text("4200\n")
            (d / "pwm1").write_text("128\n")
            row = fan_hwmon._score_hwmon(d, "thinkpad")
            self.assertIsNotNone(row)
            assert row is not None
            self.assertEqual(row.backend, "thinkpad")
            self.assertTrue(row.has_rpm)

    def test_find_prefers_asus(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            asus = root / "a"
            asus.mkdir()
            (asus / "name").write_text("asus\n")
            (asus / "fan1_input").write_text("3000\n")
            tp = root / "b"
            tp.mkdir()
            (tp / "name").write_text("thinkpad\n")
            (tp / "fan1_input").write_text("3000\n")

            def fake_list() -> list[fan_hwmon.FanHwmon]:
                rows = [
                    fan_hwmon._score_hwmon(asus, "asus"),
                    fan_hwmon._score_hwmon(tp, "thinkpad"),
                ]
                order = {n: i for i, n in enumerate(fan_hwmon.BACKEND_NAMES)}
                rows.sort(key=lambda r: (order.get(r.backend, 99), r.name))
                return rows

            with mock.patch.object(fan_hwmon, "list_fan_hwmon", side_effect=fake_list):
                row = fan_hwmon.find_fan_hwmon()
                self.assertIsNotNone(row)
                assert row is not None
                self.assertEqual(row.backend, "asus")


if __name__ == "__main__":
    unittest.main()
