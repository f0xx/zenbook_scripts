# Plasma KCM + PowerDevil session integration

**Branch:** `feature/plasma-kcm-powerdevil` (from `main` after **0.0.2**)  
**Target:** next RC / release (`0.0.3` or `0.0.3_pre1`)  
**Scope:** one shot — System Settings KCModule **and** PowerDevil / sleep–resume
session policies (not tray-only).

## Why together

| Piece | Alone | With the other |
|-------|-------|----------------|
| **KCModule** | Nice UI over existing CLIs | Place to edit **per-user** sleep/resume policies + presentation inhibit |
| **PowerDevil / resume** | elogind hooks already exist for brightness | Needs a UI + profile store; presentation mode must survive `plasmashell --replace` |

Tray (`platform-tray`) stays the quick thermal/fan surface. KCM is the
**settings** surface (System Settings → Hardware / Power / Zenbook).

## Problems we are solving

### 1. Plasma 6.6 resume / QSG leak (operator note)

On sleep/resume (Gentoo/elogind, worse on dual-eDP), `plasmashell` can leak
`QSGRenderThread` + Mesa threads after:

`qt.qpa.wayland: There are no outputs - creating placeholder screen`

Safe reset: `plasmashell --replace` (does **not** kill apps; `kwin_wayland`
holds windows). **Caveat:** presentation mode is an idle inhibit owned by
plasmashell (“User enabled presentation mode”) and is **lost** on replace.
PowerDevil itself survives.

### 2. Machine-global vs per-user

Today:

| Policy | Where | Scope |
|--------|-------|-------|
| Fan-control rules | `/etc/zenbook-scripts/fan-control.json` | **machine** (one thermal policy) |
| Brightness / fn-lock snapshot | `~/.config/zenbook-scripts/zenbook_duo.save` | **one** `command_user` |
| Touchpad | `/etc/zenbook-scripts/touchpad.json` | machine |

New sleep/resume / presentation preferences are **per-user** (Plasma session).
Fan PWM / `platform_profile` stay machine-global; KCM may *link* to them but
must not pretend they are per-seat.

## Architecture (target)

```
┌─────────────────────────────────────────────────────────────┐
│  System Settings — kcm_zenbook_platform (Qt6 / KF6)         │
│  tabs: Overview · Touchpad · Fans (read/link) · Sleep/Resume│
└─────────────┬───────────────────────────────┬───────────────┘
              │ DBus / CLI                    │ read/write
              ▼                               ▼
     platform-* CLIs              ~/.config/zenbook-scripts/
     (probe, fan, touchpad,         session.json   (per-user)
      fan-control status)           profiles/*.json
                                              │
              ┌───────────────────────────────┘
              ▼
┌─────────────────────────────────────────────────────────────┐
│  platform-session  (user service / systemd --user or        │
│                     elogind-triggered helper)                 │
│  • prepare: sleep_pre / hibernate_pre                        │
│  • resume:  sleep_post / hibernate_post                       │
│  • optional: plasmashell QSG heuristic → suggest --replace   │
│  • presentation inhibit held **outside** plasmashell         │
│    (kde-inhibit / PolicyAgent / systemd-inhibit)             │
└─────────────────────────────────────────────────────────────┘
              │
              ├─► existing kb-brightness-sleep / lid hooks
              ├─► platform-fan-control event sleep_*
              └─► PowerDevil (does not own our inhibit)
```

## Session policy sketch (`session.json`)

```json
{
  "version": 1,
  "active_profile": "default",
  "profiles": {
    "default": {
      "on_sleep": ["brightness_save", "fan_sleep_pre"],
      "on_resume": ["brightness_restore", "fan_sleep_post", "touchpad_reassert"],
      "on_hibernate": ["brightness_save"],
      "presentation": {
        "restore_after_plasmashell_replace": true,
        "inhibit_backend": "auto"
      },
      "plasmashell": {
        "watch_qsg_threads": false,
        "auto_replace": false,
        "qsg_thread_threshold": 32
      }
    }
  }
}
```

Defaults stay conservative: **no** auto `plasmashell --replace` until soaked.

## KCModule sketch

| Tab | Contents |
|-----|----------|
| **Overview** | `platform-probe --json` summary; links to services |
| **Touchpad** | Embed or launch knobs already in `platform-touchpad-gui` (reuse lib) |
| **Thermal** | Read-only status + “open fan-control.json” / tray hint (machine-global) |
| **Sleep / Resume** | Profile picker; action checklists; presentation restore toggle |
| **Advanced** | QSG watch / threshold (off by default); inhibit backend override |

**Tech preference:** Qt6 + KF6 KCM (C++ or QML KCM). Fallback for non-Plasma
distros: keep tray + CLI; KCM is `USE=plasma` / optional package.

Gentoo: new USE `plasma` (or extend `qt6`) installing:

- `kcm_zenbook_platform` + desktop file
- `platform-session` user unit / helper
- this README

## Presentation-mode inhibit (research checklist)

1. Capture current inhibit list: `systemd-inhibit --list`, Plasma PolicyAgent.
2. Prefer holding inhibit from **`platform-session`** (or `kde-inhibit`) so
   `plasmashell --replace` does not drop “presentation mode”.
3. On resume / replace: if profile says restore → re-acquire inhibit.
4. Never fight PowerDevil’s own sleep inhibits; only the **user presentation**
   idle-inhibit class.

## Incremental delivery (this branch)

| Step | Deliverable |
|------|-------------|
| **A** | Design (this doc) + roadmap/CHANGELOG wiring |
| **B** | `platform-session` CLI + per-user JSON + wire existing sleep hooks |
| **C** | Presentation inhibit save/restore outside plasmashell |
| **D** | Optional QSG-thread watcher (suggest or gated auto-replace) |
| **E** | KCModule MVP (Sleep/Resume + Overview first; Touchpad/Thermal next) |
| **F** | Packaging: USE/`--with-plasma`, docs, RC notes |

## Non-goals (this branch)

- Rewriting fan-control to per-user
- Full replacement of `platform-tray`
- UX581 lightbar (stays on `zenbook_ux581`)
- Ubuntu `.deb` / Alpine `apk` (parallel later tracks)

## Related existing code

- `bin/kb-brightness-sleep`, `contrib/systemd/zenbook-kb-brightness-sleep`
- `bin/kb-brightness-lid-watch`, `contrib/openrc/zenbook-kb-lid`
- `contrib/openrc/zenbook-fan-control-hook.sh`
- `zenbook_kb/fan_control.py` (`sleep_pre` / `sleep_post`)
- `bin/platform-tray`, `bin/platform-touchpad-gui`

## See also

- [ROADMAP.md](ROADMAP.md) — status
- [PLANNED.md](PLANNED.md) — cheatsheets
- [CHANGELOG.md](CHANGELOG.md) — Unreleased / next RC
