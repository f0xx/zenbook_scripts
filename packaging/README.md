# Distribution packaging

Install paths and operator docs remain in [`DEPLOY.md`](../DEPLOY.md) at the
repo root. This tree holds **maintainer** recipes per distro.

## Layout

| Path | Purpose |
|------|---------|
| `gentoo/zenbook_scripts-9999.ebuild` | Live git package (`EGIT`) |
| `gentoo/zenbook_scripts-0.1.ebuild.stub` | Template for first release tag |

Copy ebuilds into a local overlay, e.g.:

```bash
mkdir -p /var/db/repos/local/overlay/app-laptop/zenbook_scripts
cp packaging/gentoo/zenbook_scripts-9999.ebuild \
   /var/db/repos/local/overlay/app-laptop/zenbook_scripts/
ebuild …/zenbook_scripts-9999.ebuild manifest
emerge -av app-laptop/zenbook_scripts
```

## USE flags (Gentoo)

| Flag | Default | Meaning |
|------|---------|---------|
| `hotkeys` | on | udev + OpenRC services (hotkeys, lid watcher, sleep hooks) |
| `screenpad` | off | ScreenPad CLI + udev + `zenbook-screenpad` / `-sync` (UX5400) |
| `kernel` | on | Build/install oot `hid-asus.ko` + boot sideload service |
| `qt6` | off | `configure_gui.py` (PySide6) |
| `zenbook_ux8406` | on | Install `conf.d/UX8406*` evdev profiles |

Recommended UX8406 docked USB profile:

```bash
emerge -av app-laptop/zenbook_scripts
# or from git overlay:
USE="hotkeys kernel zenbook_ux8406" emerge -av app-laptop/zenbook_scripts
```

Recommended UX5400EA (ScreenPad, no oot hid-asus):

```bash
USE="screenpad -kernel -zenbook_ux8406" emerge -av app-laptop/zenbook_scripts
```

### Installed paths (Gentoo / configure.py)

| Component | Path |
|-----------|------|
| Userspace tree | `/usr/local/share/zenbook-scripts/` |
| ScreenPad CLIs | `/usr/local/bin/screenpad`, `screenpad-boot`, `screenpad-sync` |
| Platform profile CLI | `/usr/local/bin/kb-platform-profile` |
| ScreenPad udev | `/etc/udev/rules.d/99-zenbook-screenpad.rules` |
| ScreenPad services | OpenRC `zenbook-screenpad`, `zenbook-screenpad-sync` |
| oot `hid-asus.ko` | `/usr/lib/modules/zenbook-hid-asus/<kver>/hid-asus.ko` |
| Manual sideload | `/usr/local/libexec/zenbook-hid-asus-switch` |
| Boot sideload | OpenRC `zenbook-kb-hid-asus` → `zenbook-hid-asus-boot.sh` |
| Boot config | `/etc/conf.d/zenbook-kb-hid-asus` (`sideload=yes\|no\|auto`) |

Re-emerge after **each kernel upgrade** (`KV_FULL` changes).

## Planned (not in tree yet)

- `debian/` — debhelper + DKMS
- `arch/` — PKGBUILD
- `nix/` — flake / default.nix

## Upstream

https://github.com/f0xx/zenbook_scripts
