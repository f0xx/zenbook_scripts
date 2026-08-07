# UX5400 GDX1515 — AccelSpeed via live filter

The integrated **GDX1515** pad on UX5400EA runs through `platform-touchpad`
(EVIOCGRAB → uinput). Plasma/libinput **AccelSpeed does not apply** to the virtual
device — pointer feel must come from our pipeline.

## Preset (`touchpad.json.example.ux5400`)

| Knob | Value | Notes |
|------|-------|--------|
| `soft_accel.enabled` | `true` | Only enable after exec_delay/outlier tuned |
| `soft_accel.mode` | `nonlinear` | Slow moves ~1×; faster deltas ramp toward gain |
| `soft_accel.gain` | `1.45` | ~+45% vs raw (tune in GUI Calibrate) |
| `soft_accel.pivot` | `30` | Per-frame delta where ramp starts |

Static chain stays: `typing_inhibit` → `exec_delay` → `outlier_reject` → `soft_accel`.

## Operator notes

1. In Plasma → Input → Touchpad, set acceleration **flat / off** for the physical
   pad name while the live filter runs (compositor sees the uinput node instead).
2. Run `platform-touchpad-gui` → Calibrate if jumps return after long sessions.
3. Prefer **`default`** filter profile until static stages are stable; try
   **`adaptive`** only when outlier threshold drift is an issue.

See also [`pipeline.md`](pipeline.md), [`../daemons/touchpad.md`](../daemons/touchpad.md).
