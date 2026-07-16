"""Install helpers shared by configure.py / configure.sh."""

from __future__ import annotations


import shutil
import subprocess
from pathlib import Path

from zenbook_kb.users import resolve_run_user, validate_unix_user

INSTALL_SHARE = Path("/usr/local/share/zenbook-scripts")
INSTALL_BIN_BRIGHTNESS = Path("/usr/local/bin/kb-brightness")
INSTALL_BIN_HOTKEYS = Path("/usr/local/bin/kb-brightness-hotkeys")
INSTALL_BIN_CALIBRATE = Path("/usr/local/bin/kb-calibrate-hotkeys")
INSTALL_BIN_SLEEP = Path("/usr/local/bin/kb-brightness-sleep")
INSTALL_BIN_LID_WATCH = Path("/usr/local/bin/kb-brightness-lid-watch")
INSTALL_BIN_SCREENPAD = Path("/usr/local/bin/screenpad")
INSTALL_BIN_SCREENPAD_SYNC = Path("/usr/local/bin/screenpad-sync")
INSTALL_BIN_SCREENPAD_BOOT = Path("/usr/local/bin/screenpad-boot")
INSTALL_BIN_PLATFORM_PROFILE = Path("/usr/local/bin/kb-platform-profile")
UDEV_RULES = Path("/etc/udev/rules.d/99-zenbook-kb-hotkeys.rules")
UDEV_SCREENPAD_RULES = Path("/etc/udev/rules.d/99-zenbook-screenpad.rules")
UDEV_HELPER = Path("/usr/local/libexec/zenbook-kb-hotkeys-udev")
OPENRC_INIT = Path("/etc/init.d/zenbook-kb-hotkeys")
OPENRC_LID_INIT = Path("/etc/init.d/zenbook-kb-lid")
OPENRC_HID_ASUS_INIT = Path("/etc/init.d/zenbook-kb-hid-asus")
OPENRC_HID_ASUS_CONF = Path("/etc/conf.d/zenbook-kb-hid-asus")
OPENRC_SCREENPAD_INIT = Path("/etc/init.d/zenbook-screenpad")
OPENRC_SCREENPAD_SYNC_INIT = Path("/etc/init.d/zenbook-screenpad-sync")
OPENRC_SCREENPAD_CONF = Path("/etc/conf.d/zenbook-screenpad")
INSTALL_LIBEXEC = Path("/usr/local/libexec")
INSTALLED_KO_ROOT = Path("/usr/lib/modules/zenbook-hid-asus")
OPENRC_CONF = Path("/etc/conf.d/zenbook-kb-hotkeys")
SYSTEMD_UNIT = Path("/etc/systemd/system/zenbook-kb-hotkeys.service")
SYSTEMD_SCREENPAD_UNIT = Path("/etc/systemd/system/zenbook-screenpad.service")
SYSTEMD_SCREENPAD_SYNC_UNIT = Path("/etc/systemd/system/zenbook-screenpad-sync.service")
SYSTEMD_SLEEP_HOOK = Path("/usr/lib/systemd/system-sleep/zenbook-kb-brightness")
ACPI_EVENTS_DIR = Path("/etc/acpi/events")
ACPI_SLEEP_EVENT = ACPI_EVENTS_DIR / "zenbook-kbd-sleep"
ACPI_SLEEP_HELPER = Path("/usr/local/libexec/zenbook-kbd-sleep.sh")
MODPROBE_CONF = Path("/etc/modprobe.d/zenbook-hid-asus.conf")


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


def _sudo(cmd: list[str]) -> None:
    subprocess.run(["sudo", *cmd], check=True)


