"""KCM / tray helpers for touchpad.json knob export (mirrors platform-touchpad-gui)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from zenbook_kb.touchpad import (
    DEFAULT_CONFIG,
    discover_touchpads,
    filter_profile_for_device,
    filters_for_device,
    filters_from_knobs,
    knobs_from_filters,
    load_config,
    normalize_config,
    pick_default_device,
    resolve_touchpad,
    save_config,
    upsert_device_profile,
)
from zenbook_kb.touchpad_profiles import FILTER_PROFILE_DEFAULT


def _user_config_path() -> Path:
    user = Path.home() / ".config" / "zenbook-scripts" / "touchpad.json"
    if user.is_file():
        return user
    if DEFAULT_CONFIG.is_file():
        return DEFAULT_CONFIG
    return user


def _default_info():
    pads = discover_touchpads()
    if not pads:
        return None
    cfg = load_config(_user_config_path() if _user_config_path().is_file() else None)
    pref = (cfg or {}).get("default_device") or "auto"
    if pref and pref not in ("auto", ""):
        for p in pads:
            if p.key == pref:
                return p
    path = pick_default_device(pads)
    if path:
        for p in pads:
            if p.path == path:
                return p
    return pads[0]


def export_knobs() -> dict[str, Any]:
    info = _default_info()
    if info is None:
        return {"error": "no touchpad"}
    cfg = load_config(_user_config_path() if _user_config_path().is_file() else None)
    filters = filters_for_device(cfg, info, path=info.path)
    knobs = knobs_from_filters(filters)
    dev = (normalize_config(cfg).get("devices") or {}).get(info.key) or {}
    knobs["device_key"] = info.key
    knobs["device_name"] = info.name
    knobs["profile_enabled"] = bool(dev.get("enabled", False))
    knobs["filter_profile"] = filter_profile_for_device(cfg, info, path=info.path)
    knobs["config_path"] = str(_user_config_path())
    return knobs


def import_knobs(data: dict[str, Any]) -> Path:
    info = _default_info()
    if info is None:
        raise RuntimeError("no touchpad")
    cfg = load_config(_user_config_path() if _user_config_path().is_file() else None)
    filters = filters_from_knobs(
        delay_enabled=bool(data.get("delay_enabled", True)),
        delay_ms=float(data.get("delay_ms", 25)),
        outlier_enabled=bool(data.get("outlier_enabled", True)),
        max_delta=int(data.get("max_delta", 1200)),
        typing_enabled=bool(data.get("typing_enabled", True)),
        typing_window_ms=float(data.get("typing_window_ms", 350)),
        soft_accel_enabled=bool(data.get("soft_accel_enabled", False)),
        soft_accel_gain=float(data.get("soft_accel_gain", 1.6)),
        soft_accel_mode=str(data.get("soft_accel_mode", "linear")),
        soft_accel_pivot=int(data.get("soft_accel_pivot", 40)),
    )
    prof = str(data.get("filter_profile") or FILTER_PROFILE_DEFAULT)
    cfg = upsert_device_profile(
        cfg,
        info.key,
        filters=filters,
        filter_profile=prof,
        enabled=bool(data.get("profile_enabled", False)),
        make_default=True,
    )
    path = _user_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    save_config(cfg, path)
    if DEFAULT_CONFIG.parent.exists():
        try:
            save_config(cfg, DEFAULT_CONFIG)
        except OSError:
            pass
    return path
