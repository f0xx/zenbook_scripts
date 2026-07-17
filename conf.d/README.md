# Hotkey mapping playground (`conf.d/`)

Profiles are **`.conf` files** in this directory (and after install under
`/usr/share/zenbook-scripts/conf.d/` for the Gentoo ebuild, or
`/usr/local/share/zenbook-scripts/conf.d/` for `configure.py`). They layer like
`conf.d` on typical Unix services:

1. `00-default.*.conf` — base options (always loaded when matched)
2. `UX8406*.evdev.conf` — model family (matched by DMI `board_name` substring)
3. `~/.config/zenbook-scripts/zenbook-hotkeys.conf` — your overrides (highest priority)

## File types

| Suffix | Section | Purpose |
|--------|---------|---------|
| `.evdev.conf` | `[hotkeys]` | Linux input codes (`KEY_FN_F4`, `115`, `0x73`) |
| `.usb.conf` | `[usb_hotkeys]` | USB vendor bytes on interface 4 (`0xc4`, …) |

## Profile matching

```ini
[profile]
board_name=UX8406MA    # substring match in /sys/class/dmi/id/board_name
product_family=Zenbook Duo
priority=20            # higher wins for [options]; bindings merge in order
```

If `[profile]` is omitted, the filename stem must appear in `board_name`
(e.g. `UX8406MA.evdev.conf`).

Read DMI without root: files under `/sys/class/dmi/id/`. Compare with
`sudo dmidecode -t baseboard` if needed.

## Options

```ini
[options]
usb_poll=auto          # auto | true | false — auto disables USB polling when hid-asus is loaded
log_unmapped=true      # log keys with no binding (mapping playground)
device_name=Asus Keyboard
```

## Actions

Same as `zenbook-hotkeys.conf.example`:

- `kb-brightness:+1`, `-1`, `toggle`, `0`–`3`
- `display-brightness:up`, `down`
- `rfkill:wlan`, `bluetooth`
- `audio:mic-mute`
- `shell:…`, `exec:…`, `ignore`, `log`

## Workflow

```bash
kb-brightness-hotkeys --show-profile
kb-brightness-hotkeys --show-keys
kb-brightness-hotkeys --dry-run
# Edit conf.d/UX8406.evdev.conf or ~/.config/zenbook-scripts/zenbook-hotkeys.conf
sudo rc-service zenbook-kb-hotkeys restart
```

When the patched **hid-asus** module is loaded, leave volume/display/WLAN to the
kernel and desktop — only map keys that still need userspace (e.g. backlight if
`asus::kbd_backlight` is missing).
