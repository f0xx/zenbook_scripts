"""PID-file helpers for long-lived zenbook daemons (OpenRC / systemd / GUI).

Canonical layout (matches existing OpenRC services):
  /run/<svcname>.pid

Stale files (dead PID) are removed on read so launchers and init scripts
do not get confused.
"""

from __future__ import annotations

import atexit
import logging
import os
import signal
from pathlib import Path

log = logging.getLogger("zenbook.pidfile")

# Shared run directory for grouped state (optional; pidfiles also live flat).
RUN_GROUP_DIR = Path("/run/zenbook-scripts")


def _svc_pidfile(svcname: str) -> Path:
    return Path(f"/run/{svcname}.pid")


# Live touchpad filter (platform-touchpad run)
TOUCHPAD_SVCNAME = "zenbook-platform-touchpad"
TOUCHPAD_PIDFILE = _svc_pidfile(TOUCHPAD_SVCNAME)

# Adaptive fan / platform_profile daemon
FAN_SVCNAME = "zenbook-platform-fan-control"
FAN_PIDFILE = _svc_pidfile(FAN_SVCNAME)

# Fn+ / special-key listener
HOTKEYS_SVCNAME = "zenbook-kb-hotkeys"
HOTKEYS_PIDFILE = _svc_pidfile(HOTKEYS_SVCNAME)

# ScreenPad brightness mirror
SCREENPAD_SYNC_SVCNAME = "zenbook-screenpad-sync"
SCREENPAD_SYNC_PIDFILE = _svc_pidfile(SCREENPAD_SYNC_SVCNAME)

# Lid open/close backlight watcher
LID_SVCNAME = "zenbook-kb-lid"
LID_PIDFILE = _svc_pidfile(LID_SVCNAME)

# All long-lived service pidfiles (for docs / status dumps)
KNOWN_PIDFILES: dict[str, Path] = {
    TOUCHPAD_SVCNAME: TOUCHPAD_PIDFILE,
    FAN_SVCNAME: FAN_PIDFILE,
    HOTKEYS_SVCNAME: HOTKEYS_PIDFILE,
    SCREENPAD_SYNC_SVCNAME: SCREENPAD_SYNC_PIDFILE,
    LID_SVCNAME: LID_PIDFILE,
}


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        # Exists but we cannot signal it (e.g. root-owned) — treat as alive.
        return True
    except OSError:
        return False


def read_pidfile(path: Path, *, clear_stale: bool = True) -> int | None:
    """Return live PID from ``path``, or None. Removes stale files when asked."""
    try:
        raw = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not raw:
        if clear_stale:
            clear_pidfile(path)
        return None
    try:
        pid = int(raw.split()[0])
    except ValueError:
        if clear_stale:
            clear_pidfile(path)
        return None
    if pid_alive(pid):
        return pid
    if clear_stale:
        clear_pidfile(path)
        log.debug("removed stale pidfile %s (was pid %s)", path, pid)
    return None


def write_pidfile(path: Path, pid: int | None = None) -> None:
    """Atomically write ``pid`` (default: current process) to ``path``."""
    pid = os.getpid() if pid is None else int(pid)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(f"{pid}\n", encoding="utf-8")
    tmp.replace(path)


def clear_pidfile(path: Path, *, only_if_pid: int | None = None) -> None:
    """Remove pidfile. If ``only_if_pid`` is set, only when contents match."""
    if only_if_pid is not None:
        try:
            raw = path.read_text(encoding="utf-8").strip()
            if int(raw.split()[0]) != only_if_pid:
                return
        except (OSError, ValueError, IndexError):
            return
    try:
        path.unlink()
    except FileNotFoundError:
        return
    except OSError as exc:
        log.debug("clear_pidfile %s: %s", path, exc)


def acquire_pidfile(path: Path, *, replace: bool = False) -> int | None:
    """Claim ``path`` for this process.

    Returns the conflicting live PID if another instance holds it and
    ``replace`` is False. On success returns None.
    """
    existing = read_pidfile(path, clear_stale=True)
    if existing is not None and existing != os.getpid():
        if not replace:
            return existing
        try:
            os.kill(existing, signal.SIGTERM)
        except OSError:
            pass
        # Brief wait loop without importing time at module level cost — ok
        import time

        for _ in range(20):
            if not pid_alive(existing):
                break
            time.sleep(0.05)
        if pid_alive(existing):
            try:
                os.kill(existing, signal.SIGKILL)
            except OSError:
                pass
        clear_pidfile(path)
    write_pidfile(path)
    return None


def release_pidfile(path: Path) -> None:
    """Drop our claim (atexit / signal)."""
    clear_pidfile(path, only_if_pid=os.getpid())


def install_pidfile_hooks(path: Path) -> None:
    """Register atexit + SIGTERM/SIGINT cleanup for ``path`` (this process)."""

    def _cleanup(*_a: object) -> None:
        release_pidfile(path)

    atexit.register(_cleanup)
    # Caller usually installs its own stop flags; still clear pid on TERM.
    prev_term = signal.getsignal(signal.SIGTERM)
    prev_int = signal.getsignal(signal.SIGINT)

    def _wrap(prev):
        def handler(signum, frame):
            _cleanup()
            if callable(prev) and prev not in (signal.SIG_DFL, signal.SIG_IGN):
                prev(signum, frame)

        return handler

    try:
        signal.signal(signal.SIGTERM, _wrap(prev_term))
        signal.signal(signal.SIGINT, _wrap(prev_int))
    except (OSError, ValueError):
        # Not main thread / signals blocked — atexit still runs.
        pass
