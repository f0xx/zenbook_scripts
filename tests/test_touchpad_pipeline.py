"""Unit tests for the touchpad filter pipeline (stdlib unittest).

Push synthetic event streams through filters and compare against expected
shape — especially that exec_delay never emits a multi-SYN path replay
(Plasma "find cursor" / shake gesture parasite).
"""

from __future__ import annotations

import math
import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from zenbook_kb.touchpad import (  # noqa: E402
    ABS_MT_POSITION_X,
    ABS_MT_POSITION_Y,
    ABS_MT_SLOT,
    ABS_MT_TRACKING_ID,
    BTN_TOOL_DOUBLETAP,
    BTN_TOOL_FINGER,
    BTN_TOUCH,
    DEFAULT_MAX_DELTA,
    EV_ABS,
    EV_KEY,
    EV_SYN,
    SYN_REPORT,
    Ev,
    ExecDelayFilter,
    KeyboardActivity,
    OutlierRejectFilter,
    SoftAccelFilter,
    WhenTypingGate,
    build_pipeline,
    count_syn_reports,
    make_sim_brush,
    run_selftest,
)


def _xy_path(events: list[Ev]) -> list[tuple[int, int]]:
    """Per-SYN absolute positions (last X/Y in each frame)."""
    path: list[tuple[int, int]] = []
    x = y = None
    for ev in events:
        if ev.type == EV_ABS and ev.code == ABS_MT_POSITION_X:
            x = ev.value
        elif ev.type == EV_ABS and ev.code == ABS_MT_POSITION_Y:
            y = ev.value
        elif ev.type == EV_SYN and ev.code == SYN_REPORT:
            if x is not None and y is not None:
                path.append((x, y))
    return path


def _process_framewise(pipe, events: list[Ev]) -> list[list[Ev]]:
    """Run like the live pump: one SYN frame in → one filter call."""
    outs: list[list[Ev]] = []
    frame: list[Ev] = []
    for ev in events:
        if pipe.activity is not None:
            pipe.activity.note_ev(ev)
        frame.append(ev)
        if ev.type == EV_SYN and ev.code == SYN_REPORT:
            out = pipe.process_frame(frame)
            if out:
                outs.append(out)
            frame = []
    return outs


def make_sim_circle(
    *,
    loops: float = 3.0,
    points_per_loop: int = 24,
    radius: int = 80,
    cx: int = 2000,
    cy: int = 2000,
    step_ms: float = 8.0,
) -> list[Ev]:
    """Synthetic circular finger path (Plasma find-cursor gesture shape)."""
    import time as _time

    events: list[Ev] = []
    n = max(1, int(loops * points_per_loop))
    t0 = _time.time()

    def stamp(i: int) -> tuple[int, int]:
        t = t0 + (i * step_ms) / 1000.0
        sec = int(t)
        usec = int((t - sec) * 1_000_000)
        return sec, usec

    sec, usec = stamp(0)
    x0 = cx + radius
    y0 = cy
    events.extend(
        [
            Ev(sec, usec, EV_ABS, ABS_MT_TRACKING_ID, 1),
            Ev(sec, usec, EV_ABS, ABS_MT_POSITION_X, x0),
            Ev(sec, usec, EV_ABS, ABS_MT_POSITION_Y, y0),
            Ev(sec, usec, EV_KEY, BTN_TOUCH, 1),
            Ev(sec, usec, EV_KEY, BTN_TOOL_FINGER, 1),
            Ev.syn(sec, usec),
        ]
    )
    for i in range(1, n + 1):
        ang = 2 * math.pi * (i / points_per_loop)
        x = int(cx + radius * math.cos(ang))
        y = int(cy + radius * math.sin(ang))
        sec, usec = stamp(i)
        events.extend(
            [
                Ev(sec, usec, EV_ABS, ABS_MT_POSITION_X, x),
                Ev(sec, usec, EV_ABS, ABS_MT_POSITION_Y, y),
                Ev.syn(sec, usec),
            ]
        )
    sec, usec = stamp(n + 1)
    events.extend(
        [
            Ev(sec, usec, EV_ABS, ABS_MT_TRACKING_ID, -1),
            Ev(sec, usec, EV_KEY, BTN_TOUCH, 0),
            Ev(sec, usec, EV_KEY, BTN_TOOL_FINGER, 0),
            Ev.syn(sec, usec),
        ]
    )
    return events


