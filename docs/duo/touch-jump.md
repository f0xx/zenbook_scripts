# Dual-eDP touch jump (UX8406) — calibrator

Symptom: touch on lower panel (eDP-2) warps the cursor to the primary under
Plasma Wayland — likely **KWin seat / touch routing**, not `platform-touchpad`.

We do **not** claim “fixed” until an operator run shows `jump_count≈0` with
recv==expect on both panels. Until then this tool **proves** the bug.

## Tool: `platform-touch-cal`

Fullscreen multi-screen calibrator inspired by [`xinput-val`](file:///home/foxx/repos/My%20Projects/xinput-val)
principles (corner targets TL→TR→BR→BL, live dots, affine/bbox report).

```bash
# USE=qt6 / PySide6 — opens a fullscreen window on *every* output
platform-touch-cal
# or: ./bin/platform-touch-cal
```

| Key | Action |
|-----|--------|
| Esc / q | Quit |
| Tab / n / Enter | Next **active** screen (yellow corners) |
| g | Print JSON report (+ `~/.config/zenbook-scripts/touch-cal-last.json`) |
| r | Reset corners on active screen |

**Red dots** = jump: event window ≠ geometry under coords, **or** event
delivered to a panel other than the ACTIVE one (classic lower→primary warp).  
**Blue** = consistent.

Wayland cannot apply Xorg `TransformationMatrix`; the printed matrix is for
comparison / nested X11 only.

## Operator checklist

1. Undock keyboard so eDP-2 is on (`platform-duo-dock status`)
2. Run calibrator (all panels lit; start on non-primary when present)
3. Complete 4 corners on **each** panel (Tab to switch active)
4. Tap mid-panel on eDP-2 while eDP-2 is ACTIVE — if log says
   `recv=eDP-1 expect=eDP-2` → seat routing bug confirmed
5. Attach `touch-cal-last.json` to the issue / chat

## See also

- [`dock-and-swap.md`](dock-and-swap.md)
- [`../../README.plasma.md`](../../README.plasma.md)
- `tests/test_touch_calibrate.py`
- Reference tool: `/home/foxx/repos/My Projects/xinput-val`
