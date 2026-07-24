# Changelog

All notable changes to this project are documented here. The format is loosely
based on [Keep a Changelog](https://keepachangelog.com/). Version tags follow
Gentoo-friendly naming where needed (`v0.0.1_hf1` → PV `0.0.1_p1`,
`v0.0.2_pre1` → PV `0.0.2_pre1`).

## [0.0.3] — 2026-07-24

Tag: [`v0.0.3`](https://github.com/f0xx/zenbook_scripts/releases/tag/v0.0.3).
Gentoo PV: `0.0.3`. Draft precursor: `v0.0.3_pre1`.

### Added

- **`platform-session`:** per-user `session.json` orchestrator for sleep/resume/
  hibernate; presentation inhibit outside plasmashell; optional QSG check.
- **`kcm_zenbook_platform`:** Plasma 6 System Settings module (Overview / Duo /
  Sleep·Resume / About) — install via `plasma/kcm/build.sh` (KF6/Qt6; Gentoo
  primary — Ubuntu 24.04 Noble has no KF6 in archive).
- **`platform-profile` persistence:** last explicit CLI profile/PWM saved under
  `/var/lib/zenbook-scripts/`; `platform-profile-boot` + OpenRC/systemd oneshot
  restore after reboot/hibernate; resume hooks restore before adaptive
  fan-control re-evaluates (daemon writes sysfs only).
- **Packaging:** Gentoo `USE=plasma`; Debian CLI `.deb` (smoke-built on Ubuntu
  24.04 Server); Alpine APK (smoke-tested on cast04).

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
- **Debian packaging:** resolve `debian/` → `packaging/debian` symlink for
  `REPO_ROOT`; drop duplicate `debhelper-compat` / `debian/compat`.

### Out of scope

- **UX581 lightbar** — no hardware; stays on `zenbook_ux581`.
- Typing-inhibit palm polish (USB/BT) — continues in parallel.

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