def install_kb_brightness_tree(script_dir: Path) -> None:
    """Install kb-brightness, hotkey listener, and support files."""
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
        _sudo(["cp", str(snap_bin), "/usr/local/bin/snapshot-plan-state"])
        _sudo(["chmod", "a+x", "/usr/local/bin/snapshot-plan-state"])
    calibrate_bin = script_dir / "bin" / "kb-calibrate-hotkeys"
    if calibrate_bin.is_file():
        _sudo(["cp", str(calibrate_bin), str(INSTALL_BIN_CALIBRATE)])
        _sudo(["chmod", "a+x", str(INSTALL_BIN_CALIBRATE)])
    for src, dest in (
        (script_dir / "bin" / "screenpad", INSTALL_BIN_SCREENPAD),
        (script_dir / "bin" / "screenpad-sync", INSTALL_BIN_SCREENPAD_SYNC),
        (script_dir / "bin" / "screenpad-boot", INSTALL_BIN_SCREENPAD_BOOT),
        (script_dir / "bin" / "kb-platform-profile", INSTALL_BIN_PLATFORM_PROFILE),
    ):
        if src.is_file():
            _sudo(["cp", str(src), str(dest)])
            _sudo(["chmod", "a+x", str(dest)])
    _sudo(["chmod", "a+x", str(INSTALL_BIN_BRIGHTNESS), str(INSTALL_BIN_HOTKEYS)])
    example_hotkeys = script_dir / "zenbook-hotkeys.conf.example"
    if example_hotkeys.is_file():
        dest = INSTALL_SHARE / "zenbook-hotkeys.conf.example"
        _sudo(["cp", str(example_hotkeys), str(dest)])


def _append_sudoers_line(line: str) -> bool:
    if (
        subprocess.run(
            ["sudo", "grep", "-qF", line, "/etc/sudoers"],
            check=False,
        ).returncode
        == 0
    ):
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
    """Passwordless screenpad + platform-profile for the install user."""
    user = resolve_run_user()
    if not user:
        return
    for path in (
        INSTALL_BIN_SCREENPAD,
        INSTALL_BIN_PLATFORM_PROFILE,
        INSTALL_BIN_SCREENPAD_BOOT,
    ):
        line = f"{user} ALL=NOPASSWD:{path} *"
        if _append_sudoers_line(line):
            print(f"Added sudoers entry for passwordless {path}")


def install_udev_rules(script_dir: Path) -> None:
    _sudo(["mkdir", "-p", "/usr/local/libexec"])
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
        subprocess.run(["sudo", "usermod", "-aG", "input", user], check=False)
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
    subprocess.run(["sudo", "tee", str(OPENRC_CONF)], input=conf.encode(), check=True)

    src = script_dir / "contrib" / "openrc" / "zenbook-kb-hotkeys"
    content = src.read_text()
    for line in content.splitlines():
        code = line.split("#", 1)[0]
        if "@RUN_USER@" in code:
            raise RuntimeError(
                f"{src} still assigns @RUN_USER@ — use /etc/conf.d/zenbook-kb-hotkeys instead"
            )
    subprocess.run(["sudo", "tee", str(OPENRC_INIT)], input=content.encode(), check=True)
    _sudo(["chmod", "a+x", str(OPENRC_INIT)])
    _sudo(["touch", "/var/log/zenbook-kb-hotkeys.log"])
    _sudo(["chown", command_user, "/var/log/zenbook-kb-hotkeys.log"])
    if shutil.which("rc-update"):
        subprocess.run(["sudo", "rc-update", "add", "zenbook-kb-hotkeys", "default"], check=False)
    if shutil.which("rc-service"):
        subprocess.run(["sudo", "rc-service", "zenbook-kb-hotkeys", "restart"], check=False)
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
    _sudo(["tee", str(SYSTEMD_UNIT)], input=unit.encode())
    _sudo(["systemctl", "daemon-reload"])
    _sudo(["systemctl", "enable", "--now", "zenbook-kb-hotkeys.service"])
    print(f"Installed systemd unit {SYSTEMD_UNIT} (user {user})")


