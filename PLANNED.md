# Planned features (not implemented yet)

## `kb-platform-profile` — fan / thermal mode helper

UX8406 has **no dedicated Fn key** for platform profile. Fn+F5 is **display brightness down**.

What works today (kernel only):

```bash
cat /sys/firmware/acpi/platform_profile
echo performance | sudo tee /sys/firmware/acpi/platform_profile
# choices: quiet balanced performance
```

Planned CLI:

```bash
kb-platform-profile get
kb-platform-profile list          # quiet balanced performance
kb-platform-profile set balanced
kb-platform-profile cycle         # quiet → balanced → performance → …
```

Optional later: bind an unmapped key from calibration JSON, or a desktop shortcut — not Fn+F5.

`asusctl` / per-fan PWM curves are unlikely on this board (`fan_curve_get_factory_default` fails in dmesg).

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
| USB `0b05:1b2c` present (if docked) | lsusb |
| Touchpad node if5 → `hid-multitouch` | sysfs |
| Vendor if4 → `asus` (sideload) or `hid-generic` (stock) | sysfs |
| `event*` nodes for Primax keyboard exist | `/dev/input` |
| Optional: user confirms typing in prompt | manual |

### Your idea?

If you have a preferred flow (e.g. always BT fallback, timed rollback, TTY prompt), note it here or in an issue — the script is designed to be extended.
