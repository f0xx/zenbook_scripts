"""DMI-aware hotkey profile loading from conf.d/*.conf files."""

from __future__ import annotations

import configparser
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from zenbook_kb.keycodes import KeyAction, NAME_TO_CODE, key_label
from zenbook_kb.users import default_hotkeys_config

_PKG_ROOT = Path(__file__).resolve().parent.parent
_DMI_SYSFS = Path("/sys/class/dmi/id")

# Installed share tree overrides project-relative conf.d when present.
_CONF_SEARCH = (
    Path("/usr/local/share/zenbook-scripts/conf.d"),
    _PKG_ROOT / "conf.d",
)


@dataclass(frozen=True)
class DmiInfo:
    board_name: str = ""
    product_name: str = ""
    product_family: str = ""
    board_vendor: str = ""
    sys_vendor: str = ""
    bios_version: str = ""

    @classmethod
    def read(cls) -> DmiInfo:
        def _read(name: str) -> str:
            path = _DMI_SYSFS / name
            try:
                return path.read_text().strip()
            except OSError:
                return ""

        return cls(
            board_name=_read("board_name"),
            product_name=_read("product_name"),
            product_family=_read("product_family"),
            board_vendor=_read("board_vendor"),
            sys_vendor=_read("sys_vendor"),
            bios_version=_read("bios_version"),
        )

    def as_dict(self) -> dict[str, str]:
        return {
            "board_name": self.board_name,
            "product_name": self.product_name,
            "product_family": self.product_family,
            "board_vendor": self.board_vendor,
            "sys_vendor": self.sys_vendor,
            "bios_version": self.bios_version,
        }


@dataclass
class MappingOptions:
    usb_poll: str = "auto"  # auto | true | false
    log_unmapped: bool = True
    device_name: str = "Zenbook Duo Keyboard"
    priority: int = 0
    service_verbose: bool = False
    service_debug: bool = False


@dataclass
class MappingProfile:
    path: Path
    options: MappingOptions = field(default_factory=MappingOptions)
    evdev_actions: dict[int, KeyAction] = field(default_factory=dict)
    usb_actions: dict[int, KeyAction] = field(default_factory=dict)
    priority: int = 0


_PROFILE_FIELDS = (
    "board_name",
    "product_name",
    "product_family",
    "board_vendor",
    "sys_vendor",
    "bios_version",
)


def _parse_profile_criteria(cfg: configparser.ConfigParser) -> dict[str, str]:
    if not cfg.has_section("profile"):
        return {}
    out: dict[str, str] = {}
    for key in _PROFILE_FIELDS:
        if cfg.has_option("profile", key):
            value = cfg.get("profile", key).strip()
            if value:
                out[key] = value
    return out


def _criteria_match(criteria: dict[str, str], dmi: DmiInfo) -> bool:
    if not criteria:
        return True
    dmi_map = dmi.as_dict()
    for key, needle in criteria.items():
        hay = dmi_map.get(key, "")
        if needle.lower() not in hay.lower():
            return False
    return True


def _filename_hint_match(path: Path, dmi: DmiInfo) -> bool:
    """UX8406MA.evdev.conf matches when board_name contains UX8406MA."""
    stem = path.name.split(".", 1)[0]
    if stem in ("00-default", "default"):
        return True
    board = dmi.board_name.upper()
    return stem.upper() in board or board.startswith(stem.upper())


def _parse_actions_section(
    cfg: configparser.ConfigParser, section: str
) -> dict[int, KeyAction]:
    if section not in cfg:
        return {}
    actions: dict[int, KeyAction] = {}
    for key_name, value in cfg[section].items():
        key_name = key_name.strip().upper()
        if not key_name or key_name.startswith("#"):
            continue
        if key_name.isdigit():
            code = int(key_name, 0)
        elif key_name.startswith("0X"):
            code = int(key_name, 16)
        elif key_name in NAME_TO_CODE:
            code = NAME_TO_CODE[key_name]
        else:
            continue
        actions[code] = KeyAction.parse(value)
    return actions


