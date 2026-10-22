# Touchpad Calibrate deepen (0.0.4)

Tuner **Calibrate…** runs a guided sequence → shared analyzer → optional
before/after drop-rate → save JSON + restart live filter.

## Flow

1. **type** (~8s) — type only, palms off  
2. **palm** (~8s) — palms only, no typing  
3. **mixed** (~12s) — normal work posture  
4. Suggest `max_delta` / `exec_delay` / typing window from **mixed** drop rates  
5. Apply → write `touchpad.json` → restart `platform-touchpad run --replace`  
6. Optional 10s mixed re-capture for before/after %

Capture JSONL `meta` includes `sequence` + `transport` (`usb` / `bluetooth` /
`i2c` from phys). CLI:

```bash
platform-touchpad capture --sequence mixed --transport usb -o /tmp/cap.jsonl --seconds 12
```

Analyzer: `zenbook_kb/touchpad_calibrate.py` (also used by the GUI).

## Nested USB / Bluetooth profiles

Detachable keyboard touchpads often differ between USB and Bluetooth (latency,
noise). Saves from **Calibrate…** or **Save config** nest knobs under one
logical device key:

```json
"Primax Electronics Ltd. ASUS Zenbook Duo Keyboard Touchpad": {
  "logical": "Primax Electronics Ltd. ASUS Zenbook Duo Keyboard Touchpad",
  "enabled": true,
  "transports": {
    "usb": { "filters": [ ... ] },
    "bluetooth": { "filters": [ ... ] }
  }
}
```

Runtime picks `transports.<detected>` via `phys` / `uniq`. Flat `name|phys`
keys remain valid for i2c pads and legacy configs.

## Operator field notes

Use this table when tuning in the field; attach capture JSONL paths if filing
issues.

| Session | Transport | Symptom | Capture file | Applied knobs |
|---------|-----------|---------|--------------|---------------|
| UX8406 | USB | palm jumps while typing | `/tmp/zenbook-tp-calibrate-mixed-*.jsonl` | max_delta↑, delay 25 ms |
| UX8406 | BT | sticky cursor after spike | same pattern, BT transport | max_delta↓ vs USB, typing_window↑ |
| UX5400 | i2c (GDX1515) | sporadic jumps | CLI `--device auto` mixed capture | outlier + exec_delay; soft_accel optional |
| UX8406 | USB | adaptive sticky | enable adaptive profile first | adaptive_matrix learn-only; re-calibrate mixed |

**Tips**

- Calibrate per transport you actually use (BT often needs tighter `max_delta`).
- Compare before/after drop % in the GUI; aim for low drops on **mixed**, not zero on **palm** (some palm drops are expected).
- After apply, confirm `platform-touchpad status` shows the expected `transport=` and filter chain.

## See also

- [`pipeline.md`](pipeline.md)
- [`../daemons/touchpad.md`](../daemons/touchpad.md)
- `touchpad.json.example` (Primax nested transports)
- `tests/test_touchpad_pipeline.py`, `tests/test_touch_map_calibrate.py`
