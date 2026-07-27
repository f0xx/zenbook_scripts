# Touchpad Calibrate deepen (0.0.4)

MVP today: tuner **Calibrate…** → `platform-touchpad capture` (~20s) → suggested
`max_delta` / `exec_delay` / typing window from drop rates.

## Goal

Map **capture → knobs** more deliberately for UX8406 **BT palm parasites**
(USB pogo already better). AccelSpeed on UX5400 stays Plasma/libinput.

## Planned deepen

1. Guided sequences: type-only / palm-only / mixed, labeled in capture meta
2. Per-transport profiles in `touchpad.json` v2 (`usb` vs `bluetooth` keys)
3. Apply suggestions with one click (write JSON + restart live filter)
4. Show before/after drop-rate in the tuner after apply

## Operator field notes (fill in)

| Session | Transport | Symptom | Capture file | Applied knobs |
|---------|-----------|---------|--------------|---------------|
| | BT / USB | | | |

## See also

- [`pipeline.md`](pipeline.md)
- [`../daemons/touchpad.md`](../daemons/touchpad.md)
- `tests/test_touchpad_pipeline.py`