class TestExecDelayCoalesce(unittest.TestCase):
    def test_flush_is_single_syn_not_path_replay(self) -> None:
        filt = ExecDelayFilter(ms=40)
        brush = make_sim_brush(duration_ms=80, dx=5, step_ms=5)
        frames = []
        cur: list[Ev] = []
        for ev in brush:
            cur.append(ev)
            if ev.type == EV_SYN and ev.code == SYN_REPORT:
                frames.append(cur)
                cur = []

        outs = [filt.process_frame(fr) for fr in frames]
        # While buffering: empty outs; first non-empty must be one SYN only.
        non_empty = [o for o in outs if o]
        self.assertTrue(non_empty)
        first = non_empty[0]
        self.assertEqual(count_syn_reports(first), 1, first)
        # Coalesced position should be near the delay-expiry point, not start.
        path = _xy_path(first)
        self.assertEqual(len(path), 1)
        self.assertGreater(path[0][0], 1000)

    def test_coalesce_keeps_press_and_latest_xy(self) -> None:
        f0 = [
            Ev(0, 0, EV_ABS, ABS_MT_TRACKING_ID, 1),
            Ev(0, 0, EV_ABS, ABS_MT_POSITION_X, 100),
            Ev(0, 0, EV_ABS, ABS_MT_POSITION_Y, 100),
            Ev(0, 0, EV_KEY, BTN_TOUCH, 1),
            Ev.syn(0, 0),
        ]
        f1 = [
            Ev(0, 20_000, EV_ABS, ABS_MT_POSITION_X, 150),
            Ev(0, 20_000, EV_ABS, ABS_MT_POSITION_Y, 120),
            Ev.syn(0, 20_000),
        ]
        f2 = [
            Ev(0, 40_000, EV_ABS, ABS_MT_POSITION_X, 200),
            Ev(0, 40_000, EV_ABS, ABS_MT_POSITION_Y, 140),
            Ev.syn(0, 40_000),
        ]
        out = ExecDelayFilter.coalesce_buffered([f0, f1, f2])
        self.assertEqual(count_syn_reports(out), 1)
        codes = {(e.type, e.code, e.value) for e in out}
        self.assertIn((EV_ABS, ABS_MT_TRACKING_ID, 1), codes)
        self.assertIn((EV_KEY, BTN_TOUCH, 1), codes)
        self.assertIn((EV_ABS, ABS_MT_POSITION_X, 200), codes)
        self.assertIn((EV_ABS, ABS_MT_POSITION_Y, 140), codes)
        self.assertNotIn((EV_ABS, ABS_MT_POSITION_X, 100), codes)

    def test_event_clock_from_epoch_zero_still_arms(self) -> None:
        """Regression: sec=usec=0 used to switch to monotonic and never arm."""
        filt = ExecDelayFilter(ms=40)
        # Timestamps start at 0 and advance only in usec — realistic for sims.
        events: list[Ev] = []
        for i, x in enumerate((100, 105, 110, 115, 120, 125, 130, 135, 140)):
            usec = i * 10_000  # 10 ms steps → 80 ms total
            if i == 0:
                events.extend(
                    [
                        Ev(0, usec, EV_ABS, ABS_MT_TRACKING_ID, 1),
                        Ev(0, usec, EV_ABS, ABS_MT_POSITION_X, x),
                        Ev(0, usec, EV_ABS, ABS_MT_POSITION_Y, 100),
                        Ev(0, usec, EV_KEY, BTN_TOUCH, 1),
                        Ev.syn(0, usec),
                    ]
                )
            else:
                events.extend(
                    [
                        Ev(0, usec, EV_ABS, ABS_MT_POSITION_X, x),
                        Ev(0, usec, EV_ABS, ABS_MT_POSITION_Y, 100),
                        Ev.syn(0, usec),
                    ]
                )
        outs = []
        frame: list[Ev] = []
        for ev in events:
            frame.append(ev)
            if ev.type == EV_SYN and ev.code == SYN_REPORT:
                outs.append(filt.process_frame(frame))
                frame = []
        non_empty = [o for o in outs if o]
        self.assertTrue(non_empty, "delay never armed — clock mixing bug?")
        self.assertEqual(count_syn_reports(non_empty[0]), 1)

    def test_short_brush_still_dropped(self) -> None:
        pipe = build_pipeline(
            {
                "filters": [
                    {"plugin": "typing_inhibit", "enabled": False},
                    {"plugin": "exec_delay", "ms": 40},
                    {"plugin": "soft_accel", "enabled": False},
                ]
            }
        )
        out = pipe.process_events(make_sim_brush(duration_ms=20, dx=3))
        self.assertEqual(out, [])


