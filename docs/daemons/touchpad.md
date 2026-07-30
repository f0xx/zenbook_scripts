# Touchpad filter — `zenbook-platform-touchpad`

Live palm / typing-inhibit / soft-accel: `EVIOCGRAB` source pad → pipeline →
uinput virtual pad.

**Safety (all models):** the live filter uses `EVIOCGRAB` on the source pad. If
the filter process is stopped uncleanly, the pad can look dead until
`sudo platform-touchpad stop`. The service is **not** enabled by default.

**UX5400 (GDX1515):** field use shows `exec_delay` + `outlier_reject` help with
sporadic cursor jumps that otherwise build up until reboot. Enable via GUI,
`platform-touchpad run`, or (optional) `zenbook-platform-touchpad`.

**UX8406:** detachable Primax keyboard touchpad is the primary target; chassis
ELAN pads stay opt-in (`enabled: false` in the example). Tuning differs — do not
assume UX5400 knobs transfer verbatim.

## Start

```bash
sudo platform-touchpad run --replace --config /etc/zenbook-scripts/touchpad.json --device '<stable-key>'
# OpenRC / systemd units; GUI: platform-touchpad-gui
```

If the touchpad appears dead after experimenting with the filter:

```bash
sudo platform-touchpad stop
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

No pad / profile disabled (exit 2); non-Duo detachable pad without `--force`
(exit 3); grab/uinput fail → dead pad until `platform-touchpad stop`;
needs root/`uinput`. Pidfile conflict without `--replace`.

## Interactions

Independent of BT Fn-row remapper (different device). Session
`touchpad_reassert` may send SIGHUP — confirm handler if relying on it after resume.
