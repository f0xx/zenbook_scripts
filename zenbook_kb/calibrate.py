"""Interactive hotkey calibration for Zenbook Duo detachable keyboard.

Walks through plain-F vs Fn+F combinations, records events from all evdev
nodes (and optional hidraw), and writes a calibration file plus suggested
conf.d snippets.

Requires root (sudo) so devices can be grabbed exclusively and queues drained.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import pwd
import select
import struct
import sys
import termios
import time
import tty
from dataclasses import asdict, dataclass, field
from pathlib import Path

from zenbook_kb.detect import _find_hidraw_by_product
from zenbook_kb.hotkey import (
    EV_KEY,
    INPUT_EVENT_FMT,
    INPUT_EVENT_SIZE,
    _event_metadata,
    _interface_number,
    _usb_product_id,
    find_hotkey_devices,
)
from zenbook_kb.keycodes import key_label
from zenbook_kb.mappings import DmiInfo
from zenbook_kb.protocol import DEFAULT_USB_PRODUCT_ID, DEFAULT_USB_VENDOR_ID

EVIOCGRAB = 0x40044590
KEY_FN = 464
KEY_AUTO_REPEAT = 2
MODIFIER_CODES = frozenset({KEY_FN, 125, 126, 29, 42, 54, 97})  # FN, L/R META, shifts, RCTRL


class _TerminalSession:
    """Isolate the tty from keyboard echo while evdev nodes are grabbed."""

    def __init__(self) -> None:
        self._fd: int | None = None
        self._old: list | None = None
        self.active = False

    def __enter__(self) -> _TerminalSession:
        if not sys.stdin.isatty():
            return self
        self._fd = sys.stdin.fileno()
        self._old = termios.tcgetattr(self._fd)
        new = termios.tcgetattr(self._fd)
        new[tty.LFLAG] &= ~(termios.ECHO | termios.ICANON | termios.ISIG | termios.IEXTEN)
        new[tty.IFLAG] &= ~(
            termios.IXON | termios.ICRNL | termios.BRKINT | termios.INPCK | termios.ISTRIP
        )
        new[tty.CC][termios.VMIN] = 0
        new[tty.CC][termios.VTIME] = 0
        termios.tcsetattr(self._fd, termios.TCSADRAIN, new)
        self.active = True
        self.drain()
        return self

    def __exit__(self, *_exc: object) -> None:
        if self._old is not None and self._fd is not None:
            termios.tcsetattr(self._fd, termios.TCSADRAIN, self._old)
        self.active = False

    def drain(self) -> int:
        if self._fd is None:
            return 0
        drained = 0
        while select.select([sys.stdin], [], [], 0)[0]:
            chunk = os.read(self._fd, 4096)
            if not chunk:
                break
            drained += len(chunk)
        return drained

    def poll_skip(self) -> bool:
        """True when the user typed 's' to skip the current step."""
        if self._fd is None:
            return False
        if not select.select([sys.stdin], [], [], 0)[0]:
            return False
        ch = os.read(self._fd, 1)
        if ch == b"s":
            self.drain()
            return True
        self.drain()
        return False


def _is_zero_hidraw(data: bytes) -> bool:
    return not data or not any(data)


def _target_account() -> tuple[str, Path, int | None, int | None]:
    """Invoking user account (not root) when running under sudo."""
    env_home = os.environ.get("ZENBOOK_CALIB_HOME")
    env_user = os.environ.get("ZENBOOK_CALIB_USER")
    if env_home:
        home = Path(env_home).expanduser()
        if env_user:
            try:
                pw = pwd.getpwnam(env_user)
                return env_user, home, pw.pw_uid, pw.pw_gid
            except KeyError:
                pass
        return env_user or "unknown", home, None, None

    if os.geteuid() == 0:
        for user in (os.environ.get("SUDO_USER"), os.environ.get("LOGNAME")):
            if user and user != "root":
                try:
                    pw = pwd.getpwnam(user)
                    return user, Path(pw.pw_dir), pw.pw_uid, pw.pw_gid
                except KeyError:
                    continue
        sudo_uid = os.environ.get("SUDO_UID")
        if sudo_uid:
            try:
                pw = pwd.getpwuid(int(sudo_uid))
                if pw.pw_name != "root":
                    return pw.pw_name, Path(pw.pw_dir), pw.pw_uid, pw.pw_gid
            except (KeyError, ValueError):
                pass

    try:
        pw = pwd.getpwuid(os.getuid())
        return pw.pw_name, Path(pw.pw_dir), pw.pw_uid, pw.pw_gid
    except KeyError:
        return os.environ.get("USER", "unknown"), Path.home(), os.getuid(), os.getgid()


def calib_dir() -> Path:
    _user, home, _uid, _gid = _target_account()
    return home / ".config" / "zenbook-scripts" / "calibration"


def reexec_with_sudo_if_needed(argv: list[str] | None = None) -> None:
    """Re-invoke this script under sudo -E with the caller's HOME preserved."""
    if os.geteuid() == 0:
        return
    argv = list(sys.argv if argv is None else argv)
    _reexec_calibrate_py(argv[1:])


