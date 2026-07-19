"""Install helpers shared by configure.py / configure.sh."""

from __future__ import annotations


import os
import shutil
import subprocess
from pathlib import Path

from zenbook_kb import paths as zb_paths
from zenbook_kb.users import resolve_run_user, validate_unix_user

# Filled by refresh_install_paths() — default prefix /usr
INSTALL_SHARE: Path
INSTALL_BIN_BRIGHTNESS: Path
INSTALL_BIN_HOTKEYS: Path
INSTALL_BIN_CALIBRATE: Path
INSTALL_BIN_SLEEP: Path
INSTALL_BIN_LID_WATCH: Path
INSTALL_BIN_SCREENPAD: Path
INSTALL_BIN_SCREENPAD_SYNC: Path
INSTALL_BIN_SCREENPAD_BOOT: Path
INSTALL_BIN_PLATFORM_PROFILE: Path
INSTALL_BIN_FAN: Path
INSTALL_BIN_FAN_LEGACY: Path
INSTALL_BIN_FAN_CONTROL: Path
INSTALL_BIN_FAN_CONTROL_LEGACY: Path
INSTALL_BIN_PLATFORM_PROBE: Path
INSTALL_BIN_PLATFORM_TRAY: Path
INSTALL_BIN_FAN_HOOK: Path
INSTALL_BIN_SNAPSHOT: Path
UDEV_RULES: Path
UDEV_SCREENPAD_RULES: Path
UDEV_HELPER: Path
OPENRC_INIT: Path
OPENRC_LID_INIT: Path
OPENRC_FAN_CONTROL_INIT: Path
OPENRC_FAN_CONTROL_CONF: Path
OPENRC_FAN_CONTROL_INIT_LEGACY: Path
OPENRC_HID_ASUS_INIT: Path
OPENRC_HID_ASUS_CONF: Path
OPENRC_SCREENPAD_INIT: Path
OPENRC_SCREENPAD_SYNC_INIT: Path
OPENRC_SCREENPAD_CONF: Path
INSTALL_LIBEXEC: Path
INSTALLED_KO_ROOT: Path
OPENRC_CONF: Path
SYSTEMD_UNIT: Path
SYSTEMD_SCREENPAD_UNIT: Path
SYSTEMD_SCREENPAD_SYNC_UNIT: Path
SYSTEMD_SLEEP_HOOK: Path
ACPI_EVENTS_DIR: Path
ACPI_SLEEP_EVENT: Path
ACPI_SLEEP_HELPER: Path
MODPROBE_CONF: Path


def refresh_install_paths(prefix: str | Path | None = None) -> Path:
    """Bind module paths to *prefix* (default: ZENBOOK_PREFIX or /usr)."""
    global INSTALL_SHARE, INSTALL_BIN_BRIGHTNESS, INSTALL_BIN_HOTKEYS
    global INSTALL_BIN_CALIBRATE, INSTALL_BIN_SLEEP, INSTALL_BIN_LID_WATCH
    global INSTALL_BIN_SCREENPAD, INSTALL_BIN_SCREENPAD_SYNC, INSTALL_BIN_SCREENPAD_BOOT
    global INSTALL_BIN_PLATFORM_PROFILE, INSTALL_BIN_FAN, INSTALL_BIN_FAN_LEGACY
    global INSTALL_BIN_FAN_CONTROL, INSTALL_BIN_FAN_CONTROL_LEGACY
    global INSTALL_BIN_PLATFORM_PROBE, INSTALL_BIN_PLATFORM_TRAY, INSTALL_BIN_FAN_HOOK
    global INSTALL_BIN_SNAPSHOT, UDEV_RULES, UDEV_SCREENPAD_RULES, UDEV_HELPER
    global OPENRC_INIT, OPENRC_LID_INIT, OPENRC_FAN_CONTROL_INIT, OPENRC_FAN_CONTROL_CONF
    global OPENRC_FAN_CONTROL_INIT_LEGACY, OPENRC_HID_ASUS_INIT, OPENRC_HID_ASUS_CONF
    global OPENRC_SCREENPAD_INIT, OPENRC_SCREENPAD_SYNC_INIT, OPENRC_SCREENPAD_CONF
    global INSTALL_LIBEXEC, INSTALLED_KO_ROOT, OPENRC_CONF
    global SYSTEMD_UNIT, SYSTEMD_SCREENPAD_UNIT, SYSTEMD_SCREENPAD_SYNC_UNIT
    global SYSTEMD_SLEEP_HOOK, ACPI_EVENTS_DIR, ACPI_SLEEP_EVENT, ACPI_SLEEP_HELPER
    global MODPROBE_CONF

    if prefix is not None:
        zb_paths.set_prefix(prefix)
    pfx = zb_paths.get_prefix()
    b = zb_paths.bin_dir()
    s = zb_paths.share_dir()
    lx = zb_paths.libexec_dir()

    INSTALL_SHARE = s
    INSTALL_BIN_BRIGHTNESS = b / "kb-brightness"
    INSTALL_BIN_HOTKEYS = b / "kb-brightness-hotkeys"
    INSTALL_BIN_CALIBRATE = b / "kb-calibrate-hotkeys"
    INSTALL_BIN_SLEEP = b / "kb-brightness-sleep"
    INSTALL_BIN_LID_WATCH = b / "kb-brightness-lid-watch"
    INSTALL_BIN_SCREENPAD = b / "screenpad"
    INSTALL_BIN_SCREENPAD_SYNC = b / "screenpad-sync"
    INSTALL_BIN_SCREENPAD_BOOT = b / "screenpad-boot"
    INSTALL_BIN_PLATFORM_PROFILE = b / "kb-platform-profile"
    INSTALL_BIN_FAN = b / "platform-fan"
    INSTALL_BIN_FAN_LEGACY = b / "kb-fan"
    INSTALL_BIN_FAN_CONTROL = b / "platform-fan-control"
    INSTALL_BIN_FAN_CONTROL_LEGACY = b / "kb-fan-control"
    INSTALL_BIN_PLATFORM_PROBE = b / "platform-probe"
    INSTALL_BIN_PLATFORM_TRAY = b / "platform-tray"
    INSTALL_BIN_FAN_HOOK = b / "zenbook-fan-control-hook"
    INSTALL_BIN_SNAPSHOT = b / "snapshot-plan-state"
    UDEV_RULES = zb_paths.UDEV_RULES_DIR / "99-zenbook-kb-hotkeys.rules"
    UDEV_SCREENPAD_RULES = zb_paths.UDEV_RULES_DIR / "99-zenbook-screenpad.rules"
    UDEV_HELPER = lx / "zenbook-kb-hotkeys-udev"
    OPENRC_INIT = zb_paths.INITD_DIR / "zenbook-kb-hotkeys"
    OPENRC_LID_INIT = zb_paths.INITD_DIR / "zenbook-kb-lid"
    OPENRC_FAN_CONTROL_INIT = zb_paths.INITD_DIR / "zenbook-platform-fan-control"
    OPENRC_FAN_CONTROL_CONF = zb_paths.CONFD_DIR / "zenbook-platform-fan-control"
    OPENRC_FAN_CONTROL_INIT_LEGACY = zb_paths.INITD_DIR / "zenbook-kb-fan-control"
    OPENRC_HID_ASUS_INIT = zb_paths.INITD_DIR / "zenbook-kb-hid-asus"
    OPENRC_HID_ASUS_CONF = zb_paths.CONFD_DIR / "zenbook-kb-hid-asus"
    OPENRC_SCREENPAD_INIT = zb_paths.INITD_DIR / "zenbook-screenpad"
    OPENRC_SCREENPAD_SYNC_INIT = zb_paths.INITD_DIR / "zenbook-screenpad-sync"
    OPENRC_SCREENPAD_CONF = zb_paths.CONFD_DIR / "zenbook-screenpad"
    INSTALL_LIBEXEC = lx
    INSTALLED_KO_ROOT = zb_paths.KO_ROOT
    OPENRC_CONF = zb_paths.CONFD_DIR / "zenbook-kb-hotkeys"
    SYSTEMD_UNIT = zb_paths.SYSTEMD_DIR / "zenbook-kb-hotkeys.service"
    SYSTEMD_SCREENPAD_UNIT = zb_paths.SYSTEMD_DIR / "zenbook-screenpad.service"
    SYSTEMD_SCREENPAD_SYNC_UNIT = zb_paths.SYSTEMD_DIR / "zenbook-screenpad-sync.service"
    SYSTEMD_SLEEP_HOOK = zb_paths.SYSTEMD_SLEEP_DIR / "zenbook-kb-brightness"
    ACPI_EVENTS_DIR = zb_paths.ACPI_EVENTS_DIR
    ACPI_SLEEP_EVENT = ACPI_EVENTS_DIR / "zenbook-kbd-sleep"
    ACPI_SLEEP_HELPER = lx / "zenbook-kbd-sleep.sh"
    MODPROBE_CONF = zb_paths.MODPROBE_DIR / "zenbook-hid-asus.conf"
    return pfx


