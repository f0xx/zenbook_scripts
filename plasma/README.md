# Plasma session helpers

Plasma 6 integration for [zenbook_scripts](../README.plasma.md): KCModule,
session policy JSON, and `platform-session` sleep/resume orchestration.

```
plasma/
  README.md                 # this file
  session.json.example      # per-user profile schema
  kcm/                      # System Settings module (KF6 QML KCM)
    build.sh
    CMakeLists.txt
    src/
```

## KCModule MVP (`kcm_zenbook_platform`)

System Settings module with four tabs:

| Tab | Purpose |
|-----|---------|
| **Overview** | `platform-probe` text summary + Refresh |
| **Duo / Displays** | `platform-duo-dock status`; Docked / Undocked / Screen swap |
| **Sleep / Resume** | Edit `~/.config/zenbook-scripts/session.json` toggles |
| **About** | Version + pointer to `README.plasma.md` |

### Build dependencies (Gentoo)

Emerging the KCM requires dev packages (runtime Plasma is not enough):

```bash
emerge -av \
  kde-frameworks/extra-cmake-modules \
  kde-frameworks/kcmutils \
  kde-frameworks/kcoreaddons \
  kde-frameworks/ki18n \
  kde-frameworks/kirigami \
  dev-qt/qtbase \
  dev-qt/qtdeclarative
```

Check installed frameworks:

```bash
qlist -I | grep -iE 'kcmutils|kirigami|extra-cmake'
ls /usr/lib64/cmake/KF6KCMUtils/
```

### Build and install

From the repo root:

```bash
cd plasma/kcm
chmod +x build.sh
./build.sh
```

Default prefix is `~/.local` (no root). For `/usr`:

```bash
sudo env PREFIX=/usr ./build.sh --system
```

Manual cmake (equivalent):

```bash
cd plasma/kcm
cmake -B build -DCMAKE_INSTALL_PREFIX=$HOME/.local \
  -DZENBOOK_SCRIPTS_ROOT="$(cd ../.. && pwd)"
cmake --build build
cmake --install build
```

For a user prefix, ensure Plasma sees plugins and desktop files:

```bash
export XDG_DATA_DIRS="$HOME/.local/share:${XDG_DATA_DIRS:-/usr/local/share:/usr/share}"
export QT_PLUGIN_PATH="$HOME/.local/lib64/plugins:${QT_PLUGIN_PATH:-}"
```

### Run

Standalone window:

```bash
kcmshell6 kcm_zenbook_platform
```

Or **System Settings → Display & Monitor → ZenBook Platform**.

List modules:

```bash
kcmshell6 --list | grep -i zenbook
```

Plugin install path on Gentoo must be Qt’s plugin tree:

`/usr/lib64/qt6/plugins/plasma/kcms/systemsettings/kcm_zenbook_platform.so`

(not plain `/usr/lib64/plugins/...`).
### CLI resolution

The KCM runs repo helpers in this order:

1. `/usr/bin/<script>`
2. `/usr/local/bin/<script>`
3. `$ZENBOOK_SCRIPTS_ROOT/bin/<script>` (compile-time repo path + env override)

Install zenbook_scripts to `/usr` for production; dev builds use the checkout
via `-DZENBOOK_SCRIPTS_ROOT=...` from `build.sh`.

### Session config

Schema: [`session.json.example`](session.json.example). The Sleep/Resume tab
writes `~/.config/zenbook-scripts/session.json`. `platform-session` reads the
same file on sleep/resume.

## `platform-session` CLI

Per-user orchestrator for sleep/resume/hibernate action lists, presentation idle
inhibit (outside plasmashell), and optional plasmashell QSG thread checks.

Install `bin/platform-session` to `/usr/bin` (or run from the repo checkout).
When sleep hooks run as **root**, the CLI drops to `command_user` from
`/etc/conf.d/zenbook-kb-hotkeys` or `ZENBOOK_SESSION_USER`.

### Quick start

```bash
platform-session init                     # ~/.config/zenbook-scripts/session.json
platform-session status
platform-session show
platform-session action brightness_save   # test one action
platform-session presentation on|off|status|restore
platform-session plasmashell check        # add --apply if auto_replace enabled
platform-session run sleep|resume
```

Action names in `session.json` map to existing tools (`kb-brightness-sleep`,
`platform-fan-control`, touchpad pidfile SIGHUP). Missing binaries are skipped
with a log line.

### Sleep hooks (machine-wide)

**Prefer session.json as the single orchestrator.** Install one hook and disable
redundant brightness/fan sleep hooks when your profile lists those actions.

| Hook | Install path | Calls |
|------|--------------|-------|
| systemd | `/usr/lib/systemd/system-sleep/zenbook-platform-session` | `platform-session run …` |
| OpenRC / elogind helper | `/usr/local/libexec/zenbook-platform-session-hook` | `pre\|post [suspend\|hibernate]` |

From the repo:

```bash
sudo install -m755 contrib/systemd/zenbook-platform-session \
  /usr/lib/systemd/system-sleep/zenbook-platform-session

sudo install -m755 contrib/openrc/zenbook-platform-session-hook.sh \
  /usr/local/libexec/zenbook-platform-session-hook
```

Existing `zenbook-kb-brightness` systemd sleep hook is **not** removed by default.
After enabling `platform-session`, remove duplicate calls (either drop the old
hook or remove `brightness_*` / `fan_*` actions from `session.json`).

Presentation inhibit state:

- PID file: `~/.cache/zenbook-scripts/presentation.inhibit.pid` or
  `/run/user/$UID/zenbook-scripts/presentation.inhibit.pid`
- Marker: `presentation.was_on` in the same cache dir (for restore after
  `plasmashell --replace`)

## See also

- [`README.plasma.md`](../README.plasma.md) — architecture and roadmap
- [`ROADMAP.md`](../ROADMAP.md) — branch status