def install_sleep_hooks(script_dir: Path) -> None:
    """Sleep/lid save-restore + optional modprobe defaults for oot hid-asus."""
    _sudo(["mkdir", "-p", "/usr/lib/systemd/system-sleep", "/usr/local/libexec"])
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
                subprocess.run(
                    ["sudo", "sh", "-c", 'pidof acpid >/dev/null && kill -HUP "$(pidof acpid)" || true'],
                    check=False,
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
        subprocess.run(["sudo", "rc-update", "add", "zenbook-kb-lid", "default"], check=False)
    if shutil.which("rc-service"):
        subprocess.run(["sudo", "rc-service", "zenbook-kb-lid", "restart"], check=False)
    print(f"Installed OpenRC service {OPENRC_LID_INIT} (logind LidClosed)")


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


def install_hid_asus_ko(script_dir: Path) -> bool:
    """Copy built oot hid-asus.ko into /usr/lib/modules/zenbook-hid-asus/<kver>/."""
    kver = subprocess.check_output(["uname", "-r"], text=True).strip()
    ko_src = script_dir / "kernel" / "build" / f"linux-{kver}" / "hid-asus.ko"
    if not ko_src.is_file():
        print(
            f"No built {ko_src} — run: make -f kernel/Makefile build-current",
            flush=True,
        )
        return False
    dest_dir = INSTALLED_KO_ROOT / kver
    _sudo(["mkdir", "-p", str(dest_dir)])
    _sudo(["cp", str(ko_src), str(dest_dir / "hid-asus.ko")])
    print(f"Installed {dest_dir / 'hid-asus.ko'}")
    return True


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
    _sudo(["touch", "/var/log/zenbook-kb-hid-asus.log"])
    if enable_service and shutil.which("rc-update"):
        levels = _openrc_service_runlevels("zenbook-kb-hid-asus")
        if "boot" in levels:
            subprocess.run(
                ["sudo", "rc-update", "del", "zenbook-kb-hid-asus", "boot"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            levels.discard("boot")
        if "default" not in levels:
            subprocess.run(
                ["sudo", "rc-update", "add", "zenbook-kb-hid-asus", "default"],
                check=False,
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
            subprocess.run(
                ["sudo", "rc-update", "add", "zenbook-screenpad", "default"],
                check=False,
            )
        if shutil.which("rc-service"):
            subprocess.run(["sudo", "rc-service", "zenbook-screenpad", "start"], check=False)
        print(f"Installed OpenRC service {OPENRC_SCREENPAD_INIT}")
    if with_sync and sync_src.is_file():
        _sudo(["cp", str(sync_src), str(OPENRC_SCREENPAD_SYNC_INIT)])
        _sudo(["chmod", "a+x", str(OPENRC_SCREENPAD_SYNC_INIT)])
        _sudo(["touch", "/var/log/zenbook-screenpad-sync.log"])
        if shutil.which("rc-update"):
            subprocess.run(
                ["sudo", "rc-update", "add", "zenbook-screenpad-sync", "default"],
                check=False,
            )
        if shutil.which("rc-service"):
            subprocess.run(
                ["sudo", "rc-service", "zenbook-screenpad-sync", "restart"],
                check=False,
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


def install_hotkey_service(script_dir: Path, init_system: str | None = None) -> str:
    """Install udev rules + init-system service. Returns detected init name."""
    init = init_system or detect_init_system()
    install_udev_rules(script_dir)
    install_sleep_hooks(script_dir)
    add_user_to_input_group()
    if init == "systemd":
        install_systemd_service()
    else:
        install_openrc_service(script_dir)
        install_openrc_lid_service(script_dir)
        install_hid_asus_ko(script_dir)
        install_openrc_hid_asus_service(script_dir)
    return init


def install_all(
    script_dir: Path,
    *,
    with_hotkey_service: bool = True,
    with_screenpad: bool | None = None,
    with_screenpad_sync: bool = True,
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

    if not with_hotkey_service:
        return None
    init = install_hotkey_service(script_dir)
    print(f"Hotkey service installed for {init}")
    return init
