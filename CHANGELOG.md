# Changelog

All notable changes to this project are documented here. The format is loosely
based on [Keep a Changelog](https://keepachangelog.com/). Version tags follow
Gentoo-friendly naming where needed (`v0.0.1_hf1` → PV `0.0.1_p1`,
`v0.0.2_pre1` → PV `0.0.2_pre1`).

## [Unreleased] — toward **0.0.3_pre1** (Plasma KCM + session)

Branch: `feature/plasma-kcm-powerdevil`. Design:
[`README.plasma.md`](README.plasma.md). **UX581 lightbar not in this RC** (no
hardware). Typing-inhibit polish continues in parallel on the operator machine.

### Added

- **`platform-session`:** per-user `session.json` orchestrator for sleep/resume/
  hibernate actions; presentation inhibit outside plasmashell; optional QSG check.
- **`kcm_zenbook_platform`:** Plasma 6 System Settings module (Overview / Duo /
  Sleep·Resume / About) — install via `plasma/kcm/build.sh`.
- **Packaging scaffolds:** Gentoo `USE=plasma`; Debian `packaging/debian/`;
  Alpine `packaging/alpine/` (APK smoke-tested on cast04).

### Fixed (UX8406 Bluetooth / Duo layout)

- **BT keyboard dead keys:** oot `hid-asus` no longer applies the broken
  Usage(76h) rdesc fixup on `0b05:1b2d` (probe used to fail → touchpad only).
- **Typing-inhibit:** rescan keyboard nodes so late BT attach is seen.
- **`platform-duo-dock`:** enable/disable lower `eDP-2` on USB pogo add/remove;
  save/restore backlight; restack after enable (avoid kscreen 0,0 clone).
- **`platform-bt-fn-row`:** userspace Mode B → policy-7-ish Fn-row; RFKILL;
  session D-Bus from plasmashell environ for helpers.
- **`platform-screen-swap`:** layout + window exchange (KWin); Fn+F8.
- **`platform-probe`:** Duo keyboard (Bluetooth) health line.

## [0.0.2] — 2026-07-21

Tag: [`v0.0.2`](https://github.com/f0xx/zenbook_scripts/releases/tag/v0.0.2). Gentoo PV: `0.0.2`.

### Added

- **Typing-inhibit touchpad pipeline** (`platform-touchpad`): palm filters
  (`exec_delay`, `outlier_reject`) arm only for a short window after keyboard
  activity; idle pointing stays pass-through.
- **Soft acceleration** on the live uinput path (`soft_accel`): `linear` (constant
  gain) or `nonlinear` (smoothstep toward gain via `pivot`). DE AccelSpeed does
  not apply to the virtual device.
- **Multitouch passthrough** for soft-accel / delay / outlier stages (sticky MT
  via `TRACKING_ID`; coalesce single-finger prefix during delay).
- **Long-lived live filter**: survives GUI close; GUI toggle adopts a running
  process via pidfile `/run/zenbook-platform-touchpad.pid`.
- **Shared daemon pidfiles** (`zenbook_kb/pidfile.py` + OpenRC helpers) for
  touchpad, fan-control, hotkeys, screenpad-sync, and lid.
- **Fn-row policy docs**: [`README.fn_row_policy.md`](README.fn_row_policy.md)
  (bitmask tables, Mode B vs swap, decision flow, EC caveat).
- Unit tests: `tests/test_touchpad_pipeline.py`, `tests/test_pidfile.py`,
  `tests/test_fn_row_policy.py`.

### Changed

- Touchpad GUI / CLI: soft-accel mode combo; live filter lifecycle aligned with
  OpenRC/systemd units.
- UX8406 docked default remains **`fn_row_policy=7`** (F4–F12 swap + F1–F3
  fixed remap). See the Fn-row README for the full chord table.

### Includes (since 0.0.2_pre1)

- EPP/RAPL power hooks, `platform-probe`, Qt6 tray, palm-filter MVP, adaptive
  fan-control — see [0.0.2_pre1](#0202_pre1--2026-07-19).

## [0.0.2_pre1] — 2026-07-19

Pre-release for testing (fan-control / probe / tray / EPP-RAPL / palm-filter MVP).
Tag: [`v0.0.2_pre1`](https://github.com/f0xx/zenbook_scripts/releases/tag/v0.0.2_pre1).
Gentoo PV: `0.0.2_pre1`.

- Adaptive `platform-fan-control` + machine-global JSON.
- `platform-probe`, `platform-power` (EPP/RAPL), Qt6 `platform-tray`.
- Touchpad palm-filter MVP + per-device `touchpad.json` v2.
- UX5400 field validation for fan/tray; ScreenPad oneshot stop fix.

## [0.0.1_p1] — 2026-07-19

Hotfix release. Tag: [`v0.0.1_hf1`](https://github.com/f0xx/zenbook_scripts/releases/tag/v0.0.1_hf1)
(Gentoo PV `0.0.1_p1` — `_hf` is not a legal PMS suffix).

- UX8406 oot `hid-asus` docked Fn-row / backlight path.
- Hotkeys, brightness sleep/lid hooks, packaging baseline.
