"""Unit tests: manual lock pauses adaptive fan-control rules."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from zenbook_kb import fan_control as fc  # noqa: E402
from zenbook_kb.fan_control import (  # noqa: E402
    CONTROL_MODE_AUTO,
    CONTROL_MODE_MANUAL,
    ControllerState,
    Sample,
    get_control_mode,
    maybe_apply_continuous,
    run_event,
    set_control_mode,
)


class TestFanControlMode(unittest.TestCase):
    def setUp(self) -> None:
        self._td = tempfile.TemporaryDirectory()
        self.mode_path = Path(self._td.name) / "fan-control-mode"
        self._mode_patch = mock.patch.object(fc, "CONTROL_MODE_STATE", self.mode_path)
        self._mode_patch.start()

    def tearDown(self) -> None:
        self._mode_patch.stop()
        self._td.cleanup()

    def test_default_is_auto(self) -> None:
        self.assertEqual(get_control_mode(), CONTROL_MODE_AUTO)

    def test_set_get_manual(self) -> None:
        self.assertEqual(set_control_mode("manual"), CONTROL_MODE_MANUAL)
        self.assertEqual(get_control_mode(), CONTROL_MODE_MANUAL)
        self.assertEqual(self.mode_path.read_text(encoding="utf-8").strip(), "manual")

    def test_adaptive_alias(self) -> None:
        set_control_mode("manual")
        self.assertEqual(set_control_mode("adaptive"), CONTROL_MODE_AUTO)
        self.assertEqual(get_control_mode(), CONTROL_MODE_AUTO)

    def test_continuous_skipped_when_manual(self) -> None:
        set_control_mode("manual")
        cfg = {
            "profiles": {"quiet": {"platform_profile": "quiet", "pwm": "auto"}},
            "rules": {"ac": [{"when": {"load_gte": 0}, "profile": "quiet"}]},
            "daemon": {"hysteresis_sec": 0},
        }
        sample = Sample(on_ac=True, load_pct=90.0, temp_c=80.0, lid_open=True)
        state = ControllerState()
        with mock.patch.object(fc, "apply_profile") as apply:
            got = maybe_apply_continuous(cfg, sample, state, force=True)
        self.assertIsNone(got)
        apply.assert_not_called()

    def test_continuous_runs_when_auto(self) -> None:
        set_control_mode("auto")
        cfg = {
            "profiles": {"quiet": {"platform_profile": "quiet", "pwm": "auto"}},
            "rules": {"ac": [{"when": {"load_gte": 0}, "profile": "quiet"}]},
            "daemon": {"hysteresis_sec": 0},
        }
        sample = Sample(on_ac=True, load_pct=10.0, temp_c=40.0, lid_open=True)
        state = ControllerState()
        with mock.patch.object(fc, "apply_profile") as apply:
            got = maybe_apply_continuous(cfg, sample, state, force=True)
        self.assertEqual(got, "quiet")
        apply.assert_called_once_with(cfg, "quiet")

    def test_manual_skips_ac_event_keeps_sleep_pre(self) -> None:
        set_control_mode("manual")
        cfg = {
            "profiles": {
                "powersave": {"platform_profile": "quiet"},
                "balanced": {"platform_profile": "balanced"},
            },
            "events": {
                "ac_change": {"profile": "balanced"},
                "sleep_pre": {"profile": "powersave"},
            },
        }
        state = ControllerState()
        with mock.patch.object(fc, "apply_profile") as apply:
            run_event(cfg, "ac_change", state)
            apply.assert_not_called()
            run_event(cfg, "sleep_pre", state)
            apply.assert_called_once_with(cfg, "powersave")

    def test_manual_sleep_post_restores(self) -> None:
        set_control_mode("manual")
        cfg = {"events": {"sleep_post": {"profile": None}}}
        state = ControllerState()
        with mock.patch.object(fc, "read_lid_open", return_value=True), mock.patch.object(
            fc, "restore_user_sysfs"
        ) as restore:
            run_event(cfg, "sleep_post", state)
        restore.assert_called_once()

    def test_manual_lid_close_applies_powersave(self) -> None:
        set_control_mode("manual")
        cfg = {
            "profiles": {"powersave": {"platform_profile": "quiet", "pwm": "auto"}},
            "events": {"lid_close": {"profile": "powersave"}},
        }
        state = ControllerState()
        with mock.patch.object(fc, "apply_profile") as apply:
            run_event(cfg, "lid_close", state)
        apply.assert_called_once_with(cfg, "powersave")

    def test_manual_sleep_post_deferred_when_lid_closed(self) -> None:
        set_control_mode("manual")
        cfg = {"events": {"sleep_post": {"profile": None}}}
        state = ControllerState()
        with mock.patch.object(fc, "read_lid_open", return_value=False), mock.patch.object(
            fc, "restore_user_sysfs"
        ) as restore:
            run_event(cfg, "sleep_post", state)
        restore.assert_not_called()

    def test_manual_lid_open_restores(self) -> None:
        set_control_mode("manual")
        cfg = {"events": {"lid_open": {"profile": None}}}
        state = ControllerState()
        with mock.patch.object(fc, "restore_user_sysfs") as restore:
            run_event(cfg, "lid_open", state)
        restore.assert_called_once()


if __name__ == "__main__":
    unittest.main()
