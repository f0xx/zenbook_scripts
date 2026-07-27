# UX581 / UX582 lightbar

**Status:** sidebranch `zenbook_ux581`. Unit tests for report builders only —
no live HID tests without hardware.

Sold as UX582; DMI often UX581 (e.g. UX581GV/LV).

## What we know

| Item | Detail |
|------|--------|
| Hardware | Front multi-colour LED bar under main display (Alexa/status) |
| ACPI / HID | ALED0217 (I2C-HID); Linux HID **`0b05:0124`** — not USB Aura Core keyboard |
| Windows | ASUSOptimization / System Control Interface — full colour/rainbow |
| Linux stock | `asus::lightbar` WMI on/off only (useless for colour) |
| OpenRGB / rogauracore | Wrong protocol (Aura Core USB `0x5A` `0xBA`…) |

## Helper: `platform-lightbar`

```bash
./bin/platform-lightbar status          # DMI + device presence
./bin/platform-lightbar list            # hidraw nodes
./bin/platform-lightbar set --anim 1    # dry-run (prints hex + hidapitester line)
./bin/platform-lightbar set --anim 16 --brightness 200 --apply   # live write
```

Feature report **`0x20`** (32-byte payload). Partial map: anim, loop, repeat,
brightness, LED count. **Register index 6 is blocked** (bricks device).

Related: [andykarpov/expertbook-led](https://github.com/andykarpov/expertbook-led),
[s-light/ASUS-ZenBook-Pro-Duo-UX581GV#3](https://github.com/s-light/ASUS-ZenBook-Pro-Duo-UX581GV/issues/3).

## When device returns

1. Confirm DMI + `lsusb -d 0b05:0124` / `platform-lightbar list`
2. BIOS Fast Boot **off**
3. Dry-run then `--apply` known-good anim values; expand colour map from sniff
4. Optional OpenRGB upstream later

## See also

- [`../../README.ux581.md`](../../README.ux581.md)
- `zenbook_kb/lightbar.py`, `tests/test_lightbar.py`
