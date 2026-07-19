"""Sysfs helpers that never block on an interactive sudo password prompt.

- Already root → write/read directly
- Writable path → write directly  
- Else ``sudo -n`` only (fails fast if password would be required)

Installers that run from a TTY may set ``ZENBOOK_SUDO_ASK=1`` to allow
interactive ``sudo`` for configure.py.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def is_root() -> bool:
    return os.geteuid() == 0


def sudo_prefix(*, allow_ask: bool | None = None) -> list[str]:
    """Return argv prefix for privilege escalation, or empty if already root."""
    if is_root():
        return []
    if allow_ask is None:
        allow_ask = os.environ.get("ZENBOOK_SUDO_ASK", "").lower() in (
            "1",
            "yes",
            "true",
        ) and sys.stdin.isatty()
    if allow_ask:
        return ["sudo"]
    return ["sudo", "-n"]


def run_root(
    argv: list[str],
    *,
    check: bool = False,
    timeout: float | None = 60,
    input_bytes: bytes | None = None,
    allow_ask: bool | None = None,
    capture: bool = False,
) -> subprocess.CompletedProcess[bytes]:
    cmd = [*sudo_prefix(allow_ask=allow_ask), *argv]
    return subprocess.run(
        cmd,
        check=check,
        timeout=timeout,
        input=input_bytes,
        capture_output=capture,
    )


def write_sysfs(path: Path | str, value: str, *, allow_ask: bool | None = False) -> None:
    """Write sysfs/node; never hang waiting for a sudo password by default."""
    p = Path(path)
    data = value if value.endswith("\n") or not value else value
    try:
        p.write_text(data, encoding="utf-8")
        return
    except OSError:
        pass
    # Non-interactive elevation only (daemons / tray / hooks)
    r = run_root(
        ["tee", str(p)],
        check=False,
        input_bytes=data.encode(),
        allow_ask=allow_ask,
        timeout=15,
        capture=True,
    )
    if r.returncode != 0:
        err = (r.stderr or b"").decode(errors="replace").strip()
        raise PermissionError(
            f"Cannot write {p} (need root or NOPASSWD sudo -n). {err}"
        )
