# Dual-eDP touch jump (UX8406)

Symptom: touch on lower panel (eDP-2) warps the cursor to the primary under
Plasma Wayland — digitizers start with empty KWin `outputName` (auto), so
both panels share the wrong seat mapping.

## Fix (userspace): `platform-touch-map`

Maps each digitizer to its DRM connector via KWin D-Bus
`org.kde.KWin.InputDevice.outputName` (same idea as System Settings →
**Touchscreen**).

```bash
platform-touch-map status
platform-touch-map auto --save          # UX8406: ELAN9009→eDP-1, ELAN9008→eDP-2
platform-touch-map apply                # re-apply after sleep / login
platform-touch-map kcm                  # open Plasma Touchscreen KCM
```

Also runs from `platform-duo-dock undocked` and session action
`touch_map_apply` (see `plasma/session.json.example`).

KWin may clear mappings on logout — keep `--save` and re-`apply` on resume.

## Diagnoser: `platform-touch-cal`

Fullscreen multi-screen calibrator (xinput-val principles). Use **after**
`platform-touch-map auto` to confirm `jump_count≈0`.

```bash
platform-touch-cal
```

| Key | Action |
|-----|--------|
| Esc / q | Quit |
| Tab / n / Enter | Next **active** screen (yellow corners) |
| g | Print JSON report (+ `~/.config/zenbook-scripts/touch-cal-last.json`) |
| r | Reset corners on active screen |

**Red dots** = jump still present. **Blue** = consistent.

Wayland cannot apply Xorg `TransformationMatrix`; the printed matrix is for
comparison / nested X11 only.

## Operator checklist

1. Undock keyboard so eDP-2 is on (`platform-duo-dock status`)
2. `platform-touch-map auto --save` (or let duo-dock do it)
3. Tap mid-panel on eDP-2 — cursor should stay on eDP-2
4. Optional: run `platform-touch-cal` and complete 4 corners per panel
5. If jump persists: `platform-touch-map status` + attach JSON; try
   `platform-touch-map kcm` manual Target Display

## See also

- [`dock-and-swap.md`](dock-and-swap.md)
- [`../../README.plasma.md`](../../README.plasma.md)
- `zenbook_kb/touch_map.py`, `tests/test_touch_map_calibrate.py`
- Reference tool: `/home/foxx/repos/My Projects/xinput-val`
