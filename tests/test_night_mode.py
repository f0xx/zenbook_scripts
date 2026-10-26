"""Unit tests for closed-lid night mode snapshot/restore."""

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

from zenbook_kb import night_mode as nm  # noqa: E402


class TestNightMode(unittest.TestCase):
    def setUp(self) -> None:
        self._td = tempfile.TemporaryDirectory()
        self.addCleanup(self._td.cleanup)
        base = Path(self._td.name)
        self.state = base / "lib"
        self.state.mkdir()
        self.snap = self.state / "night-mode-snapshot.json"
        self.active = self.state / "night-mode-active"
        self.mode_patch = mock.patch.object(nm, "STATE_DIR", self.state)
        self.mode_patch.start()
        self.addCleanup(self.mode_patch.stop)
        mock.patch.object(nm, "SNAPSHOT_PATH", self.snap).start()
        mock.patch.object(nm, "ACTIVE_MARKER", self.active).start()

    def test_capture_and_restore_snapshot(self) -> None:
        with mock.patch.object(nm, "get_control_mode", return_value="manual"), mock.patch.object(
            nm, "_read_text", side_effect=lambda p: "balanced" if "platform" in str(p) else "2"
        ):
            snap = nm.capture_snapshot()
        self.assertEqual(snap["fan_control_mode"], "manual")
        nm.write_snapshot(snap)
        loaded = nm.read_snapshot()
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(loaded["platform_profile"], "balanced")

    def test_enter_skips_on_battery(self) -> None:
        cfg = {"enabled": True, "require_ac": True}
        with mock.patch.object(nm, "read_on_ac", return_value=False), mock.patch.object(
            nm, "apply_profile"
        ) as apply:
            ok = nm.enter_night(cfg)
        self.assertFalse(ok)
        apply.assert_not_called()

    def test_enter_and_exit_active_marker(self) -> None:
        cfg = {"enabled": True, "require_ac": False, "blank_displays": False}
        fan_cfg = {"profiles": {"night": {}, "powersave": {}}}
        with mock.patch.object(nm, "read_on_ac", return_value=True), mock.patch.object(
            nm, "load_fan_config", return_value=fan_cfg
        ), mock.patch.object(nm, "apply_profile"), mock.patch.object(
            nm, "capture_snapshot", return_value={"version": 1, "fan_control_mode": "auto"}
        ), mock.patch.object(nm, "restore_user_sysfs"), mock.patch.object(
            nm, "set_control_mode"
        ), mock.patch.object(nm, "run_event"), mock.patch.object(
            nm, "wake_displays"
        ), mock.patch.object(nm, "_restore_session_input"):
            self.assertTrue(nm.enter_night(cfg))
            self.assertTrue(nm.is_active())
            self.snap.write_text(json.dumps({"fan_control_mode": "auto"}) + "\n")
            self.assertTrue(nm.exit_night())
        self.assertFalse(nm.is_active())

    def test_lid_closed_forces_keyboard_off(self) -> None:
        cfg = {"enabled": True, "require_ac": False, "blank_displays": False}
        fan_cfg = {"profiles": {"night": {}, "powersave": {}}}
        profiles = {
            "modes": {
                "night": {
                    "keyboard_backlight": {"enabled": True, "level": 2, "level_pct": 66},
                }
            }
        }
        with mock.patch.object(nm, "read_on_ac", return_value=True), mock.patch.object(
            nm, "load_fan_config", return_value=fan_cfg
        ), mock.patch.object(nm, "apply_profile"), mock.patch.object(
            nm, "capture_snapshot", return_value={"version": 1}
        ), mock.patch.object(nm, "blank_displays"), mock.patch.object(
            nm, "_set_network"
        ), mock.patch.object(nm, "_set_keyboard_brightness") as kbd:
            with mock.patch("zenbook_kb.user_profiles.load", return_value=profiles):
                nm._apply_night_extras(cfg, user="foxx", entering=True, lid_closed=True)
        kbd.assert_called_once_with(0, user="foxx")

    def test_exit_restores_touchpad(self) -> None:
        cfg = {"enabled": True, "require_ac": False, "blank_displays": False}
        fan_cfg = {"profiles": {"night": {}, "powersave": {}}}
        self.active.write_text("1\n")
        self.snap.write_text(json.dumps({"fan_control_mode": "auto"}) + "\n")
        with mock.patch.object(nm, "restore_user_sysfs"), mock.patch.object(
            nm, "set_control_mode"
        ), mock.patch.object(nm, "load_fan_config", return_value=fan_cfg), mock.patch.object(
            nm, "run_event"
        ), mock.patch.object(nm, "wake_displays"), mock.patch.object(
            nm, "_restore_session_input"
        ) as restore, mock.patch.object(nm, "_apply_night_extras"):
            self.assertTrue(nm.exit_night())
        restore.assert_called_once()


if __name__ == "__main__":
    unittest.main()
