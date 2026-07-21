"""Touchpad palm-filter pipeline (stdlib only).

Ordered plugins (iptables-inspired, single chain):
  1. event_sim        — synthetic frames for tests
  2. typing_inhibit   — arm palm filters only after recent keyboard activity
  3. exec_delay       — hold contact ≤N ms; drop short brushes (when armed)
  4. outlier_reject   — drop impossible jumps (when armed)
  5. soft_accel       — scale motion for live uinput (DE AccelSpeed bypass)

Live path: EVIOCGRAB source → filters → uinput virtual device.
"""

from __future__ import annotations

import array
import fcntl
import json
import logging
import os
import select
import struct
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator, Sequence

log = logging.getLogger("zenbook.touchpad")

INPUT_EVENT_FMT = "@llHHi"
INPUT_EVENT_SIZE = struct.calcsize(INPUT_EVENT_FMT)
EVIOCGRAB = 0x40044590

EV_SYN = 0x00
EV_KEY = 0x01
EV_REL = 0x02
EV_ABS = 0x03
EV_MSC = 0x04
SYN_REPORT = 0
BTN_MISC = 0x100
BTN_TOUCH = 0x14A
BTN_TOOL_FINGER = 0x145
BTN_TOOL_DOUBLETAP = 0x14D
BTN_TOOL_TRIPLETAP = 0x14E
BTN_TOOL_QUADTAP = 0x14F
ABS_X = 0x00
ABS_Y = 0x01
ABS_MT_SLOT = 0x2F
ABS_MT_POSITION_X = 0x35
ABS_MT_POSITION_Y = 0x36
ABS_MT_TRACKING_ID = 0x39

UI_DEV_CREATE = 0x5501
UI_DEV_DESTROY = 0x5502
UI_DEV_SETUP = 0x405C5503
UI_ABS_SETUP = 0x401C5504
UI_SET_EVBIT = 0x40045564
UI_SET_KEYBIT = 0x40045565
UI_SET_RELBIT = 0x40045566
UI_SET_ABSBIT = 0x40045567
UI_SET_PROPBIT = 0x4004556E

UINPUT_MAX_NAME_SIZE = 80
DEFAULT_CONFIG = Path("/etc/zenbook-scripts/touchpad.json")
DEFAULT_EXEC_DELAY_MS = 25.0
DEFAULT_MAX_DELTA = 1200
DEFAULT_TYPING_WINDOW_MS = 350.0
DEFAULT_SOFT_ACCEL_GAIN = 1.6
# If a single-frame raw delta exceeds this, resync instead of amplifying
# (dropped frames / coalesce teleports must not become gain-scaled jumps).
DEFAULT_SOFT_ACCEL_RESYNC = 250
# Non-linear curve: |delta| at which effective gain reaches the configured gain.
DEFAULT_SOFT_ACCEL_PIVOT = 40
SOFT_ACCEL_MODE_LINEAR = "linear"
SOFT_ACCEL_MODE_NONLINEAR = "nonlinear"
DEFAULT_SOFT_ACCEL_MODE = SOFT_ACCEL_MODE_LINEAR


def normalize_soft_accel_mode(mode: object) -> str:
    """Map config/UI values to ``linear`` or ``nonlinear``."""
    raw = str(mode or DEFAULT_SOFT_ACCEL_MODE).strip().lower().replace("-", "_")
    if raw in (
        "nonlinear",
        "non_linear",
        "curve",
        "accel",
        "progressive",
    ):
        return SOFT_ACCEL_MODE_NONLINEAR
    return SOFT_ACCEL_MODE_LINEAR

INPUT_PROP_DIRECT = 0
INPUT_PROP_POINTER = 1
INPUT_PROP_BUTTONPAD = 2


def _ioc(dir_: int, type_: str, nr: int, size: int) -> int:
    return (dir_ << 30) | ((size & 0x3FFF) << 16) | (ord(type_) << 8) | nr


def eviocgabs(code: int) -> int:
    return _ioc(2, "E", 0x40 + code, 24)


def eviocgbit(ev: int, length: int) -> int:
    return _ioc(2, "E", 0x20 + ev, length)


def eviocgprop(length: int) -> int:
    return _ioc(2, "E", 0x09, length)


@dataclass(slots=True)
class Ev:
    sec: int
    usec: int
    type: int
    code: int
    value: int

    @property
    def t_ms(self) -> float:
        return self.sec * 1000.0 + self.usec / 1000.0

    def pack(self) -> bytes:
        return struct.pack(INPUT_EVENT_FMT, self.sec, self.usec, self.type, self.code, self.value)

    @classmethod
    def unpack(cls, data: bytes) -> Ev:
        sec, usec, etype, code, value = struct.unpack(INPUT_EVENT_FMT, data)
        return cls(sec, usec, etype, code, value)

    @classmethod
    def syn(cls, sec: int = 0, usec: int = 0) -> Ev:
        return cls(sec, usec, EV_SYN, SYN_REPORT, 0)


@dataclass
class FilterStats:
    name: str
    in_frames: int = 0
    out_frames: int = 0
    dropped_frames: int = 0

    def note(self, n_in: int, n_out: int) -> None:
        self.in_frames += 1 if n_in else 0
        if n_in:
            if n_out:
                self.out_frames += 1
            else:
                self.dropped_frames += 1


class Filter:
    name = "filter"

    def __init__(self) -> None:
        self.stats = FilterStats(self.name)

    def process_frame(self, frame: list[Ev]) -> list[Ev]:
        raise NotImplementedError

    def reset(self) -> None:
        pass


def _split_syn_frames(events: Sequence[Ev]) -> list[list[Ev]]:
    """Split a flat event list into SYN_REPORT-delimited frames."""
    frames: list[list[Ev]] = []
    cur: list[Ev] = []
    for ev in events:
        cur.append(ev)
        if ev.type == EV_SYN and ev.code == SYN_REPORT:
            frames.append(cur)
            cur = []
    if cur:
        frames.append(cur)
    return frames


def count_syn_reports(events: Sequence[Ev]) -> int:
    return sum(1 for e in events if e.type == EV_SYN and e.code == SYN_REPORT)


_MT_TOOL_CODES = (BTN_TOOL_DOUBLETAP, BTN_TOOL_TRIPLETAP, BTN_TOOL_QUADTAP)


def frame_is_multitouch(frame: Sequence[Ev]) -> bool:
    """True if this SYN frame clearly involves more than one contact."""
    slots: set[int] = set()
    new_ids = 0
    for ev in frame:
        if ev.type == EV_ABS and ev.code == ABS_MT_SLOT:
            slots.add(ev.value)
        elif ev.type == EV_ABS and ev.code == ABS_MT_TRACKING_ID and ev.value >= 0:
            new_ids += 1
        elif ev.type == EV_KEY and ev.code in _MT_TOOL_CODES and ev.value:
            return True
    if any(s != 0 for s in slots):
        return True
    return new_ids > 1


def _tracking_id_delta(frame: Sequence[Ev]) -> int:
    """Net change in live tracking IDs from this frame (+new / -lift)."""
    delta = 0
    for ev in frame:
        if ev.type == EV_ABS and ev.code == ABS_MT_TRACKING_ID:
            if ev.value >= 0:
                delta += 1
            else:
                delta -= 1
    return delta


class KeyboardActivity:
    """Shared clock: palm filters arm for ``window_ms`` after a key press."""

    def __init__(self, window_ms: float = DEFAULT_TYPING_WINDOW_MS) -> None:
        self.window_ms = float(window_ms)
        self._last_key_mono = 0.0
        self.key_events = 0

    def set_window_ms(self, window_ms: float) -> None:
        self.window_ms = float(window_ms)

    def note_key(self, *, mono: float | None = None) -> None:
        self._last_key_mono = time.monotonic() if mono is None else float(mono)
        self.key_events += 1

    def active(self, *, now: float | None = None) -> bool:
        if self._last_key_mono <= 0:
            return False
        t = time.monotonic() if now is None else now
        return (t - self._last_key_mono) * 1000.0 <= self.window_ms

    def note_ev(self, ev: Ev) -> bool:
        """Return True if this event counted as a typing key press."""
        if ev.type != EV_KEY or ev.value != 1:
            return False
        # Ignore mouse/tablet buttons (BTN_* start at 0x100).
        if ev.code >= BTN_MISC:
            return False
        self.note_key()
        return True


