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

## Still open

- Nested `usb`/`bluetooth` keys under one logical pad in `touchpad.json` v2
  (today: separate device keys when BT vs USB pad differ)
- Operator field table below

## Operator field notes

| Session | Transport | Symptom | Capture file | Applied knobs |
|---------|-----------|---------|--------------|---------------|
| | BT / USB | | | |

## See also

- [`pipeline.md`](pipeline.md)
- [`../daemons/touchpad.md`](../daemons/touchpad.md)
- `tests/test_touchpad_pipeline.py`, `tests/test_touch_map_calibrate.py`
