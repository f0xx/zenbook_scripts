# When to redeploy (install / restart)

Quick rule: **only redeploy userspace when installed files under `/usr/`
(default `configure.py` / Gentoo ebuild) or a custom `--prefix` must change.**
Kernel module tests and config-only edits often need **no** reinstall.

## Decision table

| You changed or are doing… | Re-run `configure.py` install? | Restart `zenbook-kb-hotkeys`? | Rebuild kernel module? | Reload `hid-asus.ko`? |
|---------------------------|-------------------------------|-------------------------------|------------------------|------------------------|
| **Try patched `hid-asus.ko`** (`insmod` test) | No | **Stop** before `insmod`; start after if you want the listener | Only if `kernel/` sources changed | **Yes** (`rmmod` + `insmod` + rebind) |
| **Edited `conf.d/*.conf`** in the git repo | **Yes** (copies to `$prefix/share/zenbook-scripts/conf.d/`) | **Yes** | No | No |
| **Edited `~/.config/zenbook-scripts/zenbook-hotkeys.conf`** | No | **Yes** | No | No |
| **Edited `zenbook_kb/*.py`** in the git repo | **Yes** | **Yes** | No | No |
| **Edited `brightness.py`, `bin/kb-brightness*`** | **Yes** | Only if hotkey wrapper changed | No | No |
| **Edited `bin/platform-fan*`, `bin/platform-probe`, `bin/platform-tray`, `lib/fan.sh`** | **Yes** | Restart `zenbook-platform-fan-control` if the daemon changed | No | No |
| **Edited `bin/screenpad*`, `bin/kb-platform-profile`, `lib/screenpad.sh`** | **Yes** | No — restart `zenbook-screenpad-sync` if that daemon changed | No | No |
| **Edited `contrib/openrc/` or udev rules** | **Yes** (install step) | **Yes** (or `rc-update` / `udevadm trigger`) | No | No |
| **Edited `kernel/` patches or port script** | No | No | **Yes** (`make -f kernel/Makefile build-current`) | **Yes** after rebuild |
| **Only use `kb-brightness` / `screenpad` / `platform-fan` CLI** | No | No | No | No |
| **Kernel upgrade** (new `uname -r`) | No | No | **Yes** for new KDIR | **Yes** (rebuild + load on new kernel) |
| **Testing from git tree without installing** | No | No | No | No — run `./bin/platform-fan` or `PYTHONPATH=. python3 …` |

## What “install” does

`configure.py` (install step) copies into system paths (default prefix **`/usr`**;
override with `--prefix` / `ZENBOOK_PREFIX`):

| Source | Destination |
|--------|-------------|
| `bin/kb-brightness`, `bin/kb-brightness-hotkeys` | `$prefix/bin/` |
| `bin/platform-fan`, `platform-fan-control`, `platform-probe`, `platform-metrics` | `$prefix/bin/` |
| `bin/platform-tray` | `$prefix/bin/` (when Qt6 path enabled) |
| `bin/screenpad`, `screenpad-boot`, `screenpad-sync`, `kb-platform-profile` | `$prefix/bin/` (when ScreenPad / UX5400 path runs) |
| `zenbook_kb/`, `brightness.py`, `lib/`, `fan-control.json.example` | `$prefix/share/zenbook-scripts/` |
| `conf.d/` | `$prefix/share/zenbook-scripts/conf.d/` |
| `contrib/udev/99-zenbook-kb-hotkeys.rules` | `/etc/udev/rules.d/`, `$prefix/libexec/` |
| `contrib/udev/99-zenbook-screenpad.rules` | `/etc/udev/rules.d/` |
| `contrib/openrc/zenbook-kb-*` | `/etc/init.d/`, `/etc/conf.d/` |
| `contrib/openrc/zenbook-platform-fan-control` | `/etc/init.d/`, `/etc/conf.d/` |
| `contrib/openrc/zenbook-screenpad*` | `/etc/init.d/zenbook-screenpad`, `zenbook-screenpad-sync` |

**OpenRC service** runs `$prefix/bin/kb-brightness-hotkeys` as the installing user
(`command_user` in `/etc/conf.d/zenbook-kb-hotkeys`). Do not copy `contrib/openrc/` by hand —
always run `configure.py` so the conf.d file is written.

## What does *not* need install

- **`insmod` / `rmmod` patched `hid-asus.ko`** — standalone; only stop the hotkey service first so it does not hold USB interface 4.
- **Personal config** in `~/.config/zenbook-scripts/` — already outside the repo; just restart the service.
- **Reading docs or building `.ko` into `kernel/build/`** — no install until you choose to load the module.

