"""Optional night-mode host setup — fan profile, PowerDevil, elogind drop-in."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from zenbook_kb.priv import write_sysfs

FAN_CONTROL_LIVE = Path("/etc/zenbook-scripts/fan-control.json")
ELOGIND_DROPIN = Path("/etc/elogind/logind.conf.d/99-zenbook-night-mode.conf")
NIGHT_MODE_LIVE = Path("/etc/zenbook-scripts/night-mode.json")

# PowerDevil 6.x PowerButtonAction::TurnOffScreen (see plasma-manager powerdevil.nix)
POWERDEVIL_LID_TURN_OFF_SCREEN = 64


def _fan_night_profile(example_path: Path) -> dict[str, Any] | None:
    if not example_path.is_file():
        return None
    raw = json.loads(example_path.read_text(encoding="utf-8"))
    profiles = raw.get("profiles") if isinstance(raw, dict) else None
    if not isinstance(profiles, dict):
        return None
    night = profiles.get("night")
    return night if isinstance(night, dict) else None


def merge_fan_night_profile(
    *,
    live_path: Path = FAN_CONTROL_LIVE,
    example_path: Path | None = None,
) -> bool:
    """Add profiles.night from example when missing. Returns True if file changed."""
    if example_path is None:
        example_path = Path("/usr/share/zenbook-scripts/fan-control.json.example")
    if not example_path.is_file():
        example_path = Path(__file__).resolve().parent.parent / "fan-control.json.example"
    night = _fan_night_profile(example_path)
    if not night:
        return False
    if not live_path.is_file():
        return False
    doc = json.loads(live_path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        return False
    profiles = doc.setdefault("profiles", {})
    if not isinstance(profiles, dict):
        return False
    if "night" in profiles:
        return False
    profiles["night"] = night
    payload = json.dumps(doc, indent=2) + "\n"
    write_sysfs(live_path, payload, allow_ask=False)
    return True


def configure_powerdevil_ac_lid(*, home: Path | None = None) -> bool:
    """AC + lid closed → turn off screen (Plasma PowerDevil 6)."""
    home = home or Path.home()
    cfg = home / ".config" / "powerdevilrc"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    kwrite = shutil.which("kwriteconfig6")
    if not kwrite:
        return False
    env = {"HOME": str(home), **os.environ}
    base = [
        kwrite,
        "--file",
        str(cfg),
        "--group",
        "AC",
        "--group",
        "SuspendAndShutdown",
    ]
    steps = [
        [*base, "--key", "LidAction", "--type", "int", str(POWERDEVIL_LID_TURN_OFF_SCREEN)],
        [*base, "--key", "InhibitLidActionWhenExternalMonitorPresent", "--type", "bool", "true"],
    ]
    for argv in steps:
        subprocess.run(argv, check=False, env=env)
    return True


def install_elogind_dropin(*, source: Path | None = None) -> bool:
    source = source or (
        Path(__file__).resolve().parent.parent / "contrib" / "elogind" / "99-zenbook-night-mode.conf"
    )
    if not source.is_file():
        return False
    ELOGIND_DROPIN.parent.mkdir(parents=True, exist_ok=True)
    if ELOGIND_DROPIN.is_file() and ELOGIND_DROPIN.read_text(encoding="utf-8") == source.read_text(
        encoding="utf-8"
    ):
        return False
    write_sysfs(ELOGIND_DROPIN, source.read_text(encoding="utf-8"), allow_ask=False)
    if shutil.which("busctl"):
        subprocess.run(
            [
                "busctl",
                "call",
                "org.freedesktop.login1",
                "/org/freedesktop/login1",
                "org.freedesktop.login1.Manager",
                "ReloadConfig",
            ],
            check=False,
        )
    return True


def seed_night_mode_json(*, example: Path | None = None, enabled: bool = False) -> bool:
    """Create /etc/zenbook-scripts/night-mode.json when absent."""
    if NIGHT_MODE_LIVE.is_file():
        return False
    if example is None:
        example = Path("/usr/share/zenbook-scripts/night-mode.json.example")
    if not example.is_file():
        example = Path(__file__).resolve().parent.parent / "night-mode.json.example"
    if not example.is_file():
        return False
    raw = json.loads(example.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        raw["enabled"] = enabled
    payload = json.dumps(raw, indent=2) + "\n"
    NIGHT_MODE_LIVE.parent.mkdir(parents=True, exist_ok=True)
    write_sysfs(NIGHT_MODE_LIVE, payload, allow_ask=False)
    return True


def reload_powerdevil(*, home: Path | None = None) -> bool:
    """Best-effort reload so LidAction applies without re-login."""
    home = home or Path.home()
    runtime = Path(f"/run/user/{os.getuid()}")
    env = {
        "HOME": str(home),
        "XDG_RUNTIME_DIR": str(runtime) if runtime.is_dir() else "",
        **os.environ,
    }
    for argv in (
        ["qdbus6", "org.kde.PowerDevil", "/org/kde/PowerDevil", "org.kde.PowerDevil.reloadConfig"],
        ["qdbus6", "org.kde.kded6", "/kded", "org.kde.kded6.reloadModule", "powerdevil"],
    ):
        if shutil.which(argv[0]):
            r = subprocess.run(argv, capture_output=True, text=True, env=env, check=False)
            if r.returncode == 0:
                return True
    return False


def _session_home() -> Path:
    for key in ("SUDO_USER", "ZENBOOK_SESSION_USER", "USER"):
        name = os.environ.get(key)
        if not name or name == "root":
            continue
        try:
            import pwd

            return Path(pwd.getpwnam(name).pw_dir)
        except (ImportError, KeyError):
            break
    return Path.home()


def run_optional_setup(*, script_dir: Path | None = None, user_home: Path | None = None) -> list[str]:
    """Apply all optional night-mode improvements. Returns human-readable lines."""
    script_dir = script_dir or Path(__file__).resolve().parent.parent
    user_home = user_home or _session_home()
    lines: list[str] = []
    elogind_src = script_dir / "contrib" / "elogind" / "99-zenbook-night-mode.conf"
    if install_elogind_dropin(source=elogind_src):
        lines.append(f"Installed elogind drop-in → {ELOGIND_DROPIN}")
    elif ELOGIND_DROPIN.is_file():
        lines.append(f"elogind drop-in already present ({ELOGIND_DROPIN})")
    if seed_night_mode_json(example=script_dir / "night-mode.json.example", enabled=False):
        lines.append(f"Seeded {NIGHT_MODE_LIVE} (enabled=false; profiles.json schedule drives timing)")
    if merge_fan_night_profile(example_path=script_dir / "fan-control.json.example"):
        lines.append(f"Added profiles.night to {FAN_CONTROL_LIVE}")
    elif FAN_CONTROL_LIVE.is_file():
        doc = json.loads(FAN_CONTROL_LIVE.read_text(encoding="utf-8"))
        if (doc.get("profiles") or {}).get("night"):
            lines.append(f"Fan profile night already in {FAN_CONTROL_LIVE}")
    if configure_powerdevil_ac_lid(home=user_home):
        lines.append(
            f"PowerDevil AC lid → turn off screen ({user_home}/.config/powerdevilrc LidAction={POWERDEVIL_LID_TURN_OFF_SCREEN})"
        )
        if reload_powerdevil(home=user_home):
            lines.append("Reloaded PowerDevil config")
    else:
        lines.append("PowerDevil: kwriteconfig6 not found — set AC lid action manually")
    return lines
