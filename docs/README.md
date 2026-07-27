# Research and contributor docs

Deep dives for contributors. Root `README.*.md` stays operator-facing.

**0.0.4 catalog** — first pass from codebase + operator notes.

## Index

| Doc | Topic |
|-----|--------|
| [kernel/fn-row-policy.md](kernel/fn-row-policy.md) | `fn_row_policy` RE, HID if0/3/4, mask math, porting |
| [daemons/README.md](daemons/README.md) | Atlas + per-daemon pages |
| [duo/bt-fn-row.md](duo/bt-fn-row.md) | BT Mode B remapper, grab safety, D-Bus |
| [duo/dock-and-swap.md](duo/dock-and-swap.md) | Dock eDP-2 + screen-swap / KWin |
| [session/plasma-session.md](session/plasma-session.md) | `session.json`, inhibit, KCM |
| [touchpad/pipeline.md](touchpad/pipeline.md) | typing-inhibit → soft_accel |
| [touchpad/calibrate.md](touchpad/calibrate.md) | Calibrate deepen plan (0.0.4) |
| [ux581/lightbar.md](ux581/lightbar.md) | Lightbar stub (hardware-blocked) |

## Conventions

- Prefer diagrams and tables over long prose
- Name sysfs / HID paths and report IDs explicitly
- Link to `bin/`, `lib/`, `kernel/`, `contrib/`
- Root READMEs = entry points; deep pages live here

## Root map

| Root | Points at |
|------|-----------|
| `README.fn_row_policy.md` | Operator chords → `docs/kernel/` for RE |
| `kernel/README.md` | OOT build/install |
| `README.plasma.md` | Design → `docs/session/` for ops |
| `DEPLOY.md` | Install / redeploy |
| `ROADMAP.md` | Status / 0.0.4 tracks |
