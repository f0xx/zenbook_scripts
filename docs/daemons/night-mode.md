# Closed-lid night profile — `platform-night-mode`

On **AC power**, keep the laptop **awake** when the lid closes: panel off,
keyboard backlight off (via existing lid watch), **quiet fan**, minimum CPU/EPP,
**network stays up**. Opening the lid **restores** the fan/thermal state that
was active before night mode (snapshot in `/var/lib/zenbook-scripts/`).

Battery behaviour is unchanged — elogind still suspends on lid close unless you
override that separately.

## Prerequisites

1. **elogind** — install the drop-in so AC lid-close does not suspend:

   ```bash
   sudo cp contrib/elogind/99-zenbook-night-mode.conf /etc/elogind/logind.conf.d/
   sudo rc-service elogind restart   # or reboot
   ```

2. **Plasma PowerDevil** (recommended) — on AC, lid closed → **Turn off screen**:

   ```bash
   platform-night-setup --powerdevil-only
   # or: kwriteconfig6 … LidAction=64 under [AC][SuspendAndShutdown]
   ```

   (`64` = TurnOffScreen in PowerDevil 6.x)

3. **Config** — copy and enable:

   ```bash
   sudo cp night-mode.json.example /etc/zenbook-scripts/night-mode.json
   # edit: "enabled": true
   ```

4. **Fan profile** — merge from example (or run full optional setup):

   ```bash
   platform-night-setup --fan-only
   # adds profiles.night to /etc/zenbook-scripts/fan-control.json
   ```

   One-shot for all optional host bits:

   ```bash
   sudo platform-night-setup
   ```

## Commands

```bash
platform-night-mode status
platform-night-mode enter          # manual enter (respects enabled + AC)
platform-night-mode exit           # restore snapshot
platform-night-mode lid-close      # called from lid watch when lid shuts
platform-night-mode lid-open
```

## Automatic lid hook

`zenbook-kb-lid` / `kb-brightness-lid-watch` calls `platform-night-mode
lid-close|lid-open` after keyboard backlight save/restore when the binary is
installed.

Session orchestration (optional) — profile `night` in
`~/.config/zenbook-scripts/session.json`:

```json
"night": {
  "on_lid_close": ["brightness_save", "night_enter"],
  "on_lid_open": ["night_exit", "brightness_restore"]
}
```

Run via `platform-session run lid-close` / `lid-open` if you wire logind
user units; the OpenRC lid watcher is the primary path today.

## Snapshot / restore

| File | Purpose |
|------|---------|
| `/var/lib/zenbook-scripts/night-mode-snapshot.json` | Saved `fan-control-mode`, persisted platform profile + PWM |
| `/var/lib/zenbook-scripts/night-mode-active` | Marker while night mode is on |

Restore path: re-apply persisted sysfs via `platform-fan restore`, restore
control mode (`auto` vs `manual`), then `platform-fan-control event lid_open`
when adaptive rules should resume.

## Key files

`bin/platform-night-mode`, `zenbook_kb/night_mode.py`,
`night-mode.json.example`, `contrib/elogind/99-zenbook-night-mode.conf`,
`fan-control.json.example` (`night` profile)

## Failure modes

- **Still suspends on AC** — elogind drop-in missing or PowerDevil overrides
- **Panel stays on** — install `kscreen-doctor` or rely on PowerDevil screen-off
- **Fan stays quiet after open** — run `platform-night-mode exit` or
  `platform-fan restore`; check snapshot exists
- **No effect** — `"enabled": false` in `night-mode.json`

See also [ROADMAP.md §4.6](../../ROADMAP.md).