class WhenTypingGate(Filter):
    """Run ``inner`` only while ``activity`` is armed; otherwise pass-through."""

    def __init__(self, inner: Filter, activity: KeyboardActivity) -> None:
        super().__init__()
        self.inner = inner
        self.activity = activity
        self.name = f"{inner.name}+typing"
        self.stats = FilterStats(self.name)
        self._was_active = False
        self.bypass_frames = 0
        self.active_frames = 0

    def reset(self) -> None:
        self.inner.reset()
        self._was_active = False

    def process_frame(self, frame: list[Ev]) -> list[Ev]:
        if not frame:
            return frame
        if not self.activity.active():
            if self._was_active:
                # Drop any unreleased buffer; do not replay it on disarm.
                self.inner.reset()
                self._was_active = False
            self.bypass_frames += 1
            self.stats.note(1, 1)
            return frame
        if not self._was_active:
            # Entering armed: clear stale inner state from a prior window.
            self.inner.reset()
            self._was_active = True
        self.active_frames += 1
        out = self.inner.process_frame(frame)
        self.stats.note(1, 1 if out else 0)
        return out


class SoftAccelFilter(Filter):
    """Scale ABS motion deltas (live uinput lacks DE AccelSpeed).

    Pads often emit X and Y in separate SYN frames. Latches each axis so a
    single-axis update never leaks a raw coordinate against an amplified peer
    (that mismatch is a cursor teleport). Large raw deltas resync without gain.

    Modes:
      * ``linear`` — constant ``gain`` on every delta (default).
      * ``nonlinear`` — slow/precise moves stay near 1×; larger per-frame
        deltas ramp toward ``gain`` (simple pointer-accel style curve).

    Multitouch (2-finger scroll, etc.) is passed through unmodified — a single
    XY latch would collapse slots and break DE scroll gestures.
    """

    name = "soft_accel"

    def __init__(
        self,
        gain: float = DEFAULT_SOFT_ACCEL_GAIN,
        *,
        mode: str = DEFAULT_SOFT_ACCEL_MODE,
        pivot: int = DEFAULT_SOFT_ACCEL_PIVOT,
        x_min: int = 0,
        x_max: int = 10000,
        y_min: int = 0,
        y_max: int = 10000,
        resync_delta: int = DEFAULT_SOFT_ACCEL_RESYNC,
    ) -> None:
        super().__init__()
        self.gain = float(gain)
        self.mode = normalize_soft_accel_mode(mode)
        self.pivot = max(1, int(pivot))
        self.x_min = int(x_min)
        self.x_max = int(x_max)
        self.y_min = int(y_min)
        self.y_max = int(y_max)
        self.resync_delta = int(resync_delta)
        self._raw_x: int | None = None
        self._raw_y: int | None = None
        self._out_x: int | None = None
        self._out_y: int | None = None
        self._fingers = 0
        self._mt_sticky = False

    def set_gain(self, gain: float) -> None:
        self.gain = float(gain)

    def set_mode(self, mode: str) -> None:
        self.mode = normalize_soft_accel_mode(mode)

    def set_pivot(self, pivot: int) -> None:
        self.pivot = max(1, int(pivot))

    def reset(self) -> None:
        self._raw_x = self._raw_y = None
        self._out_x = self._out_y = None
        self._fingers = 0
        self._mt_sticky = False

    def _clear_latch(self) -> None:
        self._raw_x = self._raw_y = None
        self._out_x = self._out_y = None

    def _effective_gain(self, delta: int) -> float:
        if self.mode != SOFT_ACCEL_MODE_NONLINEAR:
            return self.gain
        # Smoothstep from 1.0 → gain as |delta| approaches pivot.
        t = min(1.0, abs(delta) / float(self.pivot))
        t = t * t * (3.0 - 2.0 * t)
        return 1.0 + (self.gain - 1.0) * t

    @staticmethod
    def _contact_edge(frame: list[Ev]) -> str | None:
        """Prefer TRACKING_ID; ignore BTN_TOOL_FINGER when multitouch tools fire."""
        has_tid = any(
            e.type == EV_ABS and e.code == ABS_MT_TRACKING_ID for e in frame
        )
        mt_tool = any(
            e.type == EV_KEY and e.code in _MT_TOOL_CODES and e.value for e in frame
        )
        for ev in frame:
            if ev.type == EV_ABS and ev.code == ABS_MT_TRACKING_ID:
                return "new" if ev.value >= 0 else "end"
            if has_tid or mt_tool:
                continue
            if ev.type == EV_KEY and ev.code in (BTN_TOUCH, BTN_TOOL_FINGER):
                return "new" if ev.value else "end"
        return None

    @staticmethod
    def _axis_updates(frame: list[Ev]) -> tuple[int | None, int | None]:
        """Return (x, y) updates present in this frame (MT preferred over ST)."""
        mx = my = sx = sy = None
        for ev in frame:
            if ev.type != EV_ABS:
                continue
            if ev.code == ABS_MT_POSITION_X:
                mx = ev.value
            elif ev.code == ABS_MT_POSITION_Y:
                my = ev.value
            elif ev.code == ABS_X:
                sx = ev.value
            elif ev.code == ABS_Y:
                sy = ev.value
        x = mx if mx is not None else sx
        y = my if my is not None else sy
        return x, y

    def _step_axis(
        self,
        raw_attr: str,
        out_attr: str,
        value: int,
        lo: int,
        hi: int,
    ) -> int:
        raw = getattr(self, raw_attr)
        out = getattr(self, out_attr)
        if raw is None or out is None:
            setattr(self, raw_attr, value)
            setattr(self, out_attr, value)
            return value
        delta = value - raw
        setattr(self, raw_attr, value)
        if abs(delta) >= self.resync_delta:
            setattr(self, out_attr, value)
            return value
        gain = self._effective_gain(delta)
        nxt = int(round(out + delta * gain))
        nxt = max(lo, min(hi, nxt))
        setattr(self, out_attr, nxt)
        return nxt

    def process_frame(self, frame: list[Ev]) -> list[Ev]:
        if not frame or abs(self.gain - 1.0) < 1e-6:
            self.stats.note(1, 1)
            return frame
        syn_count = sum(
            1 for e in frame if e.type == EV_SYN and e.code == SYN_REPORT
        )
        if syn_count > 1:
            parts = _split_syn_frames(frame)
            out: list[Ev] = []
            for part in parts:
                out.extend(self.process_frame(part))
            return out

        self._fingers = max(0, self._fingers + _tracking_id_delta(frame))
        if self._fingers > 1 or frame_is_multitouch(frame):
            self._mt_sticky = True
        if self._fingers <= 0:
            self._mt_sticky = False
        if self._mt_sticky or self._fingers > 1 or frame_is_multitouch(frame):
            # Do not collapse slots into one amplified XY.
            self._clear_latch()
            self.stats.note(1, 1)
            return frame

        edge = self._contact_edge(frame)
        if edge == "end":
            self._clear_latch()
            if self._fingers <= 0:
                self._fingers = 0
            self.stats.note(1, 1)
            return frame
        if edge == "new":
            self._clear_latch()

        x_upd, y_upd = self._axis_updates(frame)
        if x_upd is None and y_upd is None:
            self.stats.note(1, 1)
            return frame

        if x_upd is not None:
            self._step_axis("_raw_x", "_out_x", x_upd, self.x_min, self.x_max)
        if y_upd is not None:
            self._step_axis("_raw_y", "_out_y", y_upd, self.y_min, self.y_max)

        rewritten: list[Ev] = []
        for ev in frame:
            if ev.type == EV_ABS and ev.code in (ABS_MT_POSITION_X, ABS_X):
                if self._out_x is None:
                    rewritten.append(ev)
                else:
                    rewritten.append(
                        Ev(ev.sec, ev.usec, ev.type, ev.code, self._out_x)
                    )
            elif ev.type == EV_ABS and ev.code in (ABS_MT_POSITION_Y, ABS_Y):
                if self._out_y is None:
                    rewritten.append(ev)
                else:
                    rewritten.append(
                        Ev(ev.sec, ev.usec, ev.type, ev.code, self._out_y)
                    )
            else:
                rewritten.append(ev)
        self.stats.note(1, 1)
        return rewritten