def reexec_calibrate(cal_args: list[str] | None = None) -> None:
    """Re-invoke calibrate.py under sudo -E (for kb-brightness-hotkeys --calibrate)."""
    if os.geteuid() == 0:
        return
    _reexec_calibrate_py(list(cal_args or []))


def _reexec_calibrate_py(cal_args: list[str]) -> None:
    cal_py = str(Path(__file__).resolve())
    home = os.environ.get("HOME", "")
    user = os.environ.get("USER") or os.environ.get("LOGNAME") or ""
    env = [
        f"PYTHONPATH={os.environ.get('PYTHONPATH', '')}",
        f"HOME={home}",
        f"ZENBOOK_CALIB_USER={user}",
        f"ZENBOOK_CALIB_HOME={home}",
    ]
    os.execvp("sudo", ["sudo", "-E", "env", *env, sys.executable, cal_py, *cal_args])


def _chown_tree(path: Path, uid: int, gid: int) -> None:
    if path.is_dir():
        for child in sorted(path.rglob("*"), key=lambda p: len(p.parts), reverse=True):
            try:
                os.chown(child, uid, gid)
            except OSError:
                pass
    try:
        os.chown(path, uid, gid)
    except OSError:
        pass

DEFAULT_STEPS: list[tuple[str, str]] = [
    ("F1", "Tap F1 once and release (plain F1, no Fn)"),
    ("Fn+F1", "Tap Fn+F1 once and release"),
    ("F2", "Tap F2 once and release"),
    ("Fn+F2", "Tap Fn+F2 once and release"),
    ("F3", "Tap F3 once and release"),
    ("Fn+F3", "Tap Fn+F3 once and release"),
    ("F4", "Tap F4 once and release"),
    ("Fn+F4", "Tap Fn+F4 once and release (keyboard backlight)"),
    ("F5", "Tap F5 once and release"),
    ("Fn+F5", "Tap Fn+F5 once and release"),
    ("F6", "Tap F6 once and release"),
    ("Fn+F6", "Tap Fn+F6 once and release"),
    ("F7", "Tap F7 once and release"),
    ("Fn+F7", "Tap Fn+F7 once and release"),
    ("F8", "Tap F8 once and release"),
    ("Fn+F8", "Tap Fn+F8 once and release"),
    ("F9", "Tap F9 once and release"),
    ("Fn+F9", "Tap Fn+F9 once and release"),
    ("F10", "Tap F10 once and release"),
    ("Fn+F10", "Tap Fn+F10 once and release"),
    ("F12", "Tap F12 once and release"),
    ("Fn+F12", "Tap Fn+F12 / Asus key once and release"),
]

QUICK_STEP_IDS = frozenset({
    "F1", "Fn+F1", "F2", "Fn+F2", "F3", "Fn+F3", "F4", "Fn+F4", "F12", "Fn+F12",
})

# Evdev code → suggested hotkey action (union across fn-lock modes).
_CODE_ACTIONS: dict[str, str] = {
    "KEY_KBDILLUMTOGGLE": "kb-brightness:toggle",
    "KEY_KBDILLUMDOWN": "kb-brightness:-1",
    "KEY_KBDILLUMUP": "kb-brightness:+1",
    "KEY_BRIGHTNESSDOWN": "display-brightness:down",
    "KEY_BRIGHTNESSUP": "display-brightness:up",
    "KEY_MICMUTE": "audio:mic-mute",
    "KEY_MUTE": "# audio: mute (often handled by desktop — bind if hotkey iface only)",
    "KEY_VOLUMEDOWN": "# audio: volume down (desktop may own on if00/if03)",
    "KEY_VOLUMEUP": "# audio: volume up (desktop may own on if00/if03)",
    "KEY_WLAN": "rfkill:wlan",
    "KEY_BLUETOOTH": "rfkill:bluetooth",
    "KEY_SWITCHVIDEOMODE": "# display: screen mapping (Plasma may own)",
    "KEY_PROG1": "log",
    "KEY_PROG2": "log",
    "KEY_PROG3": "log",
    "KEY_PROG4": "log",
}

