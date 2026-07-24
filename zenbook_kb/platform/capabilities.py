"""Generic laptop platform capability detection (vendor-agnostic).

Probes sysfs only (stdlib). Used by ``platform-probe``, installers, and the tray.
ASUS-specific nodes are one backend among others — absence is a normal result.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from zenbook_kb.dmi import board_name, has_platform_profile, has_screenpad_sysfs, product_name


@dataclass
class Feature:
    """One capability with support level and optional detail."""

    id: str
    label: str
    supported: bool
    detail: str = ""
    backend: str = ""  # e.g. asus-nb-wmi, intel_pstate, libinput
    install_hint: str = ""  # package / USE / CLI tip


@dataclass
class ProbeReport:
    dmi_product: str
    dmi_board: str
    features: list[Feature] = field(default_factory=list)
    recommend_use: list[str] = field(default_factory=list)
    recommend_skip_use: list[str] = field(default_factory=list)

    def by_id(self, feature_id: str) -> Feature | None:
        for f in self.features:
            if f.id == feature_id:
                return f
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "dmi_product": self.dmi_product,
            "dmi_board": self.dmi_board,
            "features": [asdict(f) for f in self.features],
            "recommend_use": self.recommend_use,
            "recommend_skip_use": self.recommend_skip_use,
        }


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return None


def _hwmon_named(name: str) -> Path | None:
    root = Path("/sys/class/hwmon")
    if not root.is_dir():
        return None
    for d in root.iterdir():
        if _read(d / "name") == name:
            return d
    return None


def find_fan_hwmon() -> tuple[Path | None, str]:
    """Prefer asus hwmon; else any hwmon with fan1_input + pwm1_enable."""
    asus = Path("/sys/devices/platform/asus-nb-wmi/hwmon")
    if asus.is_dir():
        for d in asus.iterdir():
            if _read(d / "name") == "asus":
                return d, "asus-nb-wmi"
    generic = _hwmon_named("asus")
    if generic and (generic / "fan1_input").is_file():
        return generic, "asus-hwmon"
    root = Path("/sys/class/hwmon")
    if root.is_dir():
        for d in sorted(root.iterdir()):
            if (d / "fan1_input").is_file() and (d / "pwm1_enable").is_file():
                return d, f"hwmon:{_read(d / 'name') or d.name}"
    # RPM-only (acpi_fan etc.)
    if root.is_dir():
        for d in sorted(root.iterdir()):
            if (d / "fan1_input").is_file():
                return d, f"rpm-only:{_read(d / 'name') or d.name}"
    return None, ""


def probe_fan_pwm(hw: Path | None, backend: str) -> Feature:
    if not hw:
        return Feature(
            "fan_pwm",
            "Fan PWM control",
            False,
            "no hwmon with fan1_input",
            install_hint="platform-fan needs asus-nb-wmi or pwm-capable hwmon",
        )
    enable = hw / "pwm1_enable"
    if not enable.is_file():
        return Feature(
            "fan_pwm",
            "Fan PWM control",
            False,
            f"RPM only via {backend} (no pwm1_enable)",
            backend=backend,
            install_hint="status/rpm only; no auto/full toggle",
        )
    # Probe modes without writing: try reading; document known ASUS behaviour
    curves = list(hw.glob("pwm1_auto_point_*"))
    cur = _read(enable)
    detail = f"pwm1_enable={cur}"
    if curves:
        detail += f"; {len(curves)} curve nodes present"
    else:
        detail += "; no pwm*_auto_point_* (custom curves unavailable)"
    return Feature(
        "fan_pwm",
        "Fan PWM control",
        True,
        detail,
        backend=backend,
        install_hint="platform-fan auto|full",
    )


def probe_fan_rpm(hw: Path | None, backend: str) -> Feature:
    if not hw or not (hw / "fan1_input").is_file():
        return Feature("fan_rpm", "Fan RPM readout", False, "missing fan1_input")
    rpm = _read(hw / "fan1_input")
    return Feature(
        "fan_rpm",
        "Fan RPM readout",
        True,
        f"fan1_input={rpm}",
        backend=backend,
        install_hint="platform-fan rpm|status",
    )


def probe_platform_profile() -> Feature:
    path = Path("/sys/firmware/acpi/platform_profile")
    if not path.is_file():
        return Feature(
            "platform_profile",
            "ACPI platform profile",
            False,
            "no /sys/firmware/acpi/platform_profile",
        )
    choices = _read(Path("/sys/firmware/acpi/platform_profile_choices")) or ""
    cur = _read(path) or ""
    return Feature(
        "platform_profile",
        "ACPI platform profile",
        True,
        f"current={cur}; choices={choices}",
        backend="acpi",
        install_hint="kb-platform-profile / platform-fan profile",
    )


def probe_asus_wmi() -> Feature:
    base = Path("/sys/devices/platform/asus-nb-wmi")
    if not base.is_dir():
        return Feature("asus_wmi", "ASUS WMI platform", False, "asus-nb-wmi absent")
    bits = []
    for name in ("throttle_thermal_policy", "cpufv", "platform-profile"):
        if (base / name).exists():
            bits.append(name)
    return Feature(
        "asus_wmi",
        "ASUS WMI platform",
        True,
        "nodes: " + (", ".join(bits) if bits else "(minimal)"),
        backend="asus-nb-wmi",
        install_hint="USE=fan_control optional",
    )


def probe_intel_pstate() -> Feature:
    root = Path("/sys/devices/system/cpu/intel_pstate")
    if not root.is_dir():
        driver = _read(Path("/sys/devices/system/cpu/cpu0/cpufreq/scaling_driver"))
        return Feature(
            "intel_pstate",
            "Intel P-state / HWP",
            False,
            f"scaling_driver={driver or 'n/a'}",
        )
    status = _read(root / "status") or ""
    epp = _read(
        Path("/sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference")
    )
    return Feature(
        "intel_pstate",
        "Intel P-state / HWP",
        True,
        f"status={status}; epp={epp}",
        backend="intel_pstate",
        install_hint="platform-fan-control profile key: epp",
    )


def probe_rapl() -> Feature:
    root = Path("/sys/class/powercap/intel-rapl:0")
    if not root.is_dir():
        return Feature("rapl", "Intel RAPL power caps", False, "no intel-rapl:0")
    name = _read(root / "name") or ""
    pl = _read(root / "constraint_0_power_limit_uw")
    return Feature(
        "rapl",
        "Intel RAPL power caps",
        True,
        f"name={name}; constraint_0_uw={pl}",
        backend="powercap",
        install_hint="platform-fan-control profile key: rapl.pl1_w / pl2_w",
    )


def probe_kbd_backlight() -> Feature:
    for name in ("asus::kbd_backlight", "asus::kbd_backlight_1"):
        p = Path("/sys/class/leds") / name
        if p.is_dir():
            bright = _read(p / "brightness")
            return Feature(
                "kbd_backlight",
                "Keyboard backlight",
                True,
                f"{name} brightness={bright}",
                backend="leds",
                install_hint="kb-brightness",
            )
    leds = Path("/sys/class/leds")
    if leds.is_dir():
        for d in leds.iterdir():
            if "kbd" in d.name.lower() or "keyboard" in d.name.lower():
                return Feature(
                    "kbd_backlight",
                    "Keyboard backlight",
                    True,
                    d.name,
                    backend="leds",
                    install_hint="kb-brightness (may need mapping)",
                )
    return Feature("kbd_backlight", "Keyboard backlight", False, "no kbd LED sysfs")


def probe_screenpad() -> Feature:
    if has_screenpad_sysfs():
        return Feature(
            "screenpad",
            "ASUS ScreenPad backlight",
            True,
            "asus_screenpad sysfs",
            backend="asus_screenpad",
            install_hint="USE=screenpad; screenpad CLI",
        )
    return Feature("screenpad", "ASUS ScreenPad backlight", False, "no asus_screenpad")


def probe_lid() -> Feature:
    base = Path("/proc/acpi/button/lid")
    if not base.is_dir():
        return Feature("lid", "Lid switch", False, "no /proc/acpi/button/lid")
    for state in base.glob("*/state"):
        text = _read(state) or ""
        return Feature("lid", "Lid switch", True, text, backend="acpi", install_hint="sleep/lid hooks")
    return Feature("lid", "Lid switch", False, "lid dir empty")


def probe_ac() -> Feature:
    base = Path("/sys/class/power_supply")
    if not base.is_dir():
        return Feature("ac_power", "AC adapter", False, "no power_supply")
    for psy in base.iterdir():
        if _read(psy / "type") == "Mains":
            online = _read(psy / "online")
            return Feature(
                "ac_power",
                "AC adapter",
                True,
                f"{psy.name} online={online}",
                backend="power_supply",
                install_hint="platform-fan-control rules.ac/battery",
            )
    return Feature("ac_power", "AC adapter", False, "no Mains supply")


def probe_touchpad() -> Feature:
    """Detect touchpads; sensitivity is DE/libinput — not a sysfs knob we own yet."""
    names: list[str] = []
    for name_path in Path("/sys/class/input").glob("event*/device/name"):
        n = _read(name_path) or ""
        low = n.lower()
        if (
            "touchpad" in low
            or "trackpad" in low
            or "synaptics" in low
            or ("elan" in low and "touch" in low)
        ):
            names.append(n)
    if not names and shutil.which("libinput"):
        try:
            out = subprocess.check_output(
                ["libinput", "list-devices"],
                text=True,
                stderr=subprocess.DEVNULL,
                timeout=5,
            )
        except (subprocess.SubprocessError, OSError):
            out = ""
        for line in out.splitlines():
            if line.startswith("Device:") and "touchpad" in line.lower():
                names.append(line.split(":", 1)[1].strip())
    if names:
        uniq = list(dict.fromkeys(names))[:5]
        return Feature(
            "touchpad",
            "Touchpad present",
            True,
            "; ".join(uniq),
            backend="libinput/evdev",
            install_hint=(
                "palm filter: platform-touchpad monitor|run; "
                "AccelSpeed still via Plasma/libinput"
            ),
        )
    return Feature(
        "touchpad",
        "Touchpad present",
        False,
        "no touchpad input node found",
        install_hint="roadmap item if hardware appears",
    )


def probe_touchpad_sensitivity() -> Feature:
    """Whether we can configure sensitivity from this package today."""
    # Wayland: no portable userspace write without compositor APIs.
    # X11: xinput/libinput properties — fragile under Plasma Wayland (this host).
    wayland = bool(os.environ.get("WAYLAND_DISPLAY"))
    if wayland:
        return Feature(
            "touchpad_sensitivity",
            "Touchpad sensitivity control",
            False,
            "Wayland session: use Plasma System Settings → Mouse & Touchpad "
            "(libinput AccelSpeed). Our CLI cannot set it portably yet.",
            backend="compositor",
            install_hint="platform-touchpad for palm/exec-delay; AccelSpeed via Plasma",
        )
    if shutil.which("xinput"):
        return Feature(
            "touchpad_sensitivity",
            "Touchpad sensitivity control",
            True,
            "X11: xinput/libinput AccelSpeed possible (experimental)",
            backend="xinput",
            install_hint="platform-touchpad for palm filters; AccelSpeed via xinput",
        )
    return Feature(
        "touchpad_sensitivity",
        "Touchpad sensitivity control",
        False,
        "no portable AccelSpeed path; use platform-touchpad palm filters",
        install_hint="platform-touchpad monitor|run",
    )


def probe_duo_keyboard_bt() -> Feature:
    """UX8406 Primax BT keyboard bind health (keys missing when rdesc fixup fails)."""
    product = (product_name() or "") + " " + (board_name() or "")
    if "UX8406" not in product.upper():
        return Feature(
            "duo_kb_bt",
            "Duo keyboard (Bluetooth)",
            False,
            "not UX8406",
        )
    try:
        from zenbook_kb.touchpad import duo_keyboard_hid_health

        h = duo_keyboard_hid_health()
    except Exception as exc:  # noqa: BLE001
        return Feature("duo_kb_bt", "Duo keyboard (Bluetooth)", False, str(exc))

    if h.get("usb_pogo_1b2c"):
        return Feature(
            "duo_kb_bt",
            "Duo keyboard (Bluetooth)",
            True,
            "USB pogo present (BT path idle)",
            backend="usb-1b2c",
        )
    ifaces = h.get("bt_hid_ifaces") or []
    if not ifaces:
        return Feature(
            "duo_kb_bt",
            "Duo keyboard (Bluetooth)",
            False,
            "no BT HID 0b05:1b2d",
            install_hint="pair/connect ASUS Zenbook Duo Keyboard",
        )
    if h.get("bt_keys_missing") or h.get("bt_keyboard_unbound"):
        return Feature(
            "duo_kb_bt",
            "Duo keyboard (Bluetooth)",
            False,
            h.get("hint") or "BT HID bound but no keyboard event node",
            backend="bluetooth",
            install_hint="sideload oot hid-asus (BT Usage76 skip) then reconnect BT",
        )
    nodes = h.get("bt_keyboard_event_nodes") or []
    return Feature(
        "duo_kb_bt",
        "Duo keyboard (Bluetooth)",
        True,
        f"keyboard nodes: {', '.join(nodes)}",
        backend="bluetooth",
    )


def build_report() -> ProbeReport:
    product = product_name() or "unknown"
    board = board_name() or "unknown"
    hw, backend = find_fan_hwmon()
    features = [
        probe_platform_profile(),
        probe_asus_wmi(),
        probe_fan_rpm(hw, backend),
        probe_fan_pwm(hw, backend),
        probe_intel_pstate(),
        probe_rapl(),
        probe_kbd_backlight(),
        probe_screenpad(),
        probe_lid(),
        probe_ac(),
        probe_touchpad(),
        probe_touchpad_sensitivity(),
        probe_duo_keyboard_bt(),
    ]
    use: list[str] = []
    skip: list[str] = []
    if features[0].supported:  # platform_profile
        use.append("fan_control")
    else:
        skip.append("fan_control")
    if any(f.id == "screenpad" and f.supported for f in features):
        use.append("screenpad")
    else:
        skip.append("screenpad")
    if "UX8406" in product.upper() or "UX8406" in board.upper():
        use.append("zenbook_ux8406")
        use.append("kernel")
        use.append("hotkeys")
    elif "UX5400" in product.upper():
        skip.append("kernel")
        skip.append("zenbook_ux8406")
    return ProbeReport(
        dmi_product=product,
        dmi_board=board,
        features=features,
        recommend_use=use,
        recommend_skip_use=skip,
    )


def format_report_text(report: ProbeReport, *, verbose: bool = True) -> str:
    lines = [
        f"DMI product: {report.dmi_product}",
        f"DMI board:   {report.dmi_board}",
        "",
        f"{'FEATURE':<28} {'OK':<5} DETAIL",
        "-" * 72,
    ]
    for f in report.features:
        mark = "yes" if f.supported else "no"
        detail = f.detail
        if verbose and f.backend:
            detail = f"[{f.backend}] {detail}"
        lines.append(f"{f.label:<28} {mark:<5} {detail}")
        if verbose and f.install_hint and not f.supported:
            lines.append(f"{'':28}       hint: {f.install_hint}")
    lines.append("")
    if report.recommend_use:
        lines.append("Suggested Gentoo USE+: " + " ".join(report.recommend_use))
    if report.recommend_skip_use:
        lines.append("Suggested Gentoo USE-: " + " ".join(f"-{u}" for u in report.recommend_skip_use))
    return "\n".join(lines)


def format_report_json(report: ProbeReport) -> str:
    return json.dumps(report.to_dict(), indent=2)


# Back-compat helpers used elsewhere
def has_platform_profile_feature() -> bool:
    return has_platform_profile()
