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
| `hotkeys` | on | udev + OpenRC/systemd hotkey listener |
| `qt6` | off | `configure_gui.py` (PySide6) |
| `kernel` | off | Build/install oot `hid-asus` via `kernel/Makefile` |
| `zenbook_ux8406` | on | Install `conf.d/UX8406*` profiles |

## Planned (not in tree yet)

- `debian/` — debhelper + DKMS
- `arch/` — PKGBUILD
- `nix/` — flake / default.nix

## Upstream

https://github.com/f0xx/zenbook_scripts