class TestNoParasiteBurst(unittest.TestCase):
    def test_armed_long_move_never_emits_multi_syn_chunk(self) -> None:
        """Regression: old flush concatenated ~8 SYN frames into one write."""
        pipe = build_pipeline(
            {
                "filters": [
                    {"plugin": "typing_inhibit", "window_ms": 500, "enabled": True},
                    {"plugin": "exec_delay", "ms": 40, "enabled": True},
                    {"plugin": "outlier_reject", "max_delta": DEFAULT_MAX_DELTA},
                    {"plugin": "soft_accel", "gain": 1.6, "enabled": True},
                ]
            }
        )
        assert pipe.activity is not None
        pipe.activity.note_key()
        # Circle-shaped path — burst replay would look like find-cursor.
        circle = make_sim_circle(loops=3.0, points_per_loop=20, step_ms=5)
        chunks = _process_framewise(pipe, circle)
        for chunk in chunks:
            self.assertLessEqual(
                count_syn_reports(chunk),
                1,
                f"parasite multi-SYN chunk ({count_syn_reports(chunk)} SYNs)",
            )

    def test_idle_passthrough_preserves_syn_count(self) -> None:
        pipe = build_pipeline(
            {
                "filters": [
                    {"plugin": "typing_inhibit", "window_ms": 350, "enabled": True},
                    {"plugin": "exec_delay", "ms": 40, "enabled": True},
                    {"plugin": "soft_accel", "enabled": False},
                ]
            }
        )
        brush = make_sim_brush(duration_ms=60, dx=4, step_ms=5)
        out = pipe.process_events(brush)
        self.assertEqual(count_syn_reports(out), count_syn_reports(brush))
        self.assertEqual(_xy_path(out), _xy_path(brush))

    def test_typing_then_move_no_replayed_circle(self) -> None:
        pipe = build_pipeline(
            {
                "filters": [
                    {"plugin": "typing_inhibit", "window_ms": 500, "enabled": True},
                    {"plugin": "exec_delay", "ms": 40, "enabled": True},
                    {"plugin": "soft_accel", "gain": 1.6, "enabled": True},
                ]
            }
        )
        assert pipe.activity is not None
        pipe.activity.note_key()
        circle = make_sim_circle(loops=3.0, points_per_loop=16, step_ms=5)
        out = pipe.process_events(circle)
        # Must not emit nearly as many position samples as the buffered circle
        # would have if path-replayed in one go after the delay window.
        in_path = _xy_path(circle)
        out_path = _xy_path(out)
        # First emitted point is coalesced; remaining follow 1:1 after arm.
        # Total out points should be well under full input (drop first ~40ms).
        self.assertLess(len(out_path), len(in_path))
        self.assertGreater(len(out_path), 0)
        # No single-frame dump of 3 loops worth of points.
        self.assertLess(len(out_path), len(in_path) - 3)


