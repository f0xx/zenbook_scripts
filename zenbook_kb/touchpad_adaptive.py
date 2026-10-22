"""Adaptive touchpad filter — online amplitude learning + axis matrix.

Not a scalar gain: maintains per-axis baseline amplitudes (robust EWMA), ignores
sporadic spikes for learning, and applies a 2×2 matrix to motion residuals.
Optional predictive term subtracts EWMA velocity before the matrix step.

State persists under ``~/.config/zenbook-scripts/adaptive-touchpad/<device-key>.json``.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Sequence

from zenbook_kb.touchpad import (
    ABS_MT_POSITION_X,
    ABS_MT_POSITION_Y,
    ABS_MT_TRACKING_ID,
    ABS_X,
    ABS_Y,
    BTN_TOOL_FINGER,
    BTN_TOUCH,
    EV_ABS,
    EV_KEY,
    Ev,
    Filter,
    _MT_TOOL_CODES,
    _tracking_id_delta,
    frame_is_multitouch,
)
from zenbook_kb.users import resolve_user_home

STATE_VERSION = 1
DEFAULT_LEARN_RATE = 0.08
DEFAULT_SPIKE_SIGMA = 3.5
DEFAULT_PREDICT_WEIGHT = 0.35
DEFAULT_MIN_BASELINE = 4.0
DEFAULT_PERSIST_EVERY = 120


def adaptive_state_dir() -> Path:
    return resolve_user_home() / ".config" / "zenbook-scripts" / "adaptive-touchpad"


def _safe_key(device_key: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "_", device_key.strip())
    return slug[:120] or "unknown"


@dataclass
class AdaptiveState:
    """Learned baselines + 2×2 motion matrix."""

    version: int = STATE_VERSION
    baseline_x: float = DEFAULT_MIN_BASELINE
    baseline_y: float = DEFAULT_MIN_BASELINE
    vel_x: float = 0.0
    vel_y: float = 0.0
    matrix: list[list[float]] = field(
        default_factory=lambda: [[1.0, 0.0], [0.0, 1.0]]
    )
    samples: int = 0

    def to_json(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_json(cls, raw: dict[str, Any]) -> AdaptiveState:
        m = raw.get("matrix")
        if not isinstance(m, list) or len(m) != 2:
            m = [[1.0, 0.0], [0.0, 1.0]]
        return cls(
            version=int(raw.get("version", STATE_VERSION)),
            baseline_x=float(raw.get("baseline_x", DEFAULT_MIN_BASELINE)),
            baseline_y=float(raw.get("baseline_y", DEFAULT_MIN_BASELINE)),
            vel_x=float(raw.get("vel_x", 0.0)),
            vel_y=float(raw.get("vel_y", 0.0)),
            matrix=[
                [float(m[0][0]), float(m[0][1])],
                [float(m[1][0]), float(m[1][1])],
            ],
            samples=int(raw.get("samples", 0)),
        )


def load_adaptive_state(device_key: str) -> AdaptiveState:
    path = adaptive_state_dir() / f"{_safe_key(device_key)}.json"
    if not path.is_file():
        return AdaptiveState()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            return AdaptiveState.from_json(raw)
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        pass
    return AdaptiveState()


def save_adaptive_state(device_key: str, state: AdaptiveState) -> None:
    path = adaptive_state_dir() / f"{_safe_key(device_key)}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state.to_json(), indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


class AdaptiveMatrixFilter(Filter):
    """Learn axis amplitudes; drop / attenuate motion that exceeds learned baselines."""

    name = "adaptive_matrix"

    def __init__(
        self,
        *,
        device_key: str = "auto",
        learn_rate: float = DEFAULT_LEARN_RATE,
        spike_sigma: float = DEFAULT_SPIKE_SIGMA,
        predict_weight: float = DEFAULT_PREDICT_WEIGHT,
        min_baseline: float = DEFAULT_MIN_BASELINE,
        persist_every: int = DEFAULT_PERSIST_EVERY,
        state: AdaptiveState | None = None,
    ) -> None:
        super().__init__()
        self.device_key = device_key
        self.learn_rate = max(0.001, min(1.0, float(learn_rate)))
        self.spike_sigma = max(1.0, float(spike_sigma))
        self.predict_weight = max(0.0, min(1.0, float(predict_weight)))
        self.min_baseline = max(1.0, float(min_baseline))
        self.persist_every = max(1, int(persist_every))
        self.state = state or load_adaptive_state(device_key)
        self._last: tuple[int, int] | None = None
        self._fingers = 0
        self._mt_sticky = False
        self._since_persist = 0
        self.spikes_dropped = 0
        self.learn_updates = 0

    def reset(self) -> None:
        self._last = None
        self._fingers = 0
        self._mt_sticky = False

    @staticmethod
    def _xy(frame: Sequence[Ev]) -> tuple[int, int] | None:
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
        has_tid = any(e.type == EV_ABS and e.code == ABS_MT_TRACKING_ID for e in frame)
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

    def _ewma(self, prev: float, sample: float) -> float:
        a = self.learn_rate
        return (1.0 - a) * prev + a * sample

    def _is_spike(self, dx: float, dy: float) -> bool:
        bx = max(self.min_baseline, self.state.baseline_x)
        by = max(self.min_baseline, self.state.baseline_y)
        return abs(dx) > self.spike_sigma * bx or abs(dy) > self.spike_sigma * by

    def _should_attenuate_spike(self, dx: float, dy: float) -> bool:
        """Clamp only small isolated glitches — never stall fast or ongoing motion."""
        if not self._is_spike(dx, dy):
            return False
        speed = abs(dx) + abs(dy)
        if speed > max(50.0, self.spike_sigma * self.min_baseline * 2.5):
            return False
        vel_speed = abs(self.state.vel_x) + abs(self.state.vel_y)
        if vel_speed > 6.0 and speed >= vel_speed * 0.3:
            return False
        return True

    def _clamp_delta(self, dx: float, dy: float) -> tuple[float, float]:
        bx = max(self.min_baseline, self.state.baseline_x)
        by = max(self.min_baseline, self.state.baseline_y)
        cap_x = self.spike_sigma * bx * 0.85
        cap_y = self.spike_sigma * by * 0.85
        return max(-cap_x, min(cap_x, dx)), max(-cap_y, min(cap_y, dy))

    def _update_matrix(self) -> None:
        """Diagonal scales shrink when baseline noise on an axis is high."""
        bx = max(self.min_baseline, self.state.baseline_x)
        by = max(self.min_baseline, self.state.baseline_y)
        scale_x = max(0.85, 1.0 / (1.0 + bx / 40.0))
        scale_y = max(0.85, 1.0 / (1.0 + by / 40.0))
        self.state.matrix[0][0] = scale_x
        self.state.matrix[1][1] = scale_y
        # Cross-terms reserved for future correlation learning.
        self.state.matrix[0][1] = 0.0
        self.state.matrix[1][0] = 0.0

    def _apply_matrix(self, dx: float, dy: float) -> tuple[float, float]:
        m = self.state.matrix
        ox = m[0][0] * dx + m[0][1] * dy
        oy = m[1][0] * dx + m[1][1] * dy
        return ox, oy

    def _rewrite_frame(
        self, frame: list[Ev], x: int, y: int, *, use_mt: bool
    ) -> list[Ev]:
        out: list[Ev] = []
        x_code = ABS_MT_POSITION_X if use_mt else ABS_X
        y_code = ABS_MT_POSITION_Y if use_mt else ABS_Y
        for ev in frame:
            if ev.type == EV_ABS and ev.code == x_code:
                out.append(
                    Ev(ev.sec, ev.usec, ev.type, ev.code, int(round(x)))
                )
            elif ev.type == EV_ABS and ev.code == y_code:
                out.append(
                    Ev(ev.sec, ev.usec, ev.type, ev.code, int(round(y)))
                )
            else:
                out.append(ev)
        return out

    def _maybe_persist(self) -> None:
        self._since_persist += 1
        if self._since_persist >= self.persist_every:
            save_adaptive_state(self.device_key, self.state)
            self._since_persist = 0

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
            save_adaptive_state(self.device_key, self.state)
            self._since_persist = 0
            self.stats.note(1, 1)
            return frame
        if edge == "new":
            self._last = None

        xy = self._xy(frame)
        if xy is None:
            self.stats.note(1, 1)
            return frame

        x, y = xy
        use_mt = any(e.type == EV_ABS and e.code == ABS_MT_POSITION_X for e in frame)

        if self._last is None:
            self._last = (x, y)
            self.stats.note(1, 1)
            return frame

        lx, ly = self._last
        dx = float(x - lx)
        dy = float(y - ly)

        # Learn-only: never drop or rewrite — attenuation caused sticky cursor on UX8406.
        if not self._is_spike(dx, dy):
            self.state.baseline_x = self._ewma(self.state.baseline_x, abs(dx))
            self.state.baseline_y = self._ewma(self.state.baseline_y, abs(dy))
            self.learn_updates += 1
        self.state.vel_x = self._ewma(self.state.vel_x, dx)
        self.state.vel_y = self._ewma(self.state.vel_y, dy)
        self.state.samples += 1
        self._update_matrix()

        self._last = (x, y)
        self._maybe_persist()
        self.stats.note(1, 1)
        return frame
