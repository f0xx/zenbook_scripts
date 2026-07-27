# ScreenPad sync — `zenbook-screenpad-sync`

UX5400: mirror main backlight percentage onto `asus_screenpad` (with bl_power quirk).

## Start

OpenRC after `zenbook-screenpad` oneshot: `screenpad-boot` then
`screenpad-sync --replace`.

## Inputs / outputs

Main backlight sysfs (`intel_backlight` / `amdgpu_bl*`…); env
`MAIN_BACKLIGHT`, `SCREENPAD_BACKLIGHT`, `MIN_SCREENPAD_LEVEL`, `POLL_SECONDS`.
Pid `/run/zenbook-screenpad-sync.pid`.

## Key files

`bin/screenpad-sync`, `bin/screenpad-boot`, `lib/screenpad.sh`,
`contrib/openrc/zenbook-screenpad-sync`, `contrib/udev/99-zenbook-screenpad.rules`

## Failure modes

Missing `asus_screenpad`; permissions; inotify optional → poll fallback.
