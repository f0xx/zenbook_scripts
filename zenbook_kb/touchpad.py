"""Touchpad palm-filter pipeline (stdlib only).

Ordered plugins (iptables-inspired, single chain):
  1. event_sim       — synthetic frames for tests (source, not a mid-stream rewrite)
  2. exec_delay      — hold contact ≤N ms; drop short brushes
  3. outlier_reject  — drop frames with impossible position jumps

Live path: EVIOCGRAB source → filters → uinput virtual device.
"""

from __future__ import annotations

import array
import fcntl
import json
import logging
import os
import select
import struct
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator, Sequence

log = logging.getLogger("zenbook.touchpad")

INPUT_EVENT_FMT = "@llHHi"
INPUT_EVENT_SIZE = struct.calcsize(INPUT_EVENT_FMT)
EVIOCGRAB = 0x40044590

EV_SYN = 0x00
EV_KEY = 0x01
EV_REL = 0x02
EV_ABS = 0x03
EV_MSC = 0x04
SYN_REPORT = 0
BTN_TOUCH = 0x14A
BTN_TOOL_FINGER = 0x145
ABS_X = 0x00
ABS_Y = 0x01
ABS_MT_SLOT = 0x2F
ABS_MT_POSITION_X = 0x35
ABS_MT_POSITION_Y = 0x36
ABS_MT_TRACKING_ID = 0x39

UI_DEV_CREATE = 0x5501
UI_DEV_DESTROY = 0x5502
UI_DEV_SETUP = 0x405C5503
UI_ABS_SETUP = 0x401C5504
UI_SET_EVBIT = 0x40045564
UI_SET_KEYBIT = 0x40045565
UI_SET_RELBIT = 0x40045566
UI_SET_ABSBIT = 0x40045567
UI_SET_PROPBIT = 0x4004556E

UINPUT_MAX_NAME_SIZE = 80
DEFAULT_CONFIG = Path("/etc/zenbook-scripts/touchpad.json")
DEFAULT_EXEC_DELAY_MS = 25.0
DEFAULT_MAX_DELTA = 1200


def _ioc(dir_: int, type_: str, nr: int, size: int) -> int:
    return (dir_ << 30) | ((size & 0x3FFF) << 16) | (ord(type_) << 8) | nr


def eviocgabs(code: int) -> int:
    return _ioc(2, "E", 0x40 + code, 24)


def eviocgbit(ev: int, length: int) -> int:
    return _ioc(2, "E", 0x20 + ev, length)


@dataclass(slots=True)
class Ev:
    sec: int
    usec: int
    type: int
    code: int
    value: int

    @property
    def t_ms(self) -> float:
        return self.sec * 1000.0 + self.usec / 1000.0

    def pack(self) -> bytes:
        return struct.pack(INPUT_EVENT_FMT, self.sec, self.usec, self.type, self.code, self.value)

    @classmethod
    def unpack(cls, data: bytes) -> Ev:
        sec, usec, etype, code, value = struct.unpack(INPUT_EVENT_FMT, data)
        return cls(sec, usec, etype, code, value)

    @classmethod
    def syn(cls, sec: int = 0, usec: int = 0) -> Ev:
        return cls(sec, usec, EV_SYN, SYN_REPORT, 0)


@dataclass
class FilterStats:
    name: str
    in_frames: int = 0
    out_frames: int = 0
    dropped_frames: int = 0

    def note(self, n_in: int, n_out: int) -> None:
        self.in_frames += 1 if n_in else 0
        if n_in:
            if n_out:
                self.out_frames += 1
            else:
                self.dropped_frames += 1


class Filter:
    name = "filter"

    def __init__(self) -> None:
        self.stats = FilterStats(self.name)

    def process_frame(self, frame: list[Ev]) -> list[Ev]:
        raise NotImplementedError

    def reset(self) -> None:
        pass