refresh_install_paths()


def has_systemd() -> bool:
    if not shutil.which("systemctl"):
        return False
    return subprocess.run(
        ["systemctl", "--version"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    ).returncode == 0


def detect_init_system() -> str:
    return "systemd" if has_systemd() else "openrc"


def _openrc_service_runlevels(service: str) -> set[str]:
    """Return runlevels that currently include *service* (OpenRC)."""
    if not shutil.which("rc-update"):
        return set()
    result = subprocess.run(
        ["rc-update", "show", "-v"],
        capture_output=True,
        text=True,
        check=False,
    )
    for line in result.stdout.splitlines():
        if "|" not in line:
            continue
        name, levels = line.split("|", 1)
        if name.strip() != service:
            continue
        return {part.strip() for part in levels.split() if part.strip()}
    return set()


def _sudo(cmd: list[str], *, timeout: float | None = None) -> None:
    """Run *cmd* as root. Skip nested sudo when already euid 0.

    Interactive password prompts only when ``ZENBOOK_SUDO_ASK=1`` and stdin is a
    TTY (configure.py). Otherwise ``sudo -n`` — fail fast, never hang.
    """
    from zenbook_kb.priv import run_root

    print(f"  → {' '.join(cmd)}", flush=True)
    run_root(cmd, check=True, timeout=timeout, allow_ask=None)


def _root_run(
    cmd: list[str],
    *,
    check: bool = False,
    timeout: float | None = 60,
    input_bytes: bytes | None = None,
) -> subprocess.CompletedProcess[bytes]:
    from zenbook_kb.priv import run_root

    print(f"  → {' '.join(cmd)}", flush=True)
    return run_root(
        cmd,
        check=check,
        timeout=timeout,
        input_bytes=input_bytes,
        allow_ask=None,
    )


def install_kb_brightness_tree(script_dir: Path) -> None:
    """Install kb-brightness, hotkey listener, and support files."""
    print(f"Installing share tree + CLIs under {zb_paths.get_prefix()} …", flush=True)
    _sudo(["mkdir", "-p", str(INSTALL_SHARE / "lib"), str(INSTALL_SHARE / "zenbook_kb" / "transports"), str(INSTALL_SHARE / "conf.d")])
    for name in (
        "protocol.sh",
        "state.sh",
        "detect.sh",
        "hidraw.sh",
        "limits.sh",
        "openrc-wait.sh",
        "snapshot.sh",
        "fn_lock.sh",
        "transport_usb.sh",
        "transport_bluetooth.sh",
        "screenpad.sh",
        "platform_profile.sh",
        "fan.sh",
    ):
        src = script_dir / "lib" / name
        if src.is_file():
            _sudo(["cp", str(src), f"{INSTALL_SHARE}/lib/"])
    _sudo(["cp", "-r", f"{script_dir}/zenbook_kb/.", f"{INSTALL_SHARE}/zenbook_kb/"])
    conf_d = script_dir / "conf.d"
    if conf_d.is_dir():
        _sudo(["cp", "-r", f"{conf_d}/.", f"{INSTALL_SHARE}/conf.d/"])
    _sudo(["cp", str(script_dir / "brightness.py"), str(INSTALL_SHARE / "brightness.py")])
    _sudo(["cp", str(script_dir / "bin" / "kb-brightness"), str(INSTALL_BIN_BRIGHTNESS)])
    _sudo(["cp", str(script_dir / "bin" / "kb-brightness-hotkeys"), str(INSTALL_BIN_HOTKEYS)])
    sleep_bin = script_dir / "bin" / "kb-brightness-sleep"
    if sleep_bin.is_file():
        _sudo(["cp", str(sleep_bin), str(INSTALL_BIN_SLEEP)])
        _sudo(["chmod", "a+x", str(INSTALL_BIN_SLEEP)])
    lid_watch = script_dir / "bin" / "kb-brightness-lid-watch"
    if lid_watch.is_file():
        _sudo(["cp", str(lid_watch), str(INSTALL_BIN_LID_WATCH)])
        _sudo(["chmod", "a+x", str(INSTALL_BIN_LID_WATCH)])
    snap_bin = script_dir / "bin" / "snapshot-plan-state"
    if snap_bin.is_file():
        _sudo(["cp", str(snap_bin), str(INSTALL_BIN_SNAPSHOT)])
        _sudo(["chmod", "a+x", str(INSTALL_BIN_SNAPSHOT)])
    calibrate_bin = script_dir / "bin" / "kb-calibrate-hotkeys"
    if calibrate_bin.is_file():
        _sudo(["cp", str(calibrate_bin), str(INSTALL_BIN_CALIBRATE)])
        _sudo(["chmod", "a+x", str(INSTALL_BIN_CALIBRATE)])
    for src, dest in (
        (script_dir / "bin" / "screenpad", INSTALL_BIN_SCREENPAD),
        (script_dir / "bin" / "screenpad-sync", INSTALL_BIN_SCREENPAD_SYNC),
        (script_dir / "bin" / "screenpad-boot", INSTALL_BIN_SCREENPAD_BOOT),
        (script_dir / "bin" / "kb-platform-profile", INSTALL_BIN_PLATFORM_PROFILE),
        (script_dir / "bin" / "platform-fan", INSTALL_BIN_FAN),
        (script_dir / "bin" / "platform-fan-control", INSTALL_BIN_FAN_CONTROL),
        (script_dir / "bin" / "platform-probe", INSTALL_BIN_PLATFORM_PROBE),
        (script_dir / "bin" / "platform-metrics", zb_paths.bin_dir() / "platform-metrics"),
        (script_dir / "bin" / "kb-fan", INSTALL_BIN_FAN_LEGACY),
        (script_dir / "bin" / "kb-fan-control", INSTALL_BIN_FAN_CONTROL_LEGACY),
    ):
        if src.is_file():
            _sudo(["cp", str(src), str(dest)])
            _sudo(["chmod", "a+x", str(dest)])
    tray = script_dir / "bin" / "platform-tray"
    if tray.is_file():
        _sudo(["cp", str(tray), str(INSTALL_BIN_PLATFORM_TRAY)])
        _sudo(["chmod", "a+x", str(INSTALL_BIN_PLATFORM_TRAY)])
    fan_hook = script_dir / "contrib" / "openrc" / "zenbook-fan-control-hook.sh"
    if fan_hook.is_file():
        _sudo(["cp", str(fan_hook), str(INSTALL_BIN_FAN_HOOK)])
        _sudo(["chmod", "a+x", str(INSTALL_BIN_FAN_HOOK)])
    example_fan = script_dir / "fan-control.json.example"
    if example_fan.is_file():
        _sudo(["cp", str(example_fan), str(INSTALL_SHARE / "fan-control.json.example")])
    _sudo(["chmod", "a+x", str(INSTALL_BIN_BRIGHTNESS), str(INSTALL_BIN_HOTKEYS)])
    example_hotkeys = script_dir / "zenbook-hotkeys.conf.example"
    if example_hotkeys.is_file():
        dest = INSTALL_SHARE / "zenbook-hotkeys.conf.example"
        _sudo(["cp", str(example_hotkeys), str(dest)])
    print(
        f"CLIs: {INSTALL_BIN_BRIGHTNESS.name}, {INSTALL_BIN_PLATFORM_PROBE.name}, "
        f"{INSTALL_BIN_FAN.name}, {INSTALL_BIN_FAN_CONTROL.name}, …",
        flush=True,
    )


def print_install_summary() -> None:
    """Report which expected binaries actually exist after install."""
    expected = [
        INSTALL_BIN_BRIGHTNESS,
        INSTALL_BIN_HOTKEYS,
        INSTALL_BIN_PLATFORM_PROFILE,
        INSTALL_BIN_PLATFORM_PROBE,
        INSTALL_BIN_FAN,
        INSTALL_BIN_FAN_CONTROL,
        INSTALL_BIN_SCREENPAD,
        INSTALL_BIN_PLATFORM_TRAY,
        INSTALL_BIN_FAN_HOOK,
        zb_paths.ETC_ZENBOOK / "fan-control.json",
        OPENRC_FAN_CONTROL_INIT,
    ]
    print("\n=== install summary ===", flush=True)
    print(f"  prefix: {zb_paths.get_prefix()}", flush=True)
    missing = 0
    for path in expected:
        ok = path.exists()
        mark = "OK " if ok else "MISS"
        if not ok:
            missing += 1
        print(f"  {mark}  {path}", flush=True)
    if missing:
        print(
            f"{missing} path(s) missing — install may have been interrupted.",
            flush=True,
        )
    else:
        print("All checked paths present.", flush=True)
    print(
        "Try: platform-probe && platform-fan status && kb-platform-profile get",
        flush=True,
    )


def _append_sudoers_line(line: str) -> bool:
    grep_cmd = ["grep", "-qF", line, "/etc/sudoers"]
    if os.geteuid() != 0:
        grep_cmd = ["sudo", *grep_cmd]
    if subprocess.run(grep_cmd, check=False).returncode == 0:
        return False
    _sudo(["sh", "-c", f"echo '{line}' >> /etc/sudoers"])
    return True


def install_sudoers_kb_brightness() -> None:
    user = resolve_run_user()
    if not user:
        return
    sudoers_line = f"{user} ALL=NOPASSWD:{INSTALL_BIN_BRIGHTNESS} *"
    if _append_sudoers_line(sudoers_line):
        print(f"Added sudoers entry for passwordless {INSTALL_BIN_BRIGHTNESS}")


def install_sudoers_ux5400() -> None:
    """Passwordless screenpad + platform-profile + fan for the install user."""
    user = resolve_run_user()
    if not user:
        return
    for path in (
        INSTALL_BIN_SCREENPAD,
        INSTALL_BIN_PLATFORM_PROFILE,
        INSTALL_BIN_FAN,
        INSTALL_BIN_SCREENPAD_BOOT,
    ):
        line = f"{user} ALL=NOPASSWD:{path} *"
        if _append_sudoers_line(line):
            print(f"Added sudoers entry for passwordless {path}")


def install_udev_rules(script_dir: Path) -> None:
    _sudo(["mkdir", "-p", str(INSTALL_LIBEXEC)])
    _sudo(["cp", str(script_dir / "contrib" / "udev" / "99-zenbook-kb-hotkeys.rules"), str(UDEV_RULES)])
    _sudo(["cp", str(script_dir / "contrib" / "udev" / "zenbook-kb-hotkeys-udev"), str(UDEV_HELPER)])
    _sudo(["chmod", "a+x", str(UDEV_HELPER)])
    _sudo(["udevadm", "control", "--reload-rules"])
    _sudo(["udevadm", "trigger", "--subsystem-match=input"])
    print(f"Installed {UDEV_RULES}")


def add_user_to_input_group() -> None:
    user = resolve_run_user()
    if not user:
        return
    if shutil.which("usermod"):
        _root_run(["usermod", "-aG", "input", user], check=False, timeout=30)
        print(f"Added {user} to group input (log out/in for new group)")


def install_openrc_service(script_dir: Path, run_user: str | None = None) -> None:
    user = run_user or resolve_run_user()
    validate_unix_user(user)
    command_user = f"{user}:input"

    conf = (
        "# Managed by zenbook-scripts configure.py — do not copy contrib/openrc/ by hand.\n"
        f'command_user="{command_user}"\n'
        "# Startup profile + bindings are logged to /var/log/zenbook-kb-hotkeys.log.\n"
        "# Uncomment to log every key press and extra runtime diagnostics:\n"
        '#command_args="--verbose --debug"\n'
    )
    _root_run(["tee", str(OPENRC_CONF)], check=True, input_bytes=conf.encode())

    src = script_dir / "contrib" / "openrc" / "zenbook-kb-hotkeys"
    content = src.read_text()
    for line in content.splitlines():
        code = line.split("#", 1)[0]
        if "@RUN_USER@" in code:
            raise RuntimeError(
                f"{src} still assigns @RUN_USER@ — use /etc/conf.d/zenbook-kb-hotkeys instead"
            )
    _root_run(["tee", str(OPENRC_INIT)], check=True, input_bytes=content.encode())
    _sudo(["chmod", "a+x", str(OPENRC_INIT)])
    rewrite_file_prefix(OPENRC_INIT)
    _sudo(["touch", "/var/log/zenbook-kb-hotkeys.log"])
    _sudo(["chown", command_user, "/var/log/zenbook-kb-hotkeys.log"])
    if shutil.which("rc-update"):
        _root_run(["rc-update", "add", "zenbook-kb-hotkeys", "default"], check=False, timeout=30)
    if shutil.which("rc-service"):
        _root_run(["rc-service", "zenbook-kb-hotkeys", "restart"], check=False, timeout=30)
    print(f"Installed OpenRC service {OPENRC_INIT} (user {user}, conf {OPENRC_CONF})")


def install_systemd_service(run_user: str | None = None) -> None:
    user = run_user or resolve_run_user()
    validate_unix_user(user)
    unit = f"""[Unit]
Description=Zenbook Duo keyboard hotkeys (Fn+)
After=local-fs.target

[Service]
Type=simple
User={user}
Group=input
ExecStart={INSTALL_BIN_HOTKEYS}
Restart=on-failure
RestartSec=2

[Install]
WantedBy=multi-user.target
"""
    _root_run(["tee", str(SYSTEMD_UNIT)], check=True, input_bytes=unit.encode())
    _sudo(["systemctl", "daemon-reload"])
    _sudo(["systemctl", "enable", "--now", "zenbook-kb-hotkeys.service"])
    print(f"Installed systemd unit {SYSTEMD_UNIT} (user {user})")


def install_sleep_hooks(script_dir: Path) -> None:
    """Sleep/lid save-restore + optional modprobe defaults for oot hid-asus."""
    _sudo(["mkdir", "-p", str(SYSTEMD_SLEEP_HOOK.parent), str(INSTALL_LIBEXEC)])
    src_sleep = script_dir / "contrib" / "systemd" / "zenbook-kb-brightness-sleep"
    if src_sleep.is_file():
        _sudo(["cp", str(src_sleep), str(SYSTEMD_SLEEP_HOOK)])
        _sudo(["chmod", "a+x", str(SYSTEMD_SLEEP_HOOK)])
        print(f"Installed {SYSTEMD_SLEEP_HOOK}")
    acpi_helper = script_dir / "contrib" / "acpi" / "zenbook-kbd-sleep.sh"
    if acpi_helper.is_file():
        _sudo(["cp", str(acpi_helper), str(ACPI_SLEEP_HELPER)])
        _sudo(["chmod", "a+x", str(ACPI_SLEEP_HELPER)])
        event_src = script_dir / "contrib" / "acpi" / "events" / "zenbook-kbd-sleep"
        if event_src.is_file():
            _sudo(["mkdir", "-p", str(ACPI_EVENTS_DIR)])
            _sudo(["cp", str(event_src), str(ACPI_SLEEP_EVENT)])
            if shutil.which("pidof"):
                _root_run(
                    ["sh", "-c", 'pidof acpid >/dev/null && kill -HUP "$(pidof acpid)" || true'],
                    check=False,
                    timeout=15,
                )
        print(f"Installed {ACPI_SLEEP_HELPER} and {ACPI_SLEEP_EVENT}")
        print("  (acpi lid events are unused when elogind owns the lid switch)")
    modprobe_src = script_dir / "contrib" / "modprobe" / "zenbook-hid-asus.conf"
    if modprobe_src.is_file():
        _sudo(["cp", str(modprobe_src), str(MODPROBE_CONF)])
        print(f"Installed {MODPROBE_CONF} (oot hid-asus fn-lock defaults)")


def install_openrc_lid_service(script_dir: Path) -> None:
    """elogind/logind LidClosed watcher (OpenRC + elogind systems)."""
    src = script_dir / "contrib" / "openrc" / "zenbook-kb-lid"
    if not src.is_file():
        return
    _sudo(["cp", str(src), str(OPENRC_LID_INIT)])
    _sudo(["chmod", "a+x", str(OPENRC_LID_INIT)])
    _sudo(["touch", "/var/log/zenbook-kb-lid.log"])
    if shutil.which("rc-update"):
        _root_run(["rc-update", "add", "zenbook-kb-lid", "default"], check=False, timeout=30)
    if shutil.which("rc-service"):
        _root_run(["rc-service", "zenbook-kb-lid", "restart"], check=False, timeout=30)
    print(f"Installed OpenRC service {OPENRC_LID_INIT} (logind LidClosed)")


def install_openrc_fan_control(
    script_dir: Path,
    *,
    enable_service: bool = False,
    seed_config: bool = True,
) -> None:
    """Install adaptive fan-control OpenRC unit + machine-global config."""
    src = script_dir / "contrib" / "openrc" / "zenbook-platform-fan-control"
    if not src.is_file():
        # Older tree name
        src = script_dir / "contrib" / "openrc" / "zenbook-kb-fan-control"
    conf_src = script_dir / "contrib" / "openrc" / "conf.d" / "zenbook-platform-fan-control"
    if not conf_src.is_file():
        conf_src = script_dir / "contrib" / "openrc" / "conf.d" / "zenbook-kb-fan-control"
    if not src.is_file():
        return
    etc_dir = Path("/etc/zenbook-scripts")
    _sudo(["mkdir", "-p", str(etc_dir)])
    example = script_dir / "fan-control.json.example"
    live = etc_dir / "fan-control.json"
    if example.is_file():
        _sudo(["cp", str(example), str(etc_dir / "fan-control.json.example")])
        if seed_config and not live.is_file():
            _sudo(["cp", str(example), str(live)])
            print(f"Seeded {live} from example (edit to taste)")
    if conf_src.is_file():
        _sudo(["cp", str(conf_src), str(OPENRC_FAN_CONTROL_CONF)])
    _sudo(["cp", str(src), str(OPENRC_FAN_CONTROL_INIT)])
    _sudo(["chmod", "a+x", str(OPENRC_FAN_CONTROL_INIT)])
    rewrite_file_prefix(OPENRC_FAN_CONTROL_INIT)
    # Compatibility symlink for older docs / rc-update entries
    if not OPENRC_FAN_CONTROL_INIT_LEGACY.exists():
        _sudo(["ln", "-sf", str(OPENRC_FAN_CONTROL_INIT), str(OPENRC_FAN_CONTROL_INIT_LEGACY)])
    _sudo(["touch", "/var/log/zenbook-platform-fan-control.log"])
    if enable_service:
        if shutil.which("rc-update"):
            _root_run(
                ["rc-update", "add", "zenbook-platform-fan-control", "default"],
                check=False,
                timeout=30,
            )
        if shutil.which("rc-service") and live.is_file():
            _root_run(
                ["rc-service", "zenbook-platform-fan-control", "restart"],
                check=False,
                timeout=30,
            )
            print(f"Started {OPENRC_FAN_CONTROL_INIT}")
        elif not live.is_file():
            print(f"Fan-control: missing {live} — service not started")
    print(
        f"Installed OpenRC service {OPENRC_FAN_CONTROL_INIT} "
        f"(config: {live})"
    )


def install_fan_control_support(
    script_dir: Path,
    *,
    enable_service: bool = True,
    seed_config: bool = True,
) -> None:
    """Install kb-fan-control CLI bits, config, and OpenRC unit when available."""
    # Bins land via install_kb_brightness_tree; ensure sudoers for profile/fan writes.
    install_sudoers_ux5400()
    fan_hook = script_dir / "contrib" / "openrc" / "zenbook-fan-control-hook.sh"
    if fan_hook.is_file() and INSTALL_BIN_FAN_HOOK.parent.is_dir():
        _sudo(["cp", str(fan_hook), str(INSTALL_BIN_FAN_HOOK)])
        _sudo(["chmod", "a+x", str(INSTALL_BIN_FAN_HOOK)])
    if detect_init_system() != "systemd":
        install_openrc_fan_control(
            script_dir,
            enable_service=enable_service,
            seed_config=seed_config,
        )
    else:
        etc_dir = Path("/etc/zenbook-scripts")
        _sudo(["mkdir", "-p", str(etc_dir)])
        example = script_dir / "fan-control.json.example"
        live = etc_dir / "fan-control.json"
        if example.is_file():
            _sudo(["cp", str(example), str(etc_dir / "fan-control.json.example")])
            if seed_config and not live.is_file():
                _sudo(["cp", str(example), str(live)])
                print(f"Seeded {live} from example")
        print(
            "Fan-control: no systemd unit yet — run: "
            f"{INSTALL_BIN_FAN_CONTROL} run -c {live}"
        )
    print(f"Fan-control CLI: {INSTALL_BIN_FAN_CONTROL} (alias: kb-fan-control)")
    print(f"  probe:  {INSTALL_BIN_PLATFORM_PROBE}")
    print(f"  check:  {INSTALL_BIN_FAN_CONTROL} check")
    print(f"  status: {INSTALL_BIN_FAN_CONTROL} status")


def install_hid_asus_libexec(script_dir: Path) -> None:
    """Kernel switch/rebind helpers for boot and manual sideload."""
    _sudo(["mkdir", "-p", str(INSTALL_LIBEXEC)])
    switch = script_dir / "kernel" / "scripts" / "switch-hid-asus.sh"
    rebind = script_dir / "kernel" / "scripts" / "rebind-hid-asus.sh"
    boot = script_dir / "contrib" / "openrc" / "zenbook-hid-asus-boot.sh"
    if switch.is_file():
        _sudo(["cp", str(switch), str(INSTALL_LIBEXEC / "zenbook-hid-asus-switch")])
        _sudo(["chmod", "a+x", str(INSTALL_LIBEXEC / "zenbook-hid-asus-switch")])
    if rebind.is_file():
        _sudo(["cp", str(rebind), str(INSTALL_LIBEXEC / "zenbook-hid-asus-rebind")])
        _sudo(["chmod", "a+x", str(INSTALL_LIBEXEC / "zenbook-hid-asus-rebind")])
    if boot.is_file():
        _sudo(["cp", str(boot), str(INSTALL_LIBEXEC / "zenbook-hid-asus-boot.sh")])
        _sudo(["chmod", "a+x", str(INSTALL_LIBEXEC / "zenbook-hid-asus-boot.sh")])
    print(f"Installed hid-asus helpers under {INSTALL_LIBEXEC}/")


def build_and_install_hid_asus(
    script_dir: Path,
    *,
    force: bool = False,
    kdir: str | Path | None = None,
) -> bool:
    """Build oot hid-asus from sources for this machine, then install sideload .ko.

    Never ships or reuses an arbitrary prebuilt binary from the tree without a
    fresh ``make`` against the selected KDIR.
    """
    from zenbook_kb.kernel_preflight import SKIP_FEATURES_MSG, run_preflight

    force = force or os.environ.get("ZENBOOK_KERNEL_FORCE", "").strip().lower() in (
        "1",
        "yes",
        "true",
    )
    pf = run_preflight(kdir=kdir, repo_root=script_dir, force=force)
    for line in pf.summary_lines():
        print(f"  kernel-preflight: {line}", flush=True)

    if not pf.eligible:
        print(f"Skipping oot hid-asus: not eligible.\n{SKIP_FEATURES_MSG}", flush=True)
        return False
    if not pf.has_source:
        print(f"Skipping oot hid-asus: no kernel sources.\n{SKIP_FEATURES_MSG}", flush=True)
        return False
    if pf.force_required:
        print(
            "Skipping oot hid-asus: risky (unsupported KV and/or MODVERSIONS). "
            "Re-run with --kernel-force or ZENBOOK_KERNEL_FORCE=1 if you accept the risk.\n"
            f"{SKIP_FEATURES_MSG}",
            flush=True,
        )
        return False

    kdir_path = pf.kdir
    env = os.environ.copy()
    # Portage-style ARCH breaks kbuild on amd64 hosts.
    arch = subprocess.check_output(
        ["uname", "-m"], text=True
    ).strip()
    if arch in ("x86_64", "i686", "i386"):
        env["ARCH"] = "x86"
    builddir = f"/tmp/zenbook-hid-asus-configure-{os.getuid()}"
    make_cmd = [
        "make",
        "-C",
        str(script_dir / "kernel"),
        "build-current",
        f"KDIR={kdir_path}",
        f"BUILDDIR={builddir}",
    ]
    print(f"→ building oot hid-asus: {' '.join(make_cmd)}", flush=True)
    build = subprocess.run(make_cmd, check=False, env=env)
    if build.returncode != 0:
        print(f"oot hid-asus build failed.\n{SKIP_FEATURES_MSG}", flush=True)
        return False

    # Prefer make install (modules_install + zenbook sideload path).
    install_cmd = [
        "make",
        "-C",
        str(script_dir / "kernel"),
        "install",
        f"KDIR={kdir_path}",
        f"BUILDDIR={builddir}",
        f"ZENBOOK_KO_ROOT={INSTALLED_KO_ROOT}",
    ]
    print(f"→ installing oot hid-asus: {' '.join(install_cmd)}", flush=True)
    # Preserve ARCH for kbuild when elevating.
    inst = _root_run(
        ["env", f"ARCH={env.get('ARCH', 'x86')}", *install_cmd],
        check=False,
        timeout=300,
    )
    if inst.returncode != 0:
        # Fallback: copy artifact only into zenbook sideload path.
        kver = pf.kver or subprocess.check_output(["uname", "-r"], text=True).strip()
        candidates = list((script_dir / "kernel" / "build").glob("*/hid-asus.ko"))
        if not candidates:
            print(f"No hid-asus.ko artifact after build.\n{SKIP_FEATURES_MSG}", flush=True)
            return False
        ko_src = candidates[0]
        dest_dir = INSTALLED_KO_ROOT / kver
        _sudo(["mkdir", "-p", str(dest_dir)])
        _sudo(["cp", str(ko_src), str(dest_dir / "hid-asus.ko")])
        print(f"Installed {dest_dir / 'hid-asus.ko'} (sideload path only)", flush=True)
        return True
    print(f"Installed oot hid-asus for {pf.kver}", flush=True)
    return True


def install_hid_asus_ko(script_dir: Path, *, force: bool = False) -> bool:
    """Backward-compatible name → :func:`build_and_install_hid_asus`."""
    return build_and_install_hid_asus(script_dir, force=force)


def ensure_ux8406_fn_row_policy(script_dir: Path) -> None:
    """Force ``fn_row_policy=7`` in hid-asus conf.d on UX8406 (dmidecode/sysfs)."""
    from zenbook_kb.dmi import ensure_conf_assignment, is_ux8406

    if not is_ux8406():
        return
    conf = OPENRC_HID_ASUS_CONF
    example = script_dir / "contrib" / "openrc" / "conf.d" / "zenbook-kb-hid-asus"
    if not conf.exists() and example.is_file():
        _sudo(["cp", str(example), str(conf)])
    if not conf.exists():
        print(f"UX8406: missing {conf} — cannot set fn_row_policy", flush=True)
        return
    text = conf.read_text(encoding="utf-8", errors="replace")
    new, changed = ensure_conf_assignment(text, "fn_row_policy", "7")
    if not changed:
        print(f"UX8406: {conf} already has fn_row_policy=7", flush=True)
        return
    _root_run(["tee", str(conf)], check=True, input_bytes=new.encode())
    print(f"UX8406: set fn_row_policy=7 in {conf}", flush=True)


def install_openrc_hid_asus_service(script_dir: Path, *, enable_service: bool = True) -> None:
    """Default-runlevel oot hid-asus sideload (OpenRC)."""
    init_src = script_dir / "contrib" / "openrc" / "zenbook-kb-hid-asus"
    conf_src = script_dir / "contrib" / "openrc" / "conf.d" / "zenbook-kb-hid-asus"
    if not init_src.is_file():
        return
    install_hid_asus_libexec(script_dir)
    _sudo(["cp", str(init_src), str(OPENRC_HID_ASUS_INIT)])
    _sudo(["chmod", "a+x", str(OPENRC_HID_ASUS_INIT)])
    if conf_src.is_file() and not OPENRC_HID_ASUS_CONF.exists():
        _sudo(["cp", str(conf_src), str(OPENRC_HID_ASUS_CONF)])
        print(f"Installed {OPENRC_HID_ASUS_CONF}")
    ensure_ux8406_fn_row_policy(script_dir)
    _sudo(["touch", "/var/log/zenbook-kb-hid-asus.log"])
    if enable_service and shutil.which("rc-update"):
        levels = _openrc_service_runlevels("zenbook-kb-hid-asus")
        if "boot" in levels:
            _root_run(
                ["rc-update", "del", "zenbook-kb-hid-asus", "boot"],
                check=False,
                timeout=30,
            )
            levels.discard("boot")
        if "default" not in levels:
            _root_run(
                ["rc-update", "add", "zenbook-kb-hid-asus", "default"],
                check=False,
                timeout=30,
            )
            print("Enabled zenbook-kb-hid-asus in default runlevel")
        else:
            print("zenbook-kb-hid-asus: already in default runlevel")
    print(f"Installed OpenRC service {OPENRC_HID_ASUS_INIT} (default runlevel sideload)")


def install_udev_screenpad_rules(script_dir: Path) -> None:
    src = script_dir / "contrib" / "udev" / "99-zenbook-screenpad.rules"
    if not src.is_file():
        return
    _sudo(["mkdir", "-p", "/var/lib/zenbook-scripts"])
    _sudo(["chmod", "0775", "/var/lib/zenbook-scripts"])
    _sudo(["cp", str(src), str(UDEV_SCREENPAD_RULES)])
    _sudo(["udevadm", "control", "--reload-rules"])
    _sudo(["udevadm", "trigger", "--subsystem-match=backlight", "--action=add"])
    print(f"Installed {UDEV_SCREENPAD_RULES}")


def install_openrc_screenpad(script_dir: Path, *, with_sync: bool = True) -> None:
    boot_src = script_dir / "contrib" / "openrc" / "zenbook-screenpad"
    sync_src = script_dir / "contrib" / "openrc" / "zenbook-screenpad-sync"
    conf_src = script_dir / "contrib" / "openrc" / "conf.d" / "zenbook-screenpad"
    if boot_src.is_file():
        _sudo(["cp", str(boot_src), str(OPENRC_SCREENPAD_INIT)])
        _sudo(["chmod", "a+x", str(OPENRC_SCREENPAD_INIT)])
        if conf_src.is_file() and not OPENRC_SCREENPAD_CONF.exists():
            _sudo(["cp", str(conf_src), str(OPENRC_SCREENPAD_CONF)])
        if shutil.which("rc-update"):
            _root_run(["rc-update", "add", "zenbook-screenpad", "default"], check=False, timeout=30)
        if shutil.which("rc-service"):
            _root_run(["rc-service", "zenbook-screenpad", "start"], check=False, timeout=30)
        print(f"Installed OpenRC service {OPENRC_SCREENPAD_INIT}")
    if with_sync and sync_src.is_file():
        _sudo(["cp", str(sync_src), str(OPENRC_SCREENPAD_SYNC_INIT)])
        _sudo(["chmod", "a+x", str(OPENRC_SCREENPAD_SYNC_INIT)])
        _sudo(["touch", "/var/log/zenbook-screenpad-sync.log"])
        if shutil.which("rc-update"):
            _root_run(
                ["rc-update", "add", "zenbook-screenpad-sync", "default"],
                check=False,
                timeout=30,
            )
        if shutil.which("rc-service"):
            _root_run(
                ["rc-service", "zenbook-screenpad-sync", "restart"],
                check=False,
                timeout=30,
            )
        print(f"Installed OpenRC service {OPENRC_SCREENPAD_SYNC_INIT}")


def install_systemd_screenpad(script_dir: Path, *, with_sync: bool = True) -> None:
    boot_src = script_dir / "contrib" / "systemd" / "zenbook-screenpad.service"
    sync_src = script_dir / "contrib" / "systemd" / "zenbook-screenpad-sync.service"
    if boot_src.is_file():
        _sudo(["cp", str(boot_src), str(SYSTEMD_SCREENPAD_UNIT)])
        _sudo(["systemctl", "daemon-reload"])
        _sudo(["systemctl", "enable", "--now", "zenbook-screenpad.service"])
        print(f"Installed {SYSTEMD_SCREENPAD_UNIT}")
    if with_sync and sync_src.is_file():
        _sudo(["cp", str(sync_src), str(SYSTEMD_SCREENPAD_SYNC_UNIT)])
        _sudo(["systemctl", "daemon-reload"])
        _sudo(["systemctl", "enable", "--now", "zenbook-screenpad-sync.service"])
        print(f"Installed {SYSTEMD_SCREENPAD_SYNC_UNIT}")


def install_screenpad_support(
    script_dir: Path,
    *,
    init_system: str | None = None,
    with_sync: bool = True,
) -> str:
    """Install ScreenPad CLI, udev, boot restore, optional sync daemon."""
    init = init_system or detect_init_system()
    install_kb_brightness_tree(script_dir)
    install_sudoers_ux5400()
    install_udev_screenpad_rules(script_dir)
    if init == "systemd":
        install_systemd_screenpad(script_dir, with_sync=with_sync)
    else:
        install_openrc_screenpad(script_dir, with_sync=with_sync)
    print(f"Installed {INSTALL_BIN_SCREENPAD}, {INSTALL_BIN_PLATFORM_PROFILE}")
    return init


def install_hotkey_service(
    script_dir: Path,
    init_system: str | None = None,
    *,
    with_kernel: bool = False,
    kernel_force: bool = False,
) -> str:
    """Install udev rules + init-system service. Returns detected init name."""
    from zenbook_kb.kernel_preflight import SKIP_FEATURES_MSG

    init = init_system or detect_init_system()
    install_udev_rules(script_dir)
    install_sleep_hooks(script_dir)
    add_user_to_input_group()
    if init == "systemd":
        install_systemd_service()
        if with_kernel:
            print(
                "NOTE: systemd path installs hotkeys only; oot hid-asus OpenRC "
                "sideload helpers are OpenRC-oriented. Building module anyway.",
                flush=True,
            )
            build_and_install_hid_asus(script_dir, force=kernel_force)
            install_hid_asus_libexec(script_dir)
    else:
        install_openrc_service(script_dir)
        install_openrc_lid_service(script_dir)
        if with_kernel:
            ok = build_and_install_hid_asus(script_dir, force=kernel_force)
            install_openrc_hid_asus_service(script_dir, enable_service=ok)
            if not ok:
                print(SKIP_FEATURES_MSG, flush=True)
        else:
            print(
                "Skipping oot hid-asus (no --with-kernel / declined).\n"
                f"{SKIP_FEATURES_MSG}",
                flush=True,
            )
    return init


def install_all(
    script_dir: Path,
    *,
    with_hotkey_service: bool = True,
    with_screenpad: bool | None = None,
    with_screenpad_sync: bool = True,
    with_fan_control: bool | None = None,
    fan_control_enable: bool = True,
    with_kernel: bool = False,
    kernel_force: bool = False,
) -> str | None:
    from zenbook_kb.dmi import has_platform_profile, has_screenpad_sysfs, is_ux5400

    install_kb_brightness_tree(script_dir)
    install_sudoers_kb_brightness()
    print(f"Installed {INSTALL_BIN_BRIGHTNESS} and {INSTALL_BIN_HOTKEYS}")
    print(f"Support files under {INSTALL_SHARE}/")

    if with_screenpad is None:
        with_screenpad = is_ux5400() or has_screenpad_sysfs()
    if with_screenpad:
        install_sudoers_ux5400()
        install_udev_screenpad_rules(script_dir)
        init_preview = detect_init_system()
        if init_preview == "systemd":
            install_systemd_screenpad(script_dir, with_sync=with_screenpad_sync)
        else:
            install_openrc_screenpad(script_dir, with_sync=with_screenpad_sync)
        print(f"ScreenPad tools: {INSTALL_BIN_SCREENPAD}")
    elif has_platform_profile():
        # Still install CLI + sudoers for platform profile on other ASUS boards.
        install_sudoers_ux5400()
        print(f"Platform profile CLI: {INSTALL_BIN_PLATFORM_PROFILE}")

    if with_fan_control is None:
        with_fan_control = has_platform_profile()
    if with_fan_control:
        install_fan_control_support(
            script_dir,
            enable_service=fan_control_enable,
            seed_config=True,
        )

    if not with_hotkey_service:
        return None
    init = install_hotkey_service(
        script_dir,
        with_kernel=with_kernel,
        kernel_force=kernel_force,
    )
    print(f"Hotkey service installed for {init}")
    return init


def cleanup_legacy_prefix(
    old_prefix: str | Path = "/usr/local",
    *,
    dry_run: bool = False,
) -> list[Path]:
    """Remove zenbook_scripts files from a previous prefix (e.g. /usr/local).

    Does not touch /etc (OpenRC/udev/config) or the active ZENBOOK_PREFIX tree.
    """
    old = Path(old_prefix).resolve()
    active = zb_paths.get_prefix().resolve()
    if old == active:
        print(f"Refuse to clean active prefix {active}", flush=True)
        return []

    victims: list[Path] = []
    for name in zb_paths.LEGACY_BIN_NAMES:
        victims.append(old / "bin" / name)
    for name in zb_paths.LEGACY_LIBEXEC_NAMES:
        victims.append(old / "libexec" / name)
    victims.append(old / "share" / "zenbook-scripts")

    removed: list[Path] = []
    print(f"Cleaning legacy prefix {old} (active install: {active})", flush=True)
    for path in victims:
        if not path.exists() and not path.is_symlink():
            continue
        removed.append(path)
        if dry_run:
            print(f"  would remove {path}", flush=True)
            continue
        if path.is_dir() and not path.is_symlink():
            _sudo(["rm", "-rf", str(path)])
        else:
            _sudo(["rm", "-f", str(path)])
        print(f"  removed {path}", flush=True)
    if not removed:
        print("  nothing to remove", flush=True)
    return removed


def rewrite_file_prefix(path: Path, *, from_prefix: str = "/usr/local", to_prefix: str | None = None) -> None:
    """Rewrite path prefixes inside an installed unit/script."""
    dest = to_prefix or str(zb_paths.get_prefix())
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8", errors="replace")
    if from_prefix not in text and dest == from_prefix:
        return
    new = text.replace(from_prefix, dest)
    if new == text:
        return
    _root_run(["tee", str(path)], check=True, input_bytes=new.encode())
