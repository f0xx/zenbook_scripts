# Distribution packaging

Install paths and operator docs: [`DEPLOY.md`](../DEPLOY.md).
This tree holds **maintainer / overlay recipes** per distro.

There is **no public Gentoo overlay**, **no published `.deb`**, and **no Alpine repo package** yet.
Copy recipes into your own overlay or install from a release tarball / git checkout.

## Layout

| Path | Purpose |
|------|---------|
| [`gentoo/zenbook-scripts-0.0.2.ebuild`](gentoo/zenbook-scripts-0.0.2.ebuild) | **Announced** → tag **`v0.0.2`** (typing-inhibit + prior stack) |
| [`gentoo/zenbook-scripts-0.0.2_pre1.ebuild`](gentoo/zenbook-scripts-0.0.2_pre1.ebuild) | Pre-release → tag **`v0.0.2_pre1`** |
| [`gentoo/zenbook-scripts-0.0.1_p1.ebuild`](gentoo/zenbook-scripts-0.0.1_p1.ebuild) | Older → tag **`v0.0.1_hf1`** |
| [`gentoo/zenbook-scripts-9999.ebuild`](gentoo/zenbook-scripts-9999.ebuild) | Live git (`EGIT`) |
| [`gentoo/files/`](gentoo/files/) | Conditional UX8406 patches + README (no prebuilt `.ko`) |
| [`gentoo/Manifest`](gentoo/Manifest) | Distfile digests for `0.0.1_hf1` + `0.0.2_pre1` + `0.0.2` |
| [`gentoo/metadata.xml`](gentoo/metadata.xml) | USE flag / upstream metadata |
| [`debian/`](debian/) | **debhelper scaffold** — CLI-first `.deb` (not published) |
| [`alpine/APKBUILD`](alpine/APKBUILD) | Alpine abuild recipe (not published) |

### Release `v0.0.2`

Tag + draft GitHub release first; **Manifest digests from that tarball** (`ebuild … manifest`).

https://github.com/f0xx/zenbook_scripts/archive/refs/tags/v0.0.2.tar.gz

| Algo | Digest |
|------|--------|
| Size | `243457` bytes |
| SHA256 | `be5b80f3a145a6efb53fb9863d365569f897d38b7cf722af3c32288fcf9093d9` |
| SHA512 | `36ca9e5965814d7aa1ef8c6ce156849599c61515d07b17c93f840ca78197aeadbecda01af4db42241217802a6c1dbb4f617333da43047e8d7a1f7ea9be09a052` |
| BLAKE2B | `e495347571a71fd73c7be5bf5b5f0a2809d025d719c5204abbe36be4dc8f0c12940160136ee1179b414379761f9a73f1384127357b624493c312d6bf9b8abaef` |

Portage DIST name: `zenbook_scripts-0.0.2.tar.gz`.

```bash
# UX5400 example (ScreenPad + fans, no oot hid-asus):
USE="screenpad fan_control -kernel -zenbook_ux8406" \
  emerge -av =app-laptop/zenbook-scripts-0.0.2
```

### Pre-release `v0.0.2_pre1` (superseded by 0.0.2)

https://github.com/f0xx/zenbook_scripts/archive/refs/tags/v0.0.2_pre1.tar.gz

| Algo | Digest |
|------|--------|
| Size | `187068` bytes |
| SHA256 | `3cf2601c11e6af18bf7e245add0c750a5c7076086872dbf87e73bfd1fcc55c38` |
| SHA512 | `ea455a5250bd15d03fd9b046b884d134510d481610a1e978fe74adfff78f67567b0214e4ddaaec5f1f27abac69236a34be5864a90690c82612b761168b77ee47` |
| BLAKE2B | `8f2ef64bb33105b03b1d5609f94096f8b784e232f0e5acf7f2adaa6ffccc6a57b452f0e4cf175cd6690e67591b4376a40cded0c616143ef92a62434f2a8eca00` |

Portage DIST name: `zenbook_scripts-0.0.2_pre1.tar.gz`.

### Release `v0.0.1_hf1`

Upstream source:

https://github.com/f0xx/zenbook_scripts/archive/refs/tags/v0.0.1_hf1.tar.gz

