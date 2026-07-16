"""Input key names and hotkey action descriptors."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# Linux input-event-codes.h (keyboard illumination)
KEY_KBDILLUMTOGGLE = 228
KEY_KBDILLUMDOWN = 229
KEY_KBDILLUMUP = 230

# Keys 1..114 are forwarded to other consumers when unmapped.
STANDARD_KEYS = frozenset(range(1, 115))


def _load_key_names() -> dict[int, str]:
    names: dict[int, str] = {}
    header = Path("/usr/include/linux/input-event-codes.h")
    if not header.is_file():
        return names
    for line in header.read_text().splitlines():
        if not line.startswith("#define KEY_"):
            continue
        parts = line.split()
        if len(parts) < 3:
            continue
        try:
            names[int(parts[2], 0)] = parts[1]
        except ValueError:
            continue
    return names


KEY_NAMES = _load_key_names()
NAME_TO_CODE = {name: code for code, name in KEY_NAMES.items()}


def key_label(code: int) -> str:
    return KEY_NAMES.get(code, f"KEY_{code}")


@dataclass(frozen=True)
class KeyAction:
    kind: str
    arg: str = ""

    @classmethod
    def parse(cls, text: str) -> KeyAction:
        text = text.strip()
        if not text or text == "log":
            return cls("log")
        if text == "ignore":
            return cls("ignore")
        if ":" in text:
            kind, arg = text.split(":", 1)
            return cls(kind.strip().lower(), arg.strip())
        return cls("shell", text)