class TestSoftAccel(unittest.TestCase):
    def test_gain_scales_deltas_not_absolute(self) -> None:
        filt = SoftAccelFilter(gain=2.0, x_min=0, x_max=10000, y_min=0, y_max=10000)
        brush = make_sim_brush(duration_ms=20, dx=10, step_ms=5, start_x=100, start_y=100)
        out = []
        frame: list[Ev] = []
        for ev in brush:
            frame.append(ev)
            if ev.type == EV_SYN and ev.code == SYN_REPORT:
                out.extend(filt.process_frame(frame))
                frame = []
        xs = [e.value for e in out if e.type == EV_ABS and e.code == ABS_MT_POSITION_X]
        self.assertTrue(xs)
        # Raw end ≈ 100 + 10*4 = 140; with gain 2 → larger.
        self.assertGreater(max(xs), 140)

    def test_multi_syn_blob_split_not_collapsed(self) -> None:
        """If a caller concatenates frames, soft_accel must not flatten path."""
        filt = SoftAccelFilter(gain=2.0)
        a = make_sim_brush(duration_ms=15, dx=10, step_ms=5, start_x=100, start_y=100)
        # Feed as one blob (old exec_delay bug shape).
        out = filt.process_frame(list(a))
        self.assertGreaterEqual(count_syn_reports(out), count_syn_reports(a))
        path = _xy_path(out)
        self.assertGreater(len(set(path)), 1)

    def test_partial_axis_frames_do_not_leak_raw(self) -> None:
        """X-only / Y-only SYN frames must stay in amplified space (no teleport)."""
        filt = SoftAccelFilter(gain=2.0, resync_delta=1000)
        frames = [
            [
                Ev(0, 0, EV_ABS, ABS_MT_TRACKING_ID, 1),
                Ev(0, 0, EV_ABS, ABS_MT_POSITION_X, 100),
                Ev(0, 0, EV_ABS, ABS_MT_POSITION_Y, 100),
                Ev(0, 0, EV_KEY, BTN_TOUCH, 1),
                Ev.syn(0, 0),
            ],
            # X-only step +10 → out_x should become 120, not raw 110
            [
                Ev(0, 5_000, EV_ABS, ABS_MT_POSITION_X, 110),
                Ev.syn(0, 5_000),
            ],
            # Y-only step +10 → out_y 120
            [
                Ev(0, 10_000, EV_ABS, ABS_MT_POSITION_Y, 110),
                Ev.syn(0, 10_000),
            ],
            [
                Ev(0, 15_000, EV_ABS, ABS_MT_POSITION_X, 120),
                Ev(0, 15_000, EV_ABS, ABS_MT_POSITION_Y, 120),
                Ev.syn(0, 15_000),
            ],
        ]
        outs = [filt.process_frame(fr) for fr in frames]
        x1 = next(e.value for e in outs[1] if e.code == ABS_MT_POSITION_X)
        self.assertEqual(x1, 120)  # 100 + 10*2, not raw 110
        y2 = next(e.value for e in outs[2] if e.code == ABS_MT_POSITION_Y)
        self.assertEqual(y2, 120)
        x3 = next(e.value for e in outs[3] if e.code == ABS_MT_POSITION_X)
        y3 = next(e.value for e in outs[3] if e.code == ABS_MT_POSITION_Y)
        self.assertEqual((x3, y3), (140, 140))

    def test_large_delta_resyncs_without_gain(self) -> None:
        filt = SoftAccelFilter(gain=2.0, resync_delta=50)
        f0 = [
            Ev(0, 0, EV_ABS, ABS_MT_TRACKING_ID, 1),
            Ev(0, 0, EV_ABS, ABS_MT_POSITION_X, 100),
            Ev(0, 0, EV_ABS, ABS_MT_POSITION_Y, 100),
            Ev.syn(0, 0),
        ]
        f1 = [
            Ev(0, 1, EV_ABS, ABS_MT_POSITION_X, 400),  # delta 300 >= resync
            Ev(0, 1, EV_ABS, ABS_MT_POSITION_Y, 100),
            Ev.syn(0, 1),
        ]
        filt.process_frame(f0)
        out = filt.process_frame(f1)
        x = next(e.value for e in out if e.code == ABS_MT_POSITION_X)
        # Must not amplify 300 → 600; resync to 400.
        self.assertEqual(x, 400)

    def test_nonlinear_amplifies_large_more_than_small(self) -> None:
        from zenbook_kb.touchpad import SOFT_ACCEL_MODE_NONLINEAR

        lin = SoftAccelFilter(gain=2.0, mode="linear", pivot=40)
        non = SoftAccelFilter(gain=2.0, mode=SOFT_ACCEL_MODE_NONLINEAR, pivot=40)

        def run(filt: SoftAccelFilter, step: int) -> int:
            filt.reset()
            f0 = [
                Ev(0, 0, EV_ABS, ABS_MT_TRACKING_ID, 1),
                Ev(0, 0, EV_ABS, ABS_MT_POSITION_X, 100),
                Ev(0, 0, EV_ABS, ABS_MT_POSITION_Y, 100),
                Ev.syn(0, 0),
            ]
            f1 = [
                Ev(0, 1, EV_ABS, ABS_MT_POSITION_X, 100 + step),
                Ev(0, 1, EV_ABS, ABS_MT_POSITION_Y, 100),
                Ev.syn(0, 1),
            ]
            filt.process_frame(f0)
            out = filt.process_frame(f1)
            return next(e.value for e in out if e.code == ABS_MT_POSITION_X)

        # Tiny step: nonlinear stays near 1×; linear always ×2.
        self.assertEqual(run(lin, 4), 108)  # 100 + 4*2
        self.assertLess(run(non, 4), 108)
        self.assertGreaterEqual(run(non, 4), 104)
        # Large step near pivot: nonlinear approaches linear gain.
        self.assertEqual(run(lin, 40), 180)
        self.assertGreater(run(non, 40), run(non, 4))
        self.assertAlmostEqual(run(non, 40), 180, delta=2)

    def test_mode_roundtrip_in_knobs(self) -> None:
        from zenbook_kb.touchpad import (
            filters_from_knobs,
            knobs_from_filters,
            build_pipeline,
        )

        filters = filters_from_knobs(
            delay_enabled=True,
            delay_ms=25,
            outlier_enabled=True,
            max_delta=1200,
            soft_accel_mode="nonlinear",
            soft_accel_gain=1.6,
        )
        knobs = knobs_from_filters(filters)
        self.assertEqual(knobs["soft_accel_mode"], "nonlinear")
        pipe = build_pipeline({"filters": filters})
        soft = next(
            f for f in pipe.filters if f.__class__.__name__ == "SoftAccelFilter"
        )
        self.assertEqual(soft.mode, "nonlinear")

    def test_two_slot_scroll_not_collapsed(self) -> None:
        """2-finger frames must keep distinct slot positions (scroll)."""
        filt = SoftAccelFilter(gain=2.0)
        frames = [
            [
                Ev(0, 0, EV_ABS, ABS_MT_SLOT, 0),
                Ev(0, 0, EV_ABS, ABS_MT_TRACKING_ID, 1),
                Ev(0, 0, EV_ABS, ABS_MT_POSITION_X, 100),
                Ev(0, 0, EV_ABS, ABS_MT_POSITION_Y, 100),
                Ev(0, 0, EV_KEY, BTN_TOUCH, 1),
                Ev(0, 0, EV_KEY, BTN_TOOL_FINGER, 1),
                Ev.syn(0, 0),
            ],
            [
                Ev(0, 10_000, EV_ABS, ABS_MT_SLOT, 1),
                Ev(0, 10_000, EV_ABS, ABS_MT_TRACKING_ID, 2),
                Ev(0, 10_000, EV_ABS, ABS_MT_POSITION_X, 300),
                Ev(0, 10_000, EV_ABS, ABS_MT_POSITION_Y, 300),
                Ev(0, 10_000, EV_KEY, BTN_TOOL_FINGER, 0),
                Ev(0, 10_000, EV_KEY, BTN_TOOL_DOUBLETAP, 1),
                Ev.syn(0, 10_000),
            ],
            [
                Ev(0, 20_000, EV_ABS, ABS_MT_SLOT, 0),
                Ev(0, 20_000, EV_ABS, ABS_MT_POSITION_X, 100),
                Ev(0, 20_000, EV_ABS, ABS_MT_POSITION_Y, 120),
                Ev(0, 20_000, EV_ABS, ABS_MT_SLOT, 1),
                Ev(0, 20_000, EV_ABS, ABS_MT_POSITION_X, 300),
                Ev(0, 20_000, EV_ABS, ABS_MT_POSITION_Y, 320),
                Ev.syn(0, 20_000),
            ],
        ]
        outs = [filt.process_frame(fr) for fr in frames]
        # Slot-1 landing and scroll frame must be byte-identical (no gain).
        self.assertEqual(outs[1], frames[1])
        self.assertEqual(outs[2], frames[2])
        ys = [e.value for e in outs[2] if e.code == ABS_MT_POSITION_Y]
        self.assertEqual(ys, [120, 320])