def _parse_options(cfg: configparser.ConfigParser) -> MappingOptions:
    opts = MappingOptions()
    if not cfg.has_section("options"):
        return opts
    if cfg.has_option("options", "usb_poll"):
        opts.usb_poll = cfg.get("options", "usb_poll").strip().lower()
    if cfg.has_option("options", "log_unmapped"):
        opts.log_unmapped = cfg.getboolean("options", "log_unmapped")
    if cfg.has_option("options", "device_name"):
        opts.device_name = cfg.get("options", "device_name").strip()
    if cfg.has_option("options", "service_verbose"):
        opts.service_verbose = cfg.getboolean("options", "service_verbose")
    if cfg.has_option("options", "service_debug"):
        opts.service_debug = cfg.getboolean("options", "service_debug")
    if cfg.has_option("options", "priority"):
        opts.priority = cfg.getint("options", "priority")
    if cfg.has_option("profile", "priority"):
        opts.priority = cfg.getint("profile", "priority")
    return opts


def load_profile_file(path: Path, dmi: DmiInfo) -> MappingProfile | None:
    cfg = configparser.ConfigParser()
    cfg.read(path)
    criteria = _parse_profile_criteria(cfg)
    if criteria:
        if not _criteria_match(criteria, dmi):
            return None
    elif not _filename_hint_match(path, dmi):
        return None

    opts = _parse_options(cfg)
    profile = MappingProfile(path=path, options=opts, priority=opts.priority)
    profile.evdev_actions = _parse_actions_section(cfg, "hotkeys")
    profile.usb_actions = _parse_actions_section(cfg, "usb_hotkeys")
    return profile


def conf_dirs() -> list[Path]:
    seen: set[Path] = set()
    dirs: list[Path] = []
    for path in _CONF_SEARCH:
        resolved = path.resolve()
        if resolved.is_dir() and resolved not in seen:
            seen.add(resolved)
            dirs.append(resolved)
    return dirs


def list_profile_files(kind: str) -> list[Path]:
    pattern = re.compile(rf"\.{kind}\.conf$")
    files: list[Path] = []
    for directory in conf_dirs():
        for path in sorted(directory.glob("*.conf")):
            if pattern.search(path.name):
                files.append(path)
    return files


def hid_asus_handles_detachable_keyboard() -> bool:
    """True when hid-asus (stock or sideload) owns the UX8406 USB/BT HID nodes."""
    hid_root = Path("/sys/bus/hid/devices")
    if not hid_root.is_dir():
        return False
    for node in hid_root.iterdir():
        name = node.name.upper()
        if "0B05" not in name:
            continue
        if "1B2C" not in name and "1B2D" not in name:
            continue
        driver = node / "driver"
        if driver.is_symlink() and "asus" in os.fsdecode(driver.readlink()).lower():
            return True
    return False


def usb_if4_kernel_hid_active() -> bool:
    """True when USB interface 4 already has a kernel HID node (do not claim via pyusb)."""
    hid_root = Path("/sys/bus/hid/devices")
    if not hid_root.is_dir():
        return False
    for node in hid_root.iterdir():
        if "0B05" not in node.name.upper() or "1B2C" not in node.name.upper():
            continue
        try:
            path = os.path.realpath(node)
        except OSError:
            continue
        if ":1.4/" in path:
            return True
    return False


def resolve_usb_poll(option: str) -> bool:
    mode = (option or "auto").lower()
    if mode == "true":
        return True
    if mode == "false":
        return False
    if hid_asus_handles_detachable_keyboard():
        return False
    if usb_if4_kernel_hid_active():
        return False
    return True


@dataclass
class ResolvedMappings:
    dmi: DmiInfo
    evdev_actions: dict[int, KeyAction]
    usb_actions: dict[int, KeyAction]
    options: MappingOptions
    profiles: list[MappingProfile]
    user_config: Path | None

    @property
    def log_unmapped(self) -> bool:
        return self.options.log_unmapped

    @property
    def use_usb(self) -> bool:
        return resolve_usb_poll(self.options.usb_poll)

    @property
    def device_name(self) -> str:
        return self.options.device_name or "Zenbook Duo Keyboard"


def _load_user_file(path: Path) -> tuple[dict[int, KeyAction], dict[int, KeyAction], MappingOptions]:
    opts = MappingOptions()
    evdev: dict[int, KeyAction] = {}
    usb: dict[int, KeyAction] = {}
    if not path.is_file():
        return evdev, usb, opts
    cfg = configparser.ConfigParser()
    cfg.read(path)
    evdev = _parse_actions_section(cfg, "hotkeys")
    usb = _parse_actions_section(cfg, "usb_hotkeys")
    if cfg.has_section("options"):
        if cfg.has_option("options", "usb_poll"):
            opts.usb_poll = cfg.get("options", "usb_poll").strip().lower()
        if cfg.has_option("options", "log_unmapped"):
            opts.log_unmapped = cfg.getboolean("options", "log_unmapped")
        if cfg.has_option("options", "device_name"):
            opts.device_name = cfg.get("options", "device_name").strip()
        if cfg.has_option("options", "service_verbose"):
            opts.service_verbose = cfg.getboolean("options", "service_verbose")
        if cfg.has_option("options", "service_debug"):
            opts.service_debug = cfg.getboolean("options", "service_debug")
    return evdev, usb, opts


