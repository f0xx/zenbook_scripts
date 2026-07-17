# Distribution packaging

Install paths and operator docs: [`DEPLOY.md`](../DEPLOY.md).
This tree holds **maintainer / overlay recipes** per distro.

There is **no public Gentoo overlay** and **no `.deb` package** yet.
Copy recipes into your own overlay or install from a release tarball / git checkout.

## Layout

| Path | Purpose |
|------|---------|
| [`gentoo/zenbook-scripts-0.0.1_p1.ebuild`](gentoo/zenbook-scripts-0.0.1_p1.ebuild) | Release package → upstream tag **`v0.0.1_hf1`** |
| [`gentoo/zenbook-scripts-9999.ebuild`](gentoo/zenbook-scripts-9999.ebuild) | Live git (`EGIT`) |
| [`gentoo/Manifest`](gentoo/Manifest) | Distfile digests for `0.0.1_p1` |
| [`gentoo/metadata.xml`](gentoo/metadata.xml) | USE flag / upstream metadata |
| [`debian/README.md`](debian/README.md) | Debian/Ubuntu from-source install (no `.deb` yet) |

Upstream source for the release ebuild:

https://github.com/f0xx/zenbook_scripts/archive/refs/tags/v0.0.1_hf1.tar.gz

Gentoo PV is **`0.0.1_p1`** because `_hf1` is not a legal PMS version suffix. `MY_PV` inside the ebuild still fetches **`v0.0.1_hf1`**.

### Distfile checksums (`v0.0.1_hf1` tarball)

| Algo | Digest |
|------|--------|
| Size | `120582` bytes |
| SHA256 | `b4f4c5d6cdc79c1985d779c55ddfad64159199cc4c051a13365a33b88242a0e5` |
| SHA512 | `d53dc34926e758015eee4dec7ecc5c4272bec706fc2142ac1cf907a8ced2fac0ed28383168bc035f69062ba61ffa4315f5a8f007d792be2fb347897533945acf` |
| BLAKE2B | `5490a2ad41665568c864f46b5a129d852123ed77a6149f754cb57ce4442ceaec0af7d01453ccf2c06934a03f255f1ed44232c138e7e82b35696d17a8929bd05d` |

Portage `Manifest` DIST name (after `->` rename): `zenbook_scripts-0.0.1_hf1.tar.gz`.

## Gentoo (local overlay)

Example overlay name: **`foxx`** at `/var/db/repos/foxx` (yours may differ).

### 1. Overlay

```bash
sudo mkdir -p /var/db/repos/foxx/{metadata,profiles,app-laptop/zenbook-scripts}
echo foxx | sudo tee /var/db/repos/foxx/profiles/repo_name
printf '%s\n' 'masters = gentoo' 'thin-manifests = true' \
  | sudo tee /var/db/repos/foxx/metadata/layout.conf

cat <<'EOF' | sudo tee /etc/portage/repos.conf/foxx.conf
[foxx]
location = /var/db/repos/foxx
masters = gentoo
auto-sync = false
EOF
```

### 2. Install ebuild (+ optional `files/`)

From a git checkout of this repo (or copy from the release tarball’s `packaging/gentoo/`):

```bash
PKG=/var/db/repos/foxx/app-laptop/zenbook-scripts
sudo mkdir -p "${PKG}"   # add "${PKG}/files" only if you ship patches
sudo cp packaging/gentoo/zenbook-scripts-0.0.1_p1.ebuild "${PKG}/"
sudo cp packaging/gentoo/zenbook-scripts-9999.ebuild "${PKG}/"   # optional live
sudo cp packaging/gentoo/metadata.xml "${PKG}/"
sudo cp packaging/gentoo/Manifest "${PKG}/"
```

Patches (if ever needed) go in `app-laptop/zenbook-scripts/files/` and are referenced via `${FILESDIR}`. Stock ebuilds ship **no** patches.

**`USE=kernel` build deps:** `virtual/linux-sources` + `dev-build/make` (works with **`sys-kernel/gentoo-sources`**). It does **not** pull `virtual/dist-kernel` / `gentoo-kernel`.

