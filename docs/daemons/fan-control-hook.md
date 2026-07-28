# Fan sleep / lid hook — `zenbook-fan-control-hook`

Thin shim: system-sleep / lid → `platform-fan-control event …`, and on resume
restore **persisted** profile/PWM before adaptive re-eval.

## Usage

```bash
zenbook-fan-control-hook pre|post|lid-close|lid-open
```

Also invoked from `kb-brightness-sleep` when the hook is installed.

## Behaviour

| Phase | Action |
|-------|--------|
| `pre` | `platform-fan-control event sleep_pre` (often powersave) |
| `post` | `platform-fan restore` then `event sleep_post` |
| `lid-close` / `lid-open` | matching events; lid-open also restore |

## Key files

`contrib/openrc/zenbook-fan-control-hook.sh`, `bin/platform-fan-control`,
`bin/platform-fan`

## Interactions

Overlaps `platform-session` `fan_sleep_*` — prefer one orchestrator.
Never fails the sleep path hard (`|| true`).

If `/var/lib/zenbook-scripts/fan-control-mode` is `manual`, `sleep_post` restores
the user choice and skips adaptive re-eval (see `docs/daemons/fan-control.md`).
