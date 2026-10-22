# Lid watch — `zenbook-kb-lid`

Poll elogind `LidClosed`; dim/restore keyboard backlight via
`kb-brightness-sleep lid-close|lid-open`. When `platform-night-mode` is
installed, also runs `lid-close|lid-open` for the closed-lid **night** profile
(see [night-mode.md](night-mode.md)).

## Start

OpenRC → `kb-brightness-lid-watch` (needs `login1` / elogind).

## Key files

`contrib/openrc/zenbook-kb-lid`, `bin/kb-brightness-lid-watch`,
`bin/kb-brightness-sleep`, `lib/snapshot.sh`

## Interactions

Shares brightness snapshot with hotkeys stop/start and session
`brightness_*`. Fan lid events are separate (`fan-control-hook` /
daemon `watch_lid`). Depends after hid-asus in OpenRC graph.
