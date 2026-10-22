# ASUS ZenBook Pro Duo UX581 (sold as UX582)

**ZenBook Pro Duo** line marketed / sold as UX582 but often **UX581** on DMI
(e.g. UX581GV / UX581LV). Docs and **`platform-ux581-lightbar`** ship on **`main`**
since **0.0.5** (merged from `zenbook_ux581`).

## Light bar CLI (initial — hardware effects)

I2C-HID **`0b05:0124`** (ALED0217). Safe path: built-in effects 1–20, not ExpertBook
5-zone `rgb` / subcmd `0x80` on the **7-LED** UX582.

```bash
sudo platform-ux581-lightbar effect 2 --brightness 32 --infinite
sudo platform-ux581-lightbar off
platform-ux581-lightbar effects
platform-ux581-lightbar status
```

Details, stuck-state recovery, and Windows RE without sniff:
[`docs/ux581/lightbar.md`](docs/ux581/lightbar.md),
[`docs/ux581/lightbar-windows-re.md`](docs/ux581/lightbar-windows-re.md).

**Open problem:** solid per-zone RGB / custom fades (Windows has full colour;
Linux mapping still incomplete). Hotkeys were reported OK on this hardware last time.

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

## References

- [ASUS ZenBook Pro Duo UX581GV — lightbar research](https://github.com/s-light/ASUS-ZenBook-Pro-Duo-UX581GV/issues/3)
- [andykarpov/expertbook-led](https://github.com/andykarpov/expertbook-led)
- [hidapitester](https://github.com/todbot/hidapitester)
- This repo’s Aura Core keyboard notes (different device): [OpenRGB Aura Core wiki](https://openrgb-wiki.readthedocs.io/en/latest/asus/ASUS-Aura-Core/)
