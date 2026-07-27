# UX581 / UX582 lightbar (research stub)

**Status:** blocked on hardware. Side branch: `zenbook_ux581`.
Sold as UX582; DMI often UX581 (e.g. UX581GV/LV).

## What we know

| Item | Detail |
|------|--------|
| Hardware | Front multi-colour LED bar under main display (Alexa/status) |
| ACPI / HID | ALED0217 (I2C-HID); Linux HID **`0b05:0124`** — not USB Aura Core keyboard |
| Windows | ASUSOptimization / System Control Interface — full colour/rainbow |
| Linux stock | `asus::lightbar` WMI on/off only (useless for colour) |
| OpenRGB / rogauracore | Wrong protocol (Aura Core USB `0x5A` `0xBA`…) |

## Working poke (historical)

Disable BIOS Fast Boot; `hidapitester` on `0b05:0124`; feature report **`0x20`**
(32 bytes). Partial map: reg1=anim (1–20), reg2=2 infinite loop, reg3=repeat,
reg4=brightness, reg5=LED count; **reg6 bricks device**. Related:
andykarpov/expertbook-led. Research thread:
[s-light/ASUS-ZenBook-Pro-Duo-UX581GV#3](https://github.com/s-light/ASUS-ZenBook-Pro-Duo-UX581GV/issues/3).

## When device returns

1. Confirm DMI + `lsusb -d 0b05:0124`
2. Try expertbook-led / hidapitester
3. Add repo helper for feature reports
4. Optional OpenRGB upstream later

Not in 0.0.3 / 0.0.4 feature gate until hardware is available.
