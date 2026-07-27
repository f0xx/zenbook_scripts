# Duo Bluetooth Fn-row remapper

`bin/platform-bt-fn-row` — invert BT Mode B toward docked `fn_row_policy=7`.

Do not grab USB pogo (`0b05:1b2c`); only BT (`0b05:1b2d`).

Service card: [`../daemons/bt-fn-row.md`](../daemons/bt-fn-row.md).  
RE: [`../kernel/fn-row-policy.md`](../kernel/fn-row-policy.md).

## Why userspace

BT is one HID keyboard collection — no USB-style if0/if3/if4 bitmask path.
Firmware stays Mode B; remapper grab → uinput → policy-7-ish map.

## Safety

`EVIOCGRAB` silences the physical keyboard. If uinput is not ready, keys look
dead. Recovery: `platform-bt-fn-row stop` (or `panic`). STOP helper under
`contrib/desktop/`.

## Debug

```bash
platform-bt-fn-row status
sudo tail -f /run/zenbook-bt-fn-row.debug
```

Fn+Esc Mode A/B is firmware state; remapper assumes Mode B.

## See also

- [`../daemons/bt-fn-row.md`](../daemons/bt-fn-row.md)
- [`../kernel/fn-row-policy.md`](../kernel/fn-row-policy.md)
- [`../../README.fn_row_policy.md`](../../README.fn_row_policy.md)
