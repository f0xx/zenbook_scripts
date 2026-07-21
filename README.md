# zenbook_scripts

A set of useful ASUS Zenbook scripts and patches.

**Status:** community project — not an official ASUS, Gentoo, Debian, or distro
package. We do **not** act as distro maintainers or QA. Use at your own risk.

## Models

| Model | Docs | Branch |
|-------|------|--------|
| [ASUS Zenbook UX8406 (MA)](README.ux8406.md) | [`README.ux8406.md`](README.ux8406.md) | [`zenbook_ux8406ma`](https://github.com/f0xx/zenbook_scripts/tree/zenbook_ux8406ma) |
| [ASUS Zenbook UX5400 (E)](README.ux5400.md) | [`README.ux5400.md`](README.ux5400.md) | [`zenbook_ux5400e`](https://github.com/f0xx/zenbook_scripts/tree/zenbook_ux5400e) |
| ASUS Zenbook UX582 (LR) | — | [`zenbook_ux582lr`](https://github.com/f0xx/zenbook_scripts/tree/zenbook_ux582lr) |

Model-specific READMEs live on `main` after merge; feature work continues on the model branches.

## Install

| Distro | How |
|--------|-----|
| **Gentoo** | Local overlay + ebuild — see [packaging/README.md](packaging/README.md) (**`0.0.2`** → tag [`v0.0.2`](https://github.com/f0xx/zenbook_scripts/releases/tag/v0.0.2); older **`0.0.1_p1`** → [`v0.0.1_hf1`](https://github.com/f0xx/zenbook_scripts/releases/tag/v0.0.1_hf1)) |
| **Debian / Ubuntu** | No `.deb` yet — from-source steps in [packaging/debian/README.md](packaging/debian/README.md) |
| **Any (git / tarball)** | `sudo python3 configure.py` — [DEPLOY.md](DEPLOY.md); UX8406 module: [kernel/README.md](kernel/README.md) |

### Release tarball checksums (`v0.0.2`)

Typing-inhibit / soft-accel / pidfiles + fan-control / probe / tray stack.
Draft GitHub release until publish step; Gentoo Manifest already matches this archive
([CHANGELOG.md](CHANGELOG.md)).

Source: https://github.com/f0xx/zenbook_scripts/archive/refs/tags/v0.0.2.tar.gz

| Algo | Digest |
|------|--------|
| SHA256 | `be5b80f3a145a6efb53fb9863d365569f897d38b7cf722af3c32288fcf9093d9` |
| SHA512 | `36ca9e5965814d7aa1ef8c6ce156849599c61515d07b17c93f840ca78197aeadbecda01af4db42241217802a6c1dbb4f617333da43047e8d7a1f7ea9be09a052` |
| BLAKE2B | `e495347571a71fd73c7be5bf5b5f0a2809d025d719c5204abbe36be4dc8f0c12940160136ee1179b414379761f9a73f1384127357b624493c312d6bf9b8abaef` |

### Release tarball checksums (`v0.0.1_hf1`)

Source: https://github.com/f0xx/zenbook_scripts/archive/refs/tags/v0.0.1_hf1.tar.gz

| Algo | Digest |
|------|--------|
| SHA256 | `b4f4c5d6cdc79c1985d779c55ddfad64159199cc4c051a13365a33b88242a0e5` |
| SHA512 | `d53dc34926e758015eee4dec7ecc5c4272bec706fc2142ac1cf907a8ced2fac0ed28383168bc035f69062ba61ffa4315f5a8f007d792be2fb347897533945acf` |
| BLAKE2B | `5490a2ad41665568c864f46b5a129d852123ed77a6149f754cb57ce4442ceaec0af7d01453ccf2c06934a03f255f1ed44232c138e7e82b35696d17a8929bd05d` |

### Gentoo (short path)

Full steps (overlay, Manifest, unmask, emerge, `eselect kernel`, services): **[packaging/README.md](packaging/README.md)**.

Ebuild installs under **`/usr`**. `configure.py` defaults to **`/usr`** as well
(`--prefix /usr/local` or `ZENBOOK_PREFIX=/usr/local` for the old layout).

```bash
# After copying packaging/gentoo/* into your overlay's
# app-laptop/zenbook-scripts/ and unmasking ~amd64:
# eselect kernel set <N>   # match uname -r for USE=kernel
emerge -av =app-laptop/zenbook-scripts-0.0.2
# UX5400: USE="screenpad fan_control -kernel -zenbook_ux8406" emerge -av =app-laptop/zenbook-scripts-0.0.2
sudo rc-update add zenbook-kb-hid-asus default   # UX8406 USE=kernel
sudo rc-update add zenbook-kb-hotkeys default
sudo rc-update add zenbook-platform-fan-control default   # USE=fan_control
# optional: rc-update add zenbook-platform-touchpad default
# fn_row_policy=7 in /etc/conf.d/zenbook-kb-hid-asus (auto on UX8406 install)
```

Live git: `zenbook-scripts-9999.ebuild` (needs `**` keywords).

Platform thermal tools (all models with `asus-nb-wmi`):

```bash
platform-probe                 # what this machine supports
platform-fan status|modes|auto|full
platform-fan-control status|once|run
platform-tray                  # USE=qt6 — metrics graph + profile/fan menu
```

## Contributing

- **Code / docs / packaging:** open a **pull request** against `main` (or the
  relevant model branch). Every change should go through review — please do not
  expect drive-by commits on protected branches.
- **Bugs:** open a GitHub **[issue](https://github.com/f0xx/zenbook_scripts/issues/new/choose)**
  using the bug template (hardware model, kernel, repro steps).
- We are **not** distro maintainers; packaging recipes are best-effort starting
  points for your own overlay or local install.

## Quick links

- [DEPLOY.md](DEPLOY.md) — when to rebuild / reinstall / reload `hid-asus`
- [ROADMAP.md](ROADMAP.md) — where we are / next
- [CHANGELOG.md](CHANGELOG.md) — release notes (keep updated with tags)
- [PLANNED.md](PLANNED.md) — feature cheatsheets (`platform-fan*`, probe, tray)
- [README.fn_row_policy.md](README.fn_row_policy.md) — UX8406 `fn_row_policy` bitmask / chords
- [kernel/README.md](kernel/README.md) — out-of-tree `hid-asus` build & install
- [packaging/README.md](packaging/README.md) — Gentoo ebuild / overlay notes
- [packaging/debian/README.md](packaging/debian/README.md) — Debian/Ubuntu from source
