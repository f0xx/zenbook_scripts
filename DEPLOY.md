# When to redeploy (install / restart)

Quick rule: **only redeploy userspace when files under `/usr/local/` must change.**
Kernel module tests and config-only edits often need **no** reinstall.

## Decision table

| You changed or are doing… | Re-run `configure.py` install? | Restart `zenbook-kb-hotkeys`? | Rebuild kernel module? | Reload `hid-asus.ko`? |
|---------------------------|-------------------------------|-------------------------------|------------------------|------------------------|
| **Try patched `hid-asus.ko`** (`insmod` test) | No | **Stop** before `insmod`; start after if you want the listener | Only if `kernel/` sources changed | **Yes** (`rmmod` + `insmod` + rebind) |
| **Edited `conf.d/*.conf`** in the git repo | **Yes** (copies to `/usr/local/share/zenbook-scripts/conf.d/`) | **Yes** | No | No |
| **Edited `~/.config/zenbook-scripts/zenbook-hotkeys.conf`** | No | **Yes** | No | No |
| **Edited `zenbook_kb/*.py`** in the git repo | **Yes** | **Yes** | No | No |
| **Edited `brightness.py`, `bin/kb-brightness*`** | **Yes** | Only if hotkey wrapper changed | No | No |
| **Edited `contrib/openrc/` or udev rules** | **Yes** (install step) | **Yes** (or `rc-update` / `udevadm trigger`) | No | No |
| **Edited `kernel/` patches or port script** | No | No | **Yes** (`make -f kernel/Makefile build-current`) | **Yes** after rebuild |
| **Only use `kb-brightness` CLI** (brightness up/down) | No | No | No | No |
| **Kernel upgrade** (new `uname -r`) | No | No | **Yes** for new KDIR | **Yes** (rebuild + load on new kernel) |
| **Testing from git tree without installing** | No | No | No | No — run `PYTHONPATH=. python3 zenbook_kb/hotkey.py …` |

## What “install” does

`configure.py` (install step) copies into system paths:

| Source | Destination |
|--------|-------------|
| `bin/kb-brightness`, `bin/kb-brightness-hotkeys` | `/usr/local/bin/` |
| `zenbook_kb/`, `brightness.py`, `lib/` | `/usr/local/share/zenbook-scripts/` |
| `conf.d/` | `/usr/local/share/zenbook-scripts/conf.d/` |
| `contrib/udev/` | `/etc/udev/rules.d/`, `/usr/local/libexec/` |
| `contrib/openrc/` | `/etc/init.d/zenbook-kb-hotkeys`, `/etc/conf.d/zenbook-kb-hotkeys` |

**OpenRC service** runs `/usr/local/bin/kb-brightness-hotkeys` as the installing user
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
