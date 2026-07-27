# BT Fn-row remapper — `zenbook-bt-fn-row`

When Bluetooth Duo keyboard (`0b05:1b2d`) is present, invert Mode B toward
docked `fn_row_policy=7` behaviour via grab + uinput. Idle reconnect loop if
absent. **Never grabs USB pogo (`1b2c`).**

Full design: [../duo/bt-fn-row.md](../duo/bt-fn-row.md).

## Start

```bash
sudo platform-bt-fn-row start    # or: rc-service zenbook-bt-fn-row start
platform-bt-fn-row status        # must say ACTIVE
sudo tail -f /run/zenbook-bt-fn-row.debug
```

udev: `99-zenbook-bt-fn-row.rules` → `start` on HID add (no restart storm).

## Failure modes

Grab before session accepts uinput → **all keys dead** — use STOP desktop /
`platform-bt-fn-row stop` / `panic`. Fn+Esc into Mode A + remapper = double invert.

## Interactions

Complements kernel `fn_row_policy` on docked USB. Parallel to hotkeys (hotkeys
listen; this remaps). Needs working session D-Bus for some helpers (from
plasmashell environ).
