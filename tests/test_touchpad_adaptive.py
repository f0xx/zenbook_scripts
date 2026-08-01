"""Tests for adaptive touchpad profiles and matrix filter."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from zenbook_kb.touchpad import (
    Ev,
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
    profile_filters,
    resolve_device_filters,
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
        got = resolve_device_filters({"filters": custom, "filter_profile": "adaptive"})
        self.assertEqual(got[0]["ms"], 99)

    def test_resolve_profile_when_no_filters_list(self) -> None:
        got = resolve_device_filters({"filter_profile": "adaptive"})
        plugins = [f["plugin"] for f in got]
        self.assertIn("adaptive_matrix", plugins)

    def test_upsert_adaptive_profile(self) -> None:
        cfg = upsert_device_profile(
            normalize_config({}),
            "test|phys",
            filter_profile=FILTER_PROFILE_ADAPTIVE,
        )
        entry = cfg["devices"]["test|phys"]
        self.assertEqual(entry.get("filter_profile"), FILTER_PROFILE_ADAPTIVE)
        self.assertNotIn("filters", entry)
        plugins = [p["plugin"] for p in resolve_device_filters(entry)]
        self.assertIn("adaptive_matrix", plugins)


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

        spike = f.process_frame(_syn_frame(500, 500, sec=2))
        self.assertEqual(spike, [])
        self.assertGreater(f.spikes_dropped, 0)

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
        names = [f.name.split("+")[0] for f in pipe.filters]
        self.assertIn("adaptive_matrix", names)


if __name__ == "__main__":
    unittest.main()