class TestMultitouchExecDelay(unittest.TestCase):
    def test_tool_finger_off_does_not_drop_second_contact(self) -> None:
        """BTN_TOOL_FINGER=0 on DOUBLETAP must not wipe contacts mid-scroll."""
        filt = ExecDelayFilter(ms=40)
        f0 = [
            Ev(0, 0, EV_ABS, ABS_MT_SLOT, 0),
            Ev(0, 0, EV_ABS, ABS_MT_TRACKING_ID, 1),
            Ev(0, 0, EV_ABS, ABS_MT_POSITION_X, 100),
            Ev(0, 0, EV_ABS, ABS_MT_POSITION_Y, 100),
            Ev(0, 0, EV_KEY, BTN_TOUCH, 1),
            Ev(0, 0, EV_KEY, BTN_TOOL_FINGER, 1),
            Ev.syn(0, 0),
        ]
        f1 = [
            Ev(0, 10_000, EV_ABS, ABS_MT_SLOT, 1),
            Ev(0, 10_000, EV_ABS, ABS_MT_TRACKING_ID, 2),
            Ev(0, 10_000, EV_ABS, ABS_MT_POSITION_X, 300),
            Ev(0, 10_000, EV_ABS, ABS_MT_POSITION_Y, 300),
            Ev(0, 10_000, EV_KEY, BTN_TOOL_FINGER, 0),
            Ev(0, 10_000, EV_KEY, BTN_TOOL_DOUBLETAP, 1),
            Ev.syn(0, 10_000),
        ]
        f2 = [
            Ev(0, 20_000, EV_ABS, ABS_MT_SLOT, 0),
            Ev(0, 20_000, EV_ABS, ABS_MT_POSITION_Y, 140),
            Ev(0, 20_000, EV_ABS, ABS_MT_SLOT, 1),
            Ev(0, 20_000, EV_ABS, ABS_MT_POSITION_Y, 340),
            Ev.syn(0, 20_000),
        ]
        o0 = filt.process_frame(f0)
        self.assertEqual(o0, [])  # buffering first contact
        o1 = filt.process_frame(f1)
        self.assertTrue(o1)  # MT flushes buffer + second finger
        self.assertIn((EV_KEY, BTN_TOOL_DOUBLETAP, 1), {(e.type, e.code, e.value) for e in o1})
        o2 = filt.process_frame(f2)
        self.assertEqual(o2, f2)  # armed passthrough preserves slots
        ys = [e.value for e in o2 if e.code == ABS_MT_POSITION_Y]
        self.assertEqual(ys, [140, 340])