# Plain F-keys — passthrough to apps unless they emit a hardware code above.
_PLAIN_FKEYS = frozenset({f"KEY_F{n}" for n in range(1, 13)})


@dataclass
class CapturedEvent:
    source: str
    code: int
    name: str
    value: int
    iface: str = ""
    device_name: str = ""
    offset_ms: int = 0
    tag: str = "burst"  # burst | stale | modifier


@dataclass
class StepCapture:
    step_id: str
    prompt: str
    raw_events: list[CapturedEvent] = field(default_factory=list)
    events: list[CapturedEvent] = field(default_factory=list)
    skipped: bool = False
    fn_lock_mode: str = ""


def _require_root() -> None:
    if os.geteuid() == 0:
        return
    print(
        "Calibration requires root (sudo) for exclusive /dev/input access.\n"
        "  sudo kb-calibrate-hotkeys --quick\n"
        "Stop the hotkey service first: sudo rc-service zenbook-kb-hotkeys stop",
        file=sys.stderr,
    )
    raise SystemExit(1)


def _discover_evdev_sources(*, include_main: bool = True) -> list[tuple[Path, dict[str, str]]]:
    """All Zenbook-related evdev nodes with metadata."""
    candidates: list[tuple[Path, dict[str, str]]] = []
    seen: set[Path] = set()

    def add(event_dir: Path) -> None:
        dev = Path("/dev/input") / event_dir.name
        if not dev.exists() or dev in seen:
            return
        caps = event_dir / "device" / "capabilities" / "key"
        if not caps.is_file():
            return
        meta = _event_metadata(event_dir)
        if "Mouse" in meta["name"] or "Touchpad" in meta["name"]:
            return
        seen.add(dev)
        candidates.append((dev, meta))

    for event_dir in sorted(Path("/sys/class/input").glob("event*")):
        name_path = event_dir / "device" / "name"
        if not name_path.is_file():
            continue
        name = name_path.read_text().strip()
        product = _usb_product_id(event_dir)
        iface = _interface_number(event_dir)
        if product in ("1b2c", "1bf2"):
            add(event_dir)
            continue
        if name in ("Asus WMI hotkeys",) or "Zenbook Duo" in name or name == "Asus Keyboard":
            add(event_dir)
            continue
        if include_main and name == "Asus Keyboard" and iface == "00":
            add(event_dir)

    for dev in find_hotkey_devices():
        if dev in seen:
            continue
        event_dir = Path("/sys/class/input") / dev.name
        if event_dir.is_dir():
            add(event_dir)

    has_if04 = any(
        meta.get("iface") == "04" and meta.get("product") in ("1b2c", "1bf2", "1b2d")
        for _dev, meta in candidates
    )
    sources: list[tuple[Path, dict[str, str]]] = []
    for dev, meta in candidates:
        if (
            has_if04
            and meta.get("iface") == "03"
            and meta.get("product") in ("1b2c", "1bf2", "1b2d")
        ):
            continue
        sources.append((dev, meta))

    return sorted(sources, key=lambda x: (x[1].get("iface", "99"), x[0].name))


def _discover_hidraw_sources() -> list[tuple[Path, str]]:
    """Vendor hotkey hidraw only (90-byte rdesc / USB if04), not every 1b2c node."""
    out: list[tuple[Path, str]] = []
    dev = _find_hidraw_by_product(DEFAULT_USB_VENDOR_ID, DEFAULT_USB_PRODUCT_ID, 90)
    if dev is None:
        return out
    hidraw_sysfs = Path("/sys/class/hidraw") / dev.name
    uevent = hidraw_sysfs / "device" / "uevent"
    text = uevent.read_text().strip() if uevent.is_file() else ""
    out.append((dev, text))
    return out


def _format_source(dev: Path, meta: dict[str, str]) -> str:
    iface = meta.get("iface", "?")
    return f"evdev:{dev.name}:if{iface}:{meta.get('name', '?')[:40]}"


