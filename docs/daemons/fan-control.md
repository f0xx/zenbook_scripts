# Fan control — `zenbook-platform-fan-control`

Adaptive AC / load / temp / lid rules apply named JSON profiles:
`platform_profile`, PWM mode, optional EPP/RAPL.

## Start

```bash
platform-fan-control -c /etc/zenbook-scripts/fan-control.json run --replace
# OpenRC: zenbook-platform-fan-control  (do not also enable legacy zenbook-kb-fan-control)
```

## Manual vs adaptive

| Mode | File | Behaviour |
|------|------|-----------|
| **auto** (adaptive) | `/var/lib/zenbook-scripts/fan-control-mode` = `auto` | Continuous rules + AC/lid events may change profile/PWM |
| **manual** (user lock) | same file = `manual` | Rules paused; tray/CLI choice sticks |

**Locks (→ manual):** tray/CLI `Profile: quiet|balanced|performance`,
`Fans: full`, `platform-fan-control apply …`, `kb-platform-profile set`.

**Unlocks (→ auto):** tray `Profile: auto (adaptive)`, `Fans: auto`,
`platform-fan adaptive`, `platform-fan-control mode auto` / `once`.

Sleep while locked: `sleep_pre` may still cool briefly; `sleep_post` restores
the saved user profile/PWM and does **not** re-run adaptive rules.

```bash
platform-fan-control mode          # get
platform-fan-control mode manual   # lock
platform-fan-control mode auto     # resume rules + force one eval
```

## Inputs / outputs

| | |
|--|--|
| In | JSON (`fan-control.json.example`); loadavg; power_supply; hwmon; ACPI lid; events `sleep_*` / `lid_*` / `ac_*` |
| Out | Sysfs `platform_profile` + `pwm1_enable` (**direct — does not persist**); power knobs; log + pid `/run/zenbook-platform-fan-control.pid` |

## Key files

`bin/platform-fan-control`, `zenbook_kb/fan_control.py`,
`contrib/openrc/zenbook-platform-fan-control`, `fan-control.json.example`

## Failure modes

Missing JSON; no sensors; non-root without NOPASSWD sudo; hysteresis; lid-closed
skips continuous rules unless configured; **manual lock forgotten** (use
Profile/Fans auto to resume).

## Interactions

**Must not overwrite** `/var/lib/zenbook-scripts/platform-profile` — that file is
only for explicit CLI `kb-platform-profile set` / `platform-fan quiet|…`.
Adaptive path writes sysfs only. Sleep: `zenbook-fan-control-hook` and/or
`platform-session` `fan_sleep_*`. On resume, hook restores saved profile **before**
`sleep_post` re-eval (re-eval only when mode is auto).
