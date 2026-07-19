# Debian / Ubuntu (from source)

There is **no `.deb`**, PPA, or DKMS package in this repository yet.
Use a release tarball or git checkout, then install userspace with `configure.py`
and (for UX8406) build the out-of-tree `hid-asus` module yourself.

PRs that add proper packaging are welcome; they must go through review.

## Dependencies

```bash
sudo apt update
sudo apt install -y python3 python3-usb python3-pip \
  dmidecode \
  build-essential flex bison libelf-dev libssl-dev \
  linux-headers-$(uname -r)
# optional GUI:
# sudo apt install -y python3-pyside6.qtwidgets
```

## Fetch `v0.0.2_pre1` (pre-release / testing)

```bash
cd /tmp
curl -fsSL -o zenbook_scripts-0.0.2_pre1.tar.gz \
  https://github.com/f0xx/zenbook_scripts/archive/refs/tags/v0.0.2_pre1.tar.gz

echo '3cf2601c11e6af18bf7e245add0c750a5c7076086872dbf87e73bfd1fcc55c38  zenbook_scripts-0.0.2_pre1.tar.gz' | sha256sum -c
echo 'ea455a5250bd15d03fd9b046b884d134510d481610a1e978fe74adfff78f67567b0214e4ddaaec5f1f27abac69236a34be5864a90690c82612b761168b77ee47  zenbook_scripts-0.0.2_pre1.tar.gz' | sha512sum -c

tar -xzf zenbook_scripts-0.0.2_pre1.tar.gz
cd zenbook_scripts-0.0.2_pre1
```

## Fetch `v0.0.1_hf1`

```bash
cd /tmp
curl -fsSL -o zenbook_scripts-0.0.1_hf1.tar.gz \
  https://github.com/f0xx/zenbook_scripts/archive/refs/tags/v0.0.1_hf1.tar.gz

# verify (pick one)
echo 'b4f4c5d6cdc79c1985d779c55ddfad64159199cc4c051a13365a33b88242a0e5  zenbook_scripts-0.0.1_hf1.tar.gz' | sha256sum -c
echo 'd53dc34926e758015eee4dec7ecc5c4272bec706fc2142ac1cf907a8ced2fac0ed28383168bc035f69062ba61ffa4315f5a8f007d792be2fb347897533945acf  zenbook_scripts-0.0.1_hf1.tar.gz' | sha512sum -c

tar -xzf zenbook_scripts-0.0.1_hf1.tar.gz
cd zenbook_scripts-0.0.1_hf1
```

## Userspace install

```bash
sudo python3 configure.py --defaults --all-yes --prefix /usr
# or interactive: sudo python3 configure.py
# fan-control: add --include-fan-control
# UX8406 oot module: add --with-kernel (builds from sources; see kernel/README.md)
```

That installs CLIs under `/usr/bin` (or `$prefix/bin`), the share tree under
`/usr/share/zenbook-scripts/`, udev rules, and systemd/OpenRC units when detected.

### Enable systemd units (if installed)

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now zenbook-kb-hotkeys.service   # if present
# ScreenPad (UX5400):
# sudo systemctl enable --now zenbook-screenpad.service
# sudo systemctl enable --now zenbook-screenpad-sync.service
```

Sleep hook (if not already placed by install):

```bash
# contrib/systemd/zenbook-kb-brightness-sleep → /usr/lib/systemd/system-sleep/
```

## UX8406 kernel module (optional but recommended when docked)

```bash
make -C kernel build-current
sudo make -C kernel install
# loads path: /usr/lib/modules/zenbook-hid-asus/$(uname -r)/hid-asus.ko

# one-shot test load (stop hotkeys first — pyusb on if4 bricks the dock)
sudo systemctl stop zenbook-kb-hotkeys.service 2>/dev/null || true
sudo ./kernel/scripts/switch-hid-asus.sh sideload   # or unload/insmod/rebind; see kernel/README.md
```

Set `fn_row_policy=7` when using the sideloaded module (modprobe options or
`insmod … fn_row_policy=7`). Details: [`kernel/README.md`](../../kernel/README.md),
[`DEPLOY.md`](../../DEPLOY.md).

Rebuild the module after every kernel / headers upgrade.

## Without root packaging

```bash
PYTHONPATH=. python3 -m zenbook_kb.sniff 15
./bin/kb-brightness status
```

## Want a real `.deb`?

Open a PR that adds `debian/` (debhelper + preferably DKMS for `hid-asus`).
Until then, treat this README as the supported Debian/Ubuntu path.