class ExecDelayFilter(Filter):
    """Hold first contact frames until ``ms`` elapsed; drop if contact ends sooner."""

    name = "exec_delay"

    def __init__(self, ms: float = DEFAULT_EXEC_DELAY_MS) -> None:
        super().__init__()
        self.ms = float(ms)
        self._buf: list[list[Ev]] = []
        self._contact_t0: float | None = None
        self._armed = False
        self._contacts = 0

    def set_ms(self, ms: float) -> None:
        self.ms = float(ms)

    def reset(self) -> None:
        self._buf.clear()
        self._contact_t0 = None
        self._armed = False
        self._contacts = 0

    def _update_contacts(self, frame: list[Ev]) -> None:
        for ev in frame:
            if ev.type == EV_ABS and ev.code == ABS_MT_TRACKING_ID:
                if ev.value >= 0:
                    self._contacts += 1
                elif self._contacts > 0:
                    self._contacts -= 1
            elif ev.type == EV_KEY and ev.code in (BTN_TOUCH, BTN_TOOL_FINGER):
                if ev.value:
                    self._contacts = max(self._contacts, 1)
                else:
                    self._contacts = 0

    def process_frame(self, frame: list[Ev]) -> list[Ev]:
        if not frame:
            return frame
        self._update_contacts(frame)
        now = frame[-1].t_ms if frame[-1].sec or frame[-1].usec else time.monotonic() * 1000.0

        if self._contacts <= 0:
            if self._armed:
                self._armed = False
                self._contact_t0 = None
                self._buf.clear()
                self.stats.note(1, 1)
                return frame
            # short brush ended while buffering → drop
            if self._buf:
                self._buf.clear()
                self._contact_t0 = None
                self.stats.note(1, 0)
                return []
            self.stats.note(1, 1)
            return frame

        # contact active
        if self._contact_t0 is None:
            self._contact_t0 = now
            self._armed = False
            self._buf = [frame]
            self.stats.note(1, 0)
            return []

        if self._armed:
            self.stats.note(1, 1)
            return frame

        age = now - self._contact_t0
        self._buf.append(frame)
        if age < self.ms:
            self.stats.note(1, 0)
            return []

        # delay satisfied — flush buffer + current (already in buf)
        out: list[Ev] = []
        for fr in self._buf:
            out.extend(fr)
        self._buf.clear()
        self._armed = True
        self.stats.note(1, 1)
        return out


class OutlierRejectFilter(Filter):
    """Drop frames whose absolute position jumps more than ``max_delta``.

    Resets on new/ended contact so a finger landing elsewhere is not treated as
    a spike. A rejected frame still updates the last position so one spike cannot
    lock out the rest of the gesture.
    """

    name = "outlier_reject"

    def __init__(self, max_delta: int = DEFAULT_MAX_DELTA) -> None:
        super().__init__()
        self.max_delta = int(max_delta)
        self._last: tuple[int, int] | None = None

    def set_max_delta(self, max_delta: int) -> None:
        self.max_delta = int(max_delta)

    def reset(self) -> None:
        self._last = None

    @staticmethod
    def _xy(frame: list[Ev]) -> tuple[int, int] | None:
        x = y = None
        for ev in frame:
            if ev.type != EV_ABS:
                continue
            if ev.code in (ABS_MT_POSITION_X, ABS_X):
                x = ev.value
            elif ev.code in (ABS_MT_POSITION_Y, ABS_Y):
                y = ev.value
        if x is None or y is None:
            return None
        return x, y

    def _contact_edge(self, frame: list[Ev]) -> str | None:
        """Return ``new``, ``end``, or None."""
        for ev in frame:
            if ev.type == EV_ABS and ev.code == ABS_MT_TRACKING_ID:
                return "new" if ev.value >= 0 else "end"
            if ev.type == EV_KEY and ev.code in (BTN_TOUCH, BTN_TOOL_FINGER):
                if ev.value:
                    return "new"
                return "end"
        return None

    def process_frame(self, frame: list[Ev]) -> list[Ev]:
        if not frame:
            return frame
        edge = self._contact_edge(frame)
        if edge == "end":
            self._last = None
            self.stats.note(1, 1)
            return frame
        if edge == "new":
            self._last = None

        xy = self._xy(frame)
        if xy is None:
            self.stats.note(1, 1)
            return frame
        if self._last is not None:
            dx = abs(xy[0] - self._last[0])
            dy = abs(xy[1] - self._last[1])
            if dx > self.max_delta or dy > self.max_delta:
                # Advance last so a single spike cannot black-hole the gesture.
                self._last = xy
                self.stats.note(1, 0)
                return []
        self._last = xy
        self.stats.note(1, 1)
        return frame


