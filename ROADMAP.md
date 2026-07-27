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
| Plasma KCM + PowerDevil / session | **done** (0.0.3) | `platform-session` + KCM MVP; tag `v0.0.3` |
| Ubuntu `.deb` + packaging checks | **done** (CLI) | Smoke-built on Ubuntu 24.04 Server (augury1); KF6/KCM not in Noble |
| Alpine `apk` + packaging rules | **done** (smoke) | APK built on cast04 |
| Contributor research library | **done** (seed) | [`docs/`](docs/README.md) — Fn-row RE, daemon atlas, Duo/session/touchpad |
| Gentoo KCM via `USE=plasma` | **done** (tree) | emerge builds/installs KCM; Displays tab gated |
| Touchpad GUI calibrate (capture → knobs) | **now** | MVP Calibrate… in tuner; deepen for BT palm parasites |
| UX8406 dual-eDP touch jump (Plasma/Wayland) | **now** | `platform-touch-cal` diagnoses; compositor fix TBD |
| UX5400 WM/DE annoyance (TBD) | **later** | palm OK; separate Plasma/WM issue — describe when ready |
| UX581 lightbar (HID `0b05:0124`) | **later** | **blocked on hardware**; side branch `zenbook_ux581` |
| UX5400 AccelSpeed polish | **later** | same pipeline; lower priority than UX8406 |
| Generic non-ASUS fan backends | **later** | thinkpad/hp/dell hwmon profiles |
| Ubuntu KF6 / KCM `.deb` | **later** | needs 26.04+ or Kubuntu KF6 stack |

## After **0.0.3** — next RC (**0.0.4**)

| # | Track | Intent |
|---|--------|--------|
| 4.0 | **KCM in emerge + Displays gate** | **Done (tree).** `USE=plasma` builds KCM; tab gated by Duo/ScreenPad. |
| 4.1 | **Touchpad Calibrate deepen** | BT palm parasites; capture→knobs; UX8406 primary. |
| 4.2 | **`docs/` research library** | **Seeded.** Expand as RE continues; see [`docs/README.md`](docs/README.md). |
| 4.3 | **Dual-eDP touch jump** | **Diagnoser shipped** (`platform-touch-cal`). Fix = KWin/field; claim only after jump≈0. |
| 4.4 | **UX5400 WM/DE** | When described by operator. |
| 4.5 | **UX581 lightbar** | Hardware-gated; `zenbook_ux581`. |

Visual roadmap: Cursor canvas `platform-roadmap.canvas.tsx` (toward 0.0.4).

## After **0.0.2** — shipped as **0.0.3** (`feature/plasma-kcm-powerdevil`)

| # | Track | Intent |
|---|--------|--------|
| 3.1 | **Plasma KCM + PowerDevil / session** | **Shipped in 0.0.3.** |
| 3.2 | **Ubuntu / Debian** | **CLI `.deb` smoke on 24.04.** |
| 3.3 | **Alpine** | **APK smoke on cast04.** |
| 3.4 | **UX5400 WM/DE** | Deferred → 0.0.4 later. |
| 3.5 | **UX581 lightbar** | Still blocked on hardware. |

## Gentoo USE mapping

| USE | Installs |
|-----|----------|
| `hotkeys` | brightness hotkeys, lid/sleep |
| `fan_control` | `platform-fan*`, OpenRC, probe hooks |
| `screenpad` | UX5400 ScreenPad |
| `kernel` | oot hid-asus (build from sources; fail-closed preflight) |
| `qt6` | `configure_gui.py`, `platform-tray`, `platform-touchpad-gui` |
| `plasma` | `platform-session`, Duo/ScreenPad CLIs, sleep hook, **KCM** (KF6) |

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
                              └─► (done) 0.0.3 Plasma KCM + session + Duo BT
                              └─► (now) 0.0.4: Calibrate deepen · KCM emerge · Displays gate
                              └─► (later) dual-eDP · UX581 · Ubuntu KF6

screenpad* / zenbook-screenpad (oneshot)     UX5400 only
screenpad-sync (daemon)                      optional brightness mirror
```

Contributor research: [`docs/`](docs/README.md). See also [PLANNED.md](PLANNED.md) and [CHANGELOG.md](CHANGELOG.md).
