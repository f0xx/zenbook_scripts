# UX581 / UX582 lightbar — Windows binaries (no sniff)

**Goal:** Find how ASUS sets **solid colours** and custom patterns on ALED0217 /
`0B05:0124` when you cannot capture HID traffic. Binaries help; live sniff is still
faster if you ever can do one session.

**Linux today:** Hardware effects 1–20 only (`platform-ux581-lightbar effect`).
ExpertBook **5-zone** subcmd `0x80` is **not** valid on **7-zone** UX582 — do not
probe blindly (subcmd **6** bricks; bad `0x80` latches static G–B). See
[lightbar.md](lightbar.md).

## Stack (expected)

MyASUS / Alexa UI → **ASUS Optimization** or **System Control Interface (SCI)** →
usermode **`HidD_SetFeature`** → I2C-HID **`0B05:0124`** (reports **`0x20`** 33 B,
maybe **`0x5A`** 17 B). Not USB Aura Core (`0x5A 0xBA…`).

Stopping the **ASUS Optimization** service turns the bar off on UX581-class machines
([issue #3](https://github.com/s-light/ASUS-ZenBook-Pro-Duo-UX581GV/issues/3)).

## What to collect

| Priority | Location |
|----------|----------|
| 1 | `C:\Windows\System32\DriverStore\FileRepository\asussci*\**\ASUSOptimization\` |
| 2 | Sibling **`*.dll`** in that folder (logic often not in the `.exe`) |
| 3 | Same **asussci2** / **AsusSCI** tree from an ASUS support **`.exe`** installer |
| 4 | MyASUS / Armoury Crate dirs if SCI has no hits |
| 5 | `.sys` only if name mentions ALED / light / 0124 (often generic I2C-HID) |

You do **not** need the whole driver store — one **sci2 + Optimization** tree is enough.

### Without booting Windows on the laptop

Download the UX581/UX582 **Windows driver bundle** from ASUS, extract on Linux:

```bash
7z x 'ASUS_*_System_Control*.exe' -oasus-sci-extract
# or: innoextract, unar
```

Zip the extracted **ASUSOptimization** (and parent **asussci** folder) and copy to your dev machine.

## Quick triage (strings / ripgrep)

From the extracted or copied tree:

```bash
rg -a -i 'ALED0217|ALED|0B05|0124|LightBar|Light Bar|LED bar|HidD_SetFeature|HidD_GetFeature|FeatureReport' .
rg -a 'IT8232|\x20\x01|0x20' .
```

**Good signs:** 33-byte buffers with leading **`0x20`**, subcmds **`01`–`07`**, **`80`**, brightness **1–32**,
**21** bytes of RGB (7×3), calls to **`HidD_SetFeature`**.

**Compare:** [andykarpov/expertbook-led](https://github.com/andykarpov/expertbook-led) — B9450 uses
subcmd **`0x80`** + **15** RGB bytes (5 zones). Pro Duo likely extends that or uses report **`0x5A`**.

## If strings are not enough

1. Open the DLL that hits **`0124`** / **`ALED`** / **`HidD_SetFeature`** in **Ghidra**.
2. Find xrefs to **`HidD_SetFeature`**; trace buffer fill before the call.
3. Note report ID, length, and byte layout — reproduce **one** packet on Linux.

## Test on Linux (huge)

```bash
platform-ux581-lightbar status
platform-ux581-lightbar get
# Only after RE gives a single candidate — not random fuzz:
# platform-ux581-lightbar … (future guarded send)
```

**Never** subcmd **6**. Avoid **`rgb` / 0x80** on UX582 until layout is **7-zone**-verified.
If latched static colours return: **full shutdown**, power off 1–2 minutes.

## Sniff vs RE

| Method | Effort | Result |
|--------|--------|--------|
| HID sniff (USBPcap + colour change in UI) | Low | Exact bytes per action |
| `strings` / `rg` on SCI/Optimization | Low | File names, report hints |
| Ghidra on the right DLL | Medium–high | Packet layout if not obfuscated |
| Linux HID byte fuzzing | High risk | Not recommended |

## What to share for collaboration

Filenames that matched **`rg`**, plus **10–20 lines of context** around the best hits.
Optional: one Ghidra screenshot of the **`HidD_SetFeature`** buffer setup (no need to upload full PEs).
