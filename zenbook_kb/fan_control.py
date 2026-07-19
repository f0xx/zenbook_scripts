"""Adaptive fan profile controller (stdlib only).

Watches AC/battery, CPU load, temperature, and optional lid state; applies
named profiles via ACPI platform_profile and asus-nb-wmi pwm1_enable.
Sleep/lid are also available as one-shot events for hooks.

Config: JSON (stdlib) — machine-global ``/etc/zenbook-scripts/fan-control.json``
(see fan-control.json.example). Not per-user: hardware has one platform_profile.
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from zenbook_kb.users import default_fan_control_config

log = logging.getLogger("zenbook.fan_control")

ASUS_WMI = Path("/sys/devices/platform/asus-nb-wmi")
PLATFORM_PROFILE = Path("/sys/firmware/acpi/platform_profile")
THROTTLE_TTP = ASUS_WMI / "throttle_thermal_policy"


@dataclass
class Sample:
    on_ac: bool
    load_pct: float
    temp_c: float | None
    lid_open: bool | None
    rpm: int | None = None


@dataclass
class ControllerState:
    last_profile: str | None = None
    last_change_mono: float = 0.0
    last_lid_open: bool | None = None
    last_on_ac: bool | None = None


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return None


def _write_sysfs(path: Path, value: str) -> None:
    from zenbook_kb.priv import write_sysfs

    write_sysfs(path, value, allow_ask=False)


def cpu_count() -> int:
    try:
        return max(1, os.cpu_count() or 1)
    except NotImplementedError:
        return 1


def read_load_pct() -> float:
    """1-minute load average as % of one full core * nproc (capped display-wise)."""
    raw = _read_text(Path("/proc/loadavg"))
    if not raw:
        return 0.0
    load1 = float(raw.split()[0])
    return max(0.0, min(100.0 * load1 / cpu_count(), 999.0))


def read_on_ac() -> bool:
    base = Path("/sys/class/power_supply")
    if not base.is_dir():
        return True
    for psy in base.iterdir():
        ptype = _read_text(psy / "type")
        if ptype not in ("Mains", "USB"):
            # Prefer explicit AC adapters
            continue
        if ptype == "Mains":
            online = _read_text(psy / "online")
            if online is not None:
                return online == "1"
    for psy in base.iterdir():
        name = psy.name.upper()
        if name.startswith("AC") or name.startswith("ADP"):
            online = _read_text(psy / "online")
            if online is not None:
                return online == "1"
    return True


def read_temp_c() -> float | None:
    """Prefer coretemp Package id, else first hwmon temp*_input in °C."""
    hwmon = Path("/sys/class/hwmon")
    if not hwmon.is_dir():
        return None

    candidates: list[tuple[int, float]] = []
    for d in sorted(hwmon.iterdir()):
        name = _read_text(d / "name") or ""
        for temp in sorted(d.glob("temp*_input")):
            raw = _read_text(temp)
            if raw is None:
                continue
            try:
                millideg = int(raw)
            except ValueError:
                continue
            celsius = millideg / 1000.0
            label_path = Path(str(temp).replace("_input", "_label"))
            label = (_read_text(label_path) or "").lower()
            prio = 10
            if name == "coretemp" and "package" in label:
                prio = 0
            elif name == "coretemp":
                prio = 1
            elif name in ("acpitz", "asus"):
                prio = 2
            candidates.append((prio, celsius))

    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0])
    return candidates[0][1]


def read_lid_open() -> bool | None:
    base = Path("/proc/acpi/button/lid")
    if not base.is_dir():
        return None
    for state in base.glob("*/state"):
        text = _read_text(state)
        if not text:
            continue
        # "state:      open" / "state:      closed"
        if re.search(r"\bclosed\b", text, re.I):
            return False
        if re.search(r"\bopen\b", text, re.I):
            return True
    return None


def find_asus_hwmon() -> Path | None:
    root = ASUS_WMI / "hwmon"
    if root.is_dir():
        for d in root.iterdir():
            if (_read_text(d / "name") or "") == "asus":
                return d
    hwmon = Path("/sys/class/hwmon")
    if hwmon.is_dir():
        for d in hwmon.iterdir():
            if (_read_text(d / "name") or "") == "asus" and (d / "fan1_input").is_file():
                return d
    return None


def read_rpm() -> int | None:
    hw = find_asus_hwmon()
    if not hw:
        return None
    raw = _read_text(hw / "fan1_input")
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def sample_system() -> Sample:
    return Sample(
        on_ac=read_on_ac(),
        load_pct=read_load_pct(),
        temp_c=read_temp_c(),
        lid_open=read_lid_open(),
        rpm=read_rpm(),
    )


def load_config(path: Path | None = None) -> dict[str, Any]:
    cfg_path = path or default_fan_control_config()
    if not cfg_path.is_file():
        raise FileNotFoundError(
            f"Missing config {cfg_path} (copy fan-control.json.example)"
        )
    data = json.loads(cfg_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("config root must be a JSON object")
    return data


def when_matches(when: dict[str, Any], sample: Sample) -> bool:
    """All specified predicates must hold."""
    if not when:
        return True

    load = sample.load_pct
    temp = sample.temp_c

    if "load_lt" in when and not (load < float(when["load_lt"])):
        return False
    if "load_lte" in when and not (load <= float(when["load_lte"])):
        return False
    if "load_gt" in when and not (load > float(when["load_gt"])):
        return False
    if "load_gte" in when and not (load >= float(when["load_gte"])):
        return False

    if any(k.startswith("temp_") for k in when):
        if temp is None:
            return False
        if "temp_lt" in when and not (temp < float(when["temp_lt"])):
            return False
        if "temp_lte" in when and not (temp <= float(when["temp_lte"])):
            return False
        if "temp_gt" in when and not (temp > float(when["temp_gt"])):
            return False
        if "temp_gte" in when and not (temp >= float(when["temp_gte"])):
            return False

    return True


def pick_rule_profile(cfg: dict[str, Any], sample: Sample) -> str | None:
    power_key = "ac" if sample.on_ac else "battery"
    rules = (cfg.get("rules") or {}).get(power_key) or []
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        when = rule.get("when") or {}
        if when_matches(when, sample):
            return rule.get("profile")
    return None


def _bin_candidates(*names: str) -> list[Path]:
    roots = [
        Path("/usr/bin"),
        Path("/usr/local/bin"),
        Path(__file__).resolve().parent.parent / "bin",
    ]
    out: list[Path] = []
    for root in roots:
        for name in names:
            p = root / name
            if p.is_file():
                out.append(p)
    return out


def _run_cli(argv: list[str]) -> None:
    """Run helper CLI; use sudo -n when not root (never hang on password)."""
    from zenbook_kb.priv import run_root

    if os.geteuid() == 0:
        subprocess.run(argv, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        return
    r = run_root(argv, check=False, allow_ask=False, capture=True, timeout=30)
    if r.returncode != 0:
        err = (r.stderr or b"").decode(errors="replace").strip()
        raise PermissionError(f"need root or NOPASSWD for {argv[0]}: {err}")


def apply_profile(cfg: dict[str, Any], name: str) -> None:
    profiles = cfg.get("profiles") or {}
    prof = profiles.get(name)
    if not isinstance(prof, dict):
        raise KeyError(f"unknown profile {name!r}")

    pp = prof.get("platform_profile")
    if pp:
        bins = _bin_candidates("kb-platform-profile")
        if bins:
            _run_cli([str(bins[0]), "set", str(pp)])
        elif PLATFORM_PROFILE.is_file():
            _write_sysfs(PLATFORM_PROFILE, f"{pp}\n")
        else:
            raise FileNotFoundError(str(PLATFORM_PROFILE))

    pwm = prof.get("pwm")
    if pwm is not None:
        bins = _bin_candidates("platform-fan", "kb-fan")
        if pwm in ("full", "max", "on", 0, "0"):
            if bins:
                _run_cli([str(bins[0]), "full"])
            else:
                hw = find_asus_hwmon()
                if not hw:
                    log.warning("asus hwmon missing; skip pwm=full")
                else:
                    _write_sysfs(hw / "pwm1_enable", "0")
        elif pwm in ("auto", 2, "2"):
            if bins:
                _run_cli([str(bins[0]), "auto"])
            else:
                hw = find_asus_hwmon()
                if not hw:
                    log.warning("asus hwmon missing; skip pwm=auto")
                else:
                    _write_sysfs(hw / "pwm1_enable", "2")
        elif pwm in ("manual", 1, "1"):
            raise RuntimeError("pwm=manual/curves not supported on this model")
        else:
            raise ValueError(f"unknown pwm mode {pwm!r}")

    run = prof.get("run")
    if run:
        subprocess.run(run, shell=True, check=False)

    log.info("applied profile %s (platform_profile=%s pwm=%s)", name, pp, pwm)


def run_event(cfg: dict[str, Any], event: str, state: ControllerState) -> None:
    events = cfg.get("events") or {}
    ev = events.get(event)
    if not ev:
        log.debug("no event handler for %s", event)
        return
    if not isinstance(ev, dict):
        raise ValueError(f"events.{event} must be an object")

    profile = ev.get("profile")
    if profile:
        apply_profile(cfg, profile)
        state.last_profile = profile
        state.last_change_mono = time.monotonic()

    run = ev.get("run")
    if run:
        subprocess.run(run, shell=True, check=False)

    # sleep_post / lid_open with null profile → re-evaluate continuous rules ASAP
    if profile is None and event in ("sleep_post", "lid_open", "ac_change"):
        state.last_change_mono = 0.0


def maybe_apply_continuous(
    cfg: dict[str, Any],
    sample: Sample,
    state: ControllerState,
    *,
    force: bool = False,
) -> str | None:
    daemon = cfg.get("daemon") or {}
    hysteresis = float(daemon.get("hysteresis_sec", 30))
    wanted = pick_rule_profile(cfg, sample)
    if not wanted:
        return None

    now = time.monotonic()
    if (
        not force
        and wanted == state.last_profile
    ):
        return wanted
    if (
        not force
        and state.last_profile is not None
        and (now - state.last_change_mono) < hysteresis
        and wanted != state.last_profile
    ):
        log.debug(
            "hysteresis: keep %s (want %s, %.1fs left)",
            state.last_profile,
            wanted,
            hysteresis - (now - state.last_change_mono),
        )
        return state.last_profile

    apply_profile(cfg, wanted)
    state.last_profile = wanted
    state.last_change_mono = now
    return wanted


def format_status(cfg: dict[str, Any], sample: Sample, state: ControllerState) -> str:
    lines = [
        f"power:    {'ac' if sample.on_ac else 'battery'}",
        f"load:     {sample.load_pct:.1f}%",
        f"temp_c:   {sample.temp_c if sample.temp_c is not None else 'n/a'}",
        f"lid:      {('open' if sample.lid_open else 'closed') if sample.lid_open is not None else 'n/a'}",
        f"rpm:      {sample.rpm if sample.rpm is not None else 'n/a'}",
        f"profile:  {state.last_profile or 'n/a'}",
    ]
    if PLATFORM_PROFILE.is_file():
        lines.append(f"sys_pp:   {_read_text(PLATFORM_PROFILE)}")
    if THROTTLE_TTP.is_file():
        lines.append(f"ttp:      {_read_text(THROTTLE_TTP)}")
    wanted = pick_rule_profile(cfg, sample)
    lines.append(f"rule_want:{wanted or 'none'}")
    return "\n".join(lines)


def daemon_loop(cfg: dict[str, Any], state: ControllerState) -> None:
    daemon = cfg.get("daemon") or {}
    interval = float(daemon.get("interval_sec", 5))
    watch_lid = bool(daemon.get("watch_lid", True))
    watch_power = bool(daemon.get("watch_power", True))

    sample = sample_system()
    maybe_apply_continuous(cfg, sample, state, force=True)
    state.last_lid_open = sample.lid_open
    state.last_on_ac = sample.on_ac

    while True:
        time.sleep(interval)
        sample = sample_system()

        if watch_power and state.last_on_ac is not None and sample.on_ac != state.last_on_ac:
            log.info("power change ac=%s", sample.on_ac)
            run_event(cfg, "ac_online" if sample.on_ac else "ac_offline", state)
            # also generic hook
            run_event(cfg, "ac_change", state)
            state.last_change_mono = 0.0
            state.last_on_ac = sample.on_ac

        if watch_lid and sample.lid_open is not None and state.last_lid_open is not None:
            if sample.lid_open != state.last_lid_open:
                ev = "lid_open" if sample.lid_open else "lid_close"
                log.info("lid event %s", ev)
                run_event(cfg, ev, state)
                state.last_lid_open = sample.lid_open

        if sample.lid_open is not None:
            state.last_lid_open = sample.lid_open
        state.last_on_ac = sample.on_ac

        # While lid closed, skip load/temp chasing unless configured
        if sample.lid_open is False and not bool(daemon.get("rules_while_lid_closed", False)):
            continue

        maybe_apply_continuous(cfg, sample, state)


def ensure_example_config() -> Path:
    """Return user config path; do not overwrite existing."""
    return default_fan_control_config()