def load_mappings(user_config: Path | None = None) -> ResolvedMappings:
    dmi = DmiInfo.read()
    user_path = user_config or default_hotkeys_config()
    merged_evdev: dict[int, KeyAction] = {}
    merged_usb: dict[int, KeyAction] = {}
    merged_opts = MappingOptions(log_unmapped=True, usb_poll="auto")
    applied: list[MappingProfile] = []

    for kind in ("evdev", "usb"):
        candidates: list[MappingProfile] = []
        for path in list_profile_files(kind):
            profile = load_profile_file(path, dmi)
            if profile is not None:
                candidates.append(profile)
        candidates.sort(key=lambda p: (p.priority, p.path.name))
        for profile in candidates:
            if kind == "evdev":
                merged_evdev.update(profile.evdev_actions)
            else:
                merged_usb.update(profile.usb_actions)
            if profile.options.priority >= merged_opts.priority:
                merged_opts.usb_poll = profile.options.usb_poll or merged_opts.usb_poll
                merged_opts.log_unmapped = profile.options.log_unmapped
                merged_opts.device_name = profile.options.device_name or merged_opts.device_name
            applied.append(profile)

    user_evdev, user_usb, user_opts = _load_user_file(user_path)
    merged_evdev.update(user_evdev)
    merged_usb.update(user_usb)
    if user_path.is_file():
        if user_opts.usb_poll:
            merged_opts.usb_poll = user_opts.usb_poll
        merged_opts.log_unmapped = user_opts.log_unmapped
        if user_opts.device_name:
            merged_opts.device_name = user_opts.device_name
        merged_opts.service_verbose = user_opts.service_verbose
        merged_opts.service_debug = user_opts.service_debug

    return ResolvedMappings(
        dmi=dmi,
        evdev_actions=merged_evdev,
        usb_actions=merged_usb,
        options=merged_opts,
        profiles=applied,
        user_config=user_path if user_path.is_file() else None,
    )


def format_mapping_report(resolved: ResolvedMappings, *, verbose: bool = False) -> str:
    lines = [
        "DMI:",
        f"  board_name={resolved.dmi.board_name!r}",
        f"  product_name={resolved.dmi.product_name!r}",
        f"  product_family={resolved.dmi.product_family!r}",
        f"  bios_version={resolved.dmi.bios_version!r}",
        f"hid-asus owns detachable keyboard: {hid_asus_handles_detachable_keyboard()}",
        f"usb_poll resolved: {resolved.use_usb} (option={resolved.options.usb_poll!r})",
        f"log_unmapped: {resolved.options.log_unmapped}",
        f"device_name: {resolved.options.device_name!r}",
        "",
        "conf.d profiles:",
    ]
    if resolved.profiles:
        for profile in resolved.profiles:
            lines.append(
                f"  {profile.path.name} "
                f"(evdev={len(profile.evdev_actions)}, usb={len(profile.usb_actions)})"
            )
    else:
        lines.append("  (none matched)")
    lines.append("")
    if resolved.user_config:
        lines.append(f"user overrides: {resolved.user_config}")
    else:
        hotkeys = default_hotkeys_config()
        lines.append(f"user overrides: (none — copy {hotkeys.name} to customize)")
    lines.append("")
    lines.append("evdev bindings:")
    if resolved.evdev_actions:
        for code in sorted(resolved.evdev_actions):
            action = resolved.evdev_actions[code]
            lines.append(f"  {key_label(code)} ({code}) = {action.kind}:{action.arg}")
    else:
        lines.append("  (none)")
    lines.append("usb bindings:")
    if resolved.usb_actions:
        for code in sorted(resolved.usb_actions):
            action = resolved.usb_actions[code]
            lines.append(f"  0x{code:02x} = {action.kind}:{action.arg}")
    else:
        lines.append("  (none)")
    if verbose:
        lines.extend(
            [
                "",
                f"service_verbose: {resolved.options.service_verbose}",
                f"service_debug: {resolved.options.service_debug}",
            ]
        )
    return "\n".join(lines)
