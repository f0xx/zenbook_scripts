# Zenbook scripts — UX5400EA (ScreenPad) + shared tooling

Model docs for branch `zenbook_ux5400e`. Repo index: [`README.md`](README.md).

Also includes shared UX8406-oriented keyboard tooling inherited from `zenbook_ux8406ma`
(detachable keyboard backlight / Fn+ hotkeys). Prefer that branch for dock-focused work.

Tested ScreenPad path on **UX5400EA** (`asus_screenpad`, DRM `HDMI-A-2`).
Detachable keyboard path tested with Primax (`0b05:1b2c` USB / `0b05:1b2d` Bluetooth).

---

## Quick start

```bash
cd /path/to/zenbook_scripts

# 1. Dependencies (Gentoo example)
emerge -av dev-python/pyusb sys-apps/usbutils

# 2. Configure (console, whiptail, or GUI)
./configure.py          # recommended — can install system-wide
# ./configure.sh        # whiptail → falls back to configure.py
# ./configure_gui.py    # optional PySide6 GUI (dev-python/PySide6)

# Semi-auto modes (no prompts / assume yes):
# ./configure.py --defaults --all-yes
# ./configure.sh --defaults --all-yes

# 3. Set brightness
sudo kb-brightness 2    # after install, or: sudo ./bin/kb-brightness 2

# 4. Fn+ keys (after install with hotkey service)
kb-brightness-hotkeys --dry-run   # press Fn+ keys, see actions
```

---

## Configurators

| Script | Description |
|--------|-------------|
| [`configure.py`](configure.py) | Interactive console setup; writes config; optional full install |
| [`configure.sh`](configure.sh) | Whiptail UI for basic config; can hand off to `configure.py` for install |
| [`configure_gui.py`](configure_gui.py) | PySide6 GUI for IDs and brightness (`emerge dev-python/PySide6`) |

All write `~/.config/zenbook-scripts/zenbook-duo.conf`. On first install, `zenbook-hotkeys.conf` is created from the example for Fn+ bindings.

**When to reinstall vs restart only:** see [`DEPLOY.md`](DEPLOY.md).

### What `configure.py` install does

When you answer **yes** to install:

| Component | Path |
|-----------|------|
| CLI | `/usr/local/bin/kb-brightness`, `/usr/local/bin/kb-brightness-hotkeys` |
| Support tree | `/usr/local/share/zenbook-scripts/` (`lib/`, `zenbook_kb/`, `brightness.py`, examples) |
| sudoers | Passwordless `kb-brightness` for your user |
| udev | `/etc/udev/rules.d/99-zenbook-kb-hotkeys.rules` + `/usr/local/libexec/zenbook-kb-hotkeys-udev` |
| `input` group | Your user added (re-login required) |

**Gentoo overlay package** (`app-laptop/zenbook-scripts`) installs under **`/usr`** instead of `/usr/local` — see [`packaging/README.md`](packaging/README.md). Prefer one layout; do not mix emerge with `configure.py` install without cleaning the other prefix.

**Init system detection:** if `systemctl` is available → `systemd` unit `zenbook-kb-hotkeys.service`; otherwise → OpenRC `/etc/init.d/zenbook-kb-hotkeys` + `rc-update add`.

```bash
./configure.py
# … answer prompts …
# Install kb-brightness + Fn+ hotkey service?  → y
# Install udev rules + openrc/systemd service? → y
```

Manual copy of config:

```bash
mkdir -p ~/.config/zenbook-scripts
cp zenbook-duo.conf.example ~/.config/zenbook-scripts/zenbook-duo.conf
cp zenbook-hotkeys.conf.example ~/.config/zenbook-scripts/zenbook-hotkeys.conf
```

---

## How it works