def _poll_fds(
    fds: dict[int, tuple[str, dict[str, str] | None]],
    *,
    t0: float | None = None,
) -> list[CapturedEvent]:
    """Non-blocking read; return newly parsed events."""
    out: list[CapturedEvent] = []
    readable, _, _ = select.select(list(fds), [], [], 0)
    now = time.monotonic()
    for fd in readable:
        src, meta = fds[fd]
        try:
            data = os.read(fd, 65536)
        except OSError:
            continue
        if not data:
            continue

        if meta is None:
            if _is_zero_hidraw(data):
                continue
            out.append(
                CapturedEvent(
                    source=src,
                    code=0,
                    name=f"HIDRAW:{data.hex()}",
                    value=len(data),
                    offset_ms=int((now - t0) * 1000) if t0 else 0,
                )
            )
            continue

        for off in range(0, len(data), INPUT_EVENT_SIZE):
            chunk = data[off : off + INPUT_EVENT_SIZE]
            if len(chunk) != INPUT_EVENT_SIZE:
                continue
            _sec, _usec, etype, code, val = struct.unpack(INPUT_EVENT_FMT, chunk)
            if etype != EV_KEY:
                continue
            if val == KEY_AUTO_REPEAT:
                continue
            out.append(
                CapturedEvent(
                    source=src,
                    code=code,
                    name=key_label(code),
                    value=val,
                    iface=meta.get("iface", ""),
                    device_name=meta.get("name", ""),
                    offset_ms=int((now - t0) * 1000) if t0 else 0,
                )
            )
    return out


def _drain_fds(fds: dict[int, tuple[str, dict[str, str] | None]], *, rounds: int = 8) -> int:
    """Discard queued kernel events before a step."""
    drained = 0
    for _ in range(rounds):
        batch = _poll_fds(fds)
        if not batch:
            time.sleep(0.02)
            batch = _poll_fds(fds)
        if not batch:
            break
        drained += len(batch)
    return drained


def _wait_idle(
    fds: dict[int, tuple[str, dict[str, str] | None]],
    *,
    idle_ms: int = 450,
    max_wait_s: float = 4.0,
    term: _TerminalSession | None = None,
) -> tuple[bool, bool]:
    """Wait until no new key-down for idle_ms. Returns (idle_ok, skipped)."""
    last = time.monotonic()
    deadline = last + max_wait_s
    while time.monotonic() < deadline:
        if term and term.poll_skip():
            return False, True
        batch = _poll_fds(fds)
        new_press = any(
            not ev.name.startswith("HIDRAW") and ev.value == 1 for ev in batch
        )
        if new_press:
            last = time.monotonic()
            continue
        if (time.monotonic() - last) * 1000 >= idle_ms:
            return True, False
        time.sleep(0.03)
    return False, False


def _wait_for_release(
    fds: dict[int, tuple[str, dict[str, str] | None]],
    trigger: tuple[str, int],
    *,
    term: _TerminalSession | None = None,
    max_wait_s: float = 2.0,
) -> bool:
    """Wait until the trigger key is released on the same source."""
    src, code = trigger
    deadline = time.monotonic() + max_wait_s
    while time.monotonic() < deadline:
        if term and term.poll_skip():
            return False
        for ev in _poll_fds(fds):
            if ev.source == src and ev.code == code and ev.value == 0:
                return True
        time.sleep(0.01)
    return False


def _source_rank(step_id: str, ev: CapturedEvent) -> tuple[int, int]:
    """Lower is better when picking the primary key-down."""
    fn_step = step_id.startswith("Fn+")
    iface = ev.iface
    if fn_step:
        order = {"04": 0, "": 1, "07": 2, "03": 5, "00": 6}
    else:
        order = {"00": 0, "03": 1, "": 2, "04": 5, "07": 6}
    return (order.get(iface, 9), ev.offset_ms)


def _filter_burst(step_id: str, raw: list[CapturedEvent]) -> list[CapturedEvent]:
    """Pick meaningful key-down events from a capture burst."""
    if not raw:
        return []

    # Drop leading key-ups (stale releases from previous step).
    trimmed = list(raw)
    while trimmed and trimmed[0].value == 0 and not trimmed[0].name.startswith("HIDRAW"):
        trimmed[0].tag = "stale"
        trimmed = trimmed[1:]

    downs: list[CapturedEvent] = []
    seen: set[tuple[str, int]] = set()
    for ev in trimmed:
        if ev.name.startswith("HIDRAW"):
            ev.tag = "stale"
            continue
        if ev.value != 1:
            continue
        if ev.code in MODIFIER_CODES:
            ev.tag = "modifier"
            continue
        key = (ev.source, ev.code)
        if key in seen:
            continue
        seen.add(key)
        downs.append(ev)

    downs.sort(key=lambda e: _source_rank(step_id, e))
    return downs


