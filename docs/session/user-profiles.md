# User profiles — tray + KCM

Per-user power/thermal modes in `~/.config/zenbook-scripts/profiles.json`.

## Modes

| Mode | Editable | Apply path |
|------|----------|------------|
| **auto** | view only | `platform-fan-control mode auto` |
| **quiet** | schedule + low-CPU / battery triggers | `platform-fan-control apply powersave` |
| **balanced** | same | `apply balanced` |
| **performance** | same | `apply performance` |
| **night** | schedule, screen/kbd/network toggles, base mode | `platform-night-mode` when enabled |

## UI

- **Tray:** left-click → `kcmshell6 kcm_zenbookplatform`; right-click → profile submenu
- **KCM:** Profiles tab (edit JSON-backed settings), Touchpad tab (status + open tuner)
- **Notifications:** `notify-send` / `knotify-send` on mode switch (toggle in KCM)

## CLI

```bash
platform-profiles status
platform-profiles set quiet
platform-profiles show
platform-profiles reset quiet
```

## Not yet implemented

- Background **scheduler/evaluator** daemon (cron-like start/stop + CPU/battery triggers)
- Full **touchpad knob embed** in KCM (today: open `platform-touchpad-gui`)
- Night **network off** (toggle stored; no netdev down yet)

See also [night-mode.md](../daemons/night-mode.md) for closed-lid server behaviour.
