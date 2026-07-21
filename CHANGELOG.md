# Changelog

All notable changes to this project are documented here. The format is loosely
based on [Keep a Changelog](https://keepachangelog.com/). Version tags follow
Gentoo-friendly naming where needed (`v0.0.1_hf1` → PV `0.0.1_p1`,
`v0.0.2_pre1` → PV `0.0.2_pre1`).

## [Unreleased] — toward next RC (Plasma KCM + session)

Branch: `feature/plasma-kcm-powerdevil`. Design:
[`README.plasma.md`](README.plasma.md).

### Planned

- Plasma **KCModule** (System Settings) over probe / touchpad / thermal / sleep.
- **Per-user** sleep/hibernate/resume policies + presentation inhibit outside
  plasmashell (survives `plasmashell --replace`).
- Optional QSG-thread watch / gated auto-replace (off by default).

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
