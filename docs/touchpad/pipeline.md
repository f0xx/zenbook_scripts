# Touchpad pipeline

`platform-touchpad run` — **EVIOCGRAB** the physical pad, filter, emit a virtual
uinput device. While live, the compositor only sees the virtual pad.

## What this is (and is not)

| Ours | Not ours |
|------|----------|
| Crude palm **brush** filter after typing (`exec_delay` / `outlier_reject`) | libinput / Plasma palm detection |
| Optional ABS **soft_accel** rewrite | Gesture recognition (2/3-finger) |
| Grab → rewrite → uinput | Fixing broken DE gestures |

If gestures feel wrong, **stop blaming palm first**: soft_accel rewrites every
move while enabled (not gated by typing). Palm stages only run in the typing
window.

## Stages

1. **typing_inhibit** — arm palm filters only after recent keyboard activity  
2. **exec_delay** — hold contact ≤N ms; drop short brushes (**when armed**)  
3. **outlier_reject** — drop impossible jumps (**when armed**)  
4. **soft_accel** — scale ABS deltas for live uinput (**always on if enabled**)

Default: soft_accel **off**. Enable only after calibrate; start with `gain: 1.0`.

## Failure modes (operator)

| Symptom | Likely cause | Action |
|---------|--------------|--------|
| Cursor teleports / “dangling” while moving | soft_accel gain≠1 always rewriting ABS | Disable soft_accel or `gain: 1.0` |
| Cursor + click/scroll totally dead | Grab held, nothing emitted (process hang / device EOF bug) | Stop live filter; undock recovers by killing the node |
| Undock “fixes” it | USB pad gone → grab released; BT/chassis pad unfiltered | Stop filter before undock; fix was release of grab |

```bash
# emergency stop
sudo kill "$(cat /run/zenbook-platform-touchpad.pid)" 2>/dev/null
# or: sudo rc-service zenbook-platform-touchpad stop
platform-touchpad status
```

## Config / GUI

```bash
platform-touchpad list
platform-touchpad-gui
# /etc/zenbook-scripts/touchpad.json  (v2 per-device keys)
```

Pidfile: `/run/zenbook-platform-touchpad.pid`

## 0.0.4

- soft_accel default **off** (mispoint mitigation)
- touchpad device EOF ends live run (release grab)
- Calibrate deepen still for BT palm parasites on UX8406

## See also

- [`../daemons/touchpad.md`](../daemons/touchpad.md)
- `tests/test_touchpad_pipeline.py`
