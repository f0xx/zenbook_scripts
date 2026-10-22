"""Closed-lid night profile — stay awake on AC with quiet fan and min CPU.

Snapshots fan/thermal state before entering night mode and restores it on lid
open. Does not suspend; requires elogind ``HandleLidSwitchExternalPower=ignore``
(see ``contrib/elogind/99-zenbook-night-mode.conf``).
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from zenbook_kb.fan_control import (
    CONTROL_MODE_STATE,
    apply_profile,
    get_control_mode,
    load_config as load_fan_config,
    read_on_ac,
    restore_user_sysfs,
    run_event,
    set_control_mode,
    ControllerState,
)
from zenbook_kb.users import default_fan_control_config

log = logging.getLogger("zenbook.night_mode")

DEFAULT_CONFIG = Path("/etc/zenbook-scripts/night-mode.json")
STATE_DIR = Path("/var/lib/zenbook-scripts")
ACTIVE_MARKER = STATE_DIR / "night-mode-active"
SNAPSHOT_PATH = STATE_DIR / "night-mode-snapshot.json"
PLATFORM_PROFILE_STATE = STATE_DIR / "platform-profile"
FAN_PWM_STATE = STATE_DIR / "fan-pwm-enable"


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return None


def default_config_path() -> Path:
    return DEFAULT_CONFIG


def effective_night_config(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    """Merge system night-mode.json with profiles.json night when schedule is active."""
    merged = dict(cfg or load_night_config())
    try:
        from zenbook_kb.profile_eval import _schedule_active
        from zenbook_kb.user_profiles import load as load_profiles

        prof = load_profiles().get("modes", {}).get("night") or {}
        if prof.get("enabled") and _schedule_active(prof):
            merged["enabled"] = True
            screen = prof.get("screen") or {}
            merged["blank_displays"] = bool(screen.get("power_off", merged.get("blank_displays", True)))
    except Exception:
        pass
    return merged


def load_night_config(path: Path | None = None) -> dict[str, Any]:
    target = path or default_config_path()
    if not target.is_file():
        return {"enabled": False, "require_ac": True, "fan_profile": "night"}
    raw = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{target}: root must be object")
    return raw


def _remove_state_file(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
        return
    except OSError:
        pass
    from zenbook_kb.priv import run_root

    run_root(["rm", "-f", str(path)], check=False, allow_ask=False)


def is_active() -> bool:
    return ACTIVE_MARKER.is_file()


def _fan_config_path(cfg: dict[str, Any]) -> Path:
    explicit = cfg.get("fan_control_config")
    if explicit:
        return Path(str(explicit))
    return default_fan_control_config()


def capture_snapshot(*, fan_cfg_path: Path | None = None) -> dict[str, Any]:
    fan_path = fan_cfg_path or default_fan_control_config()
    snap: dict[str, Any] = {
        "version": 1,
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "fan_control_mode": get_control_mode(),
        "platform_profile": _read_text(PLATFORM_PROFILE_STATE),
        "fan_pwm_enable": _read_text(FAN_PWM_STATE),
        "fan_control_config": str(fan_path),
    }
    try:
        from zenbook_kb.profile_eval import EVAL_STATE

        if EVAL_STATE.is_file():
            st = json.loads(EVAL_STATE.read_text(encoding="utf-8"))
            if isinstance(st, dict) and st.get("applied_mode"):
                snap["applied_profile_mode"] = st["applied_mode"]
    except (OSError, json.JSONDecodeError):
        pass
    try:
        from zenbook_kb.user_profiles import load

        snap["profiles_active_mode"] = load().get("active_mode")
    except Exception:
        pass
    return snap


def write_snapshot(data: dict[str, Any]) -> Path:
    from zenbook_kb.priv import write_sysfs

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, indent=2) + "\n"
    write_sysfs(SNAPSHOT_PATH, payload, allow_ask=False)
    return SNAPSHOT_PATH


def read_snapshot() -> dict[str, Any] | None:
    if not SNAPSHOT_PATH.is_file():
        return None
    raw = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    return raw if isinstance(raw, dict) else None


def _session_env(user: str) -> dict[str, str]:
    env = os.environ.copy()
    try:
        import pwd

        pw = pwd.getpwnam(user)
        env["HOME"] = pw.pw_dir
        env["USER"] = user
        env["LOGNAME"] = user
        runtime = Path(f"/run/user/{pw.pw_uid}")
        if runtime.is_dir():
            env["XDG_RUNTIME_DIR"] = str(runtime)
            bus = runtime / "bus"
            if bus.is_socket():
                env["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path={bus}"
    except (ImportError, KeyError):
        pass
    return env


def _run_as_user(user: str, argv: list[str], *, timeout: float = 15.0) -> bool:
    if os.geteuid() == 0:
        cmd = ["runuser", "-u", user, "--", *argv]
    else:
        cmd = argv
    try:
        r = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=_session_env(user),
            check=False,
        )
        if r.returncode != 0:
            err = (r.stderr or r.stdout or "").strip()
            log.debug("%s failed (%s): %s", argv[0], r.returncode, err)
            return False
        return True
    except (OSError, subprocess.TimeoutExpired) as exc:
        log.debug("user command %s failed: %s", argv[0], exc)
        return False


def blank_displays(*, user: str | None = None) -> bool:
    """Best-effort panel off while session stays up (Plasma / XWayland)."""
    user = user or os.environ.get("ZENBOOK_SESSION_USER") or os.environ.get("USER")
    if not user or user == "root":
        log.warning("blank_displays: no session user")
        return False
    for argv in (
        ["kscreen-doctor", "dpms", "off"],
        ["loginctl", "lock-session"],
    ):
        if shutil_which(argv[0]) and _run_as_user(user, argv):
            log.info("blanked displays via %s", argv[0])
            return True
    return False


def wake_displays(*, user: str | None = None) -> bool:
    user = user or os.environ.get("ZENBOOK_SESSION_USER") or os.environ.get("USER")
    if not user or user == "root":
        return False
    for argv in (
        ["kscreen-doctor", "dpms", "on"],
        ["loginctl", "unlock-session"],
    ):
        if shutil_which(argv[0]) and _run_as_user(user, argv):
            log.info("woke displays via %s", argv[0])
            return True
    return False


def shutil_which(name: str) -> str | None:
    from shutil import which

    return which(name)


def _set_network(stay_up: bool) -> None:
    if stay_up:
        for argv in (["nmcli", "networking", "on"], ["systemctl", "start", "NetworkManager"]):
            if shutil_which(argv[0]):
                try:
                    subprocess.run(argv, capture_output=True, timeout=10, check=False)
                except OSError:
                    pass
        return
    for argv in (["nmcli", "networking", "off"],):
        if shutil_which(argv[0]):
            try:
                subprocess.run(argv, capture_output=True, timeout=10, check=False)
                log.info("networking off via nmcli")
                return
            except OSError:
                pass
    log.debug("network off skipped (nmcli missing)")


def _set_keyboard_brightness(level: int, *, user: str | None = None) -> None:
    """Set keyboard backlight level 0–3 (best effort)."""
    level = max(0, min(3, int(level)))
    argv = ["kb-brightness", str(level)]
    if not shutil_which(argv[0]):
        return
    user = user or os.environ.get("ZENBOOK_SESSION_USER") or os.environ.get("USER")
    if user and user != "root" and os.geteuid() == 0:
        _run_as_user(user, argv, timeout=5)
        return
    try:
        subprocess.run(argv, capture_output=True, timeout=5, check=False)
    except OSError:
        pass


def _restore_session_input(*, user: str | None) -> None:
    """Re-enable KWin pointer touchpads + Duo touch-map after night/DPMS exit."""
    user = user or os.environ.get("ZENBOOK_SESSION_USER") or os.environ.get("USER")
    if not user or user == "root":
        log.warning("restore_session_input: no session user")
        return
    if shutil_which("platform-touchpad"):
        _run_as_user(user, ["platform-touchpad", "restore-kwin"])
    if shutil_which("platform-touch-map"):
        if not _run_as_user(user, ["platform-touch-map", "apply"]):
            _run_as_user(user, ["platform-touch-map", "auto", "--save"])


def _apply_night_extras(
    cfg: dict[str, Any],
    *,
    user: str | None,
    entering: bool,
    lid_closed: bool = False,
) -> None:
    """Screen/kbd/network from profiles.json night section when present."""
    try:
        from zenbook_kb.user_profiles import load

        night = load().get("modes", {}).get("night") or {}
    except Exception:
        night = {}
    if not entering:
        _set_network(bool((night.get("network") or {}).get("stay_up", True)))
        return
    screen = night.get("screen") or {}
    if screen.get("power_off", True):
        blank_displays(user=user)
    if lid_closed:
        # Closed lid: profile awake keyboard level must not override lid dim.
        _set_keyboard_brightness(0, user=user)
    else:
        kbd = night.get("keyboard_backlight") or {}
        level_pct = kbd.get("level_pct")
        if level_pct is not None:
            level = max(0, min(3, round(int(level_pct) / 100 * 3)))
        else:
            level = int(kbd.get("level", 0))
        if not kbd.get("enabled", False) or level <= 0:
            _set_keyboard_brightness(0, user=user)
        else:
            _set_keyboard_brightness(level, user=user)
    net_stay = bool((night.get("network") or {}).get("stay_up", True))
    _set_network(net_stay)


def _on_lid_closed_while_active(*, user: str | None) -> None:
    """Night already active (schedule); lid just closed — enforce off-screen/off-kbd."""
    cfg = effective_night_config()
    if cfg.get("blank_displays", True):
        blank_displays(user=user)
    _set_keyboard_brightness(0, user=user)


def enter_night(
    cfg: dict[str, Any] | None = None,
    *,
    force: bool = False,
    user: str | None = None,
    lid_closed: bool = False,
) -> bool:
    """Apply night profile; snapshot prior fan/thermal state."""
    cfg = effective_night_config(cfg)
    if not cfg.get("enabled") and not force:
        log.info("night mode disabled in config")
        return False
    if is_active():
        log.info("night mode already active")
        if lid_closed:
            _on_lid_closed_while_active(user=user)
        return True
    if cfg.get("require_ac", True) and not read_on_ac() and not force:
        log.info("night mode skipped (on battery)")
        return False

    fan_path = _fan_config_path(cfg)
    fan_cfg = load_fan_config(fan_path)
    snap = capture_snapshot(fan_cfg_path=fan_path)
    write_snapshot(snap)

    profile = str(cfg.get("fan_profile") or "night")
    try:
        apply_profile(fan_cfg, profile)
    except KeyError:
        log.warning("fan profile %r missing; falling back to powersave", profile)
        apply_profile(fan_cfg, "powersave")

    if cfg.get("blank_displays", True):
        blank_displays(user=user)
    _apply_night_extras(cfg, user=user, entering=True, lid_closed=lid_closed)

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    from zenbook_kb.priv import write_sysfs

    write_sysfs(ACTIVE_MARKER, "1\n", allow_ask=False)
    log.info("night mode entered (snapshot %s)", SNAPSHOT_PATH)
    return True


def exit_night(*, force: bool = False, user: str | None = None) -> bool:
    """Restore fan/thermal state saved at night enter."""
    if not is_active() and not force:
        log.info("night mode not active")
        return False

    snap = read_snapshot()
    if snap:
        mode = str(snap.get("fan_control_mode") or "auto")
        try:
            set_control_mode(mode)
        except OSError as exc:
            log.warning("restore fan control mode: %s", exc)
        restore_user_sysfs()
        fan_path = Path(str(snap.get("fan_control_config") or default_fan_control_config()))
        if fan_path.is_file() and mode == "auto":
            fan_cfg = load_fan_config(fan_path)
            state = ControllerState()
            run_event(fan_cfg, "lid_open", state)
    else:
        restore_user_sysfs()

    if user or is_active():
        wake_displays(user=user)
    _restore_session_input(user=user)
    _apply_night_extras({}, user=user, entering=False)

    _remove_state_file(ACTIVE_MARKER)
    log.info("night mode exited")
    return True


def handle_lid(*, closed: bool, user: str | None = None) -> bool:
    if closed:
        return enter_night(user=user, lid_closed=True)
    return exit_night(user=user)


def status_lines(cfg: dict[str, Any] | None = None) -> list[str]:
    cfg = cfg or load_night_config()
    lines = [
        f"config:   {default_config_path()} ({'present' if default_config_path().is_file() else 'missing'})",
        f"enabled:  {bool(cfg.get('enabled'))}",
        f"active:   {'yes' if is_active() else 'no'}",
        f"on_ac:    {read_on_ac()}",
        f"snapshot: {SNAPSHOT_PATH if SNAPSHOT_PATH.is_file() else 'none'}",
    ]
    if is_active() and SNAPSHOT_PATH.is_file():
        snap = read_snapshot()
        if snap:
            lines.append(
                f"saved:    mode={snap.get('fan_control_mode')} "
                f"platform_profile={snap.get('platform_profile')!r}"
            )
    return lines
