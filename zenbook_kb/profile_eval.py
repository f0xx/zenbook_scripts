"""Evaluate profile schedules and triggers (cron: platform-profiles evaluate).

No long-lived daemon — intended for once-per-minute cron as the session user.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from zenbook_kb.fan_control import read_lid_open, read_on_ac, sample_system
from zenbook_kb.user_profiles import BUILTIN_MODES, load, mode_summary, normalize

log = logging.getLogger("zenbook.profile_eval")

EVAL_STATE = Path.home() / ".cache" / "zenbook-scripts" / "profiles-eval-state.json"
# Higher index = higher priority when multiple modes match.
MODE_PRIORITY = ("auto", "quiet", "balanced", "performance", "night")


def _read_state() -> dict[str, Any]:
    if not EVAL_STATE.is_file():
        return {}
    try:
        raw = json.loads(EVAL_STATE.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _write_state(state: dict[str, Any]) -> None:
    EVAL_STATE.parent.mkdir(parents=True, exist_ok=True)
    EVAL_STATE.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def _parse_hhmm(text: str) -> tuple[int, int] | None:
    try:
        parts = str(text).strip().split(":")
        if len(parts) != 2:
            return None
        h, m = int(parts[0]), int(parts[1])
        if 0 <= h <= 23 and 0 <= m <= 59:
            return h, m
    except ValueError:
        pass
    return None


def _minutes_now() -> int:
    now = datetime.now()
    return now.hour * 60 + now.minute


def _in_schedule_window(start: str, stop: str) -> bool:
    s = _parse_hhmm(start)
    t = _parse_hhmm(stop)
    if not s or not t:
        return False
    sm = s[0] * 60 + s[1]
    tm = t[0] * 60 + t[1]
    now = _minutes_now()
    if sm <= tm:
        return sm <= now < tm
    # overnight e.g. 23:00–06:00
    return now >= sm or now < tm


def _system_awake() -> bool:
    for path in (Path("/sys/power/state"),):
        try:
            text = path.read_text(encoding="utf-8", errors="replace").strip()
            if text in ("mem", "disk"):
                return False
        except OSError:
            pass
    return True


def _schedule_active(mode: dict[str, Any]) -> bool:
    sched = mode.get("schedule") or {}
    if not sched.get("enabled"):
        return False
    return _in_schedule_window(str(sched.get("start", "00:00")), str(sched.get("stop", "00:00")))


def _low_cpu_active(mode: dict[str, Any], sample, state: dict[str, Any], mode_name: str) -> bool:
    trig = (mode.get("triggers") or {}).get("low_cpu") or {}
    if not trig.get("enabled"):
        return False
    if trig.get("require_battery") and sample.on_ac:
        state.pop(f"low_cpu_since_{mode_name}", None)
        return False
    threshold = float(trig.get("load_pct_max", 20))
    duration_s = float(trig.get("duration_min", 3)) * 60.0
    key = f"low_cpu_since_{mode_name}"
    if sample.load_pct < threshold:
        since = state.get(key)
        if since is None:
            state[key] = time.monotonic()
            return False
        return (time.monotonic() - float(since)) >= duration_s
    state.pop(key, None)
    return False


def _battery_timeout_active(mode: dict[str, Any], sample, state: dict[str, Any], mode_name: str) -> bool:
    trig = (mode.get("triggers") or {}).get("battery_timeout") or {}
    if not trig.get("enabled"):
        return False
    if sample.on_ac:
        state.pop(f"battery_since_{mode_name}", None)
        return False
    key = f"battery_since_{mode_name}"
    if state.get(key) is None:
        state[key] = time.monotonic()
    minutes = float(trig.get("minutes", 30))
    return (time.monotonic() - float(state[key])) >= minutes * 60.0


def _night_eligible(night: dict[str, Any]) -> bool:
    if not night.get("enabled"):
        return False
    if not _system_awake():
        return False
    lid = read_lid_open()
    if lid is False:
        return False
    return _schedule_active(night)


def desired_mode(cfg: dict[str, Any] | None = None, *, state: dict[str, Any] | None = None) -> str:
    """Return mode that rules say should be active (may differ from cfg active_mode)."""
    doc = normalize(cfg or load())
    state = state if state is not None else _read_state()
    sample = sample_system()
    modes = doc["modes"]
    matches: set[str] = set()

    night = modes.get("night") or {}
    if _night_eligible(night):
        matches.add("night")

    for name in ("quiet", "balanced", "performance"):
        m = modes.get(name) or {}
        if _schedule_active(m):
            matches.add(name)
        if _low_cpu_active(m, sample, state, name):
            matches.add(name)
        if _battery_timeout_active(m, sample, state, name):
            matches.add(name)

    if not matches:
        return "auto"
    return max(matches, key=lambda n: MODE_PRIORITY.index(n) if n in MODE_PRIORITY else 0)


def evaluate(*, apply_fn=None, notify_fn=None, quiet: bool = False) -> str | None:
    """Run one evaluation tick. Returns new mode if changed, else None."""
    from zenbook_kb.profile_apply import apply_mode as default_apply
    from zenbook_kb.user_profiles import save

    doc = load()
    state = _read_state()
    want = desired_mode(doc, state=state)
    applied = str(state.get("applied_mode") or doc.get("active_mode") or "auto")

    _write_state({**state, "last_eval": datetime.now().isoformat(), "desired_mode": want})

    if want == applied:
        if not quiet:
            log.debug("evaluate: unchanged %s", applied)
        return None

    apply = apply_fn or default_apply
    ok = apply(want)
    state = _read_state()
    state["applied_mode"] = want
    state["applied_at"] = datetime.now().isoformat()
    _write_state(state)

    doc = normalize(doc)
    doc["active_mode"] = want
    save(doc)

    if notify_fn:
        notify_fn("Zenbook profile", f"{mode_summary(doc)} (scheduled)", cfg=doc)
    elif not quiet:
        log.info("evaluate: %s -> %s apply=%s", applied, want, ok)

    return want