Gentoo PV **`0.0.1_p1`** maps to tag **`v0.0.1_hf1`** (`_hf` is not a legal PMS suffix).

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
sudo mkdir -p "${PKG}/files"
sudo cp packaging/gentoo/zenbook-scripts-0.0.2.ebuild "${PKG}/"
sudo cp packaging/gentoo/zenbook-scripts-0.0.2_pre1.ebuild "${PKG}/"   # optional
sudo cp packaging/gentoo/zenbook-scripts-0.0.1_p1.ebuild "${PKG}/"
sudo cp packaging/gentoo/zenbook-scripts-9999.ebuild "${PKG}/"   # optional live
sudo cp packaging/gentoo/metadata.xml "${PKG}/"
sudo cp packaging/gentoo/Manifest "${PKG}/"
sudo cp -a packaging/gentoo/files/. "${PKG}/files/"
```

`${FILESDIR}/patches/` holds conditional UX8406 patch mirrors (see `files/README.md`).
The ebuild still builds via `port-ux8406.py` against local sources — it does **not**
install a prebuilt `.ko`.

**`USE=kernel` build deps:** `virtual/linux-sources` + `dev-build/make` (works with **`sys-kernel/gentoo-sources`**). It does **not** pull `virtual/dist-kernel` / `gentoo-kernel`.

The ebuild **builds `hid-asus` from sources** at emerge time (fail-closed preflight). It never ships a precompiled `.ko`. Unsupported KV / `CONFIG_MODVERSIONS=y` → emerge dies unless `ZENBOOK_KERNEL_FORCE=1`. Conditional patches live under [`gentoo/files/patches/`](gentoo/files/patches/) (see [`gentoo/files/README.md`](gentoo/files/README.md)).

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
sudo ebuild zenbook-scripts-0.0.2.ebuild manifest
# sudo ebuild zenbook-scripts-0.0.2_pre1.ebuild manifest
# sudo ebuild zenbook-scripts-0.0.1_p1.ebuild manifest
# sudo ebuild zenbook-scripts-9999.ebuild manifest   # live; often empty DIST
```

Or keep the shipped `Manifest` (hashes for `0.0.1_hf1` + `0.0.2_pre1` + `0.0.2` above).
First fetch may come from GitHub if Gentoo mirrors lack the file.

### 4. Optional: `eix-update`

```bash
command -v eix-update >/dev/null && sudo eix-update
```

### 5. Unmask (`~amd64` / live)

Path is **`package.accept_keywords`** (plural). Release ebuild is `KEYWORDS="~amd64"`; live `9999` needs `**`:

```bash
# Prefer announced releases (0.0.2):
# /etc/portage/package.accept_keywords/zenbook-scripts
echo 'app-laptop/zenbook-scripts ~amd64' | sudo tee /etc/portage/package.accept_keywords/zenbook-scripts

# Live git only (pulls 9999 ahead of any release — see upgrade note below):
# echo 'app-laptop/zenbook-scripts **' | sudo tee /etc/portage/package.accept_keywords/zenbook-scripts
```

**Do not leave `**` in place if you want `emerge -u zenbook-scripts` to track
releases.** With `**`, Portage prefers `9999` over `0.0.2` (9999 is “newer”).

### Upgrade note: file collisions (9999 ↔ release)

Both live and versioned ebuilds are **`SLOT="0"`** and install the same paths under
`/usr/bin` and `/usr/share/zenbook-scripts`. Switching atoms is a **replace**, not a
side-by-side install.

If you see `Detected file collision(s):` while emerging `0.0.2` and the search finds
`app-laptop/zenbook-scripts-9999` (or the reverse), that is Portage listing paths
owned by the package about to be replaced. With default `protect-owned`, emerge
**continues** after the scan — it is noisy, not a hard failure.

Clean switch to the announced release:

```bash
# 1) stop preferring live
echo 'app-laptop/zenbook-scripts ~amd64' | sudo tee /etc/portage/package.accept_keywords/zenbook-scripts

# 2) optional: hard-mask live so world upgrades never pull it back
echo '=app-laptop/zenbook-scripts-9999' | sudo tee /etc/portage/package.mask/zenbook-scripts-live

# 3) pin the release atom (replace 9999 / older PV)
sudo emerge -av =app-laptop/zenbook-scripts-0.0.2
```

If collisions are from **unowned** files (a prior `configure.py --prefix /usr` over
the same tree), either remove those paths or, one-shot:

```bash
sudo FEATURES="-collision-protect -protect-owned" emerge -av =app-laptop/zenbook-scripts-0.0.2
```

Do **not** put that FEATURES tweak in `make.conf`. After Portage owns the files,
normal emerges are quiet.

### 6. Emerge (or manual ebuild phases)

```bash
# UX8406 docked (default USE: hotkeys kernel zenbook_ux8406)
emerge -av =app-laptop/zenbook-scripts-0.0.2

# UX5400 ScreenPad + fans, no oot hid-asus:
# USE="screenpad fan_control -kernel -zenbook_ux8406" emerge -av =app-laptop/zenbook-scripts-0.0.2

# Older tags still available:
# emerge -av =app-laptop/zenbook-scripts-0.0.2_pre1
# emerge -av =app-laptop/zenbook-scripts-0.0.1_p1

# Live git:
# emerge -av =app-laptop/zenbook-scripts-9999
```

