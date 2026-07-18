# Planned features

## `kb-platform-profile` — implemented

```bash
kb-platform-profile get
kb-platform-profile list          # quiet balanced performance
kb-platform-profile set balanced
kb-platform-profile cycle         # quiet → balanced → performance → …
```

## `kb-fan` — implemented (status + limited control)

Probed on UX8406MA and UX5400EA (`asus-nb-wmi` hwmon):

| Control | Result |
|---------|--------|
| Custom `pwm*_auto_point_*` curves | **Unavailable** (`fan_curve_get_factory_default` → ENODEV) |
| `platform_profile` / `throttle_thermal_policy` | **Works** — quiet↔balanced↔performance (ttp 2/0/1) |
| `pwm1_enable` | **0** = full-on (~max RPM), **2** = firmware auto; **1** (manual curve) → EINVAL |
| `fan1_input` | RPM readout |

```bash
kb-fan status
kb-fan rpm
kb-fan auto                 # pwm1_enable=2
kb-fan full                 # pwm1_enable=0 (loud; needs root/sudoers)
kb-fan quiet|balanced|performance
kb-fan profile cycle
```

---

## ScreenPad Plus (UX5400EA) — implemented

```bash
screenpad status
screenpad on [n]          # re-enable quirk: bl_power=1 then brightness
screenpad off
screenpad toggle
screenpad set <0-255>
screenpad sync            # one-shot match main panel %
screenpad-sync            # daemon (OpenRC/systemd)
screenpad-boot            # boot restore oneshot
```

Install (auto-detected when `asus_screenpad` or DMI UX5400):

```bash
sudo ./configure.py --defaults --all-yes
# or ScreenPad-only:
# python3 -c "from pathlib import Path; from zenbook_kb.install import install_screenpad_support; install_screenpad_support(Path('.'))"
```

OpenRGB / rogauracore: **not applicable** on UX5400EA (no USB Aura Core HID; white kbd backlight is WMI `asus::kbd_backlight`).

---

## Fn-lock module parameters (UX8406) — implemented

`kernel/scripts/port-ux8406.py` adds:

- `fn_lock_default` — `-1` = DMI (UX8406 → Mode B), `0` / `1` override
- `fn_lock_allow_toggle` — disable Fn+Esc when `0`

Example: `contrib/modprobe/zenbook-hid-asus.conf` → `/etc/modprobe.d/`

---

## Sleep / lid backlight save-restore — implemented

- `bin/kb-brightness-sleep` — `pre` / `post` / `lid-close` / `lid-open`
- `contrib/systemd/zenbook-kb-brightness-sleep` → `/usr/lib/systemd/system-sleep/`
- `contrib/acpi/` — acpid lid/sleep events (fallback when acpid owns lid)
- `bin/kb-brightness-lid-watch` + `contrib/openrc/zenbook-kb-lid` — **elogind** `LidClosed` (UX8406MA default)
- `bin/snapshot-plan-state` — labelled config backups before milestones

---

## Boot sideload (OpenRC) — implemented

- `contrib/openrc/zenbook-kb-hid-asus` — default runlevel, before hotkeys
- `contrib/openrc/zenbook-hid-asus-boot.sh` — wait for USB dock, `insmod` + rebind
- `/usr/lib/modules/zenbook-hid-asus/<kver>/hid-asus.ko` — installed `.ko` path
- `/etc/conf.d/zenbook-kb-hid-asus` — `sideload=yes|no|auto`, fn-lock params, `usb_wait_secs`
- `packaging/gentoo/zenbook-scripts-9999.ebuild` — `USE=kernel` builds and installs the above
- `packaging/gentoo/zenbook-scripts-0.0.1_p1.ebuild` — release ebuild for upstream tag `v0.0.1_hf1`

---

## `switch-hid-asus.sh` — safe stock ↔ sideload toggle

Goal: one command that **cannot brick** the docked keyboard without an automatic rollback path.

### Safety rules (from field experience)

1. **Stop `zenbook-kb-hotkeys` first** — pyusb claims USB if4 and kills the dock
2. **Never start the hotkey service** from the switch script
3. **Touchpad (USB if5)** must stay on `hid-multitouch`, not `asus`
4. **Keyboard if0–if4** on sideload should stay on `asus` (do not move back to `hid-generic`)
5. **Snapshot** HID driver bindings before change → `/var/tmp/zenbook-hid-asus.snapshot`
6. **Verify** after rebind; on failure run `stock` restore automatically
7. **Emergency**: `switch-hid-asus.sh stock` or replug keyboard dock

### Commands

```bash
sudo ./kernel/scripts/switch-hid-asus.sh status
sudo ./kernel/scripts/switch-hid-asus.sh sideload --watchdog 120
# test typing on dock; if OK within 120s:
sudo ./kernel/scripts/switch-hid-asus.sh keep
# otherwise stock is restored automatically
sudo ./kernel/scripts/switch-hid-asus.sh stock
sudo ./kernel/scripts/switch-hid-asus.sh verify
```

### Watchdog (keyboard may reject all input on failure)

`sideload` starts a background timer (default **120s**). If you do not run `keep` in time,
**stock is restored automatically** — so a bricked dock does not require typing `stock`.

Confirm sideload using touchpad + on-screen keyboard, SSH, or the laptop built-in keyboard:

```bash
sudo ./kernel/scripts/switch-hid-asus.sh keep
```

### Verify checklist (automated)

| Check | Pass |
|-------|------|
| Keyboard interfaces bound to `asus` (sideload) or expected stock drivers | yes |
| Touchpad remains `hid-multitouch` | yes |
| `asus::kbd_backlight` sysfs present (sideload) | yes |