class TestMultitouchOutlier(unittest.TestCase):
    def test_second_finger_not_treated_as_teleport(self) -> None:
        filt = OutlierRejectFilter(max_delta=50)
        f0 = [
            Ev(0, 0, EV_ABS, ABS_MT_SLOT, 0),
            Ev(0, 0, EV_ABS, ABS_MT_TRACKING_ID, 1),
            Ev(0, 0, EV_ABS, ABS_MT_POSITION_X, 100),
            Ev(0, 0, EV_ABS, ABS_MT_POSITION_Y, 100),
            Ev.syn(0, 0),
        ]
        f1 = [
            Ev(0, 1, EV_ABS, ABS_MT_SLOT, 1),
            Ev(0, 1, EV_ABS, ABS_MT_TRACKING_ID, 2),
            Ev(0, 1, EV_ABS, ABS_MT_POSITION_X, 800),
            Ev(0, 1, EV_ABS, ABS_MT_POSITION_Y, 800),
            Ev(0, 1, EV_KEY, BTN_TOOL_DOUBLETAP, 1),
            Ev.syn(0, 1),
        ]
        self.assertEqual(filt.process_frame(f0), f0)
        # Delta 700 >> 50 — must NOT drop when multitouch.
        self.assertEqual(filt.process_frame(f1), f1)


class TestWhenTypingGate(unittest.TestCase):
    def test_bypass_when_idle(self) -> None:
        inner = ExecDelayFilter(ms=40)
        act = KeyboardActivity(window_ms=300)
        gate = WhenTypingGate(inner, act)
        brush = make_sim_brush(duration_ms=20, dx=3)
        out = []
        frame: list[Ev] = []
        for ev in brush:
            frame.append(ev)
            if ev.type == EV_SYN and ev.code == SYN_REPORT:
                out.extend(gate.process_frame(frame))
                frame = []
        self.assertEqual(count_syn_reports(out), count_syn_reports(brush))

    def test_armed_drops_short(self) -> None:
        inner = ExecDelayFilter(ms=40)
        act = KeyboardActivity(window_ms=500)
        act.note_key()
        gate = WhenTypingGate(inner, act)
        brush = make_sim_brush(duration_ms=20, dx=3)
        out = []
        frame: list[Ev] = []
        for ev in brush:
            frame.append(ev)
            if ev.type == EV_SYN and ev.code == SYN_REPORT:
                out.extend(gate.process_frame(frame))
                frame = []
        self.assertEqual(out, [])


def _stamp(t_ms: float) -> tuple[int, int]:
    sec = int(t_ms / 1000.0)
    usec = int(round((t_ms - sec * 1000.0) * 1000.0))
    return sec, usec