## Commands cheat sheet

```bash
# Full userspace redeploy (after repo changes)
cd "/path/to/zenbook_scripts"
sudo python3 configure.py    # answer y to install
sudo python3 configure.py --defaults --all-yes   # semi-auto install (uses existing ~/.config or defaults)

# Or minimal Python + conf.d sync
sudo cp -r zenbook_kb conf.d /usr/local/share/zenbook-scripts/
sudo rc-service zenbook-kb-hotkeys restart

# Config-only (your home directory)
sudo rc-service zenbook-kb-hotkeys restart

# Kernel module only
sudo rc-service zenbook-kb-hotkeys stop
sudo insmod kernel/build/linux-$(uname -r)/hid-asus.ko
# … rebind to asus driver (see kernel/README.md)

# Check what the service will use
kb-brightness-hotkeys --show-profile
```

## How to tell if install is stale

```bash
diff -q zenbook_kb/hotkey.py /usr/local/share/zenbook-scripts/zenbook_kb/hotkey.py
ls /usr/local/share/zenbook-scripts/conf.d    # should exist after latest install
```

If `diff` reports a difference or `conf.d` is missing → **reinstall**.

## Typical workflows

### A. “I only want to test the kernel module”

1. `sudo rc-service zenbook-kb-hotkeys stop`
2. `insmod` + rebind (`kernel/README.md`)
3. Test keys / `dmesg`
4. Optional: `sudo rc-service zenbook-kb-hotkeys start` (old userspace still works, but reinstall recommended for `conf.d` + `usb_poll=auto`)

**No `configure.py` required.**

### B. “I pulled git changes to hotkeys / conf.d”

1. `sudo python3 configure.py` (install)
2. `sudo rc-service zenbook-kb-hotkeys restart`
3. `kb-brightness-hotkeys --show-profile`

**No kernel rebuild unless `kernel/` changed.**

### C. “Kernel module + new userspace together”

1. Install userspace (B)
2. Stop service → `insmod` → rebind (A)
3. `kb-brightness-hotkeys --show-profile` → expect `hid-asus owns … True`, `usb_poll … False`
4. Start service

### D. “Revert to stock kernel driver”

```bash
sudo ./kernel/scripts/switch-hid-asus.sh stock
# or: sudo ./kernel/scripts/unload-hid-asus.sh && sudo modprobe hid_asus
```

Replug keyboard dock if typing still dead. **Do not** start `zenbook-kb-hotkeys` until `verify` passes.

### E. “Safe sideload test” (planned helper — see `PLANNED.md`)

```bash
sudo ./kernel/scripts/switch-hid-asus.sh sideload --watchdog 120
# test dock keyboard; if OK within 120s:
sudo ./kernel/scripts/switch-hid-asus.sh keep
# else auto-reverts to stock (use touchpad/SSH if keyboard is dead)
sudo ./kernel/scripts/switch-hid-asus.sh status
```

**No reinstall.**

### F. “Boot sideload (OpenRC + elogind)”

After `configure.py` install (or Gentoo `emerge` with `USE=kernel`):

| Piece | Path / service |
|-------|----------------|
| oot module | `/usr/lib/modules/zenbook-hid-asus/$(uname -r)/hid-asus.ko` |
| Boot service | `zenbook-kb-hid-asus` (runlevel **default**, before `zenbook-kb-hotkeys`) |
| Config | `/etc/conf.d/zenbook-kb-hid-asus` — `sideload=yes\|no\|auto` |
| Manual switch | `/usr/local/libexec/zenbook-hid-asus-switch` |

Build + install module into system path:

```bash
make -C kernel build          # or: make -f kernel/Makefile build-current
sudo make -C kernel install   # kbuild updates/ + /usr/lib/modules/zenbook-hid-asus/$(uname -r)/
# alternative: sudo python3 configure.py --defaults --all-yes
```

`sudo make -C kernel modules_install` runs kbuild only (no zenbook sideload copy). See [`kernel/README.md`](kernel/README.md).

Disable sideload service: set `sideload=no` in `/etc/conf.d/zenbook-kb-hid-asus` and
`rc-update del zenbook-kb-hid-asus default`.

**Re-emerge / re-run `make -C kernel install` (or configure) after each kernel upgrade** — the `.ko` is per `uname -r`.
Service order at login/default: `zenbook-kb-hid-asus` → `zenbook-kb-hotkeys` + `zenbook-kb-lid`.

