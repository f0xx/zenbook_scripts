"""Tests for cron profile evaluation."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from zenbook_kb import profile_eval as pe  # noqa: E402
from zenbook_kb.user_profiles import default_document


class TestProfileEval(unittest.TestCase):
    def test_schedule_window_same_day(self) -> None:
        with mock.patch.object(pe, "_minutes_now", return_value=22 * 60 + 30):
            self.assertTrue(pe._in_schedule_window("22:00", "23:00"))
            self.assertFalse(pe._in_schedule_window("08:00", "18:00"))

    def test_schedule_overnight(self) -> None:
        with mock.patch.object(pe, "_minutes_now", return_value=1 * 60):
            self.assertTrue(pe._in_schedule_window("23:00", "06:00"))

    def test_desired_night_when_eligible(self) -> None:
        doc = default_document()
        doc["modes"]["night"]["enabled"] = True
        doc["modes"]["night"]["schedule"]["enabled"] = True
        with mock.patch.object(pe, "_night_eligible", return_value=True), mock.patch.object(
            pe, "_schedule_active", return_value=False
        ), mock.patch.object(pe, "_low_cpu_active", return_value=False), mock.patch.object(
            pe, "_battery_timeout_active", return_value=False
        ):
            self.assertEqual(pe.desired_mode(doc, state={}), "night")


if __name__ == "__main__":
    unittest.main()