Point `/usr/src/linux` at the tree that matches your **running** kernel when you want a loadable module immediately. Dist-kernel users have `/lib/modules/$(uname -r)/build`; with gentoo-sources that symlink appears only after `make modules_install`. The ebuild falls back to `/usr/src/linux` when `…/build` is missing.

```bash
uname -r
eselect kernel list
sudo eselect kernel set <N>    # match uname -r (e.g. linux-7.0.12-gentoo-r1)
ls -l /usr/src/linux /lib/modules/"$(uname -r)"/build
```

### 3. Manifest

After copying or editing ebuilds:

```bash
cd /var/db/repos/foxx/app-laptop/zenbook-scripts
sudo ebuild zenbook-scripts-0.0.1_p1.ebuild manifest
# sudo ebuild zenbook-scripts-9999.ebuild manifest   # live; often empty DIST
```

Or keep the shipped `Manifest` for `0.0.1_p1` (hashes above). First fetch may come from GitHub if Gentoo mirrors lack the file.

### 4. Optional: `eix-update`

```bash
command -v eix-update >/dev/null && sudo eix-update
```

### 5. Unmask (`~amd64` / live)

Path is **`package.accept_keywords`** (plural). Release ebuild is `KEYWORDS="~amd64"`; live `9999` needs `**`:

```bash
# /etc/portage/package.accept_keywords/zenbook-scripts
echo 'app-laptop/zenbook-scripts ~amd64' | sudo tee /etc/portage/package.accept_keywords/zenbook-scripts
# for 9999:
# echo 'app-laptop/zenbook-scripts **' | sudo tee -a /etc/portage/package.accept_keywords/zenbook-scripts
```

### 6. Emerge (or manual ebuild phases)

```bash
# UX8406 docked (default USE: hotkeys kernel zenbook_ux8406)
emerge -av =app-laptop/zenbook-scripts-0.0.1_p1

# UX5400 ScreenPad, no oot hid-asus:
# USE="screenpad -kernel -zenbook_ux8406" emerge -av =app-laptop/zenbook-scripts-0.0.1_p1

# Live git:
# emerge -av =app-laptop/zenbook-scripts-9999
```

Manual phase walk (same as emerge internals):

```bash
EBUILD=/var/db/repos/foxx/app-laptop/zenbook-scripts/zenbook-scripts-0.0.1_p1.ebuild
sudo ebuild "${EBUILD}" clean unpack prepare configure compile
sudo ebuild "${EBUILD}" install
sudo ebuild "${EBUILD}" qmerge   # or: preinst merge postinst
```

### 7. Enable services / module (if not already running)

```bash
# UX8406 oot hid-asus boot sideload
sudo sed -i 's/^fn_row_policy=.*/fn_row_policy=7/' /etc/conf.d/zenbook-kb-hid-asus
sudo rc-update add zenbook-kb-hid-asus boot
sudo rc-service zenbook-kb-hid-asus start

# Hotkeys listener
sudo rc-update add zenbook-kb-hotkeys default
sudo rc-service zenbook-kb-hotkeys start

# Optional lid watcher
# sudo rc-update add zenbook-kb-lid default
```

From a git tree without emerge (module only):

```bash
make -C kernel build && sudo make -C kernel install
# → /usr/lib/modules/zenbook-hid-asus/$(uname -r)/hid-asus.ko
```

See [`kernel/README.md`](../kernel/README.md). Re-emerge after **each kernel upgrade**.

## USE flags

| Flag | Default | Meaning |
|------|---------|---------|
| `hotkeys` | on | udev + OpenRC hotkeys / lid / sleep hooks |
| `screenpad` | off | ScreenPad CLI + udev + services (UX5400) |
| `kernel` | on | Build/install oot `hid-asus.ko` + boot sideload |
| `qt6` | off | `configure_gui.py` (PySide6) |
| `zenbook_ux8406` | on | Install `conf.d/UX8406*` profiles |

## Debian / Ubuntu

No `.deb` or PPA yet — see [`debian/README.md`](debian/README.md) for a from-source path (`configure.py` + optional kernel module).

## Planned

- Official public Gentoo overlay
- `debian/` debhelper + DKMS
- Arch `PKGBUILD`, Nix flake

## Upstream

https://github.com/f0xx/zenbook_scripts