def _capture_step(
    fds: dict[int, tuple[str, dict[str, str] | None]],
    step_id: str,
    *,
    timeout_s: float = 15.0,
    burst_ms: int = 800,
    idle_ms: int = 450,
    release_settle_ms: int = 250,
    term: _TerminalSession | None = None,
) -> tuple[list[CapturedEvent], list[CapturedEvent], bool]:
    """Drain queue, wait idle, capture until key-up, return (raw, filtered, skipped)."""
    if term:
        term.drain()

    drained = _drain_fds(fds)
    if drained:
        print(f"  (drained {drained} queued event(s))")

    idle_ok, skipped = _wait_idle(fds, idle_ms=idle_ms, term=term)
    if skipped:
        return [], [], True
    if not idle_ok:
        print("  (warn: keys still down — release before tapping)")

    deadline = time.monotonic() + timeout_s
    raw: list[CapturedEvent] = []
    t0: float | None = None
    trigger: tuple[str, int] | None = None
    released = False

    while time.monotonic() < deadline:
        if term and term.poll_skip():
            return raw, _filter_burst(step_id, raw), True
        batch = _poll_fds(fds, t0=t0)
        if not batch and t0 is None:
            time.sleep(0.02)
            continue

        for ev in batch:
            if t0 is None:
                if ev.name.startswith("HIDRAW"):
                    continue
                if ev.value != 1 or ev.code in MODIFIER_CODES:
                    ev.tag = "stale"
                    raw.append(ev)
                    continue
                t0 = time.monotonic()
                trigger = (ev.source, ev.code)
                ev.offset_ms = 0
                raw.append(ev)
                continue

            ev.offset_ms = int((time.monotonic() - t0) * 1000)
            raw.append(ev)
            if (
                trigger
                and not ev.name.startswith("HIDRAW")
                and ev.source == trigger[0]
                and ev.code == trigger[1]
                and ev.value == 0
            ):
                released = True
                break

        if released:
            break
        if t0 is not None and (time.monotonic() - t0) * 1000 >= burst_ms:
            print("  (warn: no key-up seen — release the key)")
            break

    if trigger and not released:
        if not _wait_for_release(fds, trigger, term=term):
            print("  (warn: still waiting for key release)")

    _drain_fds(fds)
    settle_ok, skipped = _wait_idle(
        fds, idle_ms=release_settle_ms, max_wait_s=2.0, term=term
    )
    if skipped:
        return raw, _filter_burst(step_id, raw), True
    if not settle_ok:
        print("  (warn: release the key before the next step)")

    filtered = _filter_burst(step_id, raw)
    return raw, filtered, False


def _open_sources(
    evdev_sources: list[tuple[Path, dict[str, str]]],
    hidraw_sources: list[tuple[Path, str]],
    *,
    grab: bool,
) -> dict[int, tuple[str, dict[str, str] | None]]:
    fds: dict[int, tuple[str, dict[str, str] | None]] = {}
    for dev, meta in evdev_sources:
        try:
            fd = os.open(dev, os.O_RDONLY | os.O_NONBLOCK)
            if grab:
                try:
                    fcntl.ioctl(fd, EVIOCGRAB, 1)
                except OSError as exc:
                    print(f"warn: could not grab {dev}: {exc}", file=sys.stderr)
            fds[fd] = (_format_source(dev, meta), meta)
        except OSError as exc:
            print(f"skip {dev}: {exc}", file=sys.stderr)
    for dev, _ in hidraw_sources:
        try:
            fd = os.open(dev, os.O_RDONLY | os.O_NONBLOCK)
            fds[fd] = (f"hidraw:{dev.name}", None)
        except OSError as exc:
            print(f"skip {dev}: {exc}", file=sys.stderr)
    return fds


def _close_fds(fds: dict[int, tuple[str, dict[str, str] | None]], *, grab: bool) -> None:
    for fd in fds:
        if grab:
            try:
                fcntl.ioctl(fd, EVIOCGRAB, 0)
            except OSError:
                pass
        os.close(fd)


def _print_sources(sources: list[tuple[Path, dict[str, str]]], hidraws: list[tuple[Path, str]]) -> None:
    print("Listening on:")
    for dev, meta in sources:
        print(f"  {_format_source(dev, meta)}")
    for dev, _uevent in hidraws:
        print(f"  hidraw:{dev.name}")
    print()


def _print_step_events(raw: list[CapturedEvent], filtered: list[CapturedEvent]) -> None:
    if not raw:
        print("  (no events)")
        return
    primary_keys = {(e.source, e.code) for e in filtered if not e.name.startswith("HIDRAW")}
    for ev in raw:
        mark = " "
        if ev.tag == "stale":
            mark = "~"
        elif ev.tag == "modifier":
            mark = "m"
        elif (ev.source, ev.code) in primary_keys and ev.value == 1:
            mark = "*"
        action = "down" if ev.value == 1 else "up"
        if ev.name.startswith("HIDRAW"):
            action = f"{ev.value}B"
        print(
            f"  {mark} {ev.offset_ms:4d}ms {ev.source}: {ev.name} "
            f"({ev.code}) {action}"
        )
    if filtered:
        labels = [
            f"{e.source}→{e.name}"
            for e in filtered
            if not e.name.startswith("HIDRAW")
        ]
        if labels:
            print(f"  → primary: {', '.join(labels)}")


