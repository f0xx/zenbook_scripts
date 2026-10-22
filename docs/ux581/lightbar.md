# UX581 / UX582 lightbar

**Status:** **`platform-ux581-lightbar`** — hardware effects 1–20 on UX581/UX582 (7 zones).
**Cold power-off** clears latched static colours after bad `rgb`/`0x80` probes.
No solid RGB on 7-zone UX582 yet.
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

Disable BIOS Fast Boot. Feature report **`0x20`**, **33 bytes** (see
[expertbook-led](https://github.com/andykarpov/expertbook-led)): byte **1** =
sub-command, byte **2** = parameter.

| Sub (byte 1) | Param (byte 2) | Action |
|--------------|----------------|--------|
| `0x01` | 1–20 | hardware effect |
| `0x02` | `0x02` | infinite loop |
| `0x03` | 1–255 | repeat count |
| `0x04` | 1–32 | brightness |
| `0x07` | — | off |
| `0xC1` | `0x02` | LED-zone query (GET → count in byte 3) |
| `0x80` | `0x00`, `0x20` + 15 RGB bytes | **B9450 only** (5 zones). On UX582 (7 zones) this
  does **not** set colour — it triggers a spurious pulse (often blue). |
| `0x5A` | 16 data bytes | second feature report; no solid fill mapped on UX582 yet |

**UX581/UX582:** hidapitester research ([issue #3](https://github.com/s-light/ASUS-ZenBook-Pro-Duo-UX581GV/issues/3))
found **effects 1–20** only; *“didn't found how to enable a constant emission yet.”*
Use `platform-ux581-lightbar effect N --brightness 32 --infinite` (**do not** use
`--all-segments` unless debugging — subcmd `5` can latch static G/B/purple segments).
**Stuck static G–B–G (effect ID ignored):** latched firmware — stop `rgb`/`recover`/`--all-segments`.
Linux-only tries: `platform-ux581-lightbar bus-reset` then minimal `effect`. Then **full
shutdown**, power off **1–2 minutes** (Windows not required). Windows reset if still stuck.
**Never subcmd `6`.**
No **`rgb`** / subcmd **`0x80`** on UX582.

Old “reg1=anim, reg4=brightness” maps were wrong and only updated HID shadow
registers. Research:
[s-light/ASUS-ZenBook-Pro-Duo-UX581GV#3](https://github.com/s-light/ASUS-ZenBook-Pro-Duo-UX581GV/issues/3).

## When device returns

1. Confirm DMI; I2C HID `0018:0B05:0124` → `/dev/hidraw*` (not USB `lsusb`).
2. `platform-ux581-lightbar status` / `led-count` — safe reads.
3. **SET** via `HIDIOCSFEATURE` only (not `write()`). Avoid byte index 6 ≠ 0 (brick risk).
4. On UX581 (2026-10): GET/SET `0x20` succeeds and readback matches (e.g. anim=3,
   brightness=6) but the physical bar can stay **off** — likely needs an extra
   enable path (WMI/ACPI/BIOS), not Aura USB. Compare with Windows; disable Fast Boot.
5. Optional: expertbook-led / hidapitester; kernel `hid-asus` bind if a quirk exists.

**No Windows sniff?** See [lightbar-windows-re.md](lightbar-windows-re.md) — extract
ASUS Optimization / SCI, `strings`/`rg`, optional Ghidra.

Shipped in **0.0.5** (initial); solid per-zone colour still research — see
[lightbar-windows-re.md](lightbar-windows-re.md).
