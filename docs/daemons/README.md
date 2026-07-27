# Daemon & service atlas

Long-lived processes and boot/sleep hooks. Pidfiles:
`/run/zenbook-*.pid` (`zenbook_kb/pidfile.py`). Probe: `platform-probe`.

| Name | Deep dive |
|------|-----------|
| Hotkeys | [hotkeys.md](hotkeys.md) |
| Fan control | [fan-control.md](fan-control.md) |
| Touchpad filter | [touchpad.md](touchpad.md) |
| BT Fn-row | [bt-fn-row.md](bt-fn-row.md) → also [../duo/bt-fn-row.md](../duo/bt-fn-row.md) |
| ScreenPad sync | [screenpad-sync.md](screenpad-sync.md) |
| Lid watch | [lid.md](lid.md) |
| Profile boot | [platform-profile.md](platform-profile.md) |
| hid-asus boot | [hid-asus-boot.md](hid-asus-boot.md) |
| Session hooks | [../session/plasma-session.md](../session/plasma-session.md) |
| Fan sleep hook | [fan-control-hook.md](fan-control-hook.md) |

## Dependency sketch

```
hid-asus boot ──► hotkeys (+ udev)
              └──► lid-watch
fan-control daemon ◄── fan-control-hook ──┐
                  ◄── platform-session ───┤ sleep/resume
kb-brightness-sleep ◄── lid / hotkeys / session
bt-fn-row (BT only)     vs     kernel fn_row_policy (USB dock)
screenpad-sync after screenpad-boot
platform-profile-boot (oneshot) + fan restore on resume
```

## One-shot CLIs (not daemons)

`kb-brightness`, `kb-platform-profile`, `platform-fan`, `platform-duo-dock`,
`platform-screen-swap`, `screenpad*`, `platform-probe`, `platform-session` —
see model READMEs and `PLANNED.md`.