**Restart speed:** `rc-service zenbook-kb-hid-asus restart` uses a **quick reload** when the
oot module is already loaded (skips `rmmod`/`insmod` and does not stop hotkeys). Brightness
and fn-lock are still restored from the snapshot. After a **cold boot** the in-tree module
is loaded first, so the first service start does a full sideload (~few seconds). Force a full
reload: `sudo ZENBOOK_HID_QUICK_RELOAD=0 rc-service zenbook-kb-hid-asus restart`.

**Runlevel:** `default`, not `boot` — avoids the “stopping a boot service” warning on
restart; USB is usually ready by default runlevel anyway (`depend()` still runs this
before `zenbook-kb-hotkeys`).

**Brightness and fn-lock across reboot:** services call `kb-brightness-sleep save` on stop and
`restore` on start (`zenbook-kb-hid-asus`, `zenbook-kb-hotkeys`, `zenbook-kb-lid`).
Snapshot: `~/.config/zenbook-scripts/zenbook_duo.save` (from `command_user`) — fields
`brightness`, `fn_lock`, `fn_lock_mode`.

#### `/etc/conf.d/zenbook-kb-hid-asus` reference

| Variable | Values | Effect |
|----------|--------|--------|
| `sideload` | `yes` / `no` / `auto` | Boot-time oot `insmod` + rebind (see above) |
| `ko_path` | path | Override installed `.ko` location |
| `usb_wait_secs` | seconds | How long to wait for docked keyboard when `sideload=yes` |
| `fn_lock_default` | `-1`, `0`, `1` | Initial layout at module load (see below) |
| `fn_lock_allow_toggle` | `0`, `1` | Whether Fn+Esc / vendor `0x4e` may switch layout |
| `fn_row_policy` | decimal bitmask | Per-key Fn-row merge; recommended docked **`7`** (plain F1–F3→`KEY_Fn` + F4–F12 swap); full `insmod` only — see [`README.fn_row_policy.md`](README.fn_row_policy.md) |

`/etc/modprobe.d/zenbook-hid-asus.conf` does **not** apply to sideload (`insmod`); set
`fn_row_policy` in this conf.d file (or `ROW_POLICY=7 ./kmod_deploy.sh`).
OpenRC may log `flock failed` / `already starting` if `zenbook-kb-hid-asus` restarts
while `zenbook-kb-hotkeys` is still stopping. The switch script waits for a clean stop;
`zenbook-kb-hotkeys` also waits in `start_pre`. If it persists: `rc-service zenbook-kb-hotkeys zap`
then `rc-service zenbook-kb-hid-asus restart`.

**Fn-lock modes (UX8406 detachable keyboard, oot `hid-asus` only):**

| Mode | `fn_lock_default` | F1–F12 without Fn | Fn+F4 backlight |
|------|-------------------|-------------------|-----------------|
| **B** (recommended docked) | `0` | special/media layer | yes (kernel path) |
| **A** | `1` | plain F-keys | needs Fn layer / different mapping |

**`fn_lock_allow_toggle`:**

| Value | Fn+Esc | After reboot |
|-------|--------|--------------|
| `0` | ignored — layout stays at `fn_lock_default` | always starts at `fn_lock_default` |
| `1` | toggles A ↔ B (also vendor hotkey `0x4e` where exposed) | restored from snapshot after save (see below) |

Example — pin Mode B but allow temporary switch:

```bash
fn_lock_default=0
fn_lock_allow_toggle=1
```

Then `sudo rc-service zenbook-kb-hid-asus restart` (or reboot). **`fn_lock_default` in
conf.d is the fallback** when no snapshot exists; once you have saved state, service
reload and reboot restore the last known mode from `zenbook_duo.save` (same file as
brightness).

**Persistence (service reload / reboot):**

| Event | Fn-lock |
|-------|---------|
| `zenbook-kb-hid-asus` / `zenbook-kb-hotkeys` **stop** | `kb-brightness-sleep save` reads live mode via USB vendor hidraw and writes `fn_lock` / `fn_lock_mode` into `~/.config/zenbook-scripts/zenbook_duo.save` |
| **Sideload / boot `insmod`** | `fn_lock_default` for `insmod` is taken from the snapshot (overrides conf.d) |
| **Service start / resume** | Full `rmmod`/`insmod` applies `fn_lock_default` from snapshot (kernel driver state). Userspace HID SET does **not** change key mapping. |
| **Fn+Esc toggle** | `zenbook-kb-hotkeys` tracks toggles in `fn-lock-mode` + `fn-lock-toggled`; keep hotkeys running when you toggle. |