Manual phase walk (same as emerge internals):

```bash
EBUILD=/var/db/repos/foxx/app-laptop/zenbook-scripts/zenbook-scripts-0.0.2.ebuild
sudo ebuild "${EBUILD}" clean unpack prepare configure compile
sudo ebuild "${EBUILD}" install
sudo ebuild "${EBUILD}" qmerge   # or: preinst merge postinst
```

### 7. Enable services / module (if not already running)

```bash
# UX8406 oot hid-asus boot sideload
sudo sed -i 's/^fn_row_policy=.*/fn_row_policy=7/' /etc/conf.d/zenbook-kb-hid-asus
sudo rc-update add zenbook-kb-hid-asus default
sudo rc-service zenbook-kb-hid-asus start

# Hotkeys listener
sudo rc-update add zenbook-kb-hotkeys default
sudo rc-service zenbook-kb-hotkeys start

# Optional typing-inhibit live filter
# sudo rc-update add zenbook-platform-touchpad default

# Optional lid watcher
# sudo rc-update add zenbook-kb-lid default
```

From a git tree without emerge (module only):

```bash
make -C kernel build && sudo make -C kernel install
# → /usr/lib/modules/zenbook-hid-asus/$(uname -r)/hid-asus.ko
```

See [`kernel/README.md`](../kernel/README.md). Re-emerge after **each kernel upgrade**.

### Installed paths (Gentoo ebuild)

| Component | Path |
|-----------|------|
| CLIs | `/usr/bin/` (`kb-brightness`, `configure.py`, …) |
| Helpers | `/usr/libexec/` (udev, ACPI sleep, hid-asus switch/boot) |
| Share tree | `/usr/share/zenbook-scripts/` |
| oot `hid-asus.ko` | `/usr/lib/modules/zenbook-hid-asus/<kver>/` |

`configure.py` defaults to **`/usr`** (same as the ebuild). Override with
`--prefix /usr/local` or `ZENBOOK_PREFIX=/usr/local`. After migrating, use
`--cleanup-usr-local` to drop leftover `/usr/local` binaries/share. The ebuild
rewrites packaged unit/helper scripts to `/usr` and does **not** run
`configure.py` in `pkg_postinst`.

## USE flags

| Flag | Default | Meaning |
|------|---------|---------|
| `hotkeys` | on | udev + OpenRC hotkeys / lid / sleep hooks |
| `fan_control` | on | `platform-fan*` + OpenRC + `/etc/zenbook-scripts` example |
| `screenpad` | off | ScreenPad CLI + udev + services (UX5400) |
| `kernel` | on | Build oot `hid-asus` from sources + OpenRC sideload (fail-closed; `ZENBOOK_KERNEL_FORCE=1` for risky KV) |
| `qt6` | off | `configure_gui.py` + `platform-tray` (PySide6) |
| `plasma` | off | `platform-session`, sleep hook, `session.json.example`, Plasma docs (KCM via `plasma/kcm/build.sh`) |
| `zenbook_ux8406` | on | Install `conf.d/UX8406*` profiles |

**Always** (RDEPEND): `sys-apps/dmidecode` (UX8406 `fn_row_policy=7` auto-set). Metrics use Python **stdlib sqlite3** (no extra dep).

## Debian / Ubuntu

**Draft `.deb` scaffold** (not published): [`debian/`](debian/) — symlink to repo root and
`dpkg-buildpackage -us -uc -b`. CLI-first on **Focal 20.04+** (`python3 >= 3.8`); Plasma KCM
optional on **24.04+** via `plasma/kcm/build.sh`. See [`debian/README.md`](debian/README.md).

```bash
cd /path/to/zenbook_scripts
ln -snf packaging/debian debian
sudo apt install -y debhelper-compat devscripts
dpkg-buildpackage -us -uc -b
```

## Alpine

**Draft APKBUILD** (not published): [`alpine/APKBUILD`](alpine/APKBUILD). Reuses
`debian/install.sh` in `package()`. See [`alpine/README.md`](alpine/README.md).

```sh
cd packaging/alpine
abuild -r -P "$HOME/packages"
```

## Planned

- Official public Gentoo overlay
- Published `.deb` / PPA and Alpine aports submission
- DKMS for `hid-asus`
- Arch `PKGBUILD`, Nix flake

## Upstream

https://github.com/f0xx/zenbook_scripts
