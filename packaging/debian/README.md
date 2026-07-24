# Debian / Ubuntu packaging (zenbook-scripts)

**No `.deb` is published yet.** This directory holds a **debhelper scaffold** for
local builds and future review. Nothing is deployed to augury0 or any apt mirror
from this repo automatically.

## What the package installs

Binary package **`zenbook-scripts`** (Architecture: `all`), CLI-first:

- `/usr/bin/` — `kb-brightness`, `platform-probe`, `platform-session`, …
- `/usr/share/zenbook-scripts/` — Python + shell support tree
- `/usr/libexec/` — udev/ACPI helpers
- udev rules, systemd units, and sleep hooks under `/etc` and `/usr/lib/systemd/`
- OpenRC scripts under `/usr/share/doc/zenbook-scripts/examples/openrc/` (reference)

**Not included:** out-of-tree `hid-asus.ko` (build from `kernel/` manually or via
future DKMS). **Plasma 6 KCM** (`plasma/kcm/`) is optional and needs Ubuntu **24.04+**
(or Debian trixie/sid) with Qt6/KF6 dev packages — build with
`plasma/kcm/build.sh --system` separately.

## Dependencies

| Relation | Packages |
|----------|----------|
| Depends | `python3 (>= 3.8)`, `dmidecode` |
| Recommends | `python3-usb`, `systemd` \| `elogind`, `acpid` |

### Ubuntu 20.04 Focal (probe host)

- Default apt has **Python 3.8** — satisfies `Depends: python3 (>= 3.8)`.
- **`platform-session`** uses `from __future__ import annotations` (no PEP 604
  runtime requirement); no `match`/`case`. Should run on 3.8, but **session CLI is
  newer** — test on Focal before relying on it in production.
- **No Qt6/KF6 in Focal** → do not expect KCM builds; CLI + hooks only.
- Build the `.deb` on Focal or newer with `debhelper-compat (= 12)`.

### Ubuntu 24.04+ / Debian bookworm+

Same CLI package. Optional Plasma KCM: install build deps (`qt6-base-dev`,
`libkf6kcmutils-dev`, …) and run `plasma/kcm/build.sh --system` — not wired into
this `.deb` yet.

## Build `.deb` from git checkout

```bash
cd /path/to/zenbook_scripts

# debhelper expects debian/ at the source root
ln -snf packaging/debian debian

sudo apt install -y debhelper-compat devscripts
dpkg-buildpackage -us -uc -b

# artifacts in parent directory:
#   ../zenbook-scripts_0.0.3~pre1_all.deb
```

Install locally:

```bash
sudo dpkg -i ../zenbook-scripts_0.0.3~pre1_all.deb
sudo apt-get install -f   # if Recommends missing
```

## Why not `configure.py` in `debian/rules`?

`configure.py` supports `--prefix /usr` but **not `DESTDIR`**, and it runs `sudo`
for `/etc`, udev reload, and sudoers — unsuitable for non-interactive package builds.
`debian/install.sh` copies the same tree Portage installs (minus USE flags / kernel
module build).

## Manual setup after install

See upstream [`DEPLOY.md`](../../DEPLOY.md):

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now zenbook-kb-hotkeys.service   # if desired
platform-probe
cp /usr/share/zenbook-scripts/plasma/session.json.example \
   ~/.config/zenbook-scripts/session.json   # Plasma session policy
```

UX8406 oot module (optional):

```bash
make -C kernel build-current
sudo make -C kernel install
```

## From-source install (without `.deb`)

Still supported — unchanged from earlier docs:

```bash
sudo python3 configure.py --defaults --all-yes --prefix /usr
```

## Future work

- Optional `zenbook-scripts-plasma` binary on 24.04+ with documented Build-Depends
- DKMS or `linux-modules-*` helper for `hid-asus`
- PPA / official archive — **not claimed today**

PRs welcome; must go through review.
