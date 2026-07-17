# ASUS ZenBook Pro Duo UX581 (sold as UX582)

Working branch for the **ZenBook Pro Duo** line marketed / sold as UX582 but
identified on hardware / photos as **UX581** (e.g. UX581GV / UX581LV family).

Hotkeys were reported working last time this machine was available. The open
problem is the **front multi-colour LED light bar** (Aura / “Alexa” bar on
Pro Duo): full colour / rainbow / modes under Windows, no useful reaction
under Linux with OpenRGB or rogauracore.

This document is a research note until hardware is back for capture.

## What the “front LED panel” actually is

On UX581GV, ASUS documents a dedicated **Lighting Bar** under the main
display (system status + optional Alexa UX). It is **not** the ScreenPad and
**not** the usual USB Aura Core keyboard HID that `rogauracore` / many OpenRGB
paths expect.

Community teardown / Windows Device Manager ([UX581GV issue #3](https://github.com/s-light/ASUS-ZenBook-Pro-Duo-UX581GV/issues/3)):

| Item | Value |
|------|--------|
| ACPI / PnP | `ALED0217` (`ACPI\VEN_ALED&DEV_0217`) |
| Path | `\_SB.PCI0.I2C*.ALED` (I²C HID) |
| HID on Linux | Appears as ASUS HID, reported **`0b05:0124`** |
| Driver IC (schematic notes) | ITE-class LED MCU (e.g. IT8232FN / similar); ~7 LEDs |
| Windows service | `ASUSOptimization` / ASUS System Control Interface — stopping it turns the bar off |

Kernel `asus-wmi` `asus::lightbar` is only an **on/off** (max brightness 1) WMI
LED for some ROG chassis bars. It does **not** implement UX581 colour modes.
Expect little or nothing useful from `/sys/class/leds/asus::lightbar` for this
panel.

## Why OpenRGB / rogauracore failed

- **rogauracore** — USB Aura Core keyboard protocol (`0x5A 0xBA …`). Wrong bus
  and wrong device class for `ALED0217`.
- **OpenRGB** — no first-class `ALED0217` / UX581 light-bar controller in the
  usual Aura USB detectors; SMBus helpers do not apply to this ACPI I²C-HID
  path.
- **asusctl** — aimed at ROG Aura / Slash / AniMe layouts via `aura_support.ron`;
  ZenBook Pro Duo bar is a different product feature unless someone adds an
  explicit layout + backend.

## Proven Linux poke (community)

With **BIOS Fast Boot disabled** so the I²C-HID node enumerates, and
[hidapitester](https://github.com/todbot/hidapitester):

Device: **`VID:PID 0b05:0124`**

Feature reports advertised:

- report id **`0x20`**, length **32** (use length 33 with report id byte)
- report id **`0x5a`**, length **16**

Examples that produced visible animation / colour (from the same issue):

```bash
# breath / animation experiments (report 0x20)
sudo hidapitester --vidpid 0B05/0124 -l 33 --open --send-feature 32,1,1
sudo hidapitester --vidpid 0B05/0124 -l 33 --open --send-feature 32,1,2
sudo hidapitester --vidpid 0B05/0124 -l 33 --open --send-feature 32,1,6
sudo hidapitester --vidpid 0B05/0124 -l 33 --open --send-feature 32,1,16

# further mode / colour bytes (community; incomplete map)
sudo hidapitester --vidpid 0B05/0124 -l 33 --open --send-feature 32,3,N
sudo hidapitester --vidpid 0B05/0124 -l 33 --open --send-feature 32,4,N
```

So control is **raw HID feature reports** on `0b05:0124`, not WMI brightness
and not Aura Core USB. A fuller mode/colour map still needs sniffing
(ASUSOptimization / Armoury / MyASUS on Windows, or systematic fuzzing).

Related userspace from the same research:
[andykarpov/expertbook-led](https://github.com/andykarpov/expertbook-led)
(ExpertBook B9450 / same ALED-class HID) — try once `0b05:0124` is confirmed
on the UX581.

## Hardware probe checklist (when the laptop is available)

```bash
# identity
cat /sys/class/dmi/id/product_name /sys/class/dmi/id/board_name

# look for the lightbar HID
lsusb -d 0b05:0124
grep -i ALED /sys/bus/i2c/devices/*/name 2>/dev/null
dmesg | grep -iE 'ALED|0124|i2c.*hid'

# HID nodes
ls -l /sys/class/hidraw/*/device/uevent
# then: hid-decode / hidapitester against 0b05:0124

# WMI lightbar (likely useless for colour)
ls /sys/class/leds/
# test only: brightness 0/1 on asus::lightbar if present
```

Optional Windows dual-boot capture:

1. Install USBPcap / similar while Armoury / ASUSOptimization drives rainbow modes.
2. Or use [OpenRGB SMBus sniffer](https://gitlab.com/OpenRGBDevelopers/Tools/openrgb-smbus-sniffer-tool) only if traffic is truly on a free SMBus (UX581 path is I²C-HID; HID capture is more relevant).

## Likely implementation direction (this repo)

1. Confirm DMI + `0b05:0124` on the real unit (UX581 vs UX582LR naming).
2. Add a small `zenbook_kb` / `bin/` helper: open hidraw for `0b05:0124`, send
   feature `0x20` / `0x5a` with documented mode tables as they are reverse
   engineered.
3. Do **not** expect OpenRGB/rogauracore to grow support without upstream work;
   optionally contribute a controller there once the report map is solid.
4. Keep keyboard backlight / hotkeys separate (Aura Core or WMI, as on other
   Zenbooks) — orthogonal to this bar.

## References

- [ASUS ZenBook Pro Duo UX581GV — lightbar research](https://github.com/s-light/ASUS-ZenBook-Pro-Duo-UX581GV/issues/3)
- [ASUS — Notebook Lighting Bar (UX581GV / Alexa)](https://rog-forum.asus.com/t5/faqs-laptops-desktops/notebook-lighting-bar-introduction/ta-p/1089495)
- Kernel `asus-wmi` lightbar LED (on/off only): `ASUS_WMI_DEVID_LIGHTBAR` → `asus::lightbar`
- [andykarpov/expertbook-led](https://github.com/andykarpov/expertbook-led) — CLI built from the HID fuzzing above
- [hidapitester](https://github.com/todbot/hidapitester)
- This repo’s Aura Core keyboard notes (different device): [OpenRGB Aura Core wiki](https://openrgb-wiki.readthedocs.io/en/latest/asus/ASUS-Aura-Core/)