@dataclass
class Pipeline:
    filters: list[Filter] = field(default_factory=list)

    def process_frame(self, frame: list[Ev]) -> list[Ev]:
        out = frame
        for filt in self.filters:
            if not out:
                # still let later filters see empties? skip
                break
            out = filt.process_frame(out)
        return out

    def process_events(self, events: Iterable[Ev]) -> list[Ev]:
        frame: list[Ev] = []
        result: list[Ev] = []
        for ev in events:
            frame.append(ev)
            if ev.type == EV_SYN and ev.code == SYN_REPORT:
                result.extend(self.process_frame(frame))
                frame = []
        if frame:
            result.extend(self.process_frame(frame))
        return result

    def reset(self) -> None:
        for filt in self.filters:
            filt.reset()

    def summary(self) -> str:
        parts = []
        for filt in self.filters:
            s = filt.stats
            parts.append(
                f"{s.name}: in={s.in_frames} out={s.out_frames} drop={s.dropped_frames}"
            )
        return "; ".join(parts) if parts else "(no filters)"


def build_pipeline(cfg: dict[str, Any] | None = None) -> Pipeline:
    cfg = cfg or {}
    filters_cfg = cfg.get("filters")
    if not filters_cfg:
        filters_cfg = [
            {"plugin": "exec_delay", "ms": cfg.get("exec_delay_ms", DEFAULT_EXEC_DELAY_MS)},
            {
                "plugin": "outlier_reject",
                "max_delta": cfg.get("max_delta", DEFAULT_MAX_DELTA),
            },
        ]
    out: list[Filter] = []
    for item in filters_cfg:
        if not isinstance(item, dict):
            continue
        if item.get("enabled") is False:
            continue
        name = str(item.get("plugin") or item.get("name") or "").lower()
        if name in ("event_sim", "event-sim", "sim"):
            # source-only; ignore mid-chain
            continue
        if name in ("exec_delay", "exec-delay", "delay"):
            out.append(
                ExecDelayFilter(ms=float(item.get("ms", DEFAULT_EXEC_DELAY_MS)))
            )
        elif name in ("outlier_reject", "outlier-reject", "outlier"):
            out.append(
                OutlierRejectFilter(
                    max_delta=int(item.get("max_delta", DEFAULT_MAX_DELTA))
                )
            )
        elif name in ("smooth",):
            log.warning("smooth filter not in MVP; skip")
        else:
            log.warning("unknown touchpad filter %r; skip", name)
    return Pipeline(out)


def pipeline_to_config(pipe: Pipeline, *, device: str = "auto") -> dict[str, Any]:
    """Legacy v1 helper — prefer ``upsert_device_profile`` for new saves."""
    filters = [{"plugin": "event_sim", "enabled": False}]
    for filt in pipe.filters:
        if isinstance(filt, ExecDelayFilter):
            filters.append({"plugin": "exec_delay", "ms": filt.ms, "enabled": True})
        elif isinstance(filt, OutlierRejectFilter):
            filters.append(
                {
                    "plugin": "outlier_reject",
                    "max_delta": filt.max_delta,
                    "enabled": True,
                }
            )
    return {"device": device, "filters": filters}