Keyboard brightness uses the ASUS Aura Core HID protocol ([OpenRGB wiki](https://openrgb-wiki.readthedocs.io/en/latest/asus/ASUS-Aura-Core/)):

| Byte | Value |
|------|-------|
| 0 | `0x5A` report ID |
| 1–3 | `0xBA 0xC5 0xC4` |
| 4 | brightness `0`–`3` |

| Mode | When | IDs | Transport |
|------|------|-----|-----------|
| **USB (pogo pins)** | Keyboard docked | `0b05:1b2c` | pyusb HID `SET_REPORT` (interface 4) |
| **Bluetooth** | Keyboard detached | `0b05:1b2d` | hidraw `HIDIOCSFEATURE` |

Auto-detection prefers USB when the docked device is present.

---

## Brightness control (`kb-brightness`)

```bash
sudo kb-brightness 2              # set level 0–3
sudo kb-brightness +1               # increase (wraps at max)
sudo kb-brightness -1               # decrease
kb-brightness get                 # cached level (no root)
kb-brightness get_min             # 0
kb-brightness get_max             # 3
kb-brightness limits              # e.g. "0 3 protocol"

kb-brightness save                # snapshot → ~/.config/zenbook-scripts/zenbook_duo.save
kb-brightness save /path/to.save
kb-brightness restore             # merge snapshot, apply brightness
kb-brightness load /path/to.save  # alias for restore
```

`get` reads the last level written to `~/.config/zenbook-scripts/keyboard-brightness`. The detachable keyboard MCU does not expose a reliable hardware read in userspace.

### Brightness limits

Resolution order:

1. **config** — `brightness_min` / `brightness_max` in `zenbook-duo.conf`
2. **sysfs** — `/sys/class/leds/asus::kbd_backlight/max_brightness` when `hid-asus` is bound
3. **protocol** — default `0`–`3` for UX8406

`get_min` / `get_max` / `limits` work without root and without the keyboard connected.

### Python CLI (full options)

```bash
sudo ./brightness.py 2 --show-mode
sudo ./brightness.py 1 --mode bluetooth
sudo ./brightness.py 3 --mode usb --vendor-id 0x0b05 --product-id 0x1b2c
```

---

## Fn+ and special keys (`kb-brightness-hotkeys`)

The detachable keyboard’s **Fn+** keys do **not** arrive as simple acpid `button/*` events. They are evdev keys on:

| Source | Typical node | Role |
|--------|--------------|------|
| USB HID interface 1.3 | `...-event-if03` | Dedicated hotkey / Fn+ interface |
| Asus WMI | `Asus WMI hotkeys` | Laptop EC hotkeys (some Fn+ combos) |
| Bluetooth | Zenbook input with `KEY_FN` | When undocked |

`hid-generic` does not drive the backlight, but it **does** publish standard key codes (`KEY_KBDILLUM*`, `KEY_FN_F*`, `KEY_BRIGHTNESS*`, etc.) on the hotkey interface.

### Listener behaviour

`kb-brightness-hotkeys` watches those input devices and:

- Runs **built-in actions** for known keys (keyboard backlight, **display** brightness, mic mute, wlan/bt, …)
- **Logs unmapped** special keys as `unmapped KEY_FN_Fx (code)` so you can bind them
- Applies **user overrides** from `~/.config/zenbook-scripts/zenbook-hotkeys.conf`

```bash
kb-brightness-hotkeys --list         # /dev/input/event* being watched
kb-brightness-hotkeys --show-keys    # mappable keys per device
kb-brightness-hotkeys --dry-run      # test without executing actions
kb-brightness-hotkeys                # foreground listener
kb-brightness-hotkeys --quiet-unmapped
```

Requires:

- Read access to `/dev/input/event*` (group `input`, or udev rule from install)
- Passwordless `sudo kb-brightness` for keyboard backlight actions

### Hotkey config (`conf.d/` + `zenbook-hotkeys.conf`)

Mappings are **not hardcoded** anymore. They layer by DMI board name:

1. `conf.d/00-default.*.conf` — base options
2. `conf.d/UX8406*.conf` — model family (see [`conf.d/README.md`](conf.d/README.md))
3. `~/.config/zenbook-scripts/zenbook-hotkeys.conf` — your overrides

```bash
kb-brightness-hotkeys --show-profile   # DMI, matched profiles, binding counts
kb-brightness-hotkeys --show-keys      # codes exposed by watched devices
kb-brightness-hotkeys --dry-run        # test without executing actions
```

When **hid-asus** owns the detachable keyboard, `usb_poll=auto` disables userspace USB
polling (no driver detach / handshake). Volume (Fn+F1–F3), display, WLAN/BT are left to
the kernel and desktop unless you add explicit bindings in `conf.d/`.

Example user override (`~/.config/zenbook-scripts/zenbook-hotkeys.conf`):

```ini
[hotkeys]
KEY_FN_F4 = kb-brightness:toggle
# KEY_F7 = ignore                    # if plain F7 is inverted vs Fn+F7 on your unit
```

**Action types:**

| Action | Example |
|--------|---------|
| `kb-brightness:+1` / `-1` / `toggle` / `2` | Keyboard backlight |
| `display-brightness:up` / `down` | `brightnessctl`, `light`, or `xbacklight` |
| `rfkill:wlan` / `bluetooth` | `rfkill toggle` |
| `audio:mic-mute` | `pactl` or `amixer` |
| `shell:…` | Run via `/bin/sh -c` |
| `exec:cmd arg …` | Run argv directly |
| `log` | Print only (default for unknown specials) |
| `ignore` | Swallow in the listener only (desktop still receives the key) |

Edit `conf.d/UX8406.evdev.conf` as the mapping playground; keep personal tweaks in
`zenbook-hotkeys.conf`.

### Service management

**OpenRC (Gentoo, etc.):**

```bash
sudo rc-service zenbook-kb-hotkeys status
sudo rc-service zenbook-kb-hotkeys restart
tail -f /var/log/zenbook-kb-hotkeys.log
```

**systemd:**

```bash
sudo systemctl status zenbook-kb-hotkeys.service
sudo systemctl restart zenbook-kb-hotkeys.service
```

### udev (permissions + replug)

**udev cannot catch individual key presses** — only device add/remove. The shipped rules:

1. Set `GROUP="input"` on Zenbook keyboard `event*` nodes
2. Restart the hotkey service when the keyboard is plugged in

Installed automatically by `configure.py`, or manually:

```bash
sudo cp contrib/udev/99-zenbook-kb-hotkeys.rules /etc/udev/rules.d/
sudo cp contrib/udev/zenbook-kb-hotkeys-udev /usr/local/libexec/
sudo chmod +x /usr/local/libexec/zenbook-kb-hotkeys-udev
sudo udevadm control --reload-rules
sudo udevadm trigger --subsystem-match=input
sudo usermod -aG input "$USER"   # re-login
```

### Fallback: acpid + WMI

If `acpi_listen` prints a line when you press a key, use `contrib/acpi/zenbook-kbd-brightness` as a template. WMI notify codes in `asus-wmi`: `0xc4` (brighter), `0xc5` (dimmer), `0xc7` (toggle). On UX8406 the kernel often consumes these before userspace sees them — prefer `kb-brightness-hotkeys`.

---

## Kernel upgrade: 7.0.12 → 7.1.3

Compared Gentoo sources at `/usr/src/linux-7.0.12-gentoo-r1` and `/usr/src/linux-7.1.3-gentoo`.

### For UX8406 specifically: little change

| Area | 7.0.12-gentoo-r1 | 7.1.3-gentoo | Impact on UX8406 |
|------|------------------|--------------|------------------|
| **hid-asus** (`0x1b2c` / `0x1b2d`) | Not present | **Still not present** | Keyboard stays on `hid-generic`; these scripts still required |
| **asus-nb-wmi** UX8406 quirk | Present | Present (unchanged) | Dock detection, ignore bogus WLAN key — same |
| **asus-nb-wmi** UX8407AA quirk | Missing | **Added** | Only helps UX8407AA, not UX8406 |
| **asus-wmi** | Present | Battery charge-threshold sysfs fix | Unrelated to keyboard backlight |
| **hid-asus** general | Older init | Refactored init | Helps other ASUS HID devices; no Zenbook Duo IDs |
| **asus_armoury** | Present | Same | BIOS tuning only; no keyboard backlight attrs |

**Bottom line:** upgrading is worthwhile for general fixes, but does **not** upstream Zenbook Duo keyboard patches ([asusctl #25](https://github.com/OpenGamingCollective/asusctl/issues/25)). Expect the same userspace workflow.

### After upgrading — quick check

```bash
uname -r
lsusb | grep -i 'zenbook duo'
ls /sys/class/leds/asus*
grep DRIVER /sys/bus/hid/devices/*1B2C*/uevent   # today: hid-generic
```

---

## Advanced / experimental

### Bash module layout

```
lib/protocol.sh              constants
lib/detect.sh                USB vs Bluetooth detection
lib/state.sh                 cached brightness
lib/limits.sh                min/max resolution
lib/snapshot.sh              save / restore
lib/hidraw.sh                HID feature ioctl
lib/transport_usb.sh         pyusb path
lib/transport_bluetooth.sh   hidraw path
bin/kb-brightness            CLI
bin/kb-brightness-hotkeys    Fn+ listener wrapper
zenbook_kb/                  Python package (protocol, transports, hotkey, install)
```

### Experimental: kernel LED path

When `hid-asus` binds `0b05:1b2c` / `0b05:1b2d`:

```bash
ls /sys/class/leds/asus::kbd_backlight/
echo 2 | sudo tee /sys/class/leds/asus::kbd_backlight/brightness
```

Community kernel work: [hacker1024/linux `ux8406-hid`](https://github.com/hacker1024/linux/compare/v6.14.4...ux8406-hid).

### Experimental: asusctl / asusd

Does **not** replace these scripts until `hid-asus` exposes `asus::kbd_backlight`. `asus_armoury` has no keyboard brightness attribute on UX8406.

### What does not work for UX8406 keyboard backlight

| Path | Status |
|------|--------|
| `/sys/class/backlight/asus_screenpad/` | ScreenPad Plus backlight (UX5400 etc.); **not** the UX8406 detachable keyboard |
| `/sys/class/leds/asus::kbd_backlight/` | Not present until `hid-asus` lands |
| `asus_armoury` firmware attributes | No keyboard brightness |
| WMI-only userspace | Targets laptop EC, not BT keyboard MCU |

### Troubleshooting

```bash
# Device present?
lsusb | grep -i '0b05:1b2c'
ls /sys/class/hidraw/hidraw*/device/uevent | xargs grep -l '1B2D'

# Brightness permission errors
sudo kb-brightness 2 --show-mode

# Hotkey listener
kb-brightness-hotkeys --list
kb-brightness-hotkeys --dry-run
groups | grep input
rc-service zenbook-kb-hotkeys status    # OpenRC
# systemctl status zenbook-kb-hotkeys  # systemd

# hidraw descriptor size (90 = USB control, 257 = BT)
wc -c < /sys/class/hidraw/hidraw0/device/report_descriptor

# Kernel driver
readlink /sys/bus/hid/devices/*1B2C*/driver
```

---

## Project layout

```
brightness.py                 Python CLI
backlight.py                  backward-compatible alias
brightness.sh                 bash wrapper → kb-brightness
bin/kb-brightness             brightness CLI
bin/kb-brightness-hotkeys     Fn+ / special-key listener
bin/kb-platform-profile       ACPI platform_profile (quiet/balanced/performance)
bin/kb-fan                    Fan RPM + auto/full-on + profile helpers
bin/kb-fan-control            Adaptive AC/battery/lid/sleep profile daemon (JSON)
bin/screenpad                 ScreenPad Plus on/off/brightness (UX5400)
bin/screenpad-boot            boot restore oneshot
bin/screenpad-sync            mirror main panel brightness %
configure.py                  console configurator + installer
configure.sh                  whiptail configurator
configure_gui.py              PySide6 GUI configurator
zenbook-duo.conf.example      keyboard / duo settings
zenbook-hotkeys.conf.example  Fn+ key bindings
zenbook_kb/                   Python library
zenbook_kb/install.py         install helpers (udev, OpenRC, systemd)
zenbook_kb/dmi.py             DMI / ScreenPad detection
lib/                          bash modules (incl. screenpad.sh, platform_profile.sh)
contrib/acpi/                 example acpid WMI rules
contrib/openrc/               OpenRC init scripts (hotkeys + ScreenPad)
contrib/udev/                 udev rules + replug helper
contrib/systemd/              systemd units (hotkeys + ScreenPad)
conf.d/UX5400EA.README        UX5400 model notes
kbd_test.sh                   brightness cycle test
```

---

## Zenbook Duo UX5400EA (ScreenPad Plus)

Branch `zenbook_ux5400e`. Fixed keyboard (WMI white backlight) + secondary ScreenPad
(DRM connector, usually `HDMI-A-2`) when EC-powered.

| Sysfs | Role |
|-------|------|
| `/sys/class/leds/asus::kbd_backlight/` | Keyboard backlight 0–3 (WMI; works out of the box) |
| `/sys/class/backlight/asus_screenpad/` | ScreenPad brightness 0–255 + power |
| `/sys/firmware/acpi/platform_profile` | `quiet` / `balanced` / `performance` (no custom fan curves) |
| `asus-nb-wmi` hwmon `fan1_input` / `pwm1_enable` | RPM; `0`=full-on, `2`=auto (`kb-fan`) |

### CLI

```bash
screenpad status
screenpad on [n]          # default: last level or 180
screenpad off
screenpad toggle
screenpad set <0-255>     # 0 = off
screenpad sync            # one-shot match main panel %
screenpad-sync [--once]   # daemon (or one-shot)

kb-platform-profile get|list|set <name>|cycle
kb-fan status|rpm|auto|full|quiet|balanced|performance
kb-fan-control status|once|run|event …   # JSON /etc/zenbook-scripts/fan-control.json
```

**Kernel quirk (mainline before screenpad power fixes):** writing brightness with
`bl_power=0` keeps the panel off. `screenpad on` always sets `bl_power=1` then
brightness, then nudges DRM `detect` so `HDMI-A-2` reappears.

Last brightness is stored in `/var/lib/zenbook-scripts/screenpad-brightness`.

### Install / services

Auto-detected when DMI contains `UX5400` or `asus_screenpad` exists:

```bash
sudo ./configure.py --defaults --all-yes
# or ScreenPad-only:
python3 -c "from pathlib import Path; from zenbook_kb.install import install_screenpad_support; install_screenpad_support(Path('.'))"
```

| Piece | Path |
|-------|------|
| CLIs | `/usr/local/bin/screenpad`, `screenpad-boot`, `screenpad-sync`, `kb-platform-profile` |
| udev | `/etc/udev/rules.d/99-zenbook-screenpad.rules` (group `video` write) |
| OpenRC | `zenbook-screenpad`, `zenbook-screenpad-sync` |
| systemd | `zenbook-screenpad.service`, `zenbook-screenpad-sync.service` |
| Boot mode | `/etc/conf.d/zenbook-screenpad` → `SCREENPAD_BOOT_MODE=on\|off\|sync\|restore` |

```bash
rc-service zenbook-screenpad status
rc-service zenbook-screenpad-sync status
# Manual brightness only (disable sync):
sudo rc-service zenbook-screenpad-sync stop
```

OpenRGB / rogauracore: **not applicable** (no USB Aura Core HID on this model).

### Troubleshooting

```bash
# Panel gone, touchpad still works?
screenpad status
# expect: state=off or drm=none →
screenpad on 180
kscreen-doctor -o | grep -A2 HDMI

# Permissions (should be root:video rw after udev)
ls -l /sys/class/backlight/asus_screenpad/brightness
groups | grep video

# Fans: profiles + full-on/auto only (no PWM curves)
dmesg | grep fan_curve_get_factory_default   # ENODEV is normal
kb-platform-profile list
kb-fan status
```

See also [`PLANNED.md`](PLANNED.md) (implemented feature notes) and [`DEPLOY.md`](DEPLOY.md).

---

## Inspired by

Special thanks to the people and projects this work builds on:

- **[Alesya Huzik](https://github.com/alesya-h/)** — original Zenbook Duo Linux bring-up, including the first working `backlight.py` and `duo.sh` integration for the UX8406 detachable keyboard. See [zenbook-duo-2024-ux8406ma-linux](https://github.com/alesya-h/zenbook-duo-2024-ux8406ma-linux).
- **[OpenRGB — ASUS Aura Core](https://openrgb-wiki.readthedocs.io/en/latest/asus/ASUS-Aura-Core/)** — HID brightness protocol documentation (`0x5A 0xBA 0xC5 0xC4`).
- **[OpenGamingCollective / asusctl](https://github.com/OpenGamingCollective/asusctl)** — UX8406 tracking and discussion ([#25](https://github.com/OpenGamingCollective/asusctl/issues/25)).
- **[hacker1024/linux](https://github.com/hacker1024/linux)** — [`ux8406-hid`](https://github.com/hacker1024/linux/compare/v6.14.4...ux8406-hid) branch with `hid-asus` support, report-descriptor fixes, and hotkey mappings for the Zenbook Duo keyboard.
- **Linux kernel** — `drivers/hid/hid-asus.c`, `drivers/platform/x86/asus-wmi.c`, `drivers/platform/x86/asus-nb-wmi.c` for WMI notify codes and ASUS vendor key mappings.

---

## References

- [ASUS Aura Core protocol](https://openrgb-wiki.readthedocs.io/en/latest/asus/ASUS-Aura-Core/)
- [zenbook-duo-2024-ux8406ma-linux (Alesya Huzik)](https://github.com/alesya-h/zenbook-duo-2024-ux8406ma-linux)
- [asusctl UX8406 tracking](https://github.com/OpenGamingCollective/asusctl/issues/25)
- [hacker1024 ux8406-hid kernel branch](https://github.com/hacker1024/linux/compare/v6.14.4...ux8406-hid)