class ExecDelayFilter(Filter):
    """Hold first contact frames until ``ms`` elapsed; drop if contact ends sooner.

    When the delay elapses, emit **one coalesced** SYN frame (contact lifecycle
    from the first buffered frame + latest ABS position). Replaying the whole
    buffer as a multi-SYN burst looks like shake/circle motion to compositors
    (e.g. Plasma "find cursor") and causes cursor jumps after soft_accel.
    """

    name = "exec_delay"

    def __init__(self, ms: float = DEFAULT_EXEC_DELAY_MS) -> None:
        super().__init__()
        self.ms = float(ms)
        self._buf: list[list[Ev]] = []
        self._contact_t0: float | None = None
        self._armed = False
        self._contacts = 0
        self._saw_mt = False

    def set_ms(self, ms: float) -> None:
        self.ms = float(ms)

    def reset(self) -> None:
        self._buf.clear()
        self._contact_t0 = None
        self._armed = False
        self._contacts = 0
        self._saw_mt = False

    def _update_contacts(self, frame: list[Ev]) -> None:
        """Count contacts from TRACKING_ID when the pad speaks MT.

        BTN_TOOL_FINGER goes 0 when the tool switches to DOUBLETAP on a
        2-finger gesture — wiping contacts there used to drop the scroll.
        ST pads (no TRACKING_ID ever) still use BTN press/release.
        """
        delta = _tracking_id_delta(frame)
        has_tid = any(
            e.type == EV_ABS and e.code == ABS_MT_TRACKING_ID for e in frame
        )
        if has_tid:
            self._saw_mt = True
            self._contacts = max(0, self._contacts + delta)
            if self._contacts <= 0:
                self._saw_mt = False
            return
        if self._saw_mt:
            return
        for ev in frame:
            if ev.type == EV_KEY and ev.code in (BTN_TOUCH, BTN_TOOL_FINGER):
                if ev.value:
                    self._contacts = max(self._contacts, 1)
                else:
                    self._contacts = 0
                return

    @staticmethod
    def coalesce_buffered(frames: list[list[Ev]]) -> list[Ev]:
        """One SYN frame: press/tracking from first, positions from last."""
        if not frames:
            return []
        if len(frames) == 1:
            return list(frames[0])
        first, last = frames[0], frames[-1]
        sec, usec = last[-1].sec, last[-1].usec
        out: list[Ev] = []
        seen: set[tuple[int, int]] = set()

        def add(ev: Ev) -> None:
            key = (ev.type, ev.code)
            if ev.type != EV_SYN and key in seen:
                return
            out.append(Ev(sec, usec, ev.type, ev.code, ev.value))
            if ev.type != EV_SYN:
                seen.add(key)

        for ev in first:
            if ev.type == EV_ABS and ev.code in (ABS_MT_SLOT, ABS_MT_TRACKING_ID):
                if ev.code == ABS_MT_TRACKING_ID and ev.value < 0:
                    continue
                add(ev)
            elif ev.type == EV_KEY and ev.code in (BTN_TOUCH, BTN_TOOL_FINGER) and ev.value:
                add(ev)
        for ev in last:
            if ev.type == EV_SYN:
                continue
            if ev.type == EV_KEY and ev.code in (BTN_TOUCH, BTN_TOOL_FINGER) and not ev.value:
                continue
            add(ev)
        out.append(Ev.syn(sec, usec))
        return out

    def process_frame(self, frame: list[Ev]) -> list[Ev]:
        if not frame:
            return frame
        self._update_contacts(frame)
        # Always use the event clock for age. Mixing monotonic (when sec/usec
        # are both 0) with later event timestamps makes age negative forever,
        # so the contact is buffered until lift and then dropped — looks like
        # "parasite" dead zones / jumps after typing.
        now = frame[-1].t_ms
        mt = self._contacts > 1 or frame_is_multitouch(frame)

        if self._contacts <= 0:
            if self._armed:
                self._armed = False
                self._contact_t0 = None
                self._buf.clear()
                self.stats.note(1, 1)
                return frame
            # short brush ended while buffering → drop
            if self._buf:
                self._buf.clear()
                self._contact_t0 = None
                self.stats.note(1, 0)
                return []
            self.stats.note(1, 1)
            return frame

        # Multitouch: never replay the palm buffer (that was the parasite
        # multi-SYN path). Coalesce any single-finger prefix to one SYN, then
        # append the current MT frame — at most two SYNs.
        if mt and not self._armed:
            out: list[Ev] = []
            if self._buf:
                out.extend(self.coalesce_buffered(self._buf))
            self._buf.clear()
            out.extend(frame)
            self._contact_t0 = now
            self._armed = True
            self.stats.note(1, 1)
            return out

        # contact active
        if self._contact_t0 is None:
            self._contact_t0 = now
            self._armed = False
            self._buf = [frame]
            self.stats.note(1, 0)
            return []

        if self._armed:
            self.stats.note(1, 1)
            return frame

        age = now - self._contact_t0
        self._buf.append(frame)
        if age < self.ms:
            self.stats.note(1, 0)
            return []

        # delay satisfied — one coalesced frame, never a multi-SYN path replay
        out = self.coalesce_buffered(self._buf)
        self._buf.clear()
        self._armed = True
        self.stats.note(1, 1)
        return out


class OutlierRejectFilter(Filter):
    """Drop frames whose absolute position jumps more than ``max_delta``.

    Resets on new/ended contact so a finger landing elsewhere is not treated as
    a spike. A rejected frame still updates the last position so one spike cannot
    lock out the rest of the gesture.

    Multitouch is passed through — last-XY is single-slot and would treat the
    second finger as a teleport.
    """

    name = "outlier_reject"

    def __init__(self, max_delta: int = DEFAULT_MAX_DELTA) -> None:
        super().__init__()
        self.max_delta = int(max_delta)
        self._last: tuple[int, int] | None = None
        self._fingers = 0
        self._mt_sticky = False

    def set_max_delta(self, max_delta: int) -> None:
        self.max_delta = int(max_delta)

    def reset(self) -> None:
        self._last = None
        self._fingers = 0
        self._mt_sticky = False

    @staticmethod
    def _xy(frame: list[Ev]) -> tuple[int, int] | None:
        x = y = None
        for ev in frame:
            if ev.type != EV_ABS:
                continue
            if ev.code in (ABS_MT_POSITION_X, ABS_X):
                x = ev.value
            elif ev.code in (ABS_MT_POSITION_Y, ABS_Y):
                y = ev.value
        if x is None or y is None:
            return None
        return x, y

    def _contact_edge(self, frame: list[Ev]) -> str | None:
        """Return ``new``, ``end``, or None."""
        has_tid = any(
            e.type == EV_ABS and e.code == ABS_MT_TRACKING_ID for e in frame
        )
        mt_tool = any(
            e.type == EV_KEY and e.code in _MT_TOOL_CODES and e.value for e in frame
        )
        for ev in frame:
            if ev.type == EV_ABS and ev.code == ABS_MT_TRACKING_ID:
                return "new" if ev.value >= 0 else "end"
            if has_tid or mt_tool:
                continue
            if ev.type == EV_KEY and ev.code in (BTN_TOUCH, BTN_TOOL_FINGER):
                if ev.value:
                    return "new"
                return "end"
        return None

    def process_frame(self, frame: list[Ev]) -> list[Ev]:
        if not frame:
            return frame
        self._fingers = max(0, self._fingers + _tracking_id_delta(frame))
        if self._fingers > 1 or frame_is_multitouch(frame):
            self._mt_sticky = True
        if self._fingers <= 0:
            self._mt_sticky = False
        if self._mt_sticky or self._fingers > 1 or frame_is_multitouch(frame):
            self._last = None
            self.stats.note(1, 1)
            return frame

        edge = self._contact_edge(frame)
        if edge == "end":
            self._last = None
            self.stats.note(1, 1)
            return frame
        if edge == "new":
            self._last = None

        xy = self._xy(frame)
        if xy is None:
            self.stats.note(1, 1)
            return frame
        if self._last is not None:
            dx = abs(xy[0] - self._last[0])
            dy = abs(xy[1] - self._last[1])
            if dx > self.max_delta or dy > self.max_delta:
                # Advance last so a single spike cannot black-hole the gesture.
                self._last = xy
                self.stats.note(1, 0)
                return []
        self._last = xy
        self.stats.note(1, 1)
        return frame


@dataclass
class Pipeline:
    filters: list[Filter] = field(default_factory=list)
    activity: KeyboardActivity | None = None

    def process_frame(self, frame: list[Ev]) -> list[Ev]:
        out = frame
        for filt in self.filters:
            if not out:
                break
            out = filt.process_frame(out)
        return out

    def process_events(self, events: Iterable[Ev]) -> list[Ev]:
        frame: list[Ev] = []
        result: list[Ev] = []
        for ev in events:
            if self.activity is not None:
                self.activity.note_ev(ev)
            frame.append(ev)
            if ev.type == EV_SYN and ev.code == SYN_REPORT:
                result.extend(self.process_frame(frame))
                frame = []
        if frame:
            result.extend(self.process_frame(frame))
        return result

    def reset(self) -> None:
        for filt in self.filters:
            filt.reset()

    def summary(self) -> str:
        parts = []
        if self.activity is not None:
            parts.append(
                f"typing_inhibit: window={self.activity.window_ms:.0f}ms "
                f"keys={self.activity.key_events} "
                f"armed={'yes' if self.activity.active() else 'no'}"
            )
        for filt in self.filters:
            s = filt.stats
            extra = ""
            if isinstance(filt, WhenTypingGate):
                extra = f" bypass={filt.bypass_frames} active={filt.active_frames}"
            parts.append(
                f"{s.name}: in={s.in_frames} out={s.out_frames} "
                f"drop={s.dropped_frames}{extra}"
            )
        return "; ".join(parts) if parts else "(no filters)"


