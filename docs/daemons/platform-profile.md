# Platform profile boot — `zenbook-platform-profile`

Oneshot: restore persisted ACPI `platform_profile` and optional fan PWM after
boot / hibernate.

## State files

| File | Written by |
|------|------------|
| `/var/lib/zenbook-scripts/platform-profile` | Explicit `kb-platform-profile set` / `platform-fan quiet|balanced|performance` |
| `/var/lib/zenbook-scripts/fan-pwm-enable` | Explicit `platform-fan auto|full` |

Adaptive `platform-fan-control` writes **sysfs only** (does not overwrite these).

## Start

```bash
platform-profile-boot
# OpenRC: zenbook-platform-profile (PLATFORM_PROFILE_BOOT_MODE=restore|skip)
# systemd: zenbook-platform-profile.service
```

## Key files

`bin/platform-profile-boot`, `lib/platform_profile.sh`, `lib/fan.sh`,
`contrib/openrc/zenbook-platform-profile`,
`contrib/systemd/zenbook-platform-profile.service`

## Interactions

Complements fan-control. Resume: `zenbook-fan-control-hook post` also
`platform-fan restore` before adaptive `sleep_post`.
