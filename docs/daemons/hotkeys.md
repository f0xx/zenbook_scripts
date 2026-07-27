# Hotkeys — `zenbook-kb-hotkeys`

Evdev listener for Duo Fn+/special keys; dispatches brightness, display, rfkill,
audio, and shell/exec actions from a conf file.

## Start

- OpenRC: `zenbook-kb-hotkeys` → `/usr/bin/kb-brightness-hotkeys --replace` as
  `command_user` from conf.d
- Optional udev restart on keyboard add (`99-zenbook-kb-hotkeys.rules`)
- systemd unit: `contrib/systemd/zenbook-kb-hotkeys.service`

## Inputs / outputs

| | |
|--|--|
| In | Evdev (USB `0b05:1b2c` / BT `0b05:1b2d`); optional USB vendor HID; `~/.config/zenbook-scripts/zenbook-hotkeys.conf` |
| Out | `kb-brightness` / helpers; log `/var/log/zenbook-kb-hotkeys.log`; pid `/run/zenbook-kb-hotkeys.pid` |

## Key files

`contrib/openrc/zenbook-kb-hotkeys`, `bin/kb-brightness-hotkeys`,
`zenbook_kb/hotkey.py`, `zenbook_kb/usb_hotkeys.py`,
`zenbook-hotkeys.conf.example`, `contrib/udev/zenbook-kb-hotkeys-udev`

## Failure modes

Missing `command_user`; no device; pidfile conflict without `--replace`; races
with hid-asus sideload (OpenRC `start_pre` waits).

## Interactions

Runs **after** `zenbook-kb-hid-asus`. Stop/start may call `kb-brightness-sleep`
save/restore. Does **not** grab by default (BT remapper does). Fn+F8 →
`platform-screen-swap` via conf.
