# UX8406 out-of-tree hid-asus

Build a sideload `hid-asus.ko` with Zenbook Duo (UX8406) keyboard support on top
of your installed Gentoo kernel sources. No DKMS — only the kernel `Makefile`
external-module build (`make -C $KDIR M=$PWD modules`).

Based on [hacker1024/linux `ux8406-hid`](https://github.com/hacker1024/linux/compare/v6.14.4...ux8406-hid),
ported to 7.0.12-gentoo-r1 and 7.1.3-gentoo.

## Prerequisites

- Kernel headers for the running (or target) kernel, e.g.:
  - `/usr/src/linux-7.0.12-gentoo-r1` (symlinked from `/lib/modules/$(uname -r)/build`)
  - `/usr/src/linux-7.1.3-gentoo`
- `CONFIG_HID_ASUS=m` (module, not built-in) so you can `rmmod` / `insmod`
- `CONFIG_ASUS_WMI` enabled (for `asus::kbd_backlight` listener integration)

## Build

From this directory:

```bash
# Running kernel (7.0.12-gentoo-r1)
make build

# Explicit tree
make build KDIR=/usr/src/linux-7.0.12-gentoo-r1
make build KDIR=/usr/src/linux-7.1.3-gentoo
```

The patched module is built at:

`build/linux-<version>/hid-asus.ko`

(kbuild runs under `/tmp/zenbook-hid-asus-linux-<version>/` because kernel
`M=` paths cannot contain spaces.)

## Load / unload (testing)

Stop userspace that holds the keyboard (`zenbook-kb-hotkeys`, etc.) first.

```bash
KVER=linux-7.0.12-gentoo-r1   # match your running kernel tree name
MOD="build/${KVER}/hid-asus.ko"

sudo rmmod hid_asus
sudo insmod "$MOD"

# Re-bind the detachable keyboard (USB 0b05:1b2c interface 4)
echo 0b05 1b2c | sudo tee /sys/bus/usb/drivers/usbhid/new_id
# Bluetooth: reconnect keyboard, or:
# echo 0b05 1b2d | sudo tee /sys/bus/hid/drivers/hid-generic/new_id
```

Check binding:

```bash
grep -l 1B2C /sys/bus/usb/devices/*/idProduct 2>/dev/null | head
cat /sys/bus/usb/devices/*/*/driver/module/name 2>/dev/null | sort -u
dmesg | tail -30
```

Expect `hid-asus` messages such as “Fixing up ZENBOOK DUO keyb report descriptor”
and “Injecting virtual Zenbook Duo keyboard usage page” on USB interface 4.

Restore the stock module (safe — unbinds devices first):

```bash
sudo ./scripts/unload-hid-asus.sh
sudo modprobe hid_asus
```

**Do not** `rmmod hid_asus` while keyboard interfaces are still bound to `asus` — older
builds can WARN in `asus_remove` (`__flush_work` / uninitialized fn-lock work).
Rebuild after pulling the latest port script fix, then use `unload-hid-asus.sh`.

Use the rebind helper after `insmod` (recommended):

```bash
sudo ./scripts/rebind-hid-asus.sh
```

## Troubleshooting (UX8406MA)

**`--show-profile` says hid-asus True but Fn keys behave wrong**

Your dmesg should include:

- `Fixing up ZENBOOK DUO keyb report descriptor`
- `Injecting virtual Zenbook Duo keyboard usage page`

If those lines are **missing**, USB **interface 4** (`…004B`, 90-byte report descriptor,
ep `0x85`) is not bound to `hid-asus`. The listener on **interface 3** (`event6`, consumer
keys) only sees keys like `KEY_VOLUMEUP` — not the real Fn+ vendor map.

**Fn-lock feels inverted / Alt+F breaks**

The sideload module was applying `QUIRK_HID_FN_LOCK` to **all** USB interfaces including
the main keyboard (if0). Rebuild with the latest port script (interface-scoped quirks) and
rebind.

**Check interface 4 exists**

```bash
ls /sys/bus/hid/devices/*1B2C.004B
lsusb -d 0b05:1b2c -v -i 4 | grep -E 'Report Descriptor|bEndpointAddress'
```

If `004B` is missing after rebind, replug the keyboard dock or run `rebind-hid-asus.sh`.

**Touchpad on the detachable keyboard stops working after `insmod`**

`insmod hid-asus.ko` matches the whole USB device `0b05:1b2c`, including the
touchpad HID node (`…004C`, USB interface 5, ~500-byte report descriptor). `hid-asus`
does not drive that interface as a touchpad.

`rebind-hid-asus.sh` now:

1. Restores touchpad (USB if5 / large rdesc) to `hid-multitouch`
2. Binds **keyboard if0–if3 and vendor if4** to `asus` (same stable layout as early sideload)
3. Does **not** move keyboard interfaces back to `hid-generic` (that regressed docked typing)

After rebind, check:

```bash
for n in /sys/bus/hid/devices/*1B2C*; do
  echo "$(basename "$n") → $(basename $(readlink -f "$n/driver"))"
done
```

Expected:

- if0–if4 nodes → `asus`
- touchpad (if5, `…0006` / `…004C`) → `hid-multitouch`
- typing works on the dock; Fn+F4 via hid-asus

**Do not start `zenbook-kb-hotkeys` with `usb_poll=auto` on stock/sideload until if4 is on asus** —
the service claims USB if4 via pyusb and breaks the dock. Use `usb_poll=false` in
`~/.config/zenbook-scripts/zenbook-hotkeys.conf` or wait until `hid-asus` owns if4 (then
`usb_poll=auto` disables pyusb).

**Emergency restore to stock**

```bash
sudo rc-service zenbook-kb-hotkeys stop
sudo ./kernel/scripts/unload-hid-asus.sh
sudo modprobe hid_asus
# if USB if4 stuck: sudo sh -c 'echo 3-6:1.4 > /sys/bus/usb/drivers/usbhid/bind'
```

Touchpad `…004C` should **not** be on `asus`. Main laptop ELAN touchpads (I2C,
`04F3:425B` / `425A`) are unrelated — if those die too, look for a broader USB reset
or replug the keyboard dock.

**Stock `hid_asus` was not loaded before**

That is fine — `CONFIG_HID_ASUS=m` loads on demand. The patched module replaces it after
`insmod`; use `modprobe hid_asus` to restore the in-tree one.

## What the patch adds

- USB `0b05:1b2c` and BT `0b05:1b2d` device IDs (UX8406MA detachable keyboard)
- Report-descriptor fixups for vendor hotkey byte stream
- Fake keyboard collection on USB interface 4 so Fn+ keys map through `hid-asus`
- Fn-lock via vendor usage `0x4e`, platform-profile cycle via `0x9d`
- HID path for `asus::kbd_backlight` on UX8406 DMI boards
- **Module parameters** (oot `hid-asus` after sideload; set in `/etc/conf.d/zenbook-kb-hid-asus` at boot, or sysfs until reload):
  - `fn_lock_default` — `-1` = DMI default (UX8406 → Mode B), `0` = Mode B (Fn layer), `1` = Mode A (plain F-keys)
  - `fn_lock_allow_toggle` — `0` = Fn+Esc ignored (pinned), `1` = allow Fn+Esc / vendor `0x4e` toggle

Full table and examples: [`DEPLOY.md`](../DEPLOY.md) §F (`/etc/conf.d/zenbook-kb-hid-asus`).

```bash
# Pin Mode B, allow Fn+Esc toggle:
# /etc/conf.d/zenbook-kb-hid-asus → fn_lock_default=0 fn_lock_allow_toggle=1

# Pin Mode B, no toggle (default UX8406 docked setup):
echo 'options hid_asus fn_lock_default=0 fn_lock_allow_toggle=0' | \
  sudo tee /etc/modprobe.d/zenbook-hid-asus.conf
```

## Patches

Unified diffs (for reference / manual apply) live under `patches/`. The build
uses `scripts/port-ux8406.py` to apply the same logical changes onto a copy of
`drivers/hid/hid-asus.c` from your kernel tree.

Regenerate patch files:

```bash
make patches
```

## UX8406CA (2025 model)

USB/BT IDs differ (`0x1bf2` / `0x1bf3`). Edit `hid-asus-oot/ux8406-ids.h` or
add another row in the port script’s device table.
