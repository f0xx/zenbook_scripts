# Roadmap — zenbook_scripts / platform tools

Status legend: **done** · **now** · **next** · **later**

## Where we are (2026-07)

| Area | Status | Notes |
|------|--------|--------|
| Docked UX8406 backlight + Fn chords | **done** | `kb-brightness`, oot `hid-asus`, hotkeys |
| ScreenPad (UX5400) | **done** | `screenpad*` |
| ACPI `platform_profile` CLI | **done** | `kb-platform-profile` |
| Fan RPM + auto/full PWM | **done** | `platform-fan` (`kb-fan` wrapper) |
| Adaptive AC/battery/lid/sleep daemon | **done** | `platform-fan-control` + JSON |
| Machine-global config (not per-user) | **done** | `/etc/zenbook-scripts/fan-control.json` |
| Capability probe / dry-run | **done** | `platform-probe` (`--json` / `--feature` / `--recommend-use`) |
| Rename away from `kb-fan` | **done** | `platform-fan*`; wrappers remain |
| Qt6 tray + thermal metrics | **done** | `platform-tray` / `platform-metrics` (SQLite, X-zoom, sticky POI) |
| Source-only oot hid-asus | **done** | preflight + `USE=kernel` / `--with-kernel` (no prebuilt `.ko`) |
| Non-interactive sudo | **done** | `sudo -n` via `zenbook_kb/priv.py` + lib helpers |
| Vendor-agnostic install hints | **done** | probe → Gentoo USE recommendations |
| EPP / RAPL in fan-control profiles | **next** | intel_pstate + powercap hooks |
| Touchpad sensitivity CLI | **next** | present on UX8406; Wayland needs KWin/DBus or quirks |
| Generic non-ASUS fan backends | **later** | thinkpad/hp/dell hwmon profiles |
| Full Plasma KCModule | **later** | optional; tray first |

## Touchpad (UX8406)

Hardware is visible (dock Primax + ELAN panels). **Sensitivity is not an ASUS WMI knob** — it is libinput `AccelSpeed` owned by the compositor (Plasma Wayland). We can detect devices today (`platform-probe`); configuring them portably is the next research item (`platform-touchpad`).

## Gentoo USE mapping

| USE | Installs |
|-----|----------|
| `hotkeys` | brightness hotkeys, lid/sleep |
| `fan_control` | `platform-fan*`, OpenRC, probe hooks |
| `screenpad` | UX5400 ScreenPad |
| `kernel` | oot hid-asus (build from sources; fail-closed preflight) |
| `qt6` | `configure_gui.py`, `platform-tray` |

```bash
platform-probe                  # human dry-run
platform-probe --json           # emerge / scripts
platform-probe --feature fan_pwm
platform-probe --recommend-use
```

## Dependency sketch

```
platform-probe ──────────────► install decisions (USE / configure flags)
       │
       ├─► platform-fan ◄──── asus-nb-wmi OR generic pwm hwmon
       │         ▲
       │         │
       └─► platform-fan-control ─► platform_profile + platform-fan
                    ▲
                    │
              platform-tray (qt6) ─► same CLIs + SQLite metrics graph
                    │
                    └─► (next) EPP/RAPL + touchpad helpers
```

See also [PLANNED.md](PLANNED.md) for command cheatsheets.
