# Changelog

All notable changes to this project are documented here. The format is loosely
based on [Keep a Changelog](https://keepachangelog.com/). Version tags follow
Gentoo-friendly naming where needed (`v0.0.1_hf1` → PV `0.0.1_p1`,
`v0.0.2_pre1` → PV `0.0.2_pre1`, `v0.0.5-rc1` → PV `0.0.5_rc1`).

## [0.0.5] — unreleased (RC: `v0.0.5-rc1`)

Tag (RC): `v0.0.5-rc1`. Gentoo PV: `0.0.5_rc1`. Final tag planned: `v0.0.5`.

### Added

- **UX581 / UX582 front lightbar (initial):** `platform-ux581-lightbar` — ALED0217
  I2C-HID `0b05:0124`, expertbook-style report `0x20` (effects 1–20, brightness,
  off, `bus-reset`, safe defaults). Docs: `docs/ux581/lightbar.md`,
  `docs/ux581/lightbar-windows-re.md`, [`README.ux581.md`](README.ux581.md).
- **`platform-hid-asus-health`:** vendor if4 / keyboard HID health watcher
  (`zenbook_kb/hid_asus_health.py`, tests, systemd unit ordering).
- **Kernel 7.2.0-gentoo:** maintained `ux8406-hid-asus.patch` (same set as 7.1.5;
  validated on hardware). Preflight + Gentoo `files/patches/` + `make build-7.2.0`.
- **Gentoo:** `zenbook-scripts-0.0.5_rc1.ebuild`; `9999` installs lightbar + hid-asus
  health + UX581 docs.

### Changed

- **KCM (Plasma):** profile path resolution (`resolveScript`), Profiles/Sleep/Touchpad
  polish, version **0.0.5**; `platform-profiles` on PATH.
- **Night mode:** apply/exit fixes; tests extended.
- **Fan control:** stale `pwm=0` / manual lock when returning to auto; ACPI `fan`
  event fight documented; `platform-fan-control` / `lib/fan.sh` guards.
- **Install (systemd):** `zenbook-kb-hid-asus.service` on `--with-kernel`; hotkeys
  `After=` + `ensure-if4` pre-start.
- **Duo dock / touchpad:** udev and OpenRC wait helpers; touch-map calibrate tests.
- **Kernel 7.1.3 patch:** regenerated port alignment with current oot tree.

### Fixed

- **UX8406:** fan stuck at high RPM when ACPI or stale sysfs fought adaptive daemon.
- **HID boot:** OpenRC/systemd hid-asus boot scripts and rebind/switch robustness.
- **Hotkeys / fn_lock / lid:** sleep and dock edge cases.

## [0.0.4] — 2026-08-07

Tag: `v0.0.4`. Gentoo PV: `0.0.4`.

### Added

- **Adaptive filter profiles** (`filter_profile`: `default` | `adaptive`): `adaptive_matrix`
  plugin with online baseline learning and persisted state (`zenbook_kb/touchpad_adaptive.py`).
- **Generic fan hwmon backends** (`zenbook_kb/fan_hwmon.py`): thinkpad, dell_smm, hp,
  asus, generic pwm — RPM read + PWM apply where sysfs exposes nodes.
- **Ubuntu KF6 deb + KCM:** binary package `zenbook-scripts-plasma` via
  `packaging/debian/build-kcm.sh`.
- **UX5400 AccelSpeed preset:** `touchpad.json.example.ux5400` + `docs/touchpad/ux5400-accel.md`
  (nonlinear `soft_accel`; **live filter required** for GDX1515 cursor motion).
- **`platform-touch-map`:** KWin `outputName` for Duo digitizers; `apply-docked` preset;
  `restore-kwin` / `list_pointer_touchpads` for pointer-class touchpads.
- **`platform-touchpad restore-kwin`:** re-enable physical pads after crashed filter.
- **Closed-lid night mode (scaffold):** `platform-night-mode`, `platform-night-setup`.
- **User profiles GUI (scaffold):** `profiles.json`, KCM Profiles tab, cron evaluate.
- **KCM:** handbook HTML/docbook, sync status on load, Touchpad knobs, live filter
  `sudo -n`, Displays tab auto-populate.
- **`contrib/udev/99-uinput.rules`:** `input` group access to `/dev/uinput`.
- **Docs:** adaptive filtering, resource-pressure, touchpad KWin recovery.

### Changed

- **Adaptive filter:** learn-only — no position rewrite (fixes sticky cursor on UX8406).
- **Touchpad config:** nested `transports.usb`/`.bluetooth` beats stale flat keys.
- **Gentoo `USE=plasma`:** emerge builds/installs KCM (KF6).
- **KCM Displays tab:** gated on Duo chassis / ScreenPad presence.
- **`platform-session` `touchpad_reassert`:** calls `restore-kwin` (SIGHUP was unhandled).
- **`platform-touchpad`:** SIGHUP graceful stop; `restore-kwin` subcommand.
- **Fan manual lock:** `lid_close` / `sleep_pre` still cool; defer `sleep_post` restore
  while lid closed; `fn_lock` sleep snapshot fix (`existing=""`).
- **`kb-brightness-sleep`:** fan hook runs even if brightness save fails; prefers
  `/usr/bin` in systemd sleep hook template.

### Fixed

- **UX5400 GDX1515 live filter:** whitelist, grab-safety, KWin `(filter)` routing on
  start/stop; GUI status timer CPU fix.
- **UX8406 dock handoff:** stop filter, `restore-kwin`, touch-map on dock/undock udev.
- **Live touchpad EOF/IO:** release EVIOCGRAB on device drop (undock/BT).
- **Fan tray stickiness:** `fan-control-mode` manual vs auto.
- **KCM live filter start:** `sudo -n platform-touchpad run` (was: direct call, uinput EPERM).
- **KWin after filter crash:** compositor touchpad re-enable via `restore-kwin`.

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
