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

- **Tray:** left-click → `kcmshell6 kcm_zenbook_platform`; right-click → profile submenu
- **KCM:** Profiles tab (edit JSON-backed settings), Touchpad tab (status + open tuner)
- **Notifications:** `notify-send` / `knotify-send` on mode switch (toggle in KCM)

## CLI

```bash
platform-profiles status
platform-profiles set quiet
platform-profiles show
platform-profiles reset quiet
```

## Scheduling (cron — no daemon)

`configure.py` installs `/etc/cron.d/zenbook-profiles`:

```cron
* * * * * foxx /usr/bin/platform-profiles evaluate -q
```

Runs once per minute as `command_user` from `zenbook-kb-hotkeys` conf.d. Manual test:

```bash
platform-profiles evaluate
platform-profiles status
```

Evaluates schedules, low-CPU and battery-timeout triggers, and night eligibility
(lid open + awake). State: `~/.cache/zenbook-scripts/profiles-eval-state.json`.

## Not yet implemented

- Background **scheduler/evaluator** daemon (cron replaces this — no fat daemon)
- Per-interface **network off** beyond `nmcli networking off`

See also [night-mode.md](../daemons/night-mode.md) for closed-lid server behaviour.