def filters_from_knobs(
    *,
    delay_enabled: bool,
    delay_ms: float,
    outlier_enabled: bool,
    max_delta: int,
) -> list[dict[str, Any]]:
    return [
        {"plugin": "event_sim", "enabled": False},
        {
            "plugin": "exec_delay",
            "ms": float(delay_ms),
            "enabled": bool(delay_enabled),
        },
        {
            "plugin": "outlier_reject",
            "max_delta": int(max_delta),
            "enabled": bool(outlier_enabled),
        },
    ]


def apply_pipeline_knobs(
    pipe: Pipeline, *, delay_ms: float | None = None, max_delta: int | None = None
) -> None:
    for filt in pipe.filters:
        if delay_ms is not None and isinstance(filt, ExecDelayFilter):
            filt.set_ms(delay_ms)
        if max_delta is not None and isinstance(filt, OutlierRejectFilter):
            filt.set_max_delta(max_delta)


@dataclass(frozen=True)
class TouchpadInfo:
    """One touchpad-like evdev node with a reboot-stable config key."""

    path: Path
    name: str
    phys: str = ""
    uniq: str = ""

    @property
    def key(self) -> str:
        """Stable id for per-device config (name + phys/uniq, not eventN)."""
        if self.uniq:
            return f"{self.name}|{self.uniq}"
        if self.phys:
            return f"{self.name}|{self.phys}"
        return self.name


def default_filters() -> list[dict[str, Any]]:
    return [
        {"plugin": "event_sim", "enabled": False},
        {"plugin": "exec_delay", "ms": DEFAULT_EXEC_DELAY_MS, "enabled": True},
        {
            "plugin": "outlier_reject",
            "max_delta": DEFAULT_MAX_DELTA,
            "enabled": True,
        },
    ]


def empty_config_v2() -> dict[str, Any]:
    return {"version": 2, "default_device": "auto", "devices": {}}


def device_key_for_path(path: Path) -> str | None:
    for info in discover_touchpads():
        if info.path == path or info.path.resolve() == path.resolve():
            return info.key
    # Fallback: read sysfs directly
    event = path.name
    sys_name = Path("/sys/class/input") / event / "device" / "name"
    if not sys_name.is_file():
        return None
    name = sys_name.read_text(encoding="utf-8", errors="replace").strip()
    phys_p = Path("/sys/class/input") / event / "device" / "phys"
    uniq_p = Path("/sys/class/input") / event / "device" / "uniq"
    phys = phys_p.read_text(encoding="utf-8", errors="replace").strip() if phys_p.is_file() else ""
    uniq = uniq_p.read_text(encoding="utf-8", errors="replace").strip() if uniq_p.is_file() else ""
    return TouchpadInfo(path, name, phys, uniq).key


