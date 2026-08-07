"""Generic hwmon fan backend detection (ASUS, ThinkPad, Dell, HP, pwm)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

HWMON = Path("/sys/class/hwmon")
ASUS_WMI = Path("/sys/devices/platform/asus-nb-wmi")

# Preferred order when multiple match.
BACKEND_NAMES = (
    "asus",
    "thinkpad",
    "dell_smm",
    "hp",
    "pwm",
)


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return None


@dataclass(frozen=True)
class FanHwmon:
    path: Path
    backend: str
    name: str
    has_rpm: bool
    has_pwm: bool


def _score_hwmon(d: Path, name: str) -> FanHwmon | None:
    has_rpm = (d / "fan1_input").is_file()
    has_pwm = (d / "pwm1").is_file()
    if not has_rpm and not has_pwm:
        return None
    backend = "pwm"
    nl = name.lower()
    if nl == "asus":
        backend = "asus"
    elif nl == "thinkpad":
        backend = "thinkpad"
    elif "dell" in nl:
        backend = "dell_smm"
    elif nl.startswith("hp") or nl == "hp":
        backend = "hp"
    return FanHwmon(path=d, backend=backend, name=name, has_rpm=has_rpm, has_pwm=has_pwm)


def list_fan_hwmon() -> list[FanHwmon]:
    found: list[FanHwmon] = []
    if not HWMON.is_dir():
        return found
    # asus-nb-wmi child hwmon first (stable on ZenBooks).
    asus_root = ASUS_WMI / "hwmon"
    if asus_root.is_dir():
        for d in asus_root.iterdir():
            if not d.is_dir():
                continue
            name = _read_text(d / "name") or ""
            row = _score_hwmon(d, name)
            if row:
                found.append(row)
    for d in sorted(HWMON.iterdir()):
        if not d.is_dir():
            continue
        name = _read_text(d / "name") or ""
        row = _score_hwmon(d, name)
        if row and row not in found:
            found.append(row)
    order = {n: i for i, n in enumerate(BACKEND_NAMES)}
    found.sort(key=lambda r: (order.get(r.backend, 99), r.name))
    return found


def find_fan_hwmon(prefer: str | None = None) -> FanHwmon | None:
    rows = list_fan_hwmon()
    if not rows:
        return None
    if prefer:
        pl = prefer.lower()
        for row in rows:
            if row.backend == pl:
                return row
    return rows[0]


def find_asus_hwmon() -> Path | None:
    """Backward-compatible ASUS path for fan_control."""
    row = find_fan_hwmon("asus")
    return row.path if row else None
