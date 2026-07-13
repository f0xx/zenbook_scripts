"""Persist last known keyboard brightness (hardware has no reliable read)."""

from __future__ import annotations

import os
from pathlib import Path

from zenbook_kb.users import resolve_config_dir, resolve_user_home


def _user_home() -> Path:
    return resolve_user_home()


DEFAULT_STATE_DIR = Path(
    os.environ.get("ZENBOOK_KB_STATE_DIR", resolve_config_dir())
)
DEFAULT_STATE_FILE = DEFAULT_STATE_DIR / "keyboard-brightness"


def read_brightness(default: int = 1) -> int:
    try:
        value = int(DEFAULT_STATE_FILE.read_text().strip())
        return max(0, min(3, value))
    except (OSError, ValueError):
        return default


def write_brightness(level: int) -> None:
    DEFAULT_STATE_DIR.mkdir(parents=True, exist_ok=True)
    DEFAULT_STATE_FILE.write_text(f"{level}\n")