def normalize_config(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Return version-2 config; migrate legacy single-device files."""
    if not raw:
        return empty_config_v2()
    if int(raw.get("version") or 0) >= 2 and isinstance(raw.get("devices"), dict):
        out = empty_config_v2()
        out["default_device"] = raw.get("default_device", "auto")
        for key, entry in raw["devices"].items():
            if not isinstance(entry, dict):
                continue
            out["devices"][str(key)] = {
                "filters": entry.get("filters") or default_filters(),
                "enabled": bool(entry.get("enabled", True)),
            }
        return out

    # v1: { "device": "...", "filters": [...] }
    out = empty_config_v2()
    device = raw.get("device", "auto")
    filters = raw.get("filters")
    if not isinstance(filters, list):
        return out
    key = "default"
    if device and device not in ("auto", ""):
        p = Path(str(device))
        if p.exists():
            key = device_key_for_path(p) or str(device)
        else:
            key = str(device)
        out["default_device"] = key
    else:
        out["default_device"] = "auto"
    out["devices"][key] = {"filters": filters, "enabled": True}
    return out


def load_config(path: Path | None = None) -> dict[str, Any]:
    path = path or DEFAULT_CONFIG
    if not path.is_file():
        return empty_config_v2()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return empty_config_v2()
    if not isinstance(raw, dict):
        return empty_config_v2()
    return normalize_config(raw)


def save_config(cfg: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = normalize_config(cfg)
    path.write_text(json.dumps(normalized, indent=2) + "\n", encoding="utf-8")


def _match_device_entry(
    cfg: dict[str, Any], info: TouchpadInfo | None, *, path: Path | None = None
) -> tuple[str | None, dict[str, Any] | None]:
    cfg = normalize_config(cfg)
    devices: dict[str, Any] = cfg.get("devices") or {}
    if info is not None:
        if info.key in devices:
            return info.key, devices[info.key]
        # name-only legacy / partial match
        for key, entry in devices.items():
            if key == info.name or key.startswith(info.name + "|"):
                return key, entry
    if path is not None:
        path_s = str(path)
        if path_s in devices:
            return path_s, devices[path_s]
        key = device_key_for_path(path)
        if key and key in devices:
            return key, devices[key]
    if "default" in devices:
        return "default", devices["default"]
    return None, None


def filters_for_device(
    cfg: dict[str, Any],
    info: TouchpadInfo | None = None,
    *,
    path: Path | None = None,
) -> list[dict[str, Any]]:
    """Per-device filters; fall back to defaults (not another device's knobs)."""
    _key, entry = _match_device_entry(cfg, info, path=path)
    if entry and isinstance(entry.get("filters"), list):
        return list(entry["filters"])
    return default_filters()


def device_profile_enabled(
    cfg: dict[str, Any],
    info: TouchpadInfo | None = None,
    *,
    path: Path | None = None,
) -> bool:
    _key, entry = _match_device_entry(cfg, info, path=path)
    if entry is None:
        return True
    return bool(entry.get("enabled", True))


def upsert_device_profile(
    cfg: dict[str, Any],
    key: str,
    *,
    filters: list[dict[str, Any]],
    enabled: bool = True,
    make_default: bool = False,
) -> dict[str, Any]:
    out = normalize_config(cfg)
    out["devices"][key] = {"filters": filters, "enabled": enabled}
    if make_default:
        out["default_device"] = key
    return out


def knobs_from_filters(filters: list[dict[str, Any]]) -> dict[str, Any]:
    """Extract GUI/CLI knob state from a filters list."""
    delay_ms = DEFAULT_EXEC_DELAY_MS
    max_delta = DEFAULT_MAX_DELTA
    delay_on = True
    outlier_on = True
    for item in filters:
        if not isinstance(item, dict):
            continue
        name = str(item.get("plugin") or item.get("name") or "").lower()
        if name in ("exec_delay", "exec-delay", "delay"):
            delay_ms = float(item.get("ms", delay_ms))
            delay_on = item.get("enabled", True) is not False
        elif name in ("outlier_reject", "outlier-reject", "outlier"):
            max_delta = int(item.get("max_delta", max_delta))
            outlier_on = item.get("enabled", True) is not False
    return {
        "delay_ms": delay_ms,
        "max_delta": max_delta,
        "delay_enabled": delay_on,
        "outlier_enabled": outlier_on,
    }


def discover_touchpads() -> list[TouchpadInfo]:
    """Return touchpad-like nodes with stable config keys."""
    found: list[TouchpadInfo] = []
    for event_dir in sorted(Path("/sys/class/input").glob("event*")):
        name_path = event_dir / "device" / "name"
        if not name_path.is_file():
            continue
        name = name_path.read_text(encoding="utf-8", errors="replace").strip()
        low = name.lower()
        if "stylus" in low or "unknown" in low:
            continue
        if "touchpad" not in low and "trackpad" not in low:
            continue
        phys_p = event_dir / "device" / "phys"
        uniq_p = event_dir / "device" / "uniq"
        phys = (
            phys_p.read_text(encoding="utf-8", errors="replace").strip()
            if phys_p.is_file()
            else ""
        )
        uniq = (
            uniq_p.read_text(encoding="utf-8", errors="replace").strip()
            if uniq_p.is_file()
            else ""
        )
        found.append(
            TouchpadInfo(
                path=Path("/dev/input") / event_dir.name,
                name=name,
                phys=phys,
                uniq=uniq,
            )
        )
    return found


def pick_default_device(
    devices: Sequence[TouchpadInfo | tuple[Path, str]] | None = None,
) -> Path | None:
    infos: list[TouchpadInfo]
    if devices is None:
        infos = discover_touchpads()
    else:
        infos = []
        for d in devices:
            if isinstance(d, TouchpadInfo):
                infos.append(d)
            else:
                infos.append(TouchpadInfo(path=d[0], name=d[1]))
    if not infos:
        return None
    for info in infos:
        if "keyboard touchpad" in info.name.lower():
            return info.path
    return infos[0].path


def resolve_touchpad(
    selector: str | None,
    cfg: dict[str, Any] | None = None,
) -> TouchpadInfo:
    """Resolve CLI/GUI device selector to a ``TouchpadInfo``.

    Accepts ``auto``, ``/dev/input/eventN``, stable key, or substring of name.
    """
    pads = discover_touchpads()
    if not pads:
        raise FileNotFoundError("no touchpad input node found")
    cfg = normalize_config(cfg)

    if not selector or selector in ("auto", ""):
        pref = cfg.get("default_device") or "auto"
        if pref and pref not in ("auto", ""):
            try:
                return resolve_touchpad(str(pref), {**cfg, "default_device": "auto"})
            except FileNotFoundError:
                pass
        path = pick_default_device(pads)
        assert path is not None
        for info in pads:
            if info.path == path:
                return info
        return pads[0]

    # Absolute / relative event node
    as_path = Path(selector)
    if as_path.exists() or selector.startswith("/dev/input/"):
        for info in pads:
            if info.path == as_path or str(info.path) == selector:
                return info
        raise FileNotFoundError(f"touchpad node not found: {selector}")

    # Exact stable key
    for info in pads:
        if info.key == selector or info.name == selector:
            return info

    # Substring match on name/key
    low = selector.lower()
    hits = [i for i in pads if low in i.name.lower() or low in i.key.lower()]
    if len(hits) == 1:
        return hits[0]
    if len(hits) > 1:
        raise FileNotFoundError(
            f"ambiguous device {selector!r}; matches: "
            + ", ".join(i.key for i in hits)
        )
    raise FileNotFoundError(f"no touchpad matching {selector!r}")


def iter_device_events(
    path: Path,
    *,
    grab: bool = False,
    stop_after_s: float | None = None,
    should_stop: Callable[[], bool] | None = None,
) -> Iterator[Ev]:
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
    grabbed = False
    t0 = time.monotonic()
    try:
        if grab:
            fcntl.ioctl(fd, EVIOCGRAB, 1)
            grabbed = True
        buf = b""
        while True:
            if should_stop and should_stop():
                break
            if stop_after_s is not None and (time.monotonic() - t0) >= stop_after_s:
                break
            r, _, _ = select.select([fd], [], [], 0.25)
            if not r:
                continue
            try:
                chunk = os.read(fd, INPUT_EVENT_SIZE * 64)
            except BlockingIOError:
                continue
            if not chunk:
                break
            buf += chunk
            while len(buf) >= INPUT_EVENT_SIZE:
                raw, buf = buf[:INPUT_EVENT_SIZE], buf[INPUT_EVENT_SIZE:]
                yield Ev.unpack(raw)
    finally:
        if grabbed:
            try:
                fcntl.ioctl(fd, EVIOCGRAB, 0)
            except OSError:
                pass
        os.close(fd)


def _bits_via_ioctl(fd: int, ev: int, max_code: int = 512) -> set[int]:
    length = (max_code + 7) // 8
    buf = array.array("B", [0]) * length
    try:
        fcntl.ioctl(fd, eviocgbit(ev, length), buf, True)
    except OSError:
        return set()
    out: set[int] = set()
    for i, byte in enumerate(buf):
        for b in range(8):
            if byte & (1 << b):
                out.add(i * 8 + b)
    return out


def _read_absinfo(fd: int, code: int) -> tuple[int, int, int, int, int, int] | None:
    buf = array.array("i", [0] * 6)
    try:
        fcntl.ioctl(fd, eviocgabs(code), buf, True)
    except OSError:
        return None
    return tuple(buf)  # type: ignore[return-value]


class UInputProxy:
    """Clone a touchpad into ``/dev/uinput`` and write filtered events."""

    def __init__(self, source: Path, name: str = "zenbook-touchpad-filter") -> None:
        self.source = source
        self.name = name[: UINPUT_MAX_NAME_SIZE - 1]
        self._fd = -1

    def open(self) -> None:
        src = os.open(self.source, os.O_RDONLY)
        try:
            ev_bits = _bits_via_ioctl(src, 0, 32)
            key_bits = _bits_via_ioctl(src, EV_KEY, 768)
            rel_bits = _bits_via_ioctl(src, EV_REL, 64)
            abs_bits = _bits_via_ioctl(src, EV_ABS, 64)
            ufd = os.open("/dev/uinput", os.O_WRONLY | os.O_NONBLOCK)
            for bit in sorted(ev_bits | {EV_SYN}):
                fcntl.ioctl(ufd, UI_SET_EVBIT, bit)
            for bit in sorted(key_bits):
                fcntl.ioctl(ufd, UI_SET_KEYBIT, bit)
            for bit in sorted(rel_bits):
                fcntl.ioctl(ufd, UI_SET_RELBIT, bit)
            for bit in sorted(abs_bits):
                fcntl.ioctl(ufd, UI_SET_ABSBIT, bit)
                info = _read_absinfo(src, bit)
                if info is None:
                    continue
                # struct uinput_abs_setup: __u16 code; pad to 4; input_absinfo
                abs_setup = struct.pack(
                    "Hxxiiiiii",
                    bit,
                    info[0],
                    info[1],
                    info[2],
                    info[3],
                    info[4],
                    info[5],
                )
                fcntl.ioctl(ufd, UI_ABS_SETUP, abs_setup)
            setup = struct.pack(
                "HHHH80sI",
                0x03,  # BUS_USB
                0x0B05,
                0x5444,  # synthetic product
                0x0001,
                self.name.encode("utf-8"),
                0,
            )
            fcntl.ioctl(ufd, UI_DEV_SETUP, setup)
            fcntl.ioctl(ufd, UI_DEV_CREATE)
            time.sleep(0.05)
            self._fd = ufd
        finally:
            os.close(src)

    def write_events(self, events: Sequence[Ev]) -> None:
        if self._fd < 0:
            raise RuntimeError("uinput not open")
        blob = b"".join(ev.pack() for ev in events)
        if blob:
            os.write(self._fd, blob)

    def close(self) -> None:
        if self._fd >= 0:
            try:
                fcntl.ioctl(self._fd, UI_DEV_DESTROY)
            except OSError:
                pass
            os.close(self._fd)
            self._fd = -1

    def __enter__(self) -> UInputProxy:
        self.open()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def make_sim_brush(
    *,
    duration_ms: float,
    dx: int = 5,
    dy: int = 0,
    start_x: int = 1000,
    start_y: int = 1000,
    step_ms: float = 5.0,
) -> list[Ev]:
    """Synthetic MT contact used by ``platform-touchpad selftest`` / ``sim``."""
    events: list[Ev] = []
    t0 = time.time()
    steps = max(1, int(duration_ms / step_ms))

    def stamp(i: int) -> tuple[int, int]:
        t = t0 + (i * step_ms) / 1000.0
        sec = int(t)
        usec = int((t - sec) * 1_000_000)
        return sec, usec

    sec, usec = stamp(0)
    events.extend(
        [
            Ev(sec, usec, EV_ABS, ABS_MT_SLOT, 0),
            Ev(sec, usec, EV_ABS, ABS_MT_TRACKING_ID, 1),
            Ev(sec, usec, EV_ABS, ABS_MT_POSITION_X, start_x),
            Ev(sec, usec, EV_ABS, ABS_MT_POSITION_Y, start_y),
            Ev(sec, usec, EV_KEY, BTN_TOUCH, 1),
            Ev(sec, usec, EV_KEY, BTN_TOOL_FINGER, 1),
            Ev.syn(sec, usec),
        ]
    )
    x, y = start_x, start_y
    for i in range(1, steps + 1):
        x += dx
        y += dy
        sec, usec = stamp(i)
        events.extend(
            [
                Ev(sec, usec, EV_ABS, ABS_MT_POSITION_X, x),
                Ev(sec, usec, EV_ABS, ABS_MT_POSITION_Y, y),
                Ev.syn(sec, usec),
            ]
        )
    sec, usec = stamp(steps + 1)
    events.extend(
        [
            Ev(sec, usec, EV_ABS, ABS_MT_TRACKING_ID, -1),
            Ev(sec, usec, EV_KEY, BTN_TOUCH, 0),
            Ev(sec, usec, EV_KEY, BTN_TOOL_FINGER, 0),
            Ev.syn(sec, usec),
        ]
    )
    return events


def run_selftest() -> dict[str, Any]:
    """Prove exec_delay drops short brushes and passes longer ones."""
    short_pipe = build_pipeline(
        {
            "filters": [
                {"plugin": "exec_delay", "ms": 40},
                {"plugin": "outlier_reject", "max_delta": DEFAULT_MAX_DELTA},
            ]
        }
    )
    short = make_sim_brush(duration_ms=20, dx=3)
    short_out = short_pipe.process_events(short)

    long_pipe = build_pipeline(
        {
            "filters": [
                {"plugin": "exec_delay", "ms": 40},
                {"plugin": "outlier_reject", "max_delta": DEFAULT_MAX_DELTA},
            ]
        }
    )
    long = make_sim_brush(duration_ms=80, dx=3)
    long_out = long_pipe.process_events(long)

    spike_pipe = build_pipeline(
        {"filters": [{"plugin": "outlier_reject", "max_delta": 50}]}
    )
    spike = make_sim_brush(duration_ms=30, dx=200, step_ms=10)
    spike_out = spike_pipe.process_events(spike)

    # New contact far from previous must not lock out (regression).
    lock_pipe = build_pipeline(
        {"filters": [{"plugin": "outlier_reject", "max_delta": 50}]}
    )
    a = make_sim_brush(duration_ms=30, start_x=100, start_y=100, dx=2)
    b = make_sim_brush(duration_ms=30, start_x=3000, start_y=2000, dx=2)
    lock_out = lock_pipe.process_events(a + b)

    return {
        "short_brush_in": len(short),
        "short_brush_out": len(short_out),
        "short_dropped": len(short_out) == 0,
        "long_brush_out": len(long_out),
        "long_passed": len(long_out) > 0,
        "spike_out": len(spike_out),
        "spike_reduced": len(spike_out) < len(spike),
        "relocated_contact_out": len(lock_out),
        "relocated_ok": len(lock_out) > len(a) // 2,
        "ok": (
            len(short_out) == 0
            and len(long_out) > 0
            and len(spike_out) < len(spike)
            and len(lock_out) > len(a) // 2
        ),
    }
