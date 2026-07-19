"""Install prefix layout (default ``/usr``, overridable).

Environment:
  ZENBOOK_PREFIX=/usr          # default
  ZENBOOK_PREFIX=/usr/local    # legacy configure.py layout

CLI: ``configure.py --prefix /usr``
"""

from __future__ import annotations

import os
from pathlib import Path

_DEFAULT = Path("/usr")
_prefix = Path(os.environ.get("ZENBOOK_PREFIX", str(_DEFAULT))).resolve()


def get_prefix() -> Path:
    return _prefix


def set_prefix(prefix: str | Path) -> Path:
    """Set install prefix for this process (also updates ``ZENBOOK_PREFIX``)."""
    global _prefix
    _prefix = Path(prefix).expanduser().resolve()
    os.environ["ZENBOOK_PREFIX"] = str(_prefix)
    return _prefix


def bin_dir() -> Path:
    return _prefix / "bin"


def share_dir() -> Path:
    return _prefix / "share" / "zenbook-scripts"


def libexec_dir() -> Path:
    return _prefix / "libexec"


# Fixed system paths (not under prefix)
ETC_ZENBOOK = Path("/etc/zenbook-scripts")
UDEV_RULES_DIR = Path("/etc/udev/rules.d")
INITD_DIR = Path("/etc/init.d")
CONFD_DIR = Path("/etc/conf.d")
SYSTEMD_DIR = Path("/etc/systemd/system")
SYSTEMD_SLEEP_DIR = Path("/usr/lib/systemd/system-sleep")
ACPI_EVENTS_DIR = Path("/etc/acpi/events")
MODPROBE_DIR = Path("/etc/modprobe.d")
KO_ROOT = Path("/usr/lib/modules/zenbook-hid-asus")

# Names that may linger under a previous /usr/local install
LEGACY_BIN_NAMES = (
    "kb-brightness",
    "kb-brightness-hotkeys",
    "kb-brightness-sleep",
    "kb-brightness-lid-watch",
    "kb-calibrate-hotkeys",
    "kb-platform-profile",
    "kb-fan",
    "kb-fan-control",
    "platform-fan",
    "platform-fan-control",
    "platform-probe",
    "platform-power",
    "platform-touchpad",
    "platform-touchpad-gui",
    "platform-metrics",
    "platform-tray",
    "zenbook-fan-control-hook",
    "screenpad",
    "screenpad-sync",
    "screenpad-boot",
    "snapshot-plan-state",
)
LEGACY_LIBEXEC_NAMES = (
    "zenbook-kb-hotkeys-udev",
    "zenbook-kbd-sleep.sh",
    "zenbook-hid-asus-switch",
    "zenbook-hid-asus-rebind",
    "zenbook-hid-asus-boot.sh",
)
