"""Tests for adaptive touchpad profiles and matrix filter."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from zenbook_kb.touchpad import (
    Ev,
    TouchpadInfo,
    build_pipeline,
    filters_for_device,
    filter_profile_for_device,
    normalize_config,
    upsert_device_profile,
)
from zenbook_kb.touchpad_adaptive import (
    AdaptiveMatrixFilter,
    AdaptiveState,
    adaptive_state_dir,
    load_adaptive_state,
    save_adaptive_state,
)
from zenbook_kb.touchpad_profiles import (
    FILTER_PROFILE_ADAPTIVE,
    FILTER_PROFILE_DEFAULT,
    adaptive_profile_filters,
    default_profile_filters,
    merge_gui_knobs,
    profile_filters,
    resolve_device_filters,
    resolve_transport_entry,
)


def _syn_frame(x: int, y: int, *, sec: int = 1) -> list[Ev]:
    return [
        Ev(sec, 0, 3, 0x35, x),
        Ev(sec, 0, 3, 0x36, y),
        Ev(sec, 0, 0, 0, 0),
    ]


class TestTouchpadProfiles(unittest.TestCase):
    def test_default_profile_has_outlier_not_adaptive(self) -> None:
        names = {f["plugin"] for f in default_profile_filters()}
        self.assertIn("outlier_reject", names)
        self.assertNotIn("adaptive_matrix", names)

    def test_adaptive_profile_swaps_outlier(self) -> None:
        filt = adaptive_profile_filters()
        by_name = {f["plugin"]: f for f in filt}
        self.assertFalse(by_name["outlier_reject"]["enabled"])
        self.assertTrue(by_name["adaptive_matrix"]["enabled"])

    def test_resolve_explicit_filters_wins(self) -> None:
        custom = [{"plugin": "exec_delay", "ms": 99, "enabled": True}]
        got = resolve_device_filters({"filters": custom, "filter_profile": "default"})
        self.assertEqual(got[0]["ms"], 99)

    def test_resolve_profile_when_no_filters_list(self) -> None:
        got = resolve_device_filters({"filter_profile": "adaptive"})
        plugins = [f["plugin"] for f in got]
        self.assertIn("adaptive_matrix", plugins)

    def test_resolve_adaptive_merges_kcm_knobs(self) -> None:
        kcm_knobs = [
            {"plugin": "typing_inhibit", "window_ms": 400, "enabled": True},
            {"plugin": "exec_delay", "ms": 30, "enabled": True},
            {"plugin": "outlier_reject", "max_delta": 900, "enabled": False},
            {"plugin": "soft_accel", "gain": 2.0, "enabled": True, "mode": "linear", "pivot": 40},
        ]
        got = resolve_device_filters({"filter_profile": "adaptive", "filters": kcm_knobs})
        by = {f["plugin"]: f for f in got}
        self.assertIn("adaptive_matrix", by)
        self.assertTrue(by["soft_accel"]["enabled"])
        self.assertEqual(by["soft_accel"]["gain"], 2.0)
        self.assertFalse(by["outlier_reject"]["enabled"])

    def test_merge_gui_soft_accel_adaptive(self) -> None:
        from zenbook_kb.touchpad import filters_from_knobs

        knobs = filters_from_knobs(
            delay_enabled=True,
            delay_ms=25,
            outlier_enabled=True,
            max_delta=1200,
            soft_accel_enabled=True,
            soft_accel_gain=2.0,
            soft_accel_mode="linear",
        )
        merged = merge_gui_knobs(FILTER_PROFILE_ADAPTIVE, knobs)
        soft = next(f for f in merged if f["plugin"] == "soft_accel")
        self.assertTrue(soft["enabled"])
        self.assertEqual(soft["gain"], 2.0)
        self.assertTrue(any(f["plugin"] == "adaptive_matrix" for f in merged))


class TestNestedTransportProfiles(unittest.TestCase):
    PRIMax = "Primax Electronics Ltd. ASUS Zenbook Duo Keyboard Touchpad"

    def test_resolve_transport_entry_prefers_sub_profile(self) -> None:
        entry = {
            "enabled": True,
            "transports": {
                "usb": {"filters": [{"plugin": "exec_delay", "ms": 11, "enabled": True}]},
                "bluetooth": {
                    "filters": [{"plugin": "exec_delay", "ms": 22, "enabled": True}]
                },
            },
        }
        usb = resolve_transport_entry(entry, "usb")
        assert usb is not None
        bt = resolve_transport_entry(entry, "bluetooth")
        assert bt is not None
        self.assertEqual(resolve_device_filters(usb)[0]["ms"], 11)
        self.assertEqual(resolve_device_filters(bt)[0]["ms"], 22)

    def test_upsert_nests_usb_and_bluetooth(self) -> None:
        cfg = normalize_config({"version": 2, "default_device": "auto", "devices": {}})
        key = f"{self.PRIMax}|usb-0000:00:14.0-6/input5"
        cfg = upsert_device_profile(
            cfg,
            key,
            filters=[{"plugin": "exec_delay", "ms": 30, "enabled": True}],
            transport="usb",
        )
        cfg = upsert_device_profile(
            cfg,
            f"{self.PRIMax}|bluez",
            filters=[{"plugin": "exec_delay", "ms": 40, "enabled": True}],
            transport="bluetooth",
        )
        dev = cfg["devices"][self.PRIMax]
        self.assertIn("transports", dev)
        self.assertEqual(dev["transports"]["usb"]["filters"][0]["ms"], 30)
        self.assertEqual(dev["transports"]["bluetooth"]["filters"][0]["ms"], 40)

    def test_nested_transport_beats_flat_composite_key(self) -> None:
        cfg = {
            "version": 2,
            "default_device": "auto",
            "devices": {
                self.PRIMax: {
                    "enabled": True,
                    "transports": {
                        "usb": {
                            "filter_profile": "adaptive",
                            "filters": adaptive_profile_filters(),
                        }
                    },
                },
                f"{self.PRIMax}|usb-0000:00:14.0-6/input5": {
                    "enabled": True,
                    "filters": default_profile_filters(),
                },
            },
        }
        info = TouchpadInfo(
            Path("/dev/input/event8"),
            self.PRIMax,
            phys="usb-0000:00:14.0-6/input5",
        )
        self.assertEqual(filter_profile_for_device(cfg, info, path=info.path), "adaptive")
        plugins = [f["plugin"] for f in filters_for_device(cfg, info, path=info.path)]
        self.assertIn("adaptive_matrix", plugins)

    def test_filters_for_device_picks_transport(self) -> None:
        cfg = {
            "version": 2,
            "default_device": "auto",
            "devices": {
                self.PRIMax: {
                    "enabled": True,
                    "transports": {
                        "usb": {
                            "filters": [
                                {"plugin": "outlier_reject", "max_delta": 500, "enabled": True}
                            ]
                        },
                        "bluetooth": {
                            "filters": [
                                {"plugin": "outlier_reject", "max_delta": 800, "enabled": True}
                            ]
                        },
                    },
                }
            },
        }
        usb_info = TouchpadInfo(
            Path("/dev/input/event9"),
            self.PRIMax,
            phys="usb-0000:00:14.0-6/input5",
        )
        bt_info = TouchpadInfo(
            Path("/dev/input/event10"),
            self.PRIMax,
            phys="",
            uniq="bluez",
        )
        usb_f = filters_for_device(cfg, usb_info)
        bt_f = filters_for_device(cfg, bt_info)
        usb_delta = next(f for f in usb_f if f["plugin"] == "outlier_reject")["max_delta"]
        bt_delta = next(f for f in bt_f if f["plugin"] == "outlier_reject")["max_delta"]
        self.assertEqual(usb_delta, 500)
        self.assertEqual(bt_delta, 800)


class TestAdaptiveMatrixFilter(unittest.TestCase):
    def test_spike_dropped_small_motion_passes(self) -> None:
        f = AdaptiveMatrixFilter(device_key="test", spike_sigma=3.0, min_baseline=5.0)
        f.state.baseline_x = 10.0
        f.state.baseline_y = 10.0
        # establish contact
        f.process_frame(_syn_frame(100, 100, sec=0))
        out = f.process_frame(_syn_frame(108, 102, sec=1))
        self.assertTrue(out)
        self.assertGreater(f.learn_updates, 0)

        # Large swipe must pass (no sticky cursor on fast motion).
        swipe = f.process_frame(_syn_frame(500, 500, sec=2))
        self.assertTrue(swipe)
        after = f.process_frame(_syn_frame(505, 502, sec=3))
        self.assertTrue(after)

    def test_isolated_glitch_passes_through(self) -> None:
        f = AdaptiveMatrixFilter(device_key="test", spike_sigma=3.0, min_baseline=5.0)
        f.state.baseline_x = 8.0
        f.state.baseline_y = 8.0
        f.process_frame(_syn_frame(200, 200, sec=0))
        glitch = f.process_frame(_syn_frame(230, 200, sec=1))
        self.assertTrue(glitch)
        x_val = next(e.value for e in glitch if e.code == 0x35)
        self.assertEqual(x_val, 230)

    def test_adaptive_is_typing_gated_in_pipeline(self) -> None:
        pipe = build_pipeline(
            {
                "filters": profile_filters(FILTER_PROFILE_ADAPTIVE),
                "device_key": "test|phys",
            }
        )
        names = [f.name for f in pipe.filters]
        self.assertIn("adaptive_matrix+typing", names)

    def test_state_persist_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            with mock.patch(
                "zenbook_kb.touchpad_adaptive.adaptive_state_dir",
                return_value=Path(td),
            ):
                st = AdaptiveState(baseline_x=22.0, baseline_y=18.0, samples=42)
                save_adaptive_state("dev|key", st)
                loaded = load_adaptive_state("dev|key")
                self.assertAlmostEqual(loaded.baseline_x, 22.0)
                self.assertEqual(loaded.samples, 42)

    def test_build_pipeline_includes_adaptive(self) -> None:
        pipe = build_pipeline(
            {
                "filters": profile_filters(FILTER_PROFILE_ADAPTIVE),
                "device_key": "test|phys",
            }
        )
        names = [f.name for f in pipe.filters]
        self.assertIn("adaptive_matrix+typing", names)


if __name__ == "__main__":
    unittest.main()
