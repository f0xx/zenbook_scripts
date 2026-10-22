# Touchpad filter — `zenbook-platform-touchpad`

Live palm / typing-inhibit / soft-accel: `EVIOCGRAB` source pad → pipeline →
uinput virtual pad.

**Safety (all models):** the live filter uses `EVIOCGRAB` on the source pad. If
the filter process is stopped uncleanly, the pad can look dead until
`sudo platform-touchpad stop`. The service is **not** enabled by default.

**KWin / Plasma (live filter running):** the filter grabs the physical pad and
KWin must route the pointer through the virtual **`(filter)`** uinput device.
If that node is **disabled** in KWin (common after `platform-touchpad stop`
without a matching restart), the cursor freezes while the BT mouse still works.

Symptoms:

- `platform-touchpad status` shows live filter **running**
- Physical pad listed but no cursor motion; BT mouse OK
- KWin: filter device `enabled=false`, physical `enabled=true` but grabbed

Manual recovery (pick one):

```bash
# A — restart filter (preferred after fix in tree: auto-enables KWin filter device)
sudo rc-service zenbook-platform-touchpad restart
# or GUI: Stop → Start live filter

# B — stop filter → use physical pad only
sudo platform-touchpad stop

# C — enable KWin filter pointer while filter runs (replace eventN with yours)
busctl --user set-property org.kde.KWin /org/kde/KWin/InputDevice/event15 \
  org.kde.KWin.InputDevice enabled b true
```

Inspect KWin state (session bus):

```bash
export XDG_RUNTIME_DIR=/run/user/$(id -u) DBUS_SESSION_BUS_ADDRESS=unix:path=$XDG_RUNTIME_DIR/bus
busctl --user get-property org.kde.KWin /org/kde/KWin/InputDevice/event15 \
  org.kde.KWin.InputDevice enabled
busctl --user get-property org.kde.KWin /org/kde/KWin/InputDevice/event6 \
  org.kde.KWin.InputDevice enabled
```

See also [../ops/resource-pressure.md](../ops/resource-pressure.md) if the
desktop feels slow while the filter is fine.

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

If the filter is **still running** but the cursor is stuck, see **KWin / Plasma**
above — `stop` alone may not re-enable the compositor pointer until restart.

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
