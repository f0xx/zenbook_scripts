# Alpine packaging (zenbook-scripts)

**Not published** in official Alpine repos. This `APKBUILD` is a maintainer scaffold
for local builds (e.g. cast04 playground on Alpine 3.24).

CLI-first package: `python3`, `py3-usb`, `dmidecode`. Plasma 6 KCM is **not**
built here; see [`plasma/kcm/build.sh`](../../plasma/kcm/build.sh) on a host with
KF6/Qt6.

Install logic reuses [`packaging/debian/install.sh`](../debian/install.sh).

## Prerequisites (cast04 / abuild)

```sh
doas apk add alpine-sdk abuild
# builder must be in group abuild (logout/login or: sudo -g abuild -u "$USER")
abuild-keygen -a -n   # once per builder user
```

Helper that packs the current checkout and builds:

```sh
# from a synced tree on cast04
sudo -g abuild -u ai -- sh packaging/alpine/cast04-abuild.sh
# → ~/packages/packaging/x86_64/zenbook-scripts-0.0.3_pre1-r0.apk
```

Smoke-tested on Alpine 3.24 (`cast04`): APK installs; `platform-session --help` works.

## Build from git checkout (recommended before tag exists)

```sh
cd /path/to/zenbook_scripts/packaging/alpine
cp -a APKBUILD zenbook-scripts-0.0.3_pre1.apkbuild   # optional working copy

# abuild expects sources under ~/aports or a dedicated aports tree; simplest:
export SRCDEST="$HOME/aports/distfiles"
mkdir -p "$SRCDEST"

# Pack current tree (avoids fetching main branch tarball during RC work)
cd /path/to/zenbook_scripts
git archive --format=tar.gz --prefix=zenbook_scripts-main/ -o \
  "$SRCDEST/main.tar.gz" HEAD

cd packaging/alpine
abuild -r -P "$HOME/packages"
```

After `v0.0.3_pre1` is tagged upstream, you can switch `source=` in `APKBUILD` to
the release tarball and run `abuild checksum` once.

## Build from GitHub tarball (after tag)

```sh
cd packaging/alpine
abuild checksum    # refresh sha512sums when source URL is stable
abuild -r -P "$HOME/packages"
```

## Install locally built APK

```sh
doas apk add --allow-untrusted "$HOME/packages/main/x86_64/zenbook-scripts-0.0.3_pre1-r0.apk"
```

## Post-install

Same as upstream [`DEPLOY.md`](../../DEPLOY.md): enable udev/systemd units as needed,
run `platform-probe`, configure `~/.config/zenbook-scripts/session.json` from
`session.json.example` for Plasma session policy.

## Python 3.x

Alpine 3.24 ships Python 3.12+. `platform-session` uses `from __future__ import
annotations` and is compatible with 3.8+ syntax-wise; test on your target release.