def build_pipeline(cfg: dict[str, Any] | None = None) -> Pipeline:
    cfg = cfg or {}
    filters_cfg = cfg.get("filters")
    if not filters_cfg:
        filters_cfg = default_filters()

    typing_enabled = False
    typing_window = DEFAULT_TYPING_WINDOW_MS
    for item in filters_cfg:
        if not isinstance(item, dict):
            continue
        name = str(item.get("plugin") or item.get("name") or "").lower()
        if name in ("typing_inhibit", "typing-inhibit", "typing"):
            typing_enabled = item.get("enabled", True) is not False
            typing_window = float(item.get("window_ms", typing_window))
            break

    activity = KeyboardActivity(window_ms=typing_window) if typing_enabled else None
    out: list[Filter] = []
    soft_bounds = cfg.get("abs_bounds") if isinstance(cfg.get("abs_bounds"), dict) else {}

    for item in filters_cfg:
        if not isinstance(item, dict):
            continue
        if item.get("enabled") is False:
            continue
        name = str(item.get("plugin") or item.get("name") or "").lower()
        if name in ("event_sim", "event-sim", "sim"):
            continue
        if name in ("typing_inhibit", "typing-inhibit", "typing"):
            continue
        if name in ("exec_delay", "exec-delay", "delay"):
            filt: Filter = ExecDelayFilter(
                ms=float(item.get("ms", DEFAULT_EXEC_DELAY_MS))
            )
            if activity is not None:
                filt = WhenTypingGate(filt, activity)
            out.append(filt)
        elif name in ("outlier_reject", "outlier-reject", "outlier"):
            filt = OutlierRejectFilter(
                max_delta=int(item.get("max_delta", DEFAULT_MAX_DELTA))
            )
            if activity is not None:
                filt = WhenTypingGate(filt, activity)
            out.append(filt)
        elif name in ("soft_accel", "soft-accel", "accel"):
            out.append(
                SoftAccelFilter(
                    gain=float(item.get("gain", DEFAULT_SOFT_ACCEL_GAIN)),
                    mode=normalize_soft_accel_mode(
                        item.get("mode", DEFAULT_SOFT_ACCEL_MODE)
                    ),
                    pivot=int(item.get("pivot", DEFAULT_SOFT_ACCEL_PIVOT)),
                    x_min=int(soft_bounds.get("x_min", item.get("x_min", 0))),
                    x_max=int(soft_bounds.get("x_max", item.get("x_max", 10000))),
                    y_min=int(soft_bounds.get("y_min", item.get("y_min", 0))),
                    y_max=int(soft_bounds.get("y_max", item.get("y_max", 10000))),
                )
            )
        elif name in ("smooth",):
            log.warning("smooth filter not implemented; skip")
        else:
            log.warning("unknown touchpad filter %r; skip", name)
    return Pipeline(out, activity=activity)


def pipeline_to_config(pipe: Pipeline, *, device: str = "auto") -> dict[str, Any]:
    """Legacy v1 helper — prefer ``upsert_device_profile`` for new saves."""
    return {
        "device": device,
        "filters": filters_from_pipeline(pipe),
    }


def filters_from_pipeline(pipe: Pipeline) -> list[dict[str, Any]]:
    filters: list[dict[str, Any]] = [{"plugin": "event_sim", "enabled": False}]
    if pipe.activity is not None:
        filters.append(
            {
                "plugin": "typing_inhibit",
                "window_ms": pipe.activity.window_ms,
                "enabled": True,
            }
        )
    else:
        filters.append(
            {
                "plugin": "typing_inhibit",
                "window_ms": DEFAULT_TYPING_WINDOW_MS,
                "enabled": False,
            }
        )
    delay_ms = DEFAULT_EXEC_DELAY_MS
    max_delta = DEFAULT_MAX_DELTA
    delay_on = False
    outlier_on = False
    soft_on = False
    soft_gain = DEFAULT_SOFT_ACCEL_GAIN
    soft_mode = DEFAULT_SOFT_ACCEL_MODE
    soft_pivot = DEFAULT_SOFT_ACCEL_PIVOT
    for filt in pipe.filters:
        inner = filt.inner if isinstance(filt, WhenTypingGate) else filt
        if isinstance(inner, ExecDelayFilter):
            delay_ms = inner.ms
            delay_on = True
        elif isinstance(inner, OutlierRejectFilter):
            max_delta = inner.max_delta
            outlier_on = True
        elif isinstance(inner, SoftAccelFilter):
            soft_gain = inner.gain
            soft_mode = inner.mode
            soft_pivot = inner.pivot
            soft_on = True
    filters.append({"plugin": "exec_delay", "ms": delay_ms, "enabled": delay_on})
    filters.append(
        {"plugin": "outlier_reject", "max_delta": max_delta, "enabled": outlier_on}
    )
    filters.append(
        {
            "plugin": "soft_accel",
            "gain": soft_gain,
            "mode": soft_mode,
            "pivot": soft_pivot,
            "enabled": soft_on,
        }
    )
    return filters


def filters_from_knobs(
    *,
    delay_enabled: bool,
    delay_ms: float,
    outlier_enabled: bool,
    max_delta: int,
    typing_enabled: bool = True,
    typing_window_ms: float = DEFAULT_TYPING_WINDOW_MS,
    soft_accel_enabled: bool = True,
    soft_accel_gain: float = DEFAULT_SOFT_ACCEL_GAIN,
    soft_accel_mode: str = DEFAULT_SOFT_ACCEL_MODE,
    soft_accel_pivot: int = DEFAULT_SOFT_ACCEL_PIVOT,
) -> list[dict[str, Any]]:
    return [
        {"plugin": "event_sim", "enabled": False},
        {
            "plugin": "typing_inhibit",
            "window_ms": float(typing_window_ms),
            "enabled": bool(typing_enabled),
        },
        {
            "plugin": "exec_delay",
            "ms": float(delay_ms),
            "enabled": bool(delay_enabled),
        },
        {
            "plugin": "outlier_reject",
            "max_delta": int(max_delta),
            "enabled": bool(outlier_enabled),
        },
        {
            "plugin": "soft_accel",
            "gain": float(soft_accel_gain),
            "mode": normalize_soft_accel_mode(soft_accel_mode),
            "pivot": int(soft_accel_pivot),
            "enabled": bool(soft_accel_enabled),
        },
    ]


def apply_pipeline_knobs(
    pipe: Pipeline,
    *,
    delay_ms: float | None = None,
    max_delta: int | None = None,
    typing_window_ms: float | None = None,
    soft_accel_gain: float | None = None,
    soft_accel_mode: str | None = None,
    soft_accel_pivot: int | None = None,
) -> None:
    if typing_window_ms is not None and pipe.activity is not None:
        pipe.activity.set_window_ms(typing_window_ms)
    for filt in pipe.filters:
        inner = filt.inner if isinstance(filt, WhenTypingGate) else filt
        if delay_ms is not None and isinstance(inner, ExecDelayFilter):
            inner.set_ms(delay_ms)
        if max_delta is not None and isinstance(inner, OutlierRejectFilter):
            inner.set_max_delta(max_delta)
        if isinstance(inner, SoftAccelFilter):
            if soft_accel_gain is not None:
                inner.set_gain(soft_accel_gain)
            if soft_accel_mode is not None:
                inner.set_mode(soft_accel_mode)
            if soft_accel_pivot is not None:
                inner.set_pivot(soft_accel_pivot)


@dataclass(frozen=True)
class TouchpadInfo:
    """One touchpad-like evdev node with a reboot-stable config key."""

    path: Path
    name: str
    phys: str = ""
    uniq: str = ""

    @property
    def key(self) -> str:
        """Stable id for per-device config (name + phys/uniq, not eventN)."""
        if self.uniq:
            return f"{self.name}|{self.uniq}"
        if self.phys:
            return f"{self.name}|{self.phys}"
        return self.name