def _warn_missing_if04(evdev_sources: list[tuple[Path, dict[str, str]]], board: str) -> None:
    if not board.upper().startswith("UX8406"):
        return
    if any(meta.get("iface") == "04" for _d, meta in evdev_sources):
        return
    print(
        "warn: USB interface 04 (hid-asus vendor hotkeys) not found.\n"
        "      Fn+ keys may be silent until hid-asus is loaded and rebound.\n"
        "      See kernel/README.md — insmod + rebind-hid-asus.sh",
        file=sys.stderr,
    )


def _prompt_fn_lock_toggle(term: _TerminalSession, target_mode: str) -> None:
    print("══ Fn-lock toggle ══")
    print(f"Press Fn+Esc once to switch fn-lock, then test mode {target_mode}.")
    if not term.active or term._fd is None:
        print("(non-interactive — pause 5s)")
        time.sleep(5)
        return
    print("Press Enter here when ready (30s timeout)…")
    deadline = time.monotonic() + 30.0
    while time.monotonic() < deadline:
        term.drain()
        if select.select([sys.stdin], [], [], 0.2)[0]:
            ch = os.read(term._fd, 1)
            if ch in (b"\n", b"\r"):
                print()
                return
        time.sleep(0.05)
    print("(timeout — continuing)\n")


def _suggest_conf(captures: list[StepCapture], dmi: DmiInfo) -> str:
    by_mode: dict[str, list[StepCapture]] = {}
    for cap in captures:
        by_mode.setdefault(cap.fn_lock_mode or "single", []).append(cap)
    return _suggest_conf_union(by_mode, dmi)


def _suggest_conf_union(
    by_mode: dict[str, list[StepCapture]],
    dmi: DmiInfo,
) -> str:
    """Build union bindings: same evdev code in mode A or B → one action."""
    lines = [
        f"# Suggested hotkeys — union of fn-lock modes ({dmi.board_name or 'unknown'})",
        "# Generated by: kb-calibrate-hotkeys --dual-fn-lock",
        "# Copy uncommented lines into ~/.config/zenbook-scripts/zenbook-hotkeys.conf",
        "# Plain KEY_F1..F12 are intentionally omitted (passthrough to desktop).",
        "# Bind by evdev CODE so both fn-lock states hit the same action.",
        "",
    ]

    # Per-mode matrix for documentation
    for mode in sorted(by_mode):
        if not mode:
            continue
        lines.append(f"# ── fn-lock mode {mode} ──")
        for cap in by_mode[mode]:
            if cap.skipped or not cap.events:
                lines.append(f"#   {cap.step_id}: (no capture)")
                continue
            ev = cap.events[0]
            if ev.name.startswith("KEY_"):
                lines.append(
                    f"#   {cap.step_id}: {ev.source} → {ev.name} ({ev.code})"
                )
        lines.append("")

    # Union: code → {modes, steps, sources}
    union: dict[str, dict[str, object]] = {}
    for mode, caps in by_mode.items():
        for cap in caps:
            if cap.skipped:
                continue
            for ev in cap.events:
                if not ev.name.startswith("KEY_") or ev.value != 1:
                    continue
                if ev.name in _PLAIN_FKEYS:
                    continue
                entry = union.setdefault(
                    ev.name,
                    {"modes": set(), "steps": set(), "sources": set(), "code": ev.code},
                )
                entry["modes"].add(mode or "?")
                entry["steps"].add(cap.step_id)
                entry["sources"].add(ev.source)

    lines.append("[hotkeys]")
    if not union:
        lines.append("# (no union codes — rerun with sideload + both fn-lock modes)")
    else:
        for name in sorted(union):
            entry = union[name]
            modes = ",".join(sorted(entry["modes"]))
            steps = ",".join(sorted(entry["steps"]))
            src = next(iter(entry["sources"]))
            action = _CODE_ACTIONS.get(name, "log")
            lines.append(f"# modes {modes}: {steps} @ {src}")
            if action.startswith("#"):
                lines.append(f"# {name} = {action[2:].strip()}")
            else:
                lines.append(f"{name} = {action}")

    lines.append("")
    return "\n".join(lines)


