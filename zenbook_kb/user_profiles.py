"""User-facing power/thermal profiles (tray + KCM).

Per-user file: ``~/.config/zenbook-scripts/profiles.json``
Machine defaults: ``/usr/share/zenbook-scripts/profiles.json.example``

Modes: auto (view-only), quiet, balanced, performance, night — each with optional
schedule and trigger rules. ``night`` adds display/backlight/network toggles.
"""

from __future__ import annotations

import copy
import json
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger("zenbook.user_profiles")

VERSION = 1
BUILTIN_MODES = ("auto", "quiet", "balanced", "performance", "night")


def user_config_path() -> Path:
    return Path.home() / ".config" / "zenbook-scripts" / "profiles.json"


def example_config_path() -> Path:
    for p in (
        Path("/usr/share/zenbook-scripts/profiles.json.example"),
        Path("/usr/local/share/zenbook-scripts/profiles.json.example"),
    ):
        if p.is_file():
            return p
    return Path(__file__).resolve().parents[1] / "profiles.json.example"


def _schedule_block(
    *,
    enabled: bool = False,
    start: str = "22:00",
    stop: str = "07:00",
) -> dict[str, Any]:
    return {"enabled": enabled, "start": start, "stop": stop}


def _triggers_block(
    *,
    low_cpu_enabled: bool = False,
    load_pct_max: int = 20,
    duration_min: int = 3,
    require_battery: bool = True,
    battery_timeout_enabled: bool = False,
    battery_minutes: int = 30,
) -> dict[str, Any]:
    return {
        "low_cpu": {
            "enabled": low_cpu_enabled,
            "load_pct_max": load_pct_max,
            "duration_min": duration_min,
            "require_battery": require_battery,
        },
        "battery_timeout": {
            "enabled": battery_timeout_enabled,
            "minutes": battery_minutes,
        },
    }


def default_mode(name: str) -> dict[str, Any]:
    if name == "auto":
        return {
            "builtin": True,
            "editable": False,
            "label": "Auto (adaptive)",
            "description": (
                "Uses platform-fan-control load/temp rules from fan-control.json. "
                "Tray manual lock disables auto until cleared."
            ),
            "fan_profile": None,
        }
    if name == "quiet":
        return {
            "builtin": True,
            "editable": True,
            "label": "Quiet (powersave)",
            "fan_profile": "powersave",
            "schedule": _schedule_block(enabled=False, start="22:00", stop="07:00"),
            "triggers": _triggers_block(
                low_cpu_enabled=True,
                load_pct_max=20,
                duration_min=3,
                require_battery=True,
            ),
        }
    if name == "balanced":
        return {
            "builtin": True,
            "editable": True,
            "label": "Balanced",
            "fan_profile": "balanced",
            "schedule": _schedule_block(enabled=False, start="08:00", stop="23:00"),
            "triggers": _triggers_block(
                low_cpu_enabled=False,
                load_pct_max=35,
                duration_min=5,
                require_battery=False,
            ),
        }
    if name == "performance":
        return {
            "builtin": True,
            "editable": True,
            "label": "Performance",
            "fan_profile": "performance",
            "schedule": _schedule_block(enabled=False, start="09:00", stop="18:00"),
            "triggers": _triggers_block(
                low_cpu_enabled=False,
                load_pct_max=60,
                duration_min=2,
                require_battery=False,
            ),
        }
    if name == "night":
        return {
            "builtin": True,
            "editable": True,
            "label": "Night mode",
            "enabled": False,
            "base_mode": "quiet",
            "schedule": _schedule_block(enabled=True, start="23:00", stop="06:00"),
            "screen": {"power_off": True, "brightness": 0},
            "keyboard_backlight": {"enabled": False, "level": 0},
            "network": {"stay_up": True},
            "notes": (
                "Schedule runs only while the laptop is awake with the lid open. "
                "Closed lid or hibernate skips scheduled start/stop; use lid night "
                "hook (platform-night-mode) for closed-lid server behaviour."
            ),
        }
    raise KeyError(name)


def default_document() -> dict[str, Any]:
    modes = {name: default_mode(name) for name in BUILTIN_MODES}
    return {
        "version": VERSION,
        "notifications": {"enabled": True, "on_mode_switch": True},
        "active_mode": "auto",
        "modes": modes,
    }


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(base)
    for key, val in overlay.items():
        if key in out and isinstance(out[key], dict) and isinstance(val, dict):
            out[key] = _deep_merge(out[key], val)
        else:
            out[key] = copy.deepcopy(val)
    return out


def normalize(raw: dict[str, Any] | None) -> dict[str, Any]:
    base = default_document()
    if not raw:
        return base
    merged = _deep_merge(base, raw if isinstance(raw, dict) else {})
    merged["version"] = VERSION
    modes = merged.setdefault("modes", {})
    for name in BUILTIN_MODES:
        modes[name] = _deep_merge(default_mode(name), modes.get(name) or {})
        modes[name]["builtin"] = True
        if name == "auto":
            modes[name]["editable"] = False
    notif = merged.setdefault("notifications", {})
    notif.setdefault("enabled", True)
    notif.setdefault("on_mode_switch", True)
    active = str(merged.get("active_mode") or "auto")
    if active not in BUILTIN_MODES:
        active = "auto"
    merged["active_mode"] = active
    return merged


def load(path: Path | None = None) -> dict[str, Any]:
    target = path or user_config_path()
    if not target.is_file():
        return default_document()
    raw = json.loads(target.read_text(encoding="utf-8"))
    return normalize(raw)


def save(cfg: dict[str, Any], path: Path | None = None) -> Path:
    target = path or user_config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    doc = normalize(cfg)
    target.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return target


def reset_mode(name: str, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    doc = normalize(cfg or load())
    if name not in BUILTIN_MODES:
        raise KeyError(name)
    doc["modes"][name] = default_mode(name)
    return doc


def reset_all(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    doc = default_document()
    if cfg:
        doc["active_mode"] = normalize(cfg).get("active_mode", "auto")
    return doc


def set_active_mode(mode: str, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    if mode not in BUILTIN_MODES:
        raise ValueError(f"unknown mode {mode!r}")
    doc = normalize(cfg or load())
    doc["active_mode"] = mode
    return doc


def mode_summary(cfg: dict[str, Any] | None = None) -> str:
    doc = normalize(cfg or load())
    active = doc["active_mode"]
    mode = doc["modes"][active]
    label = mode.get("label") or active
    if active == "night" and not mode.get("enabled"):
        return f"{label} (disabled)"
    if active == "auto":
        return label
    sched = mode.get("schedule") or {}
    if sched.get("enabled"):
        return f"{label} ({sched.get('start')}–{sched.get('stop')})"
    return label


def status_lines(cfg: dict[str, Any] | None = None) -> list[str]:
    doc = normalize(cfg or load())
    path = user_config_path()
    lines = [
        f"config: {path} ({'present' if path.is_file() else 'defaults'})",
        f"active: {doc['active_mode']} — {mode_summary(doc)}",
        f"notify: {'on' if doc['notifications'].get('enabled') else 'off'}",
    ]
    night = doc["modes"]["night"]
    lines.append(
        f"night:  {'enabled' if night.get('enabled') else 'disabled'} "
        f"base={night.get('base_mode')} "
        f"sched={night.get('schedule', {}).get('start')}–{night.get('schedule', {}).get('stop')}"
    )
    return lines