def default_filters() -> list[dict[str, Any]]:
    return [
        {"plugin": "event_sim", "enabled": False},
        {
            "plugin": "typing_inhibit",
            "window_ms": DEFAULT_TYPING_WINDOW_MS,
            "enabled": True,
        },
        {"plugin": "exec_delay", "ms": DEFAULT_EXEC_DELAY_MS, "enabled": True},
        {
            "plugin": "outlier_reject",
            "max_delta": DEFAULT_MAX_DELTA,
            "enabled": True,
        },
        {
            "plugin": "soft_accel",
            "gain": DEFAULT_SOFT_ACCEL_GAIN,
            "mode": DEFAULT_SOFT_ACCEL_MODE,
            "pivot": DEFAULT_SOFT_ACCEL_PIVOT,
            "enabled": True,
        },
    ]


def empty_config_v2() -> dict[str, Any]:
    return {"version": 2, "default_device": "auto", "devices": {}}


def device_key_for_path(path: Path) -> str | None:
    for info in discover_touchpads():
        if info.path == path or info.path.resolve() == path.resolve():
            return info.key
    # Fallback: read sysfs directly
    event = path.name
    sys_name = Path("/sys/class/input") / event / "device" / "name"
    if not sys_name.is_file():
        return None
    name = sys_name.read_text(encoding="utf-8", errors="replace").strip()
    phys_p = Path("/sys/class/input") / event / "device" / "phys"
    uniq_p = Path("/sys/class/input") / event / "device" / "uniq"
    phys = phys_p.read_text(encoding="utf-8", errors="replace").strip() if phys_p.is_file() else ""
    uniq = uniq_p.read_text(encoding="utf-8", errors="replace").strip() if uniq_p.is_file() else ""
    return TouchpadInfo(path, name, phys, uniq).key


