# Duo dock and screen swap

**Duo-only** (UX8406 / UX581 / UX582 / …). UX5400 ScreenPad is a different
path (`screenpad` CLI / `asus_screenpad`) — see KCM **Displays** ScreenPad
section, not this page.

## `platform-duo-dock`

On USB pogo (`0b05:1b2c`) add/remove: save/restore lower backlight, enable/disable
eDP-2, then restack so outputs are not left cloned at `0,0`.

```bash
platform-duo-dock status
```

Files: `bin/platform-duo-dock`, `contrib/udev/99-zenbook-duo-dock.rules`.

## `platform-screen-swap`

Fn+F8: toggle layout/priority and move windows between panels.

KWin 6: outputs are read-only from JS — use slots + `frameGeometry`; move
windows first, then kscreen.

```bash
platform-screen-swap
```

Files: `bin/platform-screen-swap`, hotkeys bindings in `conf.d/`.

## See also

- [`../kernel/fn-row-policy.md`](../kernel/fn-row-policy.md) — F8 special mapping
- [`../../README.ux8406.md`](../../README.ux8406.md)
- [`../session/plasma-session.md`](../session/plasma-session.md) — KCM Displays gating