def make_chaos_stream(
    rng: random.Random,
    *,
    gestures: int = 40,
    step_ms: float = 5.0,
) -> tuple[list[Ev], set[int]]:
    """Semi-random MT stream: moves, spikes, short brushes, dual-finger, keys.

    Returns (events, key_frame_indices) where key_frame_indices marks SYN
    frames after which the test should call ``activity.note_key()``.
    """
    events: list[Ev] = []
    key_after_syn: set[int] = set()
    t = 0.0
    syn_i = 0
    tid = 1
    x = y = 2000

    def emit(frame_evs: list[Ev]) -> None:
        nonlocal syn_i, t
        sec, usec = _stamp(t)
        for ev in frame_evs:
            events.append(Ev(sec, usec, ev.type, ev.code, ev.value))
        events.append(Ev.syn(sec, usec))
        syn_i += 1
        t += step_ms

    for g in range(gestures):
        kind = rng.choice(
            (
                "move",
                "move",
                "move",
                "brush",
                "spike",
                "dual",
                "partial",
                "reanchor",
            )
        )
        if rng.random() < 0.25:
            key_after_syn.add(syn_i)

        if kind == "brush":
            sec_evs = [
                Ev(0, 0, EV_ABS, ABS_MT_SLOT, 0),
                Ev(0, 0, EV_ABS, ABS_MT_TRACKING_ID, tid),
                Ev(0, 0, EV_ABS, ABS_MT_POSITION_X, x),
                Ev(0, 0, EV_ABS, ABS_MT_POSITION_Y, y),
                Ev(0, 0, EV_KEY, BTN_TOUCH, 1),
                Ev(0, 0, EV_KEY, BTN_TOOL_FINGER, 1),
            ]
            emit(sec_evs)
            for _ in range(rng.randint(1, 3)):
                x += rng.randint(-3, 3)
                y += rng.randint(-3, 3)
                emit(
                    [
                        Ev(0, 0, EV_ABS, ABS_MT_POSITION_X, x),
                        Ev(0, 0, EV_ABS, ABS_MT_POSITION_Y, y),
                    ]
                )
            emit(
                [
                    Ev(0, 0, EV_ABS, ABS_MT_TRACKING_ID, -1),
                    Ev(0, 0, EV_KEY, BTN_TOUCH, 0),
                    Ev(0, 0, EV_KEY, BTN_TOOL_FINGER, 0),
                ]
            )
            tid += 1
            continue

        # Contact start
        x = rng.randint(800, 3200)
        y = rng.randint(800, 3200)
        emit(
            [
                Ev(0, 0, EV_ABS, ABS_MT_SLOT, 0),
                Ev(0, 0, EV_ABS, ABS_MT_TRACKING_ID, tid),
                Ev(0, 0, EV_ABS, ABS_MT_POSITION_X, x),
                Ev(0, 0, EV_ABS, ABS_MT_POSITION_Y, y),
                Ev(0, 0, EV_KEY, BTN_TOUCH, 1),
                Ev(0, 0, EV_KEY, BTN_TOOL_FINGER, 1),
            ]
        )
        n = rng.randint(8, 24)
        for i in range(n):
            if kind == "spike" and i == n // 2:
                emit(
                    [
                        Ev(0, 0, EV_ABS, ABS_MT_POSITION_X, x + 2500),
                        Ev(0, 0, EV_ABS, ABS_MT_POSITION_Y, y + 2500),
                    ]
                )
                continue
            if kind == "partial":
                if i % 2 == 0:
                    x += rng.randint(-12, 12)
                    emit([Ev(0, 0, EV_ABS, ABS_MT_POSITION_X, x)])
                else:
                    y += rng.randint(-12, 12)
                    emit([Ev(0, 0, EV_ABS, ABS_MT_POSITION_Y, y)])
                continue
            if kind == "dual" and i == 3:
                x2 = x + rng.randint(80, 200)
                y2 = y + rng.randint(80, 200)
                emit(
                    [
                        Ev(0, 0, EV_ABS, ABS_MT_SLOT, 1),
                        Ev(0, 0, EV_ABS, ABS_MT_TRACKING_ID, tid + 1),
                        Ev(0, 0, EV_ABS, ABS_MT_POSITION_X, x2),
                        Ev(0, 0, EV_ABS, ABS_MT_POSITION_Y, y2),
                        Ev(0, 0, EV_KEY, BTN_TOOL_FINGER, 0),
                        Ev(0, 0, EV_KEY, BTN_TOOL_DOUBLETAP, 1),
                    ]
                )
                for _ in range(rng.randint(4, 10)):
                    y += rng.randint(4, 18)
                    y2 += rng.randint(4, 18)
                    emit(
                        [
                            Ev(0, 0, EV_ABS, ABS_MT_SLOT, 0),
                            Ev(0, 0, EV_ABS, ABS_MT_POSITION_Y, y),
                            Ev(0, 0, EV_ABS, ABS_MT_SLOT, 1),
                            Ev(0, 0, EV_ABS, ABS_MT_POSITION_Y, y2),
                        ]
                    )
                emit(
                    [
                        Ev(0, 0, EV_ABS, ABS_MT_SLOT, 1),
                        Ev(0, 0, EV_ABS, ABS_MT_TRACKING_ID, -1),
                        Ev(0, 0, EV_KEY, BTN_TOOL_DOUBLETAP, 0),
                        Ev(0, 0, EV_KEY, BTN_TOOL_FINGER, 1),
                    ]
                )
                continue
            if kind == "reanchor" and i == n // 2:
                # Lift + land far away (new tracking id) — must not look like spike.
                emit(
                    [
                        Ev(0, 0, EV_ABS, ABS_MT_TRACKING_ID, -1),
                        Ev(0, 0, EV_KEY, BTN_TOUCH, 0),
                        Ev(0, 0, EV_KEY, BTN_TOOL_FINGER, 0),
                    ]
                )
                tid += 1
                x = rng.randint(500, 4000)
                y = rng.randint(500, 4000)
                emit(
                    [
                        Ev(0, 0, EV_ABS, ABS_MT_SLOT, 0),
                        Ev(0, 0, EV_ABS, ABS_MT_TRACKING_ID, tid),
                        Ev(0, 0, EV_ABS, ABS_MT_POSITION_X, x),
                        Ev(0, 0, EV_ABS, ABS_MT_POSITION_Y, y),
                        Ev(0, 0, EV_KEY, BTN_TOUCH, 1),
                        Ev(0, 0, EV_KEY, BTN_TOOL_FINGER, 1),
                    ]
                )
                continue
            x += rng.randint(-15, 15)
            y += rng.randint(-15, 15)
            emit(
                [
                    Ev(0, 0, EV_ABS, ABS_MT_POSITION_X, x),
                    Ev(0, 0, EV_ABS, ABS_MT_POSITION_Y, y),
                ]
            )
        emit(
            [
                Ev(0, 0, EV_ABS, ABS_MT_TRACKING_ID, -1),
                Ev(0, 0, EV_KEY, BTN_TOUCH, 0),
                Ev(0, 0, EV_KEY, BTN_TOOL_FINGER, 0),
            ]
        )
        tid += 2
        t += rng.uniform(20.0, 80.0)  # gap between gestures

    return events, key_after_syn


