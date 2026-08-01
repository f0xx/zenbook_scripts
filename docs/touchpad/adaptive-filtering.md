# Adaptive touchpad filtering (experimental)

**Status:** scaffold on `feature/adaptive-touchpad-filter` — field validation pending.

## Problem

Static `outlier_reject` / `exec_delay` knobs work for obvious palm brushes but
do not **adapt** when a pad's noise floor drifts (UX5400 GDX1515 long-session
jumps, UX8406 BT parasites). Operators re-calibrate manually; leftovers still
slip through until reboot.

## Approach

Selectable **filter profiles** in `touchpad.json` v2:

| `filter_profile` | Behaviour |
|------------------|-----------|
| `default` | Today's shipped static chain (unchanged) |
| `adaptive` | Same typing gate + exec_delay; **adaptive_matrix** replaces fixed outlier threshold |

### adaptive_matrix plugin

Per-frame (single-finger only; MT passthrough like other stages):

```
raw (x,y) → Δx,Δy
         → subtract predict_weight × EWMA(velocity)
         → if |residual| > spike_sigma × EWMA(|residual|): DROP (no learn)
         → else: update baselines + velocity EWMA
         → apply 2×2 matrix to residual (diagonal scales from learned noise)
         → emit corrected position
```

**Not** soft_accel-style scalar gain — matrix entries derive from historical
amplitude per axis. Sporadic spikes are excluded from learning so baselines
track “typical” motion, not teleports.

### Persistence

`~/.config/zenbook-scripts/adaptive-touchpad/<device-key>.json`:

- `baseline_x`, `baseline_y` — learned amplitude EWMA  
- `vel_x`, `vel_y` — predictive velocity  
- `matrix` — 2×2 (identity + adaptive diagonal)  
- `samples` — frames used for learning  

Saved on contact end and every `persist_every` accepted frames.

## Future work

- Cross-axis matrix terms (correlation / rotation)  
- Typing-armed vs always-on adaptive modes  
- GUI profile selector in `platform-touchpad-gui`  
- Calibrate wizard seeding adaptive baselines from capture JSONL  
- Optional always-on OpenRC unit (today: opt-in like static filter)

## Merge policy

1. Validate on UX5400 (GDX1515) and UX8406 (keyboard pad)  
2. Merge **`feature/adaptive-touchpad-filter` → `feature/0.0.4-touch-map-calibrate`**  
3. Merge **`feature/0.0.4-touch-map-calibrate` → `main`** (0.0.4 tag)

## Commands

```bash
# Enable adaptive profile for one device (see touchpad.json.example.adaptive)
platform-touchpad status          # shows filter_profile=
sudo platform-touchpad run --replace
ls ~/.config/zenbook-scripts/adaptive-touchpad/
```

## See also

- [`pipeline.md`](pipeline.md)  
- [`../daemons/touchpad.md`](../daemons/touchpad.md)  
- `tests/test_touchpad_adaptive.py`
