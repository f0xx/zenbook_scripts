"""Named touchpad filter profiles (default vs adaptive).

``default`` — static chain: typing_inhibit → exec_delay → outlier_reject → soft_accel.
``adaptive`` — same gate, but ``adaptive_matrix`` replaces fixed outlier thresholds
with online amplitude learning (see ``touchpad_adaptive``).
"""

from __future__ import annotations

from typing import Any

from zenbook_kb.touchpad import DEFAULT_EXEC_DELAY_MS, DEFAULT_MAX_DELTA, DEFAULT_TYPING_WINDOW_MS

FILTER_PROFILE_DEFAULT = "default"
FILTER_PROFILE_ADAPTIVE = "adaptive"

FILTER_PROFILES = frozenset({FILTER_PROFILE_DEFAULT, FILTER_PROFILE_ADAPTIVE})


def default_profile_filters() -> list[dict[str, Any]]:
    """Static palm / brush filters (today's shipped behaviour)."""
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
            "gain": 1.6,
            "mode": "linear",
            "pivot": 40,
            "enabled": False,
        },
    ]


def adaptive_profile_filters() -> list[dict[str, Any]]:
    """Self-educating amplitude matrix; static outlier_reject disabled."""
    return [
        {"plugin": "event_sim", "enabled": False},
        {
            "plugin": "typing_inhibit",
            "window_ms": DEFAULT_TYPING_WINDOW_MS,
            "enabled": True,
        },
        {"plugin": "exec_delay", "ms": DEFAULT_EXEC_DELAY_MS, "enabled": True},
        {"plugin": "outlier_reject", "max_delta": DEFAULT_MAX_DELTA, "enabled": False},
        {
            "plugin": "adaptive_matrix",
            "enabled": True,
            "learn_rate": 0.08,
            "spike_sigma": 3.5,
            "predict_weight": 0.35,
            "min_baseline": 4.0,
            "persist_every": 120,
        },
        {
            "plugin": "soft_accel",
            "gain": 1.6,
            "mode": "linear",
            "pivot": 40,
            "enabled": False,
        },
    ]


def profile_filters(name: str) -> list[dict[str, Any]]:
    key = str(name or FILTER_PROFILE_DEFAULT).strip().lower()
    if key == FILTER_PROFILE_ADAPTIVE:
        return adaptive_profile_filters()
    return default_profile_filters()


def merge_gui_knobs(
    profile: str,
    knob_filters: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Overlay GUI knob state onto a default or adaptive preset."""
    base = profile_filters(profile)
    by_name = {
        str(f.get("plugin", "")): f
        for f in knob_filters
        if isinstance(f, dict) and f.get("plugin")
    }
    out: list[dict[str, Any]] = []
    for item in base:
        plugin = str(item.get("plugin", ""))
        if plugin in by_name:
            merged = dict(item)
            merged.update(by_name[plugin])
            merged["plugin"] = plugin
            out.append(merged)
        else:
            out.append(dict(item))
    return out


def entry_uses_adaptive(entry: dict[str, Any] | None) -> bool:
    if not entry:
        return False
    if normalize_filter_profile(entry.get("filter_profile")) == FILTER_PROFILE_ADAPTIVE:
        filters = entry.get("filters")
        return not (isinstance(filters, list) and filters)
    filters = entry.get("filters")
    if not isinstance(filters, list):
        return False
    for item in filters:
        if not isinstance(item, dict):
            continue
        name = str(item.get("plugin") or "").lower()
        if name in ("adaptive_matrix", "adaptive-matrix", "adaptive"):
            return item.get("enabled", True) is not False
    return False


def normalize_filter_profile(name: object) -> str:
    key = str(name or FILTER_PROFILE_DEFAULT).strip().lower()
    if key in FILTER_PROFILES:
        return key
    return FILTER_PROFILE_DEFAULT


def resolve_device_filters(entry: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Device entry → filter chain.

    Explicit ``filters`` list wins. Otherwise ``filter_profile`` selects a preset.
    """
    if not entry:
        return default_profile_filters()
    filters = entry.get("filters")
    if isinstance(filters, list) and filters:
        return list(filters)
    return profile_filters(entry.get("filter_profile", FILTER_PROFILE_DEFAULT))


def device_filter_profile(entry: dict[str, Any] | None) -> str:
    if not entry:
        return FILTER_PROFILE_DEFAULT
    if entry_uses_adaptive(entry):
        return FILTER_PROFILE_ADAPTIVE
    if isinstance(entry.get("filters"), list) and entry.get("filters"):
        return FILTER_PROFILE_DEFAULT
    return normalize_filter_profile(entry.get("filter_profile", FILTER_PROFILE_DEFAULT))
