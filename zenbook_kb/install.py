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
UDEV_RULES = Path("/etc/udev/rules.d/99-zenbook-kb-hotkeys.rules")
UDEV_HELPER = Path("/usr/local/libexec/zenbook-kb-hotkeys-udev")
OPENRC_INIT = Path("/etc/init.d/zenbook-kb-hotkeys")
OPENRC_CONF = Path("/etc/conf.d/zenbook-kb-hotkeys")
SYSTEMD_UNIT = Path("/etc/systemd/system/zenbook-kb-hotkeys.service")


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
        "snapshot.sh",
        "transport_usb.sh",
        "transport_bluetooth.sh",
    ):
        _sudo(["cp", str(script_dir / "lib" / name), f"{INSTALL_SHARE}/lib/"])
    _sudo(["cp", "-r", f"{script_dir}/zenbook_kb/.", f"{INSTALL_SHARE}/zenbook_kb/"])
    conf_d = script_dir / "conf.d"
    if conf_d.is_dir():
        _sudo(["cp", "-r", f"{conf_d}/.", f"{INSTALL_SHARE}/conf.d/"])
    _sudo(["cp", str(script_dir / "brightness.py"), str(INSTALL_SHARE / "brightness.py")])
    _sudo(["cp", str(script_dir / "bin" / "kb-brightness"), str(INSTALL_BIN_BRIGHTNESS)])
    _sudo(["cp", str(script_dir / "bin" / "kb-brightness-hotkeys"), str(INSTALL_BIN_HOTKEYS)])
    calibrate_bin = script_dir / "bin" / "kb-calibrate-hotkeys"
    if calibrate_bin.is_file():
        _sudo(["cp", str(calibrate_bin), str(INSTALL_BIN_CALIBRATE)])
        _sudo(["chmod", "a+x", str(INSTALL_BIN_CALIBRATE)])
    _sudo(["chmod", "a+x", str(INSTALL_BIN_BRIGHTNESS), str(INSTALL_BIN_HOTKEYS)])
    example_hotkeys = script_dir / "zenbook-hotkeys.conf.example"
    if example_hotkeys.is_file():
        dest = INSTALL_SHARE / "zenbook-hotkeys.conf.example"
        _sudo(["cp", str(example_hotkeys), str(dest)])


def install_sudoers_kb_brightness() -> None:
    user = resolve_run_user()
    if not user:
        return
    sudoers_line = f"{user} ALL=NOPASSWD:{INSTALL_BIN_BRIGHTNESS} *"
    if (
        subprocess.run(
            ["sudo", "grep", "-qF", sudoers_line, "/etc/sudoers"],
            check=False,
        ).returncode
        != 0
    ):
        _sudo(["sh", "-c", f"echo '{sudoers_line}' >> /etc/sudoers"])
        print(f"Added sudoers entry for passwordless {INSTALL_BIN_BRIGHTNESS}")


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


def install_hotkey_service(script_dir: Path, init_system: str | None = None) -> str:
    """Install udev rules + init-system service. Returns detected init name."""
    init = init_system or detect_init_system()
    install_udev_rules(script_dir)
    add_user_to_input_group()
    if init == "systemd":
        install_systemd_service()
    else:
        install_openrc_service(script_dir)
    return init


def install_all(script_dir: Path, *, with_hotkey_service: bool = True) -> str | None:
    install_kb_brightness_tree(script_dir)
    install_sudoers_kb_brightness()
    print(f"Installed {INSTALL_BIN_BRIGHTNESS} and {INSTALL_BIN_HOTKEYS}")
    print(f"Support files under {INSTALL_SHARE}/")
    if not with_hotkey_service:
        return None
    init = install_hotkey_service(script_dir)
    print(f"Hotkey service installed for {init}")
    return init
