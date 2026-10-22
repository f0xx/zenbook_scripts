# hid-asus boot — `zenbook-kb-hid-asus`

Oneshot: sideload oot UX8406 `hid-asus.ko`, rebind docked keyboard, apply
`fn_lock_*` / `fn_row_policy` from conf.d, then **ensure vendor USB if4**
(Fn+Esc, Fn+F4–F12).

## Start

OpenRC → `/usr/libexec/zenbook-hid-asus-boot.sh` → `switch-hid-asus.sh sideload`
→ `switch-hid-asus.sh ensure-if4`. Waits for USB pogo `0b05:1b2c`
(`usb_wait_secs`), then settles and reprobes if4 if missing
(`vendor_if4_settle_secs`, `vendor_if4_reprobe_*` in conf.d).

systemd: `zenbook-kb-hid-asus.service` (same boot script). Hotkeys start only
after hid-asus (OpenRC `after zenbook-kb-hid-asus`; systemd unit ordering).

## Key files

`contrib/openrc/zenbook-kb-hid-asus`, `contrib/openrc/zenbook-hid-asus-boot.sh`,
`contrib/systemd/zenbook-kb-hid-asus.service`,
`contrib/openrc/conf.d/zenbook-kb-hid-asus`, `kernel/scripts/switch-hid-asus.sh`,
`kernel/scripts/rebind-hid-asus.sh`, `lib/fn_lock.sh`, `kernel/`

## Failure modes

Missing `.ko` → exit 0 (stock remains); undocked timeout skip; sideload fail →
stock stays. **Vendor if4 missing** after settle/reprobe → service exit 1;
`zenbook-kb-hotkeys` start_pre / systemd `ExecStartPre` runs `ensure-if4` again.

Manual recovery: `sudo zenbook-hid-asus-switch ensure-if4`

Runtime: `zenbook-kb-hotkeys` runs a periodic vendor-if4 health check (~60s) and
triggers `ensure-if4` when `event27` / `hidraw4` vanish. Manual: `platform-hid-asus-health ensure`.

Policy deep dive: [../kernel/fn-row-policy.md](../kernel/fn-row-policy.md).