def normalize_config(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Return version-2 config; migrate legacy single-device files."""
    if not raw:
        return empty_config_v2()
    if int(raw.get("version") or 0) >= 2 and isinstance(raw.get("devices"), dict):
        out = empty_config_v2()
        out["default_device"] = raw.get("default_device", "auto")
        for key, entry in raw["devices"].items():
            if not isinstance(entry, dict):
                continue
            out["devices"][str(key)] = {
                "filters": entry.get("filters") or default_filters(),
                "enabled": bool(entry.get("enabled", True)),
            }
        return out

    # v1: { "device": "...", "filters": [...] }
    out = empty_config_v2()
    device = raw.get("device", "auto")
    filters = raw.get("filters")
    if not isinstance(filters, list):
        return out
    # Legacy profiles had always-on exec_delay (cursor jump every contact).
    # Inject typing_inhibit so palm filters only arm after keys.
    names = {
        str(item.get("plugin") or item.get("name") or "").lower()
        for item in filters
        if isinstance(item, dict)
    }
    if "typing_inhibit" not in names and "typing-inhibit" not in names and "typing" not in names:
        inserted: list[Any] = []
        for item in filters:
            inserted.append(item)
            name = (
                str(item.get("plugin") or item.get("name") or "").lower()
                if isinstance(item, dict)
                else ""
            )
            if name in ("event_sim", "event-sim", "sim") and not any(
                str(x.get("plugin") or "").lower().startswith("typing")
                for x in inserted
                if isinstance(x, dict)
            ):
                inserted.append(
                    {
                        "plugin": "typing_inhibit",
                        "window_ms": DEFAULT_TYPING_WINDOW_MS,
                        "enabled": True,
                    }
                )
        if not any(
            str(x.get("plugin") or "").lower().startswith("typing")
            for x in inserted
            if isinstance(x, dict)
        ):
            inserted.insert(
                0,
                {
                    "plugin": "typing_inhibit",
                    "window_ms": DEFAULT_TYPING_WINDOW_MS,
                    "enabled": True,
                },
            )
        filters = inserted
    key = "default"
    if device and device not in ("auto", ""):
        p = Path(str(device))
        if p.exists():
            key = device_key_for_path(p) or str(device)
        else:
            key = str(device)
        out["default_device"] = key
    else:
        out["default_device"] = "auto"
    out["devices"][key] = {"filters": filters, "enabled": True}
    return out


def load_config(path: Path | None = None) -> dict[str, Any]:
    path = path or DEFAULT_CONFIG
    if not path.is_file():
        return empty_config_v2()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return empty_config_v2()
    if not isinstance(raw, dict):
        return empty_config_v2()
    return normalize_config(raw)


def save_config(cfg: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = normalize_config(cfg)
    path.write_text(json.dumps(normalized, indent=2) + "\n", encoding="utf-8")


def _match_device_entry(
    cfg: dict[str, Any], info: TouchpadInfo | None, *, path: Path | None = None
) -> tuple[str | None, dict[str, Any] | None]:
    cfg = normalize_config(cfg)
    devices: dict[str, Any] = cfg.get("devices") or {}
    if info is not None:
        if info.key in devices:
            return info.key, devices[info.key]
        # name-only legacy / partial match
        for key, entry in devices.items():
            if key == info.name or key.startswith(info.name + "|"):
                return key, entry
    if path is not None:
        path_s = str(path)
        if path_s in devices:
            return path_s, devices[path_s]
        key = device_key_for_path(path)
        if key and key in devices:
            return key, devices[key]
    if "default" in devices:
        return "default", devices["default"]
    return None, None


def filters_for_device(
    cfg: dict[str, Any],
    info: TouchpadInfo | None = None,
    *,
    path: Path | None = None,
) -> list[dict[str, Any]]:
    """Per-device filters; fall back to defaults (not another device's knobs)."""
    _key, entry = _match_device_entry(cfg, info, path=path)
    if entry and isinstance(entry.get("filters"), list):
        return list(entry["filters"])
    return default_filters()


def device_profile_enabled(
    cfg: dict[str, Any],
    info: TouchpadInfo | None = None,
    *,
    path: Path | None = None,
) -> bool:
    _key, entry = _match_device_entry(cfg, info, path=path)
    if entry is None:
        return True
    return bool(entry.get("enabled", True))


def upsert_device_profile(
    cfg: dict[str, Any],
    key: str,
    *,
    filters: list[dict[str, Any]],
    enabled: bool = True,
    make_default: bool = False,
) -> dict[str, Any]:
    out = normalize_config(cfg)
    out["devices"][key] = {"filters": filters, "enabled": enabled}
    if make_default:
        out["default_device"] = key
    return out


def knobs_from_filters(filters: list[dict[str, Any]]) -> dict[str, Any]:
    """Extract GUI/CLI knob state from a filters list."""
    delay_ms = DEFAULT_EXEC_DELAY_MS
    max_delta = DEFAULT_MAX_DELTA
    delay_on = True
    outlier_on = True
    typing_on = True
    typing_window = DEFAULT_TYPING_WINDOW_MS
    soft_on = True
    soft_gain = DEFAULT_SOFT_ACCEL_GAIN
    soft_mode = DEFAULT_SOFT_ACCEL_MODE
    soft_pivot = DEFAULT_SOFT_ACCEL_PIVOT
    for item in filters:
        if not isinstance(item, dict):
            continue
        name = str(item.get("plugin") or item.get("name") or "").lower()
        if name in ("typing_inhibit", "typing-inhibit", "typing"):
            typing_window = float(item.get("window_ms", typing_window))
            typing_on = item.get("enabled", True) is not False
        elif name in ("exec_delay", "exec-delay", "delay"):
            delay_ms = float(item.get("ms", delay_ms))
            delay_on = item.get("enabled", True) is not False
        elif name in ("outlier_reject", "outlier-reject", "outlier"):
            max_delta = int(item.get("max_delta", max_delta))
            outlier_on = item.get("enabled", True) is not False
        elif name in ("soft_accel", "soft-accel", "accel"):
            soft_gain = float(item.get("gain", soft_gain))
            soft_mode = normalize_soft_accel_mode(item.get("mode", soft_mode))
            soft_pivot = int(item.get("pivot", soft_pivot))
            soft_on = item.get("enabled", True) is not False
    return {
        "delay_ms": delay_ms,
        "max_delta": max_delta,
        "delay_enabled": delay_on,
        "outlier_enabled": outlier_on,
        "typing_enabled": typing_on,
        "typing_window_ms": typing_window,
        "soft_accel_enabled": soft_on,
        "soft_accel_gain": soft_gain,
        "soft_accel_mode": soft_mode,
        "soft_accel_pivot": soft_pivot,
    }


def discover_keyboards(*, exclude: Sequence[Path] | None = None) -> list[Path]:
    """Evdev nodes that look like keyboards (for typing-inhibit).

    Includes USB/BT Primax Duo nodes (name contains ``keyboard`` / ``asus``) and
    the laptop AT set. Callers should rescan — BT attach is often late.
    """
    skip = {p.resolve() for p in (exclude or [])}
    found: list[Path] = []
    for event_dir in sorted(Path("/sys/class/input").glob("event*")):
        name_path = event_dir / "device" / "name"
        if not name_path.is_file():
            continue
        name = name_path.read_text(encoding="utf-8", errors="replace").strip()
        low = name.lower()
        if "touchpad" in low or "trackpad" in low or "mouse" in low:
            continue
        key_caps = event_dir / "device" / "capabilities" / "key"
        if not key_caps.is_file():
            continue
        # Heuristic: key bitmap non-empty and name not a consumer IR remote
        raw = key_caps.read_text().strip()
        if not raw or raw.replace("0", "").replace(" ", "") == "":
            continue
        if "keyboard" not in low and "atkbd" not in low and "asus" not in low:
            # Prefer explicit keyboard-ish names; skip pure power buttons etc.
            if "button" in low or "lid" in low or "video" in low:
                continue
            if "keyboard" not in low:
                continue
        # Prefer Primax / Duo HID keyboards over WMI "Asus … hotkeys" (no typing)
        if "hotkey" in low and "keyboard" not in low:
            continue
        path = Path("/dev/input") / event_dir.name
        if path.resolve() in skip:
            continue
        if path.exists():
            found.append(path)
    return found


def duo_keyboard_hid_health() -> dict[str, object]:
    """Detect UX8406 Primax dock/BT binding problems (for probe / operators)."""
    usb = False
    bt_hid: list[dict[str, str]] = []
    bt_key_events: list[str] = []
    for line in Path("/sys/bus/usb/devices").glob("*"):
        pass
    try:
        import subprocess

        r = subprocess.run(
            ["lsusb", "-d", "0b05:1b2c"],
            capture_output=True,
            text=True,
            check=False,
        )
        usb = bool(r.stdout.strip())
    except OSError:
        usb = False

    for d in sorted(Path("/sys/bus/hid/devices").glob("0005:0B05:1B2D.*")):
        drv = "NONE"
        if (d / "driver").exists():
            drv = (d / "driver").resolve().name
        rdesc = d / "report_descriptor"
        rlen = rdesc.stat().st_size if rdesc.is_file() else 0
        bt_hid.append({"id": d.name, "driver": drv, "rdesc_bytes": str(rlen)})

    for event_dir in sorted(Path("/sys/class/input").glob("event*")):
        name_path = event_dir / "device" / "name"
        if not name_path.is_file():
            continue
        name = name_path.read_text(encoding="utf-8", errors="replace").strip()
        low = name.lower()
        if "zenbook duo keyboard" not in low:
            continue
        if "touchpad" in low or "mouse" in low:
            continue
        vendor = event_dir / "device" / "id" / "vendor"
        product = event_dir / "device" / "id" / "product"
        bustype = event_dir / "device" / "id" / "bustype"
        if vendor.is_file() and product.is_file():
            v = vendor.read_text().strip().lower()
            p = product.read_text().strip().lower()
            if v in ("0b05", "b05") and p in ("1b2d", "1b2c"):
                bt_key_events.append(event_dir.name)
        elif bustype.is_file() and bustype.read_text().strip() == "0005":
            bt_key_events.append(event_dir.name)

    orphan_bt = any(h["driver"] == "NONE" for h in bt_hid)
    return {
        "usb_pogo_1b2c": usb,
        "bt_hid_ifaces": bt_hid,
        "bt_keyboard_event_nodes": bt_key_events,
        "bt_keyboard_unbound": orphan_bt,
        "bt_keys_missing": bool(bt_hid) and not bt_key_events,
        "hint": (
            "hid-asus BT rdesc fixup failed — rebuild/sideload oot hid-asus "
            "(skip BT Usage76) or reconnect after fix"
            if (orphan_bt or (bt_hid and not bt_key_events))
            else ""
        ),
    }


def abs_bounds_for_device(path: Path) -> dict[str, int]:
    """Read ABS_X/Y ranges for soft-accel clamping."""
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return {}
    try:
        info_x = _read_absinfo(fd, ABS_MT_POSITION_X) or _read_absinfo(fd, ABS_X)
        info_y = _read_absinfo(fd, ABS_MT_POSITION_Y) or _read_absinfo(fd, ABS_Y)
    finally:
        os.close(fd)
    out: dict[str, int] = {}
    if info_x:
        out["x_min"], out["x_max"] = int(info_x[1]), int(info_x[2])
    if info_y:
        out["y_min"], out["y_max"] = int(info_y[1]), int(info_y[2])
    return out


def bind_soft_accel_bounds(pipe: Pipeline, path: Path) -> None:
    bounds = abs_bounds_for_device(path)
    if not bounds:
        return
    for filt in pipe.filters:
        inner = filt.inner if isinstance(filt, WhenTypingGate) else filt
        if isinstance(inner, SoftAccelFilter):
            if "x_min" in bounds:
                inner.x_min = bounds["x_min"]
                inner.x_max = bounds["x_max"]
            if "y_min" in bounds:
                inner.y_min = bounds["y_min"]
                inner.y_max = bounds["y_max"]


def iter_touchpad_with_typing(
    touchpad: Path,
    *,
    activity: KeyboardActivity | None,
    grab: bool = False,
    stop_after_s: float | None = None,
    should_stop: Callable[[], bool] | None = None,
    keyboard_rescan_s: float = 2.0,
) -> Iterator[Ev]:
    """Yield touchpad events; update ``activity`` from keyboard key presses.

    Rescans keyboard nodes periodically so a late Bluetooth Duo keyboard is
    picked up (and dead USB nodes after undock are dropped).
    """
    fds: dict[int, tuple[Path, bool]] = {}  # fd -> (path, is_touchpad)
    grabbed = False
    t0 = time.monotonic()
    last_scan = 0.0
    open_kbd: set[Path] = set()

    def _open_keyboards() -> None:
        nonlocal last_scan
        last_scan = time.monotonic()
        want = set(discover_keyboards(exclude=[touchpad])) if activity is not None else set()
        # Drop disappeared
        for fd, (path, is_tp) in list(fds.items()):
            if is_tp:
                continue
            if path not in want or not path.exists():
                try:
                    os.close(fd)
                except OSError:
                    pass
                fds.pop(fd, None)
                open_kbd.discard(path)
        for kp in want:
            if kp in open_kbd:
                continue
            try:
                kfd = os.open(kp, os.O_RDONLY | os.O_NONBLOCK)
            except OSError:
                continue
            fds[kfd] = (kp, False)
            open_kbd.add(kp)

    try:
        tfd = os.open(touchpad, os.O_RDONLY | os.O_NONBLOCK)
        fds[tfd] = (touchpad, True)
        if grab:
            fcntl.ioctl(tfd, EVIOCGRAB, 1)
            grabbed = True
        _open_keyboards()
        bufs: dict[int, bytes] = {fd: b"" for fd in fds}
        while True:
            if should_stop and should_stop():
                break
            if stop_after_s is not None and (time.monotonic() - t0) >= stop_after_s:
                break
            if activity is not None and (time.monotonic() - last_scan) >= keyboard_rescan_s:
                before = set(fds)
                _open_keyboards()
                for fd in fds:
                    if fd not in before:
                        bufs[fd] = b""
                for fd in list(bufs):
                    if fd not in fds:
                        bufs.pop(fd, None)
            r, _, _ = select.select(list(fds), [], [], 0.25)
            if not r:
                continue
            for fd in r:
                path, is_tp = fds[fd]
                try:
                    chunk = os.read(fd, INPUT_EVENT_SIZE * 64)
                except OSError:
                    if not is_tp:
                        try:
                            os.close(fd)
                        except OSError:
                            pass
                        fds.pop(fd, None)
                        open_kbd.discard(path)
                        bufs.pop(fd, None)
                    continue
                except BlockingIOError:
                    continue
                if not chunk:
                    # EOF / device gone (common on BT undock)
                    if not is_tp:
                        try:
                            os.close(fd)
                        except OSError:
                            pass
                        fds.pop(fd, None)
                        open_kbd.discard(path)
                        bufs.pop(fd, None)
                    continue
                bufs.setdefault(fd, b"")
                bufs[fd] += chunk
                while len(bufs[fd]) >= INPUT_EVENT_SIZE:
                    raw, bufs[fd] = (
                        bufs[fd][:INPUT_EVENT_SIZE],
                        bufs[fd][INPUT_EVENT_SIZE:],
                    )
                    ev = Ev.unpack(raw)
                    if not is_tp:
                        if activity is not None:
                            activity.note_ev(ev)
                        continue
                    yield ev
    finally:
        for fd, (_path, is_tp) in list(fds.items()):
            if is_tp and grabbed:
                try:
                    fcntl.ioctl(fd, EVIOCGRAB, 0)
                except OSError:
                    pass
            try:
                os.close(fd)
            except OSError:
                pass


def discover_touchpads() -> list[TouchpadInfo]:
    """Return touchpad-like nodes with stable config keys."""
    found: list[TouchpadInfo] = []
    for event_dir in sorted(Path("/sys/class/input").glob("event*")):
        name_path = event_dir / "device" / "name"
        if not name_path.is_file():
            continue
        name = name_path.read_text(encoding="utf-8", errors="replace").strip()
        low = name.lower()
        if "stylus" in low or "unknown" in low:
            continue
        if "touchpad" not in low and "trackpad" not in low:
            continue
        phys_p = event_dir / "device" / "phys"
        uniq_p = event_dir / "device" / "uniq"
        phys = (
            phys_p.read_text(encoding="utf-8", errors="replace").strip()
            if phys_p.is_file()
            else ""
        )
        uniq = (
            uniq_p.read_text(encoding="utf-8", errors="replace").strip()
            if uniq_p.is_file()
            else ""
        )
        found.append(
            TouchpadInfo(
                path=Path("/dev/input") / event_dir.name,
                name=name,
                phys=phys,
                uniq=uniq,
            )
        )
    return found


def pick_default_device(
    devices: Sequence[TouchpadInfo | tuple[Path, str]] | None = None,
) -> Path | None:
    infos: list[TouchpadInfo]
    if devices is None:
        infos = discover_touchpads()
    else:
        infos = []
        for d in devices:
            if isinstance(d, TouchpadInfo):
                infos.append(d)
            else:
                infos.append(TouchpadInfo(path=d[0], name=d[1]))
    if not infos:
        return None
    for info in infos:
        if "keyboard touchpad" in info.name.lower():
            return info.path
    return infos[0].path


def resolve_touchpad(
    selector: str | None,
    cfg: dict[str, Any] | None = None,
) -> TouchpadInfo:
    """Resolve CLI/GUI device selector to a ``TouchpadInfo``.

    Accepts ``auto``, ``/dev/input/eventN``, stable key, or substring of name.
    """
    pads = discover_touchpads()
    if not pads:
        raise FileNotFoundError("no touchpad input node found")
    cfg = normalize_config(cfg)

    if not selector or selector in ("auto", ""):
        pref = cfg.get("default_device") or "auto"
        if pref and pref not in ("auto", ""):
            try:
                return resolve_touchpad(str(pref), {**cfg, "default_device": "auto"})
            except FileNotFoundError:
                pass
        path = pick_default_device(pads)
        assert path is not None
        for info in pads:
            if info.path == path:
                return info
        return pads[0]

    # Absolute / relative event node
    as_path = Path(selector)
    if as_path.exists() or selector.startswith("/dev/input/"):
        for info in pads:
            if info.path == as_path or str(info.path) == selector:
                return info
        raise FileNotFoundError(f"touchpad node not found: {selector}")

    # Exact stable key
    for info in pads:
        if info.key == selector or info.name == selector:
            return info

    # Substring match on name/key
    low = selector.lower()
    hits = [i for i in pads if low in i.name.lower() or low in i.key.lower()]
    if len(hits) == 1:
        return hits[0]
    if len(hits) > 1:
        raise FileNotFoundError(
            f"ambiguous device {selector!r}; matches: "
            + ", ".join(i.key for i in hits)
        )
    raise FileNotFoundError(f"no touchpad matching {selector!r}")


def iter_device_events(
    path: Path,
    *,
    grab: bool = False,
    stop_after_s: float | None = None,
    should_stop: Callable[[], bool] | None = None,
) -> Iterator[Ev]:
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
    grabbed = False
    t0 = time.monotonic()
    try:
        if grab:
            fcntl.ioctl(fd, EVIOCGRAB, 1)
            grabbed = True
        buf = b""
        while True:
            if should_stop and should_stop():
                break
            if stop_after_s is not None and (time.monotonic() - t0) >= stop_after_s:
                break
            r, _, _ = select.select([fd], [], [], 0.25)
            if not r:
                continue
            try:
                chunk = os.read(fd, INPUT_EVENT_SIZE * 64)
            except BlockingIOError:
                continue
            if not chunk:
                break
            buf += chunk
            while len(buf) >= INPUT_EVENT_SIZE:
                raw, buf = buf[:INPUT_EVENT_SIZE], buf[INPUT_EVENT_SIZE:]
                yield Ev.unpack(raw)
    finally:
        if grabbed:
            try:
                fcntl.ioctl(fd, EVIOCGRAB, 0)
            except OSError:
                pass
        os.close(fd)


def _bits_via_ioctl(fd: int, ev: int, max_code: int = 512) -> set[int]:
    length = (max_code + 7) // 8
    buf = array.array("B", [0]) * length
    try:
        fcntl.ioctl(fd, eviocgbit(ev, length), buf, True)
    except OSError:
        return set()
    out: set[int] = set()
    for i, byte in enumerate(buf):
        for b in range(8):
            if byte & (1 << b):
                out.add(i * 8 + b)
    return out


def _props_via_ioctl(fd: int, max_code: int = 32) -> set[int]:
    length = (max_code + 7) // 8
    buf = array.array("B", [0]) * length
    try:
        fcntl.ioctl(fd, eviocgprop(length), buf, True)
    except OSError:
        return set()
    out: set[int] = set()
    for i, byte in enumerate(buf):
        for b in range(8):
            if byte & (1 << b):
                out.add(i * 8 + b)
    return out


def _read_absinfo(fd: int, code: int) -> tuple[int, int, int, int, int, int] | None:
    buf = array.array("i", [0] * 6)
    try:
        fcntl.ioctl(fd, eviocgabs(code), buf, True)
    except OSError:
        return None
    return tuple(buf)  # type: ignore[return-value]


class UInputProxy:
    """Clone a touchpad into ``/dev/uinput`` and write filtered events."""

    def __init__(self, source: Path, name: str | None = None) -> None:
        self.source = source
        # Default name keeps USB/name quirks matching the stock pad; suffix
        # distinguishes the virtual node in logs without breaking libinput class.
        self.name_override = name
        self._fd = -1

    def open(self) -> None:
        src = os.open(self.source, os.O_RDONLY)
        try:
            ev_bits = _bits_via_ioctl(src, 0, 32)
            key_bits = _bits_via_ioctl(src, EV_KEY, 768)
            rel_bits = _bits_via_ioctl(src, EV_REL, 64)
            abs_bits = _bits_via_ioctl(src, EV_ABS, 64)
            src_props = _props_via_ioctl(src)
            try:
                id_buf = fcntl.ioctl(src, 0x80084502, bytes(8))  # EVIOCGID
                bus, vendor, product, version = struct.unpack("HHHH", id_buf)
            except OSError:
                bus, vendor, product, version = 0x03, 0x0B05, 0x5444, 0x0001
            sys_name = (
                Path("/sys/class/input") / self.source.name / "device" / "name"
            )
            src_name = (
                sys_name.read_text(encoding="utf-8", errors="replace").strip()
                if sys_name.is_file()
                else "zenbook-touchpad"
            )
            if self.name_override:
                vname = self.name_override[: UINPUT_MAX_NAME_SIZE - 1]
            else:
                # Keep quirk match (VID/PID + Touchpad name); mark virtual.
                base = src_name[: UINPUT_MAX_NAME_SIZE - 10]
                vname = f"{base} (filter)"[: UINPUT_MAX_NAME_SIZE - 1]

            ufd = os.open("/dev/uinput", os.O_WRONLY | os.O_NONBLOCK)
            for bit in sorted(ev_bits | {EV_SYN}):
                fcntl.ioctl(ufd, UI_SET_EVBIT, bit)
            for bit in sorted(key_bits):
                fcntl.ioctl(ufd, UI_SET_KEYBIT, bit)
            for bit in sorted(rel_bits):
                fcntl.ioctl(ufd, UI_SET_RELBIT, bit)
            for bit in sorted(abs_bits):
                fcntl.ioctl(ufd, UI_SET_ABSBIT, bit)
                info = _read_absinfo(src, bit)
                if info is None:
                    continue
                # struct uinput_abs_setup: __u16 code; pad to 4; input_absinfo
                abs_setup = struct.pack(
                    "Hxxiiiiii",
                    bit,
                    info[0],
                    info[1],
                    info[2],
                    info[3],
                    info[4],
                    info[5],
                )
                fcntl.ioctl(ufd, UI_ABS_SETUP, abs_setup)
            # Copy props verbatim (including INPUT_PROP_DIRECT). Forcing POINTER
            # and stripping DIRECT makes libinput classify the node as
            # "pointer touch" (identity calibration) — finger motion scrolls
            # like a touchscreen. Stock Primax/ELAN pads keep DIRECT and are
            # quirked to "pointer gesture"; cloning VID/PID + props matches that.
            for bit in sorted(src_props):
                fcntl.ioctl(ufd, UI_SET_PROPBIT, bit)
            setup = struct.pack(
                "HHHH80sI",
                bus,
                vendor,
                product,
                version,
                vname.encode("utf-8"),
                0,
            )
            fcntl.ioctl(ufd, UI_DEV_SETUP, setup)
            fcntl.ioctl(ufd, UI_DEV_CREATE)
            time.sleep(0.05)
            self._fd = ufd
        finally:
            os.close(src)

    def write_events(self, events: Sequence[Ev]) -> None:
        if self._fd < 0:
            raise RuntimeError("uinput not open")
        blob = b"".join(ev.pack() for ev in events)
        if blob:
            os.write(self._fd, blob)

    def close(self) -> None:
        if self._fd >= 0:
            try:
                fcntl.ioctl(self._fd, UI_DEV_DESTROY)
            except OSError:
                pass
            os.close(self._fd)
            self._fd = -1

    def __enter__(self) -> UInputProxy:
        self.open()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def make_sim_brush(
    *,
    duration_ms: float,
    dx: int = 5,
    dy: int = 0,
    start_x: int = 1000,
    start_y: int = 1000,
    step_ms: float = 5.0,
) -> list[Ev]:
    """Synthetic MT contact used by ``platform-touchpad selftest`` / ``sim``."""
    events: list[Ev] = []
    t0 = time.time()
    steps = max(1, int(duration_ms / step_ms))

    def stamp(i: int) -> tuple[int, int]:
        t = t0 + (i * step_ms) / 1000.0
        sec = int(t)
        usec = int((t - sec) * 1_000_000)
        return sec, usec

    sec, usec = stamp(0)
    events.extend(
        [
            Ev(sec, usec, EV_ABS, ABS_MT_SLOT, 0),
            Ev(sec, usec, EV_ABS, ABS_MT_TRACKING_ID, 1),
            Ev(sec, usec, EV_ABS, ABS_MT_POSITION_X, start_x),
            Ev(sec, usec, EV_ABS, ABS_MT_POSITION_Y, start_y),
            Ev(sec, usec, EV_KEY, BTN_TOUCH, 1),
            Ev(sec, usec, EV_KEY, BTN_TOOL_FINGER, 1),
            Ev.syn(sec, usec),
        ]
    )
    x, y = start_x, start_y
    for i in range(1, steps + 1):
        x += dx
        y += dy
        sec, usec = stamp(i)
        events.extend(
            [
                Ev(sec, usec, EV_ABS, ABS_MT_POSITION_X, x),
                Ev(sec, usec, EV_ABS, ABS_MT_POSITION_Y, y),
                Ev.syn(sec, usec),
            ]
        )
    sec, usec = stamp(steps + 1)
    events.extend(
        [
            Ev(sec, usec, EV_ABS, ABS_MT_TRACKING_ID, -1),
            Ev(sec, usec, EV_KEY, BTN_TOUCH, 0),
            Ev(sec, usec, EV_KEY, BTN_TOOL_FINGER, 0),
            Ev.syn(sec, usec),
        ]
    )
    return events


def run_selftest() -> dict[str, Any]:
    """Prove delay/outlier/typing-inhibit/soft-accel behaviours."""
    # Palm filters without typing_inhibit still work when always armed.
    short_pipe = build_pipeline(
        {
            "filters": [
                {"plugin": "typing_inhibit", "enabled": False},
                {"plugin": "exec_delay", "ms": 40},
                {"plugin": "outlier_reject", "max_delta": DEFAULT_MAX_DELTA},
                {"plugin": "soft_accel", "enabled": False},
            ]
        }
    )
    short = make_sim_brush(duration_ms=20, dx=3)
    short_out = short_pipe.process_events(short)

    long_pipe = build_pipeline(
        {
            "filters": [
                {"plugin": "typing_inhibit", "enabled": False},
                {"plugin": "exec_delay", "ms": 40},
                {"plugin": "outlier_reject", "max_delta": DEFAULT_MAX_DELTA},
                {"plugin": "soft_accel", "enabled": False},
            ]
        }
    )
    long = make_sim_brush(duration_ms=80, dx=3)
    long_out = long_pipe.process_events(long)

    spike_pipe = build_pipeline(
        {
            "filters": [
                {"plugin": "typing_inhibit", "enabled": False},
                {"plugin": "outlier_reject", "max_delta": 50},
                {"plugin": "soft_accel", "enabled": False},
            ]
        }
    )
    spike = make_sim_brush(duration_ms=30, dx=200, step_ms=10)
    spike_out = spike_pipe.process_events(spike)

    lock_pipe = build_pipeline(
        {
            "filters": [
                {"plugin": "typing_inhibit", "enabled": False},
                {"plugin": "outlier_reject", "max_delta": 50},
                {"plugin": "soft_accel", "enabled": False},
            ]
        }
    )
    a = make_sim_brush(duration_ms=30, start_x=100, start_y=100, dx=2)
    b = make_sim_brush(duration_ms=30, start_x=3000, start_y=2000, dx=2)
    lock_out = lock_pipe.process_events(a + b)

    # Typing-inhibit: short brush passes when idle (not typing).
    idle_pipe = build_pipeline(
        {
            "filters": [
                {"plugin": "typing_inhibit", "window_ms": 500, "enabled": True},
                {"plugin": "exec_delay", "ms": 40, "enabled": True},
                {"plugin": "soft_accel", "enabled": False},
            ]
        }
    )
    idle_out = idle_pipe.process_events(make_sim_brush(duration_ms=20, dx=3))

    # Same short brush drops when a key was just pressed.
    armed_pipe = build_pipeline(
        {
            "filters": [
                {"plugin": "typing_inhibit", "window_ms": 500, "enabled": True},
                {"plugin": "exec_delay", "ms": 40, "enabled": True},
                {"plugin": "soft_accel", "enabled": False},
            ]
        }
    )
    assert armed_pipe.activity is not None
    armed_pipe.activity.note_key()
    armed_out = armed_pipe.process_events(make_sim_brush(duration_ms=20, dx=3))

    # Soft accel amplifies deltas.
    accel_pipe = build_pipeline(
        {
            "filters": [
                {"plugin": "typing_inhibit", "enabled": False},
                {"plugin": "soft_accel", "gain": 2.0, "enabled": True},
            ]
        }
    )
    accel_in = make_sim_brush(duration_ms=20, dx=10, step_ms=5, start_x=100, start_y=100)
    accel_out = accel_pipe.process_events(accel_in)
    # Last motion frame before lift should have larger X than raw end.
    raw_end_x = 100 + 10 * max(1, int(20 / 5))
    out_xs = [
        e.value
        for e in accel_out
        if e.type == EV_ABS and e.code == ABS_MT_POSITION_X
    ]
    accel_ok = bool(out_xs) and max(out_xs) > raw_end_x

    # Armed long brush: each live pump chunk must be ≤1 SYN (no path replay).
    burst_pipe = build_pipeline(
        {
            "filters": [
                {"plugin": "typing_inhibit", "window_ms": 500, "enabled": True},
                {"plugin": "exec_delay", "ms": 40, "enabled": True},
                {"plugin": "soft_accel", "gain": 1.6, "enabled": True},
            ]
        }
    )
    assert burst_pipe.activity is not None
    burst_pipe.activity.note_key()
    long_armed = make_sim_brush(duration_ms=100, dx=4, step_ms=5)
    burst_ok = True
    frame: list[Ev] = []
    for ev in long_armed:
        frame.append(ev)
        if ev.type == EV_SYN and ev.code == SYN_REPORT:
            chunk = burst_pipe.process_frame(frame)
            frame = []
            if count_syn_reports(chunk) > 1:
                burst_ok = False
                break

    return {
        "short_brush_in": len(short),
        "short_brush_out": len(short_out),
        "short_dropped": len(short_out) == 0,
        "long_brush_out": len(long_out),
        "long_passed": len(long_out) > 0,
        "spike_out": len(spike_out),
        "spike_reduced": len(spike_out) < len(spike),
        "relocated_contact_out": len(lock_out),
        "relocated_ok": len(lock_out) > len(a) // 2,
        "idle_short_out": len(idle_out),
        "idle_passthrough": len(idle_out) > 0,
        "armed_short_out": len(armed_out),
        "armed_drops_short": len(armed_out) == 0,
        "soft_accel_ok": accel_ok,
        "no_multi_syn_burst": burst_ok,
        "ok": (
            len(short_out) == 0
            and len(long_out) > 0
            and len(spike_out) < len(spike)
            and len(lock_out) > len(a) // 2
            and len(idle_out) > 0
            and len(armed_out) == 0
            and accel_ok
            and burst_ok
        ),
    }