class TestChaosStress(unittest.TestCase):
    """Feed ~10× denser semi-random streams; catch parasite / outlier leaks."""

    def _armed_pipe(self):
        return build_pipeline(
            {
                "filters": [
                    {"plugin": "typing_inhibit", "window_ms": 500, "enabled": True},
                    {"plugin": "exec_delay", "ms": 25, "enabled": True},
                    {"plugin": "outlier_reject", "max_delta": DEFAULT_MAX_DELTA},
                    {"plugin": "soft_accel", "gain": 1.6, "enabled": True},
                ]
            }
        )

    def test_chaos_no_multi_syn_and_bounded_jumps(self) -> None:
        rng = random.Random(20260720)
        pipe = self._armed_pipe()
        assert pipe.activity is not None
        events, key_at = make_chaos_stream(rng, gestures=48, step_ms=5.0)

        chunks: list[list[Ev]] = []
        frame: list[Ev] = []
        syn_i = 0
        for ev in events:
            if syn_i in key_at and not frame:
                pipe.activity.note_key()
            frame.append(ev)
            if ev.type == EV_SYN and ev.code == SYN_REPORT:
                out = pipe.process_frame(frame)
                if out:
                    chunks.append(out)
                    self.assertLessEqual(
                        count_syn_reports(out),
                        2,  # MT flush may emit buffered frames + current
                        f"parasite multi-SYN ({count_syn_reports(out)}) at syn {syn_i}",
                    )
                frame = []
                syn_i += 1

        # Flatten path; within a contact, steps must stay below soft_accel resync
        # unless the input itself jumped (spike dropped or contact edge).
        path = _xy_path([e for chunk in chunks for e in chunk])
        self.assertGreater(len(path), 20, "chaos produced almost no motion")
        big = 0
        for (x0, y0), (x1, y1) in zip(path, path[1:]):
            d = math.hypot(x1 - x0, y1 - y0)
            if d > 800:
                big += 1
        # Occasional reanchor / coalesce edges are OK; a flood of teleports is not.
        self.assertLess(
            big,
            max(6, len(path) // 15),
            f"too many parasite teleports: {big}/{len(path)} steps >800",
        )

    def test_chaos_ten_seeds_stable(self) -> None:
        """Run the same invariants across 10 RNG seeds (~10× coverage)."""
        for seed in range(10):
            rng = random.Random(1000 + seed)
            pipe = self._armed_pipe()
            assert pipe.activity is not None
            events, key_at = make_chaos_stream(rng, gestures=36, step_ms=5.0)
            frame: list[Ev] = []
            syn_i = 0
            dual_out = 0
            for ev in events:
                if syn_i in key_at and not frame:
                    pipe.activity.note_key()
                frame.append(ev)
                if ev.type == EV_SYN and ev.code == SYN_REPORT:
                    out = pipe.process_frame(frame)
                    if out:
                        self.assertLessEqual(count_syn_reports(out), 2, seed)
                        if any(
                            e.type == EV_KEY
                            and e.code == BTN_TOOL_DOUBLETAP
                            and e.value
                            for e in out
                        ):
                            dual_out += 1
                    frame = []
                    syn_i += 1
            # At least some dual-finger frames must survive when present in input.
            dual_in = sum(
                1
                for e in events
                if e.type == EV_KEY and e.code == BTN_TOOL_DOUBLETAP and e.value
            )
            if dual_in:
                self.assertGreater(dual_out, 0, f"seed {seed} dropped all multitouch")


class TestSelftest(unittest.TestCase):
    def test_run_selftest_ok(self) -> None:
        result = run_selftest()
        self.assertTrue(result["ok"], result)


if __name__ == "__main__":
    unittest.main()
