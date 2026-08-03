"""Map touchscreens to DRM outputs via KWin D-Bus (Plasma Wayland).

KWin exposes writable ``outputName`` on ``org.kde.KWin.InputDevice``
(``/org/kde/KWin/InputDevice/eventN``). Empty ``outputName`` means
automatic / whole-desktop mapping — on UX8406 Duo that often routes
lower-panel (eDP-2) touches onto the primary. Explicit mapping fixes it
without waiting for a compositor patch.

Stdlib only: uses ``busctl --user`` (no PyQt D-Bus required).
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

log = logging.getLogger("zenbook.touch_map")

KWIN_DEST = "org.kde.KWin"
KWIN_IFACE = "org.kde.KWin.InputDevice"
KWIN_PATH_TMPL = "/org/kde/KWin/InputDevice/{sysname}"
KWIN_MANAGER_PATH = "/org/kde/KWin/InputDevice"
KWIN_MANAGER_IFACE = "org.kde.KWin.InputDeviceManager"

# Resolved once per process — session discovery + kwin probe is not cheap.
_BUSCTL_ENV_CACHE: dict[str, str] | None = None

# Reboot-stable intent (eventN changes). Applied by matching name substring.
DEFAULT_STATE = Path.home() / ".config" / "zenbook-scripts" / "touch-map.json"

# UX8406 ScreenPad Plus (field-validated 2026-07-30):
# ELAN9009 = bottom (eDP-2), ELAN9008 = top (eDP-1) — opposite of name order.
UX8406_PRESET: list[tuple[str, str]] = [
    ("ELAN9008", "eDP-1"),
    ("ELAN9009", "eDP-2"),
]


@dataclass
class KWinInputDevice:
    sysname: str  # event11
    name: str
    touch: bool
    tablet_tool: bool
    output_name: str
    enabled: bool = True

    @property
    def path(self) -> str:
        return KWIN_PATH_TMPL.format(sysname=self.sysname)


@dataclass
class MapRule:
    """Match device name (substring, case-sensitive) → DRM connector name."""

    match: str
    output: str


def _discover_graphical_session_env() -> dict[str, str]:
    """DBus/session env for seat0 (works when invoked via sudo as root)."""
    out: dict[str, str] = {}
    uid: int | None = None
    user: str | None = None
    try:
        proc = subprocess.run(
            ["loginctl", "list-sessions", "--no-legend"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        for line in (proc.stdout or "").splitlines():
            parts = line.split()
            if len(parts) < 3 or "seat0" not in line:
                continue
            try:
                uid = int(parts[1])
            except ValueError:
                continue
            user = parts[2]
            if uid > 0 and user:
                break
    except OSError:
        pass
    if uid is None:
        return out
    runtime = f"/run/user/{uid}"
    out["XDG_RUNTIME_DIR"] = runtime
    bus = Path(runtime) / "bus"
    if bus.is_socket():
        out["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path={bus}"
    for proc_name in ("kwin_wayland", "plasmashell", "kwin_x11", "ksmserver"):
        try:
            pids = subprocess.check_output(
                ["pgrep", "-u", str(uid), "-x", proc_name],
                text=True,
                stderr=subprocess.DEVNULL,
                timeout=3,
            ).split()
        except (OSError, subprocess.CalledProcessError):
            continue
        for pid in pids:
            try:
                raw = Path(f"/proc/{pid}/environ").read_bytes()
            except OSError:
                continue
            for item in raw.split(b"\0"):
                if b"=" not in item:
                    continue
                k, _, v = item.partition(b"=")
                try:
                    key = k.decode()
                    val = v.decode()
                except UnicodeDecodeError:
                    continue
                if key in ("DBUS_SESSION_BUS_ADDRESS", "XDG_RUNTIME_DIR"):
                    out[key] = val
            if "DBUS_SESSION_BUS_ADDRESS" in out:
                break
        if "DBUS_SESSION_BUS_ADDRESS" in out:
            break
    if user:
        out["_ZENBOOK_SEAT_USER"] = user
    return out


def _busctl_env() -> dict[str, str]:
    global _BUSCTL_ENV_CACHE
    if _BUSCTL_ENV_CACHE is not None:
        return _BUSCTL_ENV_CACHE.copy()

    env = os.environ.copy()

    def _kwin_ok(candidate: dict[str, str]) -> bool:
        r = subprocess.run(
            ["busctl", "--user", "status", KWIN_DEST],
            capture_output=True,
            text=True,
            check=False,
            timeout=2,
            env=candidate,
        )
        return r.returncode == 0

    if not _kwin_ok(env):
        env = {**env, **_discover_graphical_session_env()}
        if not _kwin_ok(env):
            seat_user = env.get("_ZENBOOK_SEAT_USER")
            if seat_user and os.geteuid() == 0 and env.get("DBUS_SESSION_BUS_ADDRESS"):
                env["_ZENBOOK_USE_RUNUSER"] = seat_user
    _BUSCTL_ENV_CACHE = env.copy()
    return env.copy()


def _busctl(*args: str, check: bool = False) -> subprocess.CompletedProcess[str]:
    env = _busctl_env()
    seat_user = env.pop("_ZENBOOK_USE_RUNUSER", None)
    env.pop("_ZENBOOK_SEAT_USER", None)
    cmd = ["busctl", "--user", *args]
    if seat_user:
        return subprocess.run(
            ["runuser", "-u", seat_user, "--", *cmd],
            capture_output=True,
            text=True,
            check=check,
            timeout=8,
            env=env,
        )
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=check,
        timeout=8,
        env=env,
    )


def _parse_busctl_variant(line: str) -> Any:
    """Parse ``busctl get-property`` one-line value (s/b/u/…)."""
    line = (line or "").strip()
    if not line:
        return None
    # e.g. s "ELAN9009:00 04F3:425A"  |  b true  |  u 16986
    m = re.match(r'^([a-zA-Z()]+)\s+(.*)$', line)
    if not m:
        return line
    typ, rest = m.group(1), m.group(2).strip()
    if typ == "s":
        if rest.startswith('"') and rest.endswith('"'):
            return rest[1:-1]
        return rest
    if typ == "b":
        return rest.lower() in ("true", "1", "yes")
    if typ in ("u", "i", "n", "q", "x", "t"):
        try:
            return int(rest)
        except ValueError:
            return rest
    return rest


def _parse_busctl_string_array(text: str) -> list[str]:
    """Parse ``busctl get-property`` string array (``as N "a" "b" …``)."""
    return re.findall(r'"([^"]+)"', text or "")


def _device_property(sysname: str, prop: str) -> Any:
    path = KWIN_PATH_TMPL.format(sysname=sysname)
    r = _busctl("get-property", KWIN_DEST, path, KWIN_IFACE, prop)
    if r.returncode != 0:
        return None
    return _parse_busctl_variant(r.stdout)


def kwin_available() -> bool:
    r = _busctl("status", KWIN_DEST)
    return r.returncode == 0


def list_input_sysnames(limit: int = 64) -> list[str]:
    """Discover eventN nodes registered with KWin (one D-Bus call)."""
    r = _busctl(
        "get-property",
        KWIN_DEST,
        KWIN_MANAGER_PATH,
        KWIN_MANAGER_IFACE,
        "devicesSysNames",
    )
    if r.returncode == 0:
        names = _parse_busctl_string_array(r.stdout or "")
        if names:
            return names[:limit]
    # Fallback: only nodes that exist on disk (never probe event0..event63 blindly).
    found: list[str] = []
    for node in sorted(Path("/dev/input").glob("event*")):
        sysname = node.name
        path = KWIN_PATH_TMPL.format(sysname=sysname)
        probe = _busctl("get-property", KWIN_DEST, path, KWIN_IFACE, "name")
        if probe.returncode == 0 and (probe.stdout or "").strip():
            found.append(sysname)
        if len(found) >= limit:
            break
    return found


def get_device(sysname: str) -> KWinInputDevice | None:
    path = KWIN_PATH_TMPL.format(sysname=sysname)
    name = _parse_busctl_variant(
        _busctl("get-property", KWIN_DEST, path, KWIN_IFACE, "name").stdout
    )
    if not isinstance(name, str) or not name:
        return None
    touch = bool(
        _parse_busctl_variant(
            _busctl("get-property", KWIN_DEST, path, KWIN_IFACE, "touch").stdout
        )
    )
    r_tab = _busctl("get-property", KWIN_DEST, path, KWIN_IFACE, "tabletTool")
    if r_tab.returncode == 0:
        tablet = bool(_parse_busctl_variant(r_tab.stdout))
    else:
        tablet = "stylus" in name.lower() or "pen" in name.lower()
    out = _parse_busctl_variant(
        _busctl("get-property", KWIN_DEST, path, KWIN_IFACE, "outputName").stdout
    )
    en = _parse_busctl_variant(
        _busctl("get-property", KWIN_DEST, path, KWIN_IFACE, "enabled").stdout
    )
    return KWinInputDevice(
        sysname=sysname,
        name=name,
        touch=touch,
        tablet_tool=bool(tablet),
        output_name=str(out or ""),
        enabled=bool(en) if en is not None else True,
    )


def list_touch_devices(*, include_stylus: bool = True) -> list[KWinInputDevice]:
    out: list[KWinInputDevice] = []
    for sysname in list_input_sysnames():
        dev = get_device(sysname)
        if not dev:
            continue
        if dev.touch or (include_stylus and dev.tablet_tool):
            out.append(dev)
    return out


def set_device_enabled(sysname: str, enabled: bool) -> None:
    path = KWIN_PATH_TMPL.format(sysname=sysname)
    r = _busctl(
        "set-property",
        KWIN_DEST,
        path,
        KWIN_IFACE,
        "enabled",
        "b",
        "true" if enabled else "false",
    )
    if r.returncode != 0:
        err = (r.stderr or r.stdout or "").strip()
        raise RuntimeError(f"set enabled failed for {sysname}: {err}")


def find_kwin_filter_sysname(*, name_hint: str | None = None) -> str | None:
    """Return KWin sysname (eventN) for the live-filter uinput node, if present."""
    hint_base = (name_hint or "").replace(" (filter)", "").strip()
    for cand in list_input_sysnames():
        name = _device_property(cand, "name")
        if not isinstance(name, str) or "(filter)" not in name:
            continue
        if hint_base and hint_base not in name:
            continue
        return cand
    return None


def release_kwin_after_live_filter(
    *,
    touchpad_path: Path | str | None = None,
    name_hint: str | None = None,
    filter_sysname: str | None = None,
    phase: str = "full",
) -> bool:
    """Hand the pointer back to the physical pad after live-filter teardown.

    ``phase=pre`` — disable the virtual (filter) pointer while uinput still exists.
    ``phase=post`` — nudge the physical pad after uinput is destroyed.
    ``phase=full`` — both (post-destroy path).
    """
    if not kwin_available():
        return False
    phys = Path(touchpad_path).name if touchpad_path else None
    changed = False

    if phase in ("pre", "full"):
        fs = filter_sysname or find_kwin_filter_sysname(name_hint=name_hint)
        if fs:
            try:
                set_device_enabled(fs, False)
                changed = True
                time.sleep(0.03)
            except RuntimeError as exc:
                log.warning("%s", exc)

    if phase in ("post", "full") and phys:
        try:
            set_device_enabled(phys, False)
            set_device_enabled(phys, True)
            changed = True
        except RuntimeError as exc:
            log.warning("%s", exc)
    return changed


def restore_kwin_touchpad_after_filter(
    *,
    touchpad_path: Path | str | None = None,
    name_hint: str | None = None,
    filter_sysname: str | None = None,
) -> bool:
    """Compatibility wrapper — full post-teardown KWin release."""
    return release_kwin_after_live_filter(
        touchpad_path=touchpad_path,
        name_hint=name_hint,
        filter_sysname=filter_sysname,
        phase="full",
    )


def set_output_name(sysname: str, output: str) -> None:
    path = KWIN_PATH_TMPL.format(sysname=sysname)
    r = _busctl(
        "set-property",
        KWIN_DEST,
        path,
        KWIN_IFACE,
        "outputName",
        "s",
        output,
    )
    if r.returncode != 0:
        err = (r.stderr or r.stdout or "").strip()
        raise RuntimeError(f"set outputName failed for {sysname}: {err}")


def list_drm_outputs() -> list[str]:
    """Connector names from /sys/class/drm (card*-NAME)."""
    base = Path("/sys/class/drm")
    names: list[str] = []
    if not base.is_dir():
        return names
    for p in sorted(base.iterdir()):
        m = re.match(r"^card\d+-(.+)$", p.name)
        if not m:
            continue
        status = (p / "status").read_text(encoding="utf-8", errors="replace").strip()
        if status == "connected":
            names.append(m.group(1))
    return names


def _dmi_product() -> str:
    for path in (
        Path("/sys/class/dmi/id/product_name"),
        Path("/sys/devices/virtual/dmi/id/product_name"),
    ):
        try:
            return path.read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            continue
    return ""


def preset_rules_for_machine() -> list[MapRule]:
    product = _dmi_product().upper()
    if "UX8406" in product or "UX8402" in product:
        return [MapRule(m, o) for m, o in UX8406_PRESET]
    # Generic: pair sorted touchscreens (not stylus) to sorted eDP*
    return []


def load_state(path: Path | None = None) -> dict[str, Any]:
    p = path or DEFAULT_STATE
    if not p.is_file():
        return {"version": 1, "rules": []}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"version": 1, "rules": []}
    if not isinstance(raw, dict):
        return {"version": 1, "rules": []}
    raw.setdefault("version", 1)
    raw.setdefault("rules", [])
    return raw


def save_state(state: dict[str, Any], path: Path | None = None) -> Path:
    p = path or DEFAULT_STATE
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    return p


def rules_from_state(state: dict[str, Any]) -> list[MapRule]:
    rules: list[MapRule] = []
    for item in state.get("rules") or []:
        if not isinstance(item, dict):
            continue
        match = str(item.get("match") or "").strip()
        output = str(item.get("output") or "").strip()
        if match and output:
            rules.append(MapRule(match, output))
    return rules


def auto_rules(
    devices: list[KWinInputDevice] | None = None,
    outputs: list[str] | None = None,
) -> list[MapRule]:
    """Build mapping rules: machine preset, else zip touchscreens ↔ eDP*."""
    preset = preset_rules_for_machine()
    if preset:
        return preset
    devices = devices if devices is not None else list_touch_devices(include_stylus=False)
    outputs = outputs if outputs is not None else list_drm_outputs()
    edp = sorted(o for o in outputs if o.startswith("eDP"))
    pads = sorted(
        (d for d in devices if d.touch and "stylus" not in d.name.lower()),
        key=lambda d: d.name,
    )
    return [MapRule(d.name, edp[i]) for i, d in enumerate(pads) if i < len(edp)]


def apply_rules(
    rules: list[MapRule],
    *,
    include_stylus: bool = True,
    dry_run: bool = False,
) -> list[dict[str, str]]:
    """Apply rules to matching KWin devices. Stylus inherits sibling panel map."""
    devices = list_touch_devices(include_stylus=include_stylus)
    applied: list[dict[str, str]] = []
    name_to_output: dict[str, str] = {}

    def _apply_one(dev: KWinInputDevice, output: str) -> None:
        row = {"sysname": dev.sysname, "name": dev.name, "output": output}
        if dry_run:
            row["dry_run"] = "1"
            applied.append(row)
            return
        set_output_name(dev.sysname, output)
        applied.append(row)

    # Touchscreens first
    for rule in rules:
        for dev in devices:
            if not dev.touch:
                continue
            if rule.match not in dev.name:
                continue
            _apply_one(dev, rule.output)
            name_to_output[dev.name] = rule.output
            stem = re.sub(r"\s+Stylus$", "", dev.name)
            name_to_output[stem] = rule.output

    if not include_stylus:
        return applied

    for dev in devices:
        if not (dev.tablet_tool or "stylus" in dev.name.lower()):
            continue
        stem = re.sub(r"\s+Stylus$", "", dev.name)
        want = name_to_output.get(stem)
        if not want:
            for rule in rules:
                if rule.match in dev.name:
                    want = rule.output
                    break
        if want:
            _apply_one(dev, want)
    return applied


def format_status() -> str:
    lines: list[str] = []
    if not kwin_available():
        return "KWin D-Bus not available (need Plasma Wayland session)"
    outs = list_drm_outputs()
    lines.append(f"drm_outputs: {', '.join(outs) or '(none)'}")
    lines.append(f"dmi: {_dmi_product() or '(unknown)'}")
    preset = preset_rules_for_machine()
    if preset:
        lines.append(
            "preset: "
            + ", ".join(f"{r.match}→{r.output}" for r in preset)
        )
    lines.append("devices:")
    for dev in list_touch_devices(include_stylus=True):
        kind = "touch" if dev.touch else ("stylus" if dev.tablet_tool else "?")
        mapped = dev.output_name or "(auto/empty)"
        lines.append(f"  {dev.sysname:8} [{kind:6}] {mapped:12}  {dev.name}")
    return "\n".join(lines)


def devices_as_dicts() -> list[dict[str, Any]]:
    return [asdict(d) for d in list_touch_devices(include_stylus=True)]