def _print_dual_analysis(by_mode: dict[str, list[StepCapture]]) -> None:
    print("\n── Dual fn-lock analysis ──")
    for key in ("F4", "Fn+F4"):
        codes: dict[str, str] = {}
        for mode, caps in by_mode.items():
            cap = next((c for c in caps if c.step_id == key and c.events), None)
            if cap and cap.events:
                codes[mode] = cap.events[0].name
        if codes:
            print(f"  {key}: " + ", ".join(f"{m}→{n}" for m, n in sorted(codes.items())))
    vol_names = {"KEY_MUTE", "KEY_VOLUMEDOWN", "KEY_VOLUMEUP"}
    found: set[str] = set()
    for caps in by_mode.values():
        for cap in caps:
            if cap.step_id in ("F1", "Fn+F1", "F2", "Fn+F2", "F3", "Fn+F3"):
                for ev in cap.events:
                    if ev.name in vol_names:
                        found.add(ev.name)
    if found:
        print(f"  volume codes (union): {', '.join(sorted(found))}")
    illum = any(
        ev.name.startswith("KEY_KBDILLUM")
        for caps in by_mode.values()
        for cap in caps
        for ev in cap.events
    )
    if illum:
        print("  keyboard backlight: KEY_KBDILLUM* present in at least one mode")


def _print_analysis(results: list[StepCapture]) -> None:
    print("\n── Analysis ──")
    plain_vol = [r for r in results if r.step_id in ("F1", "F2", "F3") and r.events]
    fn_vol = [r for r in results if r.step_id in ("Fn+F1", "Fn+F2", "Fn+F3") and r.events]
    if plain_vol and not fn_vol:
        print(
            "Plain F1–F3 emit media keys but Fn+F1–F3 are silent → try Fn+Esc to toggle fn-lock."
        )
    if plain_vol and fn_vol:
        print("Both plain and Fn+F1–F3 produce events — mapping looks healthy.")

    fn_f4 = next((r for r in results if r.step_id == "Fn+F4"), None)
    if fn_f4 and fn_f4.events:
        codes = {e.name for e in fn_f4.events}
        if codes & {"KEY_KBDILLUMTOGGLE", "KEY_KBDILLUMUP", "KEY_KBDILLUMDOWN"}:
            print("Fn+F4 → keyboard illumination keys (hid-asus path OK).")


