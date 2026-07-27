# Touchpad pipeline

`platform-touchpad run` — grab physical pad, filter, emit uinput.

## Stages

1. **typing_inhibit** — palm filters only shortly after keyboard activity  
2. **exec_delay** — delay / coalesce early motion  
3. **outlier_reject** — drop jump outliers  
4. **soft_accel** — `linear` / `nonlinear` (+ pivot)

Idle pointing stays pass-through when typing-inhibit is inactive.

## Config / GUI

```bash
platform-touchpad list
platform-touchpad-gui
# /etc/zenbook-scripts/touchpad.json  (v2 per-device keys)
```

Pidfile: `/run/zenbook-platform-touchpad.pid`

## 0.0.4

Deepen Calibrate (capture → knobs) for BT palm parasites on UX8406. AccelSpeed
on UX5400 is lower priority.

## See also

- [`../daemons/touchpad.md`](../daemons/touchpad.md)
- `tests/test_touchpad_pipeline.py`
