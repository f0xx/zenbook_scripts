# `fn_row_policy` — reverse engineering and porting

Operator chords/conf: [`../../README.fn_row_policy.md`](../../README.fn_row_policy.md).  
Build/install: [`../../kernel/README.md`](../../kernel/README.md).  
Tests: `python3 -m unittest tests.test_fn_row_policy -v`.

## Problem

Dock firmware Mode B: plain Fx = specials, Fn+Fx = `KEY_F*`. Linux usually
wants the inverse for F4–F12. OOT `hid-asus` `fn_row_policy` does that on USB
pogo only; BT needs `platform-bt-fn-row`.

## USB topology (`0b05:1b2c`)

| Interface | Role |
|-----------|------|
| if0 | Boot keyboard — `KEY_F*`, Meta, Fn, modifiers |
| if3 | Consumer — plain F1–F3 media in Mode B |
| if4 | Vendor — BL, brightness, swap, mic, RFKILL, … |
| if5 | Multitouch / mouse |
| EC | May still nudge volume on F2/F3 — not HID-gatable |

## Bitmask

Decimal `u32`. Bits 0–2 ignored. Bits 3–11: clear = swap, set = keep Mode B.

Non-zero policy enables F1–F3 fixed path. `0` = raw Mode B.

**Default `7`:** F4–F12 swapped + F1–F3 Linux-friendly path.

| Goal | Value |
|------|------:|
| Raw Mode B | `0` |
| Docked default | `7` |
| Keep F4 Mode B | `15` (`0x0F`) |
| Keep F4–F7 Mode B | `120` / `127` with F1–F3 path |
| Keep only F12 Mode B | `2048` / `2055` with F1–F3 path |

## Apply

Boot sideload uses `insmod` (conf.d), not modprobe. Live:
`echo 7 | sudo tee /sys/module/hid_asus/parameters/fn_row_policy`.

## See also

- [`../../README.fn_row_policy.md`](../../README.fn_row_policy.md)
- [`../duo/bt-fn-row.md`](../duo/bt-fn-row.md)
- [`../daemons/README.md`](../daemons/README.md)
- `tests/test_fn_row_policy.py`