def run_calibration(
    steps: list[tuple[str, str]] | None = None,
    output_dir: Path | None = None,
    timeout_s: float = 15.0,
    *,
    grab: bool = True,
    burst_ms: int = 800,
    idle_ms: int = 450,
    release_settle_ms: int = 250,
    dual_fn_lock: bool = False,
) -> int:
    _require_root()
    steps = steps or DEFAULT_STEPS
    dmi = DmiInfo.read()
    user, home, uid, gid = _target_account()
    out_dir = output_dir or calib_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    if uid is not None and gid is not None and os.geteuid() == 0:
        _chown_tree(out_dir, uid, gid)
    board = dmi.board_name or "unknown"
    suffix = "-dual" if dual_fn_lock else ""
    out_json = out_dir / f"{board}{suffix}.json"
    out_conf = out_dir / f"{board}{suffix}-suggested.conf"

    evdev_sources = _discover_evdev_sources()
    hidraw_sources = _discover_hidraw_sources()
    if not evdev_sources and not hidraw_sources:
        print("No input sources found. Is the keyboard connected?", file=sys.stderr)
        return 1

    fds = _open_sources(evdev_sources, hidraw_sources, grab=grab)
    if not fds:
        print("Could not open any input devices.", file=sys.stderr)
        return 1

    user = os.environ.get("ZENBOOK_CALIB_USER") or os.environ.get("SUDO_USER") or user
    print(f"Zenbook hotkey calibration — {board} (user {user})")
    print(f"Output directory: {out_dir}")
    if dual_fn_lock:
        print("Mode: dual fn-lock (A then B) — union conf at end")
    print("s=skip step  Ctrl+C=abort  (keyboard is grabbed — keys won't echo here)")
    if grab:
        print("Devices grabbed exclusively (stop zenbook-kb-hotkeys while calibrating).")
    print()
    _print_sources(evdev_sources, hidraw_sources)
    _warn_missing_if04(evdev_sources, board)

    results: list[StepCapture] = []
    modes = ("A", "B") if dual_fn_lock else ("",)
    try:
        with _TerminalSession() as term:
            for mode in modes:
                if dual_fn_lock:
                    if mode == "B":
                        _prompt_fn_lock_toggle(term, "B")
                    print(f"════════ fn-lock mode {mode} ════════")
                    print(
                        "Mode A: media often on plain F1–F3; Mode B: media on Fn+F1–F3."
                        if mode == "A"
                        else "You toggled fn-lock — F4/backlight layer may have swapped."
                    )
                    print()
                for step_id, prompt in steps:
                    term.drain()
                    label = f"[{mode}] {step_id}" if mode else step_id
                    print(f"── {label} ──")
                    print(prompt)
                    print(f"(tap once and release; {timeout_s:.0f}s timeout, s=skip)")
                    raw_events, filtered, skipped = _capture_step(
                        fds,
                        step_id,
                        timeout_s=timeout_s,
                        burst_ms=burst_ms,
                        idle_ms=idle_ms,
                        release_settle_ms=release_settle_ms,
                        term=term,
                    )
                    if skipped:
                        print("  (skipped)")
                    elif not raw_events:
                        print("  (no events — timed out)")
                    else:
                        _print_step_events(raw_events, filtered)
                    results.append(
                        StepCapture(
                            step_id=step_id,
                            prompt=prompt,
                            raw_events=raw_events,
                            events=filtered,
                            skipped=skipped,
                            fn_lock_mode=mode,
                        )
                    )
                    print()
    except KeyboardInterrupt:
        print("\nAborted.")
        return 130
    finally:
        _close_fds(fds, grab=grab)

    by_mode: dict[str, list[StepCapture]] = {}
    for r in results:
        by_mode.setdefault(r.fn_lock_mode or "single", []).append(r)

    payload = {
        "dmi": dmi.as_dict(),
        "captured_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "captured_by": user,
        "dual_fn_lock": dual_fn_lock,
        "sources": [_format_source(d, m) for d, m in evdev_sources],
        "fn_lock_modes": {
            mode: [
                {
                    **{k: v for k, v in asdict(r).items() if k not in ("raw_events", "events")},
                    "raw_events": [asdict(e) for e in r.raw_events],
                    "events": [asdict(e) for e in r.events],
                }
                for r in caps
            ]
            for mode, caps in by_mode.items()
        },
        "steps": [
            {
                **{k: v for k, v in asdict(r).items() if k not in ("raw_events", "events")},
                "raw_events": [asdict(e) for e in r.raw_events],
                "events": [asdict(e) for e in r.events],
            }
            for r in results
        ],
    }
    out_json.write_text(json.dumps(payload, indent=2) + "\n")
    out_conf.write_text(_suggest_conf_union(by_mode, dmi))
    if uid is not None and gid is not None and os.geteuid() == 0:
        for path in (out_json, out_conf):
            _chown_tree(path, uid, gid)

    print(f"Wrote {out_json}")
    print(f"Wrote {out_conf}")
    if dual_fn_lock:
        _print_dual_analysis(by_mode)
    else:
        _print_analysis(results)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Calibrate Zenbook Duo Fn+ / plain-F key mappings (requires sudo)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help=f"Directory for JSON + suggested .conf (default: {calib_dir()})",
    )
    parser.add_argument("--timeout", type=float, default=15.0, help="Seconds per step")
    parser.add_argument(
        "--burst-ms",
        type=int,
        default=800,
        help="Safety cap (ms) if key-up is never seen",
    )
    parser.add_argument(
        "--release-ms",
        type=int,
        default=250,
        help="Milliseconds of quiet time required after key-up",
    )
    parser.add_argument(
        "--idle-ms",
        type=int,
        default=450,
        help="Milliseconds of silence required before each step",
    )
    parser.add_argument(
        "--no-grab",
        action="store_true",
        help="Do not EVIOCGRAB devices (not recommended)",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Shorter key set (F1–F4, F12/Asus)",
    )
    parser.add_argument(
        "--dual-fn-lock",
        action="store_true",
        help="Capture fn-lock mode A and B, emit union conf",
    )
    args = parser.parse_args(argv)
    reexec_with_sudo_if_needed(argv)
    steps = None
    if args.quick:
        steps = [s for s in DEFAULT_STEPS if s[0] in QUICK_STEP_IDS]
    return run_calibration(
        steps=steps,
        output_dir=args.output_dir,
        timeout_s=args.timeout,
        grab=not args.no_grab,
        burst_ms=args.burst_ms,
        idle_ms=args.idle_ms,
        release_settle_ms=args.release_ms,
        dual_fn_lock=args.dual_fn_lock,
    )


if __name__ == "__main__":
    raise SystemExit(main())
