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
| EPP / RAPL in fan-control profiles | **next** | intel_pstate + powercap hooks (**blocks announced 0.0.2**) |
| Touchpad palm / accidental-click filter | **next** | `platform-touchpad` pipeline (**blocks announced 0.0.2**) |
| Generic non-ASUS fan backends | **later** | thinkpad/hp/dell hwmon profiles |
| Full Plasma KCModule | **later** | optional; tray first |

## Touchpad / palm rejection (UX8406, related UX5400)

**Problem (not “sensitivity” alone):** large pad near the keyboard; while typing,
palm edges + light taps move the pointer and steal focus from the current field.
AccelSpeed / compositor tweaks help a little; they do not model “ignore short
palm brushes while keys are active.”

**Approach — single ordered filter pipeline** (iptables-inspired, but one chain
first; multi-chain enable/disable can come later if needed):

```
[libinput/evdev events]
        │
        ▼
┌─ platform-touchpad interceptor ─────────────────────────┐
│  enabled plugins in order (config JSON):                │
│    1. event-sim      (optional; inject for tests)       │
│    2. exec-delay     (hold ≤N ms — drop short brushes)  │
│    3. outlier-reject (drop impossible jumps / spikes)   │
│    4. smooth         (optional later: EMA / Kalman)     │
└──────────────────────────────────────┬──────────────────┘
                                       ▼
                              compositor / DE
```

MVP (good effect, small code): **event-sim + exec-delay + outlier-reject**.
Defer multi-branch chains and Kalman until the MVP proves out on UX8406 typing.

Probe already sees Primax/ELAN devices; wiring is userspace (evdev grab or
libinput plugin path — research item), not ASUS WMI.

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
                    └─► (next) EPP/RAPL + platform-touchpad filter pipeline
```

See also [PLANNED.md](PLANNED.md) for command cheatsheets.