Changes apply on next `insmod` (boot service or manual `zenbook-hid-asus-switch sideload`).
Runtime sysfs: `/sys/module/hid_asus/parameters/fn_lock_*` (read-only until reload).

### G. Multi-user / profiles

**Not multi-profile today.** Layers split like this:

| Layer | Scope | Config |
|-------|-------|--------|
| Kernel / fn-lock | **machine** — one layout for the physical keyboard | `/etc/conf.d/zenbook-kb-hid-asus`, boot `insmod` params |
| Hotkey listener | **one Unix user** (`command_user`) | `/etc/conf.d/zenbook-kb-hotkeys` |
| Key bindings | per-user file, but only `command_user`'s listener runs | `~/.config/zenbook-scripts/zenbook-hotkeys.conf` |
| Brightness + fn-lock snapshot | **one user** (same as `command_user` for lid/sleep hooks) | `~/.config/zenbook-scripts/zenbook_duo.save` |

If two people share the laptop: only the configured `command_user` gets custom Fn+
mappings and brightness save/restore. Other users' `~/.config/zenbook-scripts/` files
are ignored unless you change `command_user` and restart services. **Fn-lock mode is
always shared** — it is a kernel property of the docked keyboard, not per login session.

Workarounds: separate Linux users with manual `command_user` changes (not automated);
or per-user evdev remapping outside this stack (e.g. desktop session tools).

### H. Security notes (SSH / multi-user)

**Threat model:** local input stack + optional passwordless `sudo` for one user.
Not a network-facing daemon.

| Action | Typical requirement |
|--------|---------------------|
| Sideload / `insmod` / HID rebind | **root** (`zenbook-hid-asus-switch`, boot service) |
| Write `asus::kbd_backlight` sysfs | **root** (or udev rule — not installed by default) |
| `kb-brightness` via sudoers | **install user only** (NOPASSWD line from `configure.py`) |
| Hotkey listener | runs as `command_user`, group `input` — reads evdev nodes |
| Lid / sleep brightness hooks | **root** (OpenRC), snapshot path from `command_user` |

**SSH session:** a remote user cannot press Fn keys on the physical keyboard through
SSH. They can only affect this stack if they already have sufficient privilege on the
host (e.g. **root**, membership in `input` plus running their own listener, or the
install user's passwordless `kb-brightness` sudo rule).

**Low practical risk** for a single-user laptop: unprivileged SSH users cannot sideload
the module, rebind HID, or change `/etc/conf.d/zenbook-kb-hid-asus`. Do not grant
untrusted users `input`, `plugdev`, or write access to `/dev/hidraw*` if you run
`usb_poll=true` (not recommended on UX8406 docked USB).

**Do not** run `zenbook-kb-hotkeys` as root; `configure.py` sets a normal user.
Re-run `configure.py` after adding untrusted sudoers rules that expose `kb-brightness`
to extra users.

## UX5400EA / ScreenPad Plus

| Piece | Path / service |
|-------|----------------|
| CLI | `/usr/local/bin/screenpad`, `screenpad-boot`, `screenpad-sync`, `kb-platform-profile` |
| Last brightness | `/var/lib/zenbook-scripts/screenpad-brightness` |
| udev | `/etc/udev/rules.d/99-zenbook-screenpad.rules` (`video` group write) |
| Boot oneshot | OpenRC `zenbook-screenpad` / systemd `zenbook-screenpad.service` |
| Brightness sync | OpenRC `zenbook-screenpad-sync` / systemd `zenbook-screenpad-sync.service` |
| Boot mode | `/etc/conf.d/zenbook-screenpad` → `SCREENPAD_BOOT_MODE=on\|off\|sync\|restore` |

### G. “ScreenPad disappeared (touchpad only)”

```bash
screenpad status          # often state=off / drm=none
screenpad on 180          # bl_power quirk + DRM detect
kscreen-doctor -o         # expect HDMI-A-2 connected
```

No reinstall. If permissions fail: `groups | grep video` and re-trigger udev, or use sudo.

### H. “Redeploy ScreenPad userspace after git pull”

```bash
sudo python3 configure.py --defaults --all-yes
# or ScreenPad-only:
python3 -c "from pathlib import Path; from zenbook_kb.install import install_screenpad_support; install_screenpad_support(Path('.'))"
sudo rc-service zenbook-screenpad-sync restart
```

Manual brightness only: `sudo rc-service zenbook-screenpad-sync stop`.

| Action | Typical requirement |
|--------|---------------------|
| `screenpad` / `kb-platform-profile` | install user (sudoers) or group `video` for ScreenPad sysfs |
| Sync daemon | root OpenRC/systemd service |