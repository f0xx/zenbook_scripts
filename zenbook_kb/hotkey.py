"""Dispatch Zenbook Duo / ASUS WMI special-key (Fn+) events."""

from __future__ import annotations

import argparse
import errno
import fcntl
import getpass
import importlib.util
import os
import pwd
import select
import shlex
import struct
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Support `python3 .../zenbook_kb/hotkey.py` without installing as a package.
_PKG_DIR = Path(__file__).resolve().parent
_PKG_ROOT = _PKG_DIR.parent
if str(_PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(_PKG_ROOT))


def _load_usb_hotkeys_module():
    """Import usb_hotkeys when executed as a script (OpenRC/systemd)."""
    try:
        from zenbook_kb import usb_hotkeys as mod

        return mod
    except ImportError:
        pass
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "zenbook_usb_hotkeys", _PKG_DIR / "usb_hotkeys.py"
    )
    if spec is None or spec.loader is None:
        raise ImportError("usb_hotkeys.py not found next to hotkey.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

EV_KEY = 0x01
INPUT_EVENT_SIZE = struct.calcsize("@llHHi")
INPUT_EVENT_FMT = "@llHHi"
EVIOCGRAB = 0x40044590

from zenbook_kb.fn_lock import find_vendor_hidraw, note_fn_lock_toggle
from zenbook_kb.keycodes import (
    KEY_KBDILLUMDOWN,
    KEY_KBDILLUMTOGGLE,
    KEY_KBDILLUMUP,
    NAME_TO_CODE,
    STANDARD_KEYS,
    KeyAction,
    key_label,
)
from zenbook_kb.mappings import format_mapping_report, load_mappings
from zenbook_kb.users import default_hotkeys_config

EXAMPLE_CONFIG_NAME = "zenbook-hotkeys.conf.example"
KEY_FN_ESC = NAME_TO_CODE.get("KEY_FN_ESC", 0x1D1)
FN_LOCK_VENDOR_CODE = 0x4E


def _seed_fn_lock_state() -> None:
    """Align tracked fn-lock with snapshot when hotkeys starts."""
    import re

    from zenbook_kb.fn_lock import read_fn_lock_state, write_fn_lock_state
    from zenbook_kb.users import resolve_config_dir

    if read_fn_lock_state() is not None:
        return
    snap = resolve_config_dir() / "zenbook_duo.save"
    if not snap.is_file():
        return
    for line in snap.read_text().splitlines():
        match = re.match(r"^fn_lock\s*=\s*([01])", line.strip())
        if match:
            write_fn_lock_state(int(match.group(1)))
            break


def _illum_codes(keys: set[int]) -> list[int]:
    need = {KEY_KBDILLUMTOGGLE, KEY_KBDILLUMDOWN, KEY_KBDILLUMUP}
    return sorted(keys & need)


def _format_watched_devices(devices: list[Path], *, verbose: bool = False) -> str:
    lines = ["Watched devices:"]
    if not devices:
        lines.append("  (none)")
        return "\n".join(lines)
    event_names = {p.name: p for p in Path("/sys/class/input").glob("event*")}
    for dev in devices:
        sys_path = event_names.get(dev.name)
        if not sys_path:
            lines.append(f"  {dev}: (sysfs node missing)")
            continue
        name = (sys_path / "device" / "name").read_text().strip()
        meta = _event_metadata(sys_path)
        illum = _illum_codes(_key_bitmap(sys_path / "device" / "capabilities" / "key"))
        iface = meta.get("iface", "?")
        product = meta.get("product", "?")
        lines.append(
            f"  {dev}: iface={iface} product={product} name={name!r} illum={illum}"
        )
        if verbose:
            special = sorted(
                c
                for c in _key_bitmap(sys_path / "device" / "capabilities" / "key")
                if c not in STANDARD_KEYS and c != 0
            )
            if special:
                lines.append("    special keys:")
                for code in special:
                    lines.append(f"      {code:4d}  {key_label(code)}")
    return "\n".join(lines)


def _log_service_startup(
    resolved,
    devices: list[Path],
    *,
    verbose: bool,
    debug: bool,
    dry_run: bool,
    grab: bool,
    kb_brightness: str,
    config_path: Path | None,
) -> None:
    try:
        pw = pwd.getpwuid(os.getuid())
        run_user = pw.pw_name
        run_home = pw.pw_dir
    except KeyError:
        run_user = getpass.getuser()
        run_home = str(Path.home())

    stamp = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    header = [
        "=== zenbook-kb-hotkeys start ===",
        f"timestamp: {stamp}",
        f"pid: {os.getpid()}",
        f"uid: {os.getuid()} user: {run_user}",
        f"home: {run_home}",
        f"kb_brightness: {kb_brightness}",
        f"config: {config_path or default_hotkeys_config()}",
        f"dry_run: {dry_run}",
        f"grab: {grab}",
        f"verbose: {verbose}",
        f"debug: {debug}",
        "",
        "Profile:",
        format_mapping_report(resolved, verbose=verbose),
        "",
        _format_watched_devices(devices, verbose=verbose),
        "=== listening ===",
        "",
    ]
    for line in header:
        print(line, flush=True)


def _key_bitmap(path: Path) -> set[int]:
    words = [int(word, 16) for word in path.read_text().split()]
    keys: set[int] = set()
    for word_index, word in enumerate(words):
        for bit in range(64):
            if (word >> bit) & 1:
                keys.add(word_index * 64 + bit)
    return keys


def _interface_number(event_dir: Path) -> str | None:
    """USB bInterfaceNumber for this input node, if any."""
    device = (event_dir / "device").resolve()
    for parent in [device, *device.parents]:
        iface = parent / "bInterfaceNumber"
        if iface.is_file():
            return iface.read_text().strip()
    return None


def _usb_product_id(event_dir: Path) -> str | None:
    """USB idProduct hex string for this input node, if any."""
    device = (event_dir / "device").resolve()
    for parent in [device, *device.parents]:
        product = parent / "idProduct"
        if product.is_file():
            return product.read_text().strip().lower()
    return None


def _event_metadata(event_dir: Path) -> dict[str, str]:
    """Sysfs metadata for an input event node."""
    name = (event_dir / "device" / "name").read_text().strip()
    meta: dict[str, str] = {"name": name, "event": event_dir.name}
    device = (event_dir / "device").resolve()
    for parent in [device, *device.parents]:
        for key, fname in (
            ("iface", "bInterfaceNumber"),
            ("product", "idProduct"),
            ("vendor", "idVendor"),
        ):
            if key not in meta and (parent / fname).is_file():
                meta[key] = (parent / fname).read_text().strip().lower()
    return meta


def _is_hotkey_candidate(event_dir: Path, name: str) -> bool:
    if name == "Asus WMI hotkeys":
        return True

    iface = _interface_number(event_dir)
    product = _usb_product_id(event_dir)

    detachable_names = (
        "Zenbook Duo Keyboard",
        "Asus Keyboard",
    )
    if not any(token in name for token in detachable_names):
        if iface != "04" or product not in (None, "1b2c", "1bf2"):
            if "Zenbook Duo" not in name and "ASUS" not in name.upper():
                return False
    if "Mouse" in name or "Touchpad" in name:
        return False

    # hid-asus vendor hotkeys: USB interface 4 (…004B, 90-byte rdesc, ep 0x85)
    if iface == "04" and product in (None, "1b2c", "1bf2"):
        return True

    # hid-asus after fake-keyboard inject may name this "Asus Keyboard"
    if name == "Asus Keyboard" and iface == "04":
        return True

    # hid-generic era: dedicated consumer / Fn interface 3 (not primary target)
    if "Zenbook Duo Keyboard" in name and iface == "03":
        return True

    keys = _key_bitmap(event_dir / "device" / "capabilities" / "key")
    # Main USB keyboard (interface 00) also lists consumer keys; never watch it.
    if iface in ("00", "01", "02"):
        return False
    if NAME_TO_CODE.get("KEY_FN", 464) in keys and iface in (None, "03", "04"):
        return True
    if keys & {KEY_KBDILLUMTOGGLE, KEY_KBDILLUMDOWN, KEY_KBDILLUMUP}:
        return iface in (None, "03", "04")
    return False


def find_hotkey_devices(name_substring: str = "Zenbook Duo Keyboard") -> list[Path]:
    """Input nodes that carry Fn+/vendor hotkeys (not the main typing interface)."""
    candidates: list[tuple[Path, Path]] = []
    input_root = Path("/sys/class/input")

    for event_dir in sorted(input_root.glob("event*")):
        caps_path = event_dir / "device" / "capabilities" / "key"
        if not caps_path.is_file():
            continue
        name = (event_dir / "device" / "name").read_text().strip()
        if not _is_hotkey_candidate(event_dir, name):
            continue
        dev = Path("/dev/input") / event_dir.name
        if dev.exists():
            candidates.append((dev, event_dir))

    has_if04 = any(
        _event_metadata(ed).get("iface") == "04"
        and _event_metadata(ed).get("product") in (None, "1b2c", "1bf2")
        for _d, ed in candidates
    )

    devices: list[Path] = []
    seen: set[Path] = set()
    for dev, event_dir in candidates:
        meta = _event_metadata(event_dir)
        if (
            has_if04
            and meta.get("iface") == "03"
            and meta.get("product") in ("1b2c", "1bf2")
        ):
            continue
        if dev not in seen:
            seen.add(dev)
            devices.append(dev)
    return devices


def load_user_actions(config_path: Path | None) -> dict[int, KeyAction]:
    """Legacy helper — prefer load_mappings()."""
    resolved = load_mappings(config_path)
    return dict(resolved.evdev_actions)


def load_usb_user_actions(config_path: Path | None) -> dict[int, KeyAction]:
    resolved = load_mappings(config_path)
    return dict(resolved.usb_actions)


def resolve_usb_action(
    code: int,
    *,
    actions: dict[int, KeyAction],
    log_unmapped: bool,
) -> KeyAction | None:
    if code in actions:
        return actions[code]
    if log_unmapped:
        return KeyAction("log")
    return None


def _run_cmd(argv: list[str], dry_run: bool) -> None:
    if dry_run:
        print("would run:", " ".join(shlex.quote(a) for a in argv), flush=True)
        return
    subprocess.run(argv, check=False)


def _run_shell(command: str, dry_run: bool) -> None:
    if dry_run:
        print("would shell:", command, flush=True)
        return
    subprocess.run(command, shell=True, check=False)


def _display_brightness(delta: str, dry_run: bool) -> None:
    for cmd in (
        ["brightnessctl", "set", f"{delta}10%"],
        ["light", "-A", "10"] if delta == "up" else ["light", "-U", "10"],
        ["xbacklight", "-inc", "10"] if delta == "up" else ["xbacklight", "-dec", "10"],
    ):
        if dry_run:
            print("would try:", " ".join(cmd), flush=True)
            return
        if subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
            return


def _rfkill_toggle(which: str, dry_run: bool) -> None:
    argv = ["rfkill", "toggle", which]
    if dry_run:
        print("would run:", " ".join(argv), flush=True)
        return
    subprocess.run(argv, check=False)


def _audio_mic_mute(dry_run: bool) -> None:
    for cmd in (
        ["pactl", "set-source-mute", "@DEFAULT_SOURCE@", "toggle"],
        ["amixer", "set", "Capture", "toggle"],
    ):
        if dry_run:
            print("would try:", " ".join(cmd), flush=True)
            return
        if subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
            return


def dispatch_action(
    action: KeyAction,
    *,
    kb_brightness: str,
    dry_run: bool,
) -> None:
    if action.kind == "ignore":
        return
    if action.kind == "log":
        return
    if action.kind == "kb-brightness":
        if action.arg == "toggle":
            _run_cmd([kb_brightness, "+1"], dry_run)
        elif action.arg.startswith("+") or action.arg.startswith("-"):
            _run_cmd([kb_brightness, action.arg], dry_run)
        elif action.arg.isdigit():
            _run_cmd([kb_brightness, action.arg], dry_run)
        else:
            _run_cmd([kb_brightness, action.arg], dry_run)
        return
    if action.kind == "display-brightness":
        if action.arg in ("up", "down"):
            _display_brightness(action.arg, dry_run)
        return
    if action.kind == "rfkill":
        _rfkill_toggle(action.arg or "wlan", dry_run)
        return
    if action.kind == "audio" and action.arg == "mic-mute":
        _audio_mic_mute(dry_run)
        return
    if action.kind == "shell":
        _run_shell(action.arg, dry_run)
        return
    if action.kind == "exec":
        _run_cmd(shlex.split(action.arg), dry_run)
        return
    _run_shell(f"{action.kind}:{action.arg}", dry_run)


def resolve_action(
    code: int,
    *,
    actions: dict[int, KeyAction],
    log_unmapped: bool,
) -> KeyAction | None:
    if code in actions:
        action = actions[code]
        if action.kind == "ignore":
            return action
        return action
    if code in STANDARD_KEYS:
        return None
    if log_unmapped:
        return KeyAction("log")
    return None


def _open_evdev_devices(devices: list[Path], *, grab: bool) -> dict[int, Path]:
    fds: dict[int, Path] = {}
    for dev in devices:
        try:
            fd = os.open(dev, os.O_RDONLY | os.O_NONBLOCK)
        except OSError as exc:
            print(f"warn: could not open {dev}: {exc}", file=sys.stderr, flush=True)
            continue
        if grab:
            try:
                fcntl.ioctl(fd, EVIOCGRAB, 1)
            except OSError as exc:
                print(f"warn: could not grab {dev}: {exc}", file=sys.stderr, flush=True)
        fds[fd] = dev
    return fds


def _close_evdev_fds(fds: dict[int, Path], *, grab: bool) -> None:
    for fd in list(fds):
        if grab:
            try:
                fcntl.ioctl(fd, EVIOCGRAB, 0)
            except OSError:
                pass
        try:
            os.close(fd)
        except OSError:
            pass


def listen(
    devices: list[Path],
    kb_brightness: str,
    config_path: Path | None = None,
    debounce_s: float = 0.15,
    dry_run: bool = False,
    log_unmapped: bool | None = None,
    use_usb: bool | None = None,
    grab: bool = False,
    watchdog_s: float | None = None,
    log_all_keys: bool = False,
    verbose: bool = False,
    debug: bool = False,
    *,
    device_name: str = "Zenbook Duo Keyboard",
    allow_rediscover: bool = True,
) -> int:
    resolved = load_mappings(config_path)
    evdev_actions = resolved.evdev_actions
    usb_actions = resolved.usb_actions
    verbose = verbose or resolved.options.service_verbose
    debug = debug or resolved.options.service_debug
    log_all_keys = log_all_keys or debug
    effective_log = resolved.log_unmapped if log_unmapped is None else log_unmapped
    if verbose or debug:
        effective_log = True
    effective_usb = resolved.use_usb if use_usb is None else use_usb

    watched_devices = list(devices)
    _log_service_startup(
        resolved,
        watched_devices,
        verbose=verbose,
        debug=debug,
        dry_run=dry_run,
        grab=grab,
        kb_brightness=kb_brightness,
        config_path=config_path,
    )
    fds = _open_evdev_devices(watched_devices, grab=grab)

    last_fire: dict[str, float] = {}

    def _rediscover_evdev(reason: str) -> None:
        nonlocal fds, watched_devices
        if not allow_rediscover:
            return
        _close_evdev_fds(fds, grab=grab)
        fds = {}
        watched_devices = find_hotkey_devices(device_name)
        if not watched_devices:
            print(f"Hotplug: {reason}; waiting for input devices...", flush=True)
            return
        fds = _open_evdev_devices(watched_devices, grab=grab)
        if fds:
            print(
                f"Hotplug: {reason}; now listening on "
                + ", ".join(str(fds[fd]) for fd in fds),
                flush=True,
            )

    usb_mod = None
    if effective_usb:
        try:
            usb_mod = _load_usb_hotkeys_module()
        except Exception as exc:
            print(f"USB hotkey module unavailable: {exc}", file=sys.stderr, flush=True)

    usb_mon = None
    if effective_usb and usb_mod is not None:
        try:
            usb_mon = usb_mod.UsbVendorHotkeys()
            if usb_mon.available:
                usb_mon.open()
                print("USB vendor hotkeys: interface 4 (interrupt 0x85)", flush=True)
            else:
                usb_mon = None
        except Exception as exc:
            print(f"USB vendor hotkeys unavailable: {exc}", file=sys.stderr, flush=True)
            usb_mon = None
    elif not effective_usb:
        print("USB vendor polling disabled (hid-asus or config)", flush=True)

    fn_hidraw_fd: int | None = None
    if not effective_usb:
        vendor_hidraw = find_vendor_hidraw()
        if vendor_hidraw is not None:
            try:
                fn_hidraw_fd = os.open(vendor_hidraw, os.O_RDONLY | os.O_NONBLOCK)
                if verbose:
                    print(f"fn-lock hidraw watch: {vendor_hidraw}", flush=True)
            except OSError as exc:
                print(f"fn-lock hidraw unavailable: {exc}", file=sys.stderr, flush=True)

    parts = [str(d) for d in watched_devices]
    if usb_mon:
        parts.append("usb:0b05:1b2c:if4")
    print("Listening on:", ", ".join(parts) or "(usb only)", flush=True)
    if watchdog_s is not None:
        print(f"Watchdog: {watchdog_s:.1f}s", flush=True)

    start = time.monotonic()

    try:
        while True:
            if watchdog_s is not None and (time.monotonic() - start) >= watchdog_s:
                print("Watchdog expired — exiting listener.", flush=True)
                return 0
            poll_fds = list(fds)
            if fn_hidraw_fd is not None:
                poll_fds.append(fn_hidraw_fd)
            if poll_fds:
                try:
                    readable, _, _ = select.select(poll_fds, [], [], 0.1)
                except OSError as exc:
                    if exc.errno == errno.ENODEV:
                        _rediscover_evdev("input device removed")
                        continue
                    raise
            else:
                readable = []
                if allow_rediscover:
                    _rediscover_evdev("no open devices")
                time.sleep(0.5)

            for fd in readable:
                if fn_hidraw_fd is not None and fd == fn_hidraw_fd:
                    while True:
                        try:
                            raw = os.read(fn_hidraw_fd, 64)
                        except BlockingIOError:
                            break
                        except OSError:
                            break
                        if not raw:
                            break
                        if usb_mod is not None:
                            ev = usb_mod.parse_vendor_report(raw)
                            if ev is not None and ev.code == usb_mod.VENDOR_FNLOCK:
                                new_mode = note_fn_lock_toggle()
                                if verbose:
                                    mode = "A" if new_mode else "B"
                                    print(
                                        f"fn-lock hidraw: → mode {mode} (tracked)",
                                        flush=True,
                                    )
                    continue
                while True:
                    try:
                        data = os.read(fd, INPUT_EVENT_SIZE * 32)
                    except BlockingIOError:
                        break
                    except OSError as exc:
                        if exc.errno == errno.ENODEV:
                            dead = fds.pop(fd, None)
                            try:
                                os.close(fd)
                            except OSError:
                                pass
                            label = str(dead) if dead else "fd"
                            _rediscover_evdev(f"{label} disconnected")
                            break
                        raise
                    if not data:
                        if fd in fds:
                            dead = fds.pop(fd)
                            try:
                                os.close(fd)
                            except OSError:
                                pass
                            _rediscover_evdev(f"{dead} closed")
                        break
                    for offset in range(0, len(data), INPUT_EVENT_SIZE):
                        chunk = data[offset : offset + INPUT_EVENT_SIZE]
                        if len(chunk) != INPUT_EVENT_SIZE:
                            continue
                        _sec, _usec, ev_type, code, value = struct.unpack(
                            INPUT_EVENT_FMT, chunk
                        )
                        if ev_type != EV_KEY or value != 1:
                            continue
                        if code == KEY_FN_ESC:
                            ev_sysfs = Path("/sys/class/input") / fds[fd].name
                            try:
                                if _event_metadata(ev_sysfs).get("name") == "Asus Keyboard":
                                    new_mode = note_fn_lock_toggle()
                                    if verbose:
                                        mode = "A" if new_mode else "B"
                                        print(
                                            f"{fds[fd].name}: fn-lock → mode {mode} (tracked)",
                                            flush=True,
                                        )
                            except OSError:
                                pass
                        if log_all_keys:
                            print(f"{fds[fd].name}: {key_label(code)} ({code})", flush=True)
                        action = resolve_action(
                            code,
                            actions=evdev_actions,
                            log_unmapped=effective_log,
                        )
                        if action is None:
                            continue
                        key_id = f"evdev:{code}"
                        now = time.monotonic()
                        if now - last_fire.get(key_id, 0.0) < debounce_s:
                            continue
                        last_fire[key_id] = now
                        label = key_label(code)
                        if action.kind == "ignore":
                            if verbose:
                                print(
                                    f"{fds[fd].name}: {label} ({code}) -> ignore",
                                    flush=True,
                                )
                            continue
                        if action.kind == "log":
                            print(
                                f"{fds[fd].name}: unmapped {label} ({code})",
                                flush=True,
                            )
                            continue
                        print(
                            f"{fds[fd].name}: {label} ({code}) -> {action.kind}:{action.arg}",
                            flush=True,
                        )
                        dispatch_action(action, kb_brightness=kb_brightness, dry_run=dry_run)

            if usb_mon is not None:
                ev = usb_mon.poll(timeout_ms=50)
                if ev is None:
                    continue
                if ev.code == FN_LOCK_VENDOR_CODE:
                    new_mode = note_fn_lock_toggle()
                    if verbose:
                        mode = "A" if new_mode else "B"
                        print(
                            f"usb:0x{ev.code:02x} fn-lock → mode {mode} (tracked)",
                            flush=True,
                        )
                action = resolve_usb_action(
                    ev.code,
                    actions=usb_actions,
                    log_unmapped=effective_log,
                )
                if action is None:
                    if debug:
                        print(
                            f"usb:0x{ev.code:02x} (unbound) raw={ev.raw.hex()}",
                            flush=True,
                        )
                    continue
                key_id = f"usb:{ev.code}"
                now = time.monotonic()
                if now - last_fire.get(key_id, 0.0) < debounce_s:
                    continue
                last_fire[key_id] = now
                if action.kind == "log":
                    print(
                        f"usb:0x{ev.code:02x} unmapped vendor code (raw={ev.raw.hex()})",
                        flush=True,
                    )
                    continue
                print(
                    f"usb:0x{ev.code:02x} -> {action.kind}:{action.arg} (raw={ev.raw.hex()})",
                    flush=True,
                )
                dispatch_action(action, kb_brightness=kb_brightness, dry_run=dry_run)
    except KeyboardInterrupt:
        return 0
    finally:
        if usb_mon is not None:
            usb_mon.close()
        if fn_hidraw_fd is not None:
            try:
                os.close(fn_hidraw_fd)
            except OSError:
                pass
        _close_evdev_fds(fds, grab=grab)


def list_device_keys(devices: list[Path]) -> int:
    """Print special keys exposed by watched devices (for mapping)."""
    event_names = {p.name: p for p in Path("/sys/class/input").glob("event*")}
    for dev in devices:
        ev = dev.name
        sys_path = event_names.get(ev)
        if not sys_path:
            print(f"{dev}: unknown")
            continue
        name = (sys_path / "device" / "name").read_text().strip()
        keys = sorted(_key_bitmap(sys_path / "device" / "capabilities" / "key"))
        special = [c for c in keys if c not in STANDARD_KEYS and c != 0]
        print(f"{dev}: {name}")
        for code in special:
            print(f"  {code:4d}  {key_label(code)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Handle Zenbook Duo Fn+ / vendor hotkeys",
    )
    parser.add_argument("--device", action="append", default=[], help="Explicit /dev/input/eventN")
    parser.add_argument("--kb-brightness", default="kb-brightness")
    parser.add_argument("--config", type=Path, default=None, help="Hotkey bindings config")
    parser.add_argument("--name", default="Zenbook Duo Keyboard")
    parser.add_argument("--list", action="store_true", help="List watched input devices")
    parser.add_argument("--show-keys", action="store_true", help="List special keys on watched devices")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--grab",
        action="store_true",
        help="EVIOCGRAB watched evdev nodes (prevents terminal escape garbage)",
    )
    parser.add_argument(
        "--watchdog",
        type=float,
        metavar="SECS",
        default=None,
        help="Exit after SECS (useful with --grab or --device event5)",
    )
    parser.add_argument(
        "--log-all-keys",
        action="store_true",
        help="Print every EV_KEY press (same as --debug for evdev)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Log startup diagnostics and runtime key dispatch/unmapped specials",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Like --verbose, and log every evdev key plus unbound USB vendor codes",
    )
    parser.add_argument("--no-usb", action="store_true", help="Disable USB vendor interface polling")
    parser.add_argument("--sniff-usb", type=float, metavar="SECS", help="Print raw USB vendor reports")
    parser.add_argument(
        "--sniff-all",
        type=float,
        metavar="SECS",
        help="Sniff evdev + hidraw + all USB interfaces (diagnostic)",
    )
    parser.add_argument("--show-profile", action="store_true", help="Show DMI + conf.d mapping profile")
    parser.add_argument("--quiet-unmapped", action="store_true", help="Do not log unmapped special keys")
    parser.add_argument(
        "--calibrate",
        action="store_true",
        help="Interactive Fn+/plain-F calibration walkthrough",
    )
    parser.add_argument(
        "--calibrate-quick",
        action="store_true",
        help="Calibration for F1–F4 only",
    )
    args = parser.parse_args(argv)

    if args.calibrate or args.calibrate_quick:
        from zenbook_kb.calibrate import main as calibrate_main, reexec_calibrate

        cal_argv: list[str] = []
        if args.calibrate_quick:
            cal_argv.append("--quick")
        reexec_calibrate(cal_argv)
        return calibrate_main(cal_argv)

    if args.show_profile:
        print(format_mapping_report(load_mappings(args.config)))
        return 0

    mapping = load_mappings(args.config)
    device_name = args.name if args.name != "Zenbook Duo Keyboard" else mapping.device_name

    if args.sniff_usb is not None:
        mod = _load_usb_hotkeys_module()
        return mod.sniff_usb(args.sniff_usb)

    if args.sniff_all is not None:
        spec = importlib.util.spec_from_file_location(
            "zenbook_sniff", _PKG_DIR / "sniff.py"
        )
        if spec is None or spec.loader is None:
            print("sniff.py not found", file=sys.stderr)
            return 1
        sniff_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(sniff_mod)
        return sniff_mod.sniff_all(args.sniff_all)

    devices = [Path(p) for p in args.device] if args.device else find_hotkey_devices(device_name)

    if args.list:
        for dev in devices:
            print(dev)
        if not args.no_usb:
            try:
                mod = _load_usb_hotkeys_module()
                if mod.UsbVendorHotkeys().available:
                    print("usb:0b05:1b2c:interface4")
            except Exception:
                pass
        return 0

    if args.show_keys:
        if not devices:
            print("No evdev hotkey devices; use --sniff-usb for USB vendor codes", file=sys.stderr)
            return 1
        return list_device_keys(devices)

    if not devices and args.no_usb:
        print(
            "No Zenbook / ASUS WMI hotkey input device found. "
            "Connect the keyboard and retry, or pass --device.",
            file=sys.stderr,
        )
        return 1

    _seed_fn_lock_state()

    return listen(
        devices,
        args.kb_brightness,
        config_path=args.config,
        dry_run=args.dry_run,
        log_unmapped=False if args.quiet_unmapped else None,
        use_usb=None if not args.no_usb else False,
        grab=args.grab,
        watchdog_s=args.watchdog,
        log_all_keys=args.log_all_keys,
        verbose=args.verbose,
        debug=args.debug,
        device_name=device_name,
        allow_rediscover=not args.device,
    )


if __name__ == "__main__":
    raise SystemExit(main())
