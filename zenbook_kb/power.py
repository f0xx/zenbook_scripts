"""Intel P-state EPP + RAPL helpers for fan-control profiles (stdlib only)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from zenbook_kb.priv import write_sysfs

log = logging.getLogger("zenbook.power")

CPUFREQ_ROOT = Path("/sys/devices/system/cpu")
INTEL_PSTATE = Path("/sys/devices/system/cpu/intel_pstate")
RAPL_PACKAGE = Path("/sys/class/powercap/intel-rapl:0")

EPP_ALIASES = {
    "powersave": "power",
    "power": "power",
    "balance_power": "balance_power",
    "balanced_power": "balance_power",
    "balance_performance": "balance_performance",
    "balanced_performance": "balance_performance",
    "balanced": "balance_performance",
    "performance": "performance",
    "default": "default",
}


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return None


def has_intel_pstate() -> bool:
    return INTEL_PSTATE.is_dir()


def has_epp() -> bool:
    return (CPUFREQ_ROOT / "cpu0/cpufreq/energy_performance_preference").is_file()


def has_rapl() -> bool:
    return RAPL_PACKAGE.is_dir()


def available_epp() -> list[str]:
    raw = _read(CPUFREQ_ROOT / "cpu0/cpufreq/energy_performance_available_preferences")
    if not raw:
        return []
    return raw.split()


def read_epp() -> str | None:
    return _read(CPUFREQ_ROOT / "cpu0/cpufreq/energy_performance_preference")


def normalize_epp(value: str) -> str:
    key = value.strip().lower().replace("-", "_")
    return EPP_ALIASES.get(key, value.strip())


def _cpufreq_dirs() -> list[Path]:
    policies = sorted(Path("/sys/devices/system/cpu/cpufreq").glob("policy*"))
    if policies:
        return policies
    return sorted(CPUFREQ_ROOT.glob("cpu*/cpufreq"))


def set_scaling_governor(governor: str) -> None:
    written = 0
    for d in _cpufreq_dirs():
        path = d / "scaling_governor"
        if path.is_file():
            write_sysfs(path, f"{governor}\n", allow_ask=False)
            written += 1
    if not written:
        raise FileNotFoundError("no scaling_governor nodes")
    log.info("scaling_governor=%s (%d)", governor, written)


def set_epp(value: str) -> None:
    """Write EPP on every policy/cpu.

    With ``intel_pstate`` active, the ``performance`` governor often rejects EPP
    writes (EBUSY). Non-performance EPP values switch governor to ``powersave``
    first; ``performance`` EPP uses the ``performance`` governor.
    """
    pref = normalize_epp(value)
    avail = available_epp()
    if avail and pref not in avail:
        raise ValueError(f"EPP {pref!r} not in available {avail}")

    if pref == "performance":
        # performance governor locks EPP writes (EBUSY); governor alone is enough.
        set_scaling_governor("performance")
        log.info("epp=performance via scaling_governor=performance")
        return

    try:
        set_scaling_governor("powersave")
    except OSError as exc:
        log.warning("could not set governor powersave before EPP: %s", exc)

    written = 0
    errors: list[str] = []
    for d in _cpufreq_dirs():
        path = d / "energy_performance_preference"
        if not path.is_file():
            continue
        try:
            write_sysfs(path, f"{pref}\n", allow_ask=False)
            written += 1
        except OSError as exc:
            errors.append(f"{path}: {exc}")
    if not written:
        detail = "; ".join(errors[:3]) or "no energy_performance_preference nodes"
        raise OSError(f"failed to set EPP={pref}: {detail}")
    if errors:
        log.warning("EPP partial apply (%d ok): %s", written, errors[0])
    log.info("epp=%s (%d policies)", pref, written)


def read_intel_pstate() -> dict[str, str | None]:
    if not has_intel_pstate():
        return {}
    return {
        name: _read(INTEL_PSTATE / name)
        for name in ("status", "no_turbo", "min_perf_pct", "max_perf_pct")
    }


def apply_intel_pstate(opts: dict[str, Any]) -> None:
    """Apply optional intel_pstate knobs: no_turbo, min_perf_pct, max_perf_pct."""
    if not opts:
        return
    if not has_intel_pstate():
        log.warning("intel_pstate missing; skip %s", opts)
        return
    if "no_turbo" in opts:
        val = opts["no_turbo"]
        if isinstance(val, bool):
            raw = "1" if val else "0"
        elif isinstance(val, str):
            raw = "1" if val.strip().lower() in ("1", "yes", "true", "on") else "0"
        else:
            raw = "1" if int(val) else "0"
        write_sysfs(INTEL_PSTATE / "no_turbo", f"{raw}\n", allow_ask=False)
    for key in ("min_perf_pct", "max_perf_pct"):
        if key not in opts:
            continue
        pct = int(opts[key])
        if not 0 <= pct <= 100:
            raise ValueError(f"{key} must be 0..100, got {pct}")
        write_sysfs(INTEL_PSTATE / key, f"{pct}\n", allow_ask=False)
    log.info("intel_pstate applied %s", opts)


def _uw(value: Any) -> int:
    """Accept watts (float / small int) or microwatts (large int)."""
    if isinstance(value, str):
        text = value.strip().lower().removesuffix("w").strip()
        value = float(text)
    if isinstance(value, float):
        return int(value * 1_000_000)
    iv = int(value)
    if abs(iv) < 1000:
        return iv * 1_000_000
    return iv


def resolve_rapl_zone(name: str | None = None) -> Path:
    if name:
        p = Path("/sys/class/powercap") / name
        if p.is_dir():
            return p
        raise FileNotFoundError(f"RAPL zone {name}")
    if RAPL_PACKAGE.is_dir():
        return RAPL_PACKAGE
    raise FileNotFoundError("no intel-rapl:0")


def read_rapl(zone: Path | None = None) -> dict[str, Any]:
    root = zone or (RAPL_PACKAGE if has_rapl() else None)
    if root is None or not root.is_dir():
        return {}
    out: dict[str, Any] = {"zone": root.name, "name": _read(root / "name")}
    for idx, label in ((0, "pl1"), (1, "pl2"), (2, "peak")):
        lim = _read(root / f"constraint_{idx}_power_limit_uw")
        cname = _read(root / f"constraint_{idx}_name")
        if lim is None and cname is None:
            continue
        try:
            uw = int(lim) if lim is not None else None
        except ValueError:
            uw = None
        out[label] = {
            "name": cname,
            "uw": uw,
            "w": (uw / 1_000_000.0) if uw is not None else None,
        }
    return out


def apply_rapl(opts: dict[str, Any]) -> None:
    """Apply RAPL package limits (pl1/pl2/peak in watts or microwatts)."""
    if not opts:
        return
    zone = resolve_rapl_zone(opts.get("zone"))
    mapping = (
        (("pl1", "pl1_w", "pl1_uw"), 0),
        (("pl2", "pl2_w", "pl2_uw"), 1),
        (("peak", "peak_w", "peak_uw"), 2),
    )
    applied: list[str] = []
    for keys, idx in mapping:
        raw = None
        for k in keys:
            if k in opts and opts[k] is not None:
                raw = opts[k]
                break
        if raw is None:
            continue
        uw = _uw(raw)
        path = zone / f"constraint_{idx}_power_limit_uw"
        if not path.is_file():
            log.warning("missing %s; skip", path)
            continue
        write_sysfs(path, f"{uw}\n", allow_ask=False)
        applied.append(f"c{idx}={uw / 1_000_000:.1f}W")
    if not applied:
        log.warning("rapl options present but nothing applied: %s", opts)
    else:
        log.info("rapl %s %s", zone.name, ", ".join(applied))


def apply_power_knobs(prof: dict[str, Any]) -> None:
    """Apply epp / intel_pstate / rapl keys from a fan-control profile object."""
    if "epp" in prof and prof["epp"] is not None:
        if has_epp():
            set_epp(str(prof["epp"]))
        else:
            log.warning("EPP sysfs missing; skip epp=%s", prof["epp"])

    ip = prof.get("intel_pstate")
    if isinstance(ip, dict):
        apply_intel_pstate(ip)
    elif ip is not None:
        raise ValueError("intel_pstate must be an object")

    flat_ip = {
        k: prof[k]
        for k in ("no_turbo", "min_perf_pct", "max_perf_pct")
        if k in prof
    }
    if flat_ip:
        apply_intel_pstate(flat_ip)

    rapl = prof.get("rapl")
    if isinstance(rapl, dict):
        apply_rapl(rapl)
    elif rapl is not None:
        raise ValueError("rapl must be an object")


def format_power_status() -> list[str]:
    lines: list[str] = []
    gov = _read(CPUFREQ_ROOT / "cpu0/cpufreq/scaling_governor")
    epp = read_epp()
    if gov is not None or epp is not None:
        avail = available_epp()
        extra = f" avail=[{' '.join(avail)}]" if avail else ""
        lines.append(f"cpufreq:  governor={gov or 'n/a'} epp={epp or 'n/a'}{extra}")
    ip = read_intel_pstate()
    if ip:
        bits = [f"{k}={v}" for k, v in ip.items() if v is not None]
        if bits:
            lines.append("pstate:   " + " ".join(bits))
    rapl = read_rapl()
    if rapl:
        parts = []
        for key in ("pl1", "pl2", "peak"):
            block = rapl.get(key)
            if isinstance(block, dict) and block.get("w") is not None:
                parts.append(f"{key}={block['w']:.1f}W")
        if parts:
            lines.append(f"rapl:     {rapl.get('zone')} " + " ".join(parts))
    return lines
