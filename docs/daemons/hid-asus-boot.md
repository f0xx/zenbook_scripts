# hid-asus boot — `zenbook-kb-hid-asus`

Oneshot: sideload oot UX8406 `hid-asus.ko`, rebind docked keyboard, apply
`fn_lock_*` / `fn_row_policy` from conf.d.

## Start

OpenRC → `/usr/libexec/zenbook-hid-asus-boot.sh` → `switch-hid-asus.sh sideload`.
Waits for USB pogo `0b05:1b2c` (`usb_wait_secs`).

## Key files

`contrib/openrc/zenbook-kb-hid-asus`, `contrib/openrc/zenbook-hid-asus-boot.sh`,
`contrib/openrc/conf.d/zenbook-kb-hid-asus`, `kernel/scripts/switch-hid-asus.sh`,
`lib/fn_lock.sh`, `kernel/`

## Failure modes

Missing `.ko` → exit 0 (stock remains); undocked timeout skip; switch fail →
stock stays. **Before** hotkeys/lid in depend graph.

Policy deep dive: [../kernel/fn-row-policy.md](../kernel/fn-row-policy.md).
