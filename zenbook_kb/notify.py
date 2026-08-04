"""Plasma / freedesktop notifications for mode switches."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from typing import Any

log = logging.getLogger("zenbook.notify")


def _run(argv: list[str], *, env: dict[str, str] | None = None) -> bool:
    try:
        r = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=8,
            env=env,
            check=False,
        )
        return r.returncode == 0
    except (OSError, subprocess.TimeoutExpired) as exc:
        log.debug("notify %s failed: %s", argv[0], exc)
        return False


def notify_mode_switch(
    title: str,
    body: str,
    *,
    cfg: dict[str, Any] | None = None,
    urgency: str = "low",
) -> bool:
    """Show a desktop notification if enabled in profiles.json."""
    if cfg is not None:
        notif = cfg.get("notifications") or {}
        if not notif.get("enabled") or not notif.get("on_mode_switch"):
            return False
    else:
        try:
            from zenbook_kb.user_profiles import load

            doc = load()
            notif = doc.get("notifications") or {}
            if not notif.get("enabled") or not notif.get("on_mode_switch"):
                return False
        except Exception:
            pass

    env = os.environ.copy()
    if notify_send := shutil.which("notify-send"):
        return _run(
            [
                notify_send,
                "-a",
                "zenbook-scripts",
                "-i",
                "preferences-system-power",
                f"-u{urgency}",
                title,
                body,
            ],
            env=env,
        )
    if knotify := shutil.which("knotify-send"):
        return _run(
            [knotify, title, body, "-a", "zenbook-scripts", "-i", "preferences-system-power"],
            env=env,
        )
    log.debug("no notify-send or knotify-send")
    return False
