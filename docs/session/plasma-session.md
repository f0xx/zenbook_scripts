# Plasma session (`platform-session`) + KCM

Per-user sleep/resume/hibernate actions and presentation-mode inhibit held
outside plasmashell (survives `plasmashell --replace`).

## Config

`plasma/session.json.example` → `~/.config/zenbook-scripts/session.json`

```bash
platform-session status
platform-session init
platform-session presentation status
```

## Hooks

- systemd: `contrib/systemd/zenbook-platform-session`
- OpenRC/elogind: `contrib/openrc/zenbook-platform-session-hook.sh`

If session.json owns fan/brightness sleep, avoid duplicate system-sleep hooks.

## KCM install (Gentoo)

`USE=plasma` builds `kcm_zenbook_platform` at emerge time (KF6). Devel-only:

`cd plasma/kcm && ./build.sh --system`

**Displays** tab: Duo (eDP-2 dock) and/or ScreenPad only — not every model.

## See also

- [`../../README.plasma.md`](../../README.plasma.md)
- [`../../plasma/README.md`](../../plasma/README.md)
- [`../daemons/fan-control-hook.md`](../daemons/fan-control-hook.md)
- [`../duo/dock-and-swap.md`](../duo/dock-and-swap.md)
- [`../touchpad/pipeline.md`](../touchpad/pipeline.md)
