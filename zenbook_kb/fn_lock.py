"""Track UX8406 fn-lock Mode A/B in userspace (kernel toggle is not HID-readable)."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from zenbook_kb.users import resolve_config_dir

FN_LOCK_STATE_FILE = Path(
    os.environ.get(
        "ZENBOOK_KB_FN_LOCK_STATE_FILE",
        str(resolve_config_dir() / "fn-lock-mode"),
    )
)
FN_LOCK_TOGGLED_FILE = Path(
    os.environ.get(
        "ZENBOOK_KB_FN_LOCK_TOGGLED_FILE",
        str(resolve_config_dir() / "fn-lock-toggled"),
    )
)


def read_fn_lock_state() -> int | None:
    try:
        raw = FN_LOCK_STATE_FILE.read_text().strip().upper()
    except OSError:
        return None
    if raw in {"0", "B"}:
        return 0
    if raw in {"1", "A"}:
        return 1
    return None


def write_fn_lock_state(fn_lock: int) -> None:
    FN_LOCK_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    FN_LOCK_STATE_FILE.write_text(f"{int(bool(fn_lock))}\n")


def mark_fn_lock_toggled() -> None:
    FN_LOCK_TOGGLED_FILE.parent.mkdir(parents=True, exist_ok=True)
    FN_LOCK_TOGGLED_FILE.write_text(
        datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") + "\n"
    )


def find_vendor_hidraw() -> Path | None:
    """USB if4 vendor hidraw (90–120 byte rdesc) for fn-lock input reports."""
    for hidraw in sorted(Path("/sys/class/hidraw").glob("hidraw*")):
        uevent = hidraw / "device" / "uevent"
        if not uevent.is_file():
            continue
        text = uevent.read_text()
        if "1B2C" not in text.upper():
            continue
        rdesc = hidraw / "device" / "report_descriptor"
        if not rdesc.is_file():
            continue
        size = rdesc.stat().st_size
        if 90 <= size <= 120:
            return Path("/dev") / hidraw.name
    return None


def note_fn_lock_toggle() -> int:
    """Kernel toggled fn-lock (Fn+Esc); flip tracked state for save/restore."""
    cur = read_fn_lock_state()
    if cur is None:
        cur = 0
    new = 1 - cur
    write_fn_lock_state(new)
    mark_fn_lock_toggled()
    return new
