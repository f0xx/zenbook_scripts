# Roadmap — zenbook_scripts / platform tools

Status legend: **done** · **now** · **next** · **later**

## Where we are (2026-07)

| Area | Status | Notes |
|------|--------|--------|
| Docked UX8406 backlight + Fn chords | **done** | `kb-brightness`, oot `hid-asus`, hotkeys; [`README.fn_row_policy.md`](README.fn_row_policy.md) |
| ScreenPad (UX5400) | **done** | `screenpad*`; oneshot OpenRC stop fixed |
| ACPI `platform_profile` CLI | **done** | `kb-platform-profile` |
| Fan RPM + auto/full PWM | **done** | `platform-fan` (`kb-fan` wrapper) |
| Adaptive AC/battery/lid/sleep daemon | **done** | `platform-fan-control` + JSON; OpenRC `-c` order fixed |
| Machine-global config (not per-user) | **done** | `/etc/zenbook-scripts/fan-control.json` |
| Capability probe / dry-run | **done** | `platform-probe` (`--json` / `--feature` / `--recommend-use`) |
| Rename away from `kb-fan` | **done** | `platform-fan*`; wrappers remain |
| Qt6 tray + thermal metrics | **done** | `platform-tray` / `platform-metrics` — **validated UX5400** |
| Source-only oot hid-asus | **done** | preflight + `USE=kernel` / `--with-kernel` (no prebuilt `.ko`) |
| Non-interactive sudo | **done** | `sudo -n` via `zenbook_kb/priv.py` + lib helpers |
| Vendor-agnostic install hints | **done** | probe → Gentoo USE recommendations |
| EPP / RAPL in fan-control profiles | **done** | `epp` / `rapl` / `intel_pstate` + `platform-power` |
| Touchpad palm filter MVP | **done** | per-device profiles + Qt6 tuner; UX8406 primary |
| Touchpad typing-inhibit + soft-accel | **done** | shipped in **0.0.2** |
| Package / announce **0.0.2** | **done** | tag + published release + Gentoo Manifest/ebuild |
| Plasma resume hooks + sleep policies | **next** | per-user save/restore profiles |
| Ubuntu `.deb` + packaging checks | **later** | after 0.0.2; Ubuntu access / install verification |
| Alpine `apk` + packaging rules | **later** | after 0.0.2; Alpine install checks |
| UX5400 WM/DE annoyance (TBD) | **later** | palm OK; separate Plasma/WM issue — describe when ready |
| UX581 lightbar (HID `0b05:0124`) | **later** | no hardware on hand; side branch when accessible |
| UX5400 AccelSpeed polish | **later** | same pipeline; lower priority than UX8406 |
| Generic non-ASUS fan backends | **later** | thinkpad/hp/dell hwmon profiles |
| Full Plasma KCModule | **later** | optional; tray first |

### Field check — UX5400EA (`feature/epp-rapl-touchpad`)

Validated on-device: `platform-probe`, fan readings/PWM modes, `platform-fan-control`
daemon, tray metrics graph across profiles. ScreenPad oneshot restart no longer
spams `start-stop-daemon: no matching processes`.

## Touchpad / palm rejection (UX8406, related UX5400)

**Problem (not “sensitivity” alone):** large pad near the keyboard; while typing,
palm edges + light taps move the pointer and steal focus from the current field.

**MVP shipped:** ordered pipeline + per-device `touchpad.json` v2 +
`platform-touchpad-gui` (also from tray when on PATH).

**Now (typing-inhibit branch):** `typing_inhibit` (palm filters only for ~350 ms
after keyboard activity), `soft_accel` (`linear` / `nonlinear` + `pivot`),
multitouch passthrough, long-lived live filter + shared daemon pidfiles.

```bash
platform-touchpad list
platform-touchpad-gui
sudo platform-touchpad run --device '<stable-key>'
```

## After **0.0.2** (prep next)

| # | Track | Intent |
|---|--------|--------|
| 3.1 | **Plasma resume / sleep policy** | Resume watcher; sleep/hibernate/resume **configurable** policies; save/restore per **user profiles**. Presentation-mode inhibit survives `plasmashell --replace` (hold outside plasmashell). See operator note on Plasma 6.6 QSG leaks. |
| 3.2 | **Ubuntu / Debian** | Ship `.deb`; Ubuntu access; packaging + installation checks (not just from-source README). |
| 3.3 | **Alpine** | `apk` recipe; Alpine install checks; packaging rules for musl / OpenRC-native layout. |
| 3.4 | **UX5400 WM/DE** | Palm path looks fine; separate annoying behaviour (Plasma vs whole WM/DE) — details TBD by hardware owner. |
| 3.5 | **UX581 lightbar** | Still **no hardware on hand**. Blind research OK on side branch (`zenbook_ux581`); install + test when device returns. Path: ACPI ALED / HID `0b05:0124` feature report `0x20` — not Aura USB. |

## Gentoo USE mapping

| USE | Installs |
|-----|----------|
| `hotkeys` | brightness hotkeys, lid/sleep |
| `fan_control` | `platform-fan*`, OpenRC, probe hooks |
| `screenpad` | UX5400 ScreenPad |
| `kernel` | oot hid-asus (build from sources; fail-closed preflight) |
| `qt6` | `configure_gui.py`, `platform-tray`, `platform-touchpad-gui` |

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
                    │                      │
                    │                      └─► platform-power (EPP/RAPL/pstate)
                    │                                 ▲
                    │                                 │ profile JSON keys
                    ▼                                 │
              platform-tray (qt6) ────────────────────┘
                    │
                    ├─► metrics SQLite graph  (validated UX5400)
                    ├─► platform-touchpad-gui ──► platform-touchpad
                    │         │                         │
                    │         │                         ├─ typing-inhibit
                    │         │                         ├─ exec-delay
                    │         │                         ├─ outlier-reject
                    │         │                         └─ soft-accel
                    │         └─ per-device touchpad.json v2
                    │
                    └─► (done) announced 0.0.2
                              └─► (next) Plasma resume · .deb · apk · UX581

screenpad* / zenbook-screenpad (oneshot)     UX5400 only
screenpad-sync (daemon)                      optional brightness mirror
```

See also [PLANNED.md](PLANNED.md) for command cheatsheets and [CHANGELOG.md](CHANGELOG.md).
