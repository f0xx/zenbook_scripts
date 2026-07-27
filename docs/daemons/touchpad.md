# Touchpad filter — `zenbook-platform-touchpad`

Live palm / typing-inhibit / soft-accel: `EVIOCGRAB` source pad → pipeline →
uinput virtual pad.

## Start

```bash
sudo platform-touchpad run --replace --config /etc/zenbook-scripts/touchpad.json --device '<stable-key>'
# OpenRC / systemd units; GUI: platform-touchpad-gui
```

Pipeline order (see [../touchpad/pipeline.md](../touchpad/pipeline.md)):
`typing_inhibit` → `exec_delay` → `outlier_reject` → `soft_accel`.

## Inputs / outputs

| | |
|--|--|
| In | Touchpad evdev (+ keyboards for typing gate); per-device `touchpad.json` v2 |
| Out | Virtual uinput pad; pid `/run/zenbook-platform-touchpad.pid` |

## Key files

`bin/platform-touchpad`, `zenbook_kb/touchpad.py`, `touchpad.json.example`,
`contrib/openrc/zenbook-platform-touchpad`, `bin/platform-touchpad-gui`

## Failure modes

No pad / profile disabled (exit 2); grab/uinput fail → dead pad until stop;
needs root/`uinput`. Pidfile conflict without `--replace`.

## Interactions

Independent of BT Fn-row remapper (different device). Session
`touchpad_reassert` may send SIGHUP — confirm handler if relying on it after resume.
