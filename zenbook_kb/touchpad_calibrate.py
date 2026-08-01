"""Analyze touchpad capture JSONL and suggest filter knobs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class CaptureStats:
    frames: int = 0
    drops: int = 0
    outlier: int = 0
    delay: int = 0
    typing_armed: int = 0
    by_reason: dict[str, int] | None = None
    meta: dict[str, Any] | None = None

    @property
    def drop_pct(self) -> float:
        return 100.0 * self.drops / self.frames if self.frames else 0.0

    @property
    def typing_armed_pct(self) -> float:
        return 100.0 * self.typing_armed / self.frames if self.frames else 0.0


@dataclass
class KnobSuggestion:
    max_delta: int
    delay_ms: int
    typing_window_ms: int
    notes: list[str]


def analyze_capture_jsonl(path: Path | str) -> CaptureStats:
    stats = CaptureStats(by_reason={})
    p = Path(path)
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if rec.get("kind") == "meta":
            stats.meta = rec
            continue
        stats.frames += 1
        if rec.get("typing_armed"):
            stats.typing_armed += 1
        if not rec.get("passed"):
            stats.drops += 1
            reason = str(rec.get("dropped_by") or "unknown")
            assert stats.by_reason is not None
            stats.by_reason[reason] = stats.by_reason.get(reason, 0) + 1
            if "outlier" in reason:
                stats.outlier += 1
            if "exec_delay" in reason or reason.endswith("delay"):
                stats.delay += 1
    return stats


def suggest_knobs(
    stats: CaptureStats,
    *,
    max_delta: int,
    delay_ms: int,
    typing_window_ms: int,
) -> KnobSuggestion:
    sug_delta = int(max_delta)
    sug_delay = int(delay_ms)
    sug_win = int(typing_window_ms)
    notes: list[str] = []
    frames = stats.frames
    if frames <= 0:
        return KnobSuggestion(sug_delta, sug_delay, sug_win, ["No frames captured."])

    if stats.outlier >= max(5, frames * 0.05):
        sug_delta = min(5000, max(sug_delta + 400, int(sug_delta * 1.4)))
        notes.append(f"Many outlier drops ({stats.outlier}) → raise max_delta to {sug_delta}")
    if stats.delay >= max(5, frames * 0.08):
        sug_delay = max(5, sug_delay - 10)
        notes.append(f"Many exec_delay drops ({stats.delay}) → lower delay to {sug_delay} ms")
    if stats.typing_armed > frames * 0.7 and stats.drop_pct > 40:
        sug_win = max(100, sug_win - 100)
        notes.append(
            f"Armed most of the time with high drop rate → shorten typing window to {sug_win} ms"
        )
    if not notes:
        notes.append("Drop rate looks moderate — keep current knobs or retune manually.")
    return KnobSuggestion(sug_delta, sug_delay, sug_win, notes)


def format_stats_line(stats: CaptureStats) -> str:
    by = stats.by_reason or {}
    return (
        f"frames={stats.frames} dropped={stats.drops} ({stats.drop_pct:.1f}%) "
        f"typing_armed={stats.typing_armed} by={by or '{}'}"
    )


def detect_transport(*, name: str = "", phys: str = "", uniq: str = "") -> str:
    blob = f"{name}|{phys}|{uniq}".lower()
    if "bluetooth" in blob or "bluez" in blob:
        return "bluetooth"
    if "usb-" in blob or "/usb" in blob or phys.startswith("usb-"):
        return "usb"
    if "i2c-" in blob:
        return "i2c"
    return "unknown"
