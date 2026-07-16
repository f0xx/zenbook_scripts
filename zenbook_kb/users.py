"""Resolve the invoking (non-root) user and config paths under sudo."""

from __future__ import annotations

import os
import pwd
from pathlib import Path


def resolve_run_user(*, allow_root: bool = False) -> str:
    """Login user for services, sudoers, and ~/.config paths.

    When ``allow_root`` is false (default), never returns ``root`` unless no
    other account can be determined.
    """
    for key in ("SUDO_USER", "ZENBOOK_CALIB_USER", "LOGNAME", "USER"):
        value = os.environ.get(key)
        if value and (allow_root or value != "root"):
            return value

    if os.geteuid() == 0 and not allow_root:
        sudo_uid = os.environ.get("SUDO_UID")
        if sudo_uid:
            try:
                pw = pwd.getpwuid(int(sudo_uid))
                if pw.pw_name != "root":
                    return pw.pw_name
            except (KeyError, ValueError):
                pass

    try:
        pw = pwd.getpwuid(os.getuid())
        if allow_root or pw.pw_name != "root":
            return pw.pw_name
    except KeyError:
        pass

    return os.environ.get("USER", "root")


def resolve_user_home(user: str | None = None) -> Path:
    """Home directory for *user* or the resolved invoking user."""
    env_home = os.environ.get("ZENBOOK_CALIB_HOME")
    if env_home and user is None:
        return Path(env_home).expanduser()

    name = user or resolve_run_user()
    try:
        return Path(pwd.getpwnam(name).pw_dir)
    except KeyError:
        return Path.home()


def resolve_config_dir() -> Path:
    """``~/.config/zenbook-scripts`` for the invoking user."""
    return resolve_user_home() / ".config" / "zenbook-scripts"


def default_hotkeys_config() -> Path:
    return resolve_config_dir() / "zenbook-hotkeys.conf"


def default_duo_config() -> Path:
    return resolve_config_dir() / "zenbook-duo.conf"


def validate_unix_user(user: str) -> None:
    """Raise ``KeyError`` if *user* is not a local passwd entry."""
    pwd.getpwnam(user)
