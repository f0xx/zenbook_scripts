# Gentoo overlay ``files/`` for app-laptop/zenbook-scripts

Conditional UX8406 `hid-asus` patches (mirrors of `kernel/patches/` in the
upstream tree). The ebuild does **not** ship precompiled `.ko` files.

| Patch dir | Kernel release |
|-----------|----------------|
| `patches/linux-7.0.12-gentoo-r1/` | `7.0.12-gentoo-r1` |
| `patches/linux-7.1.3-gentoo/` | `7.1.3-gentoo` |

## How they are used

- **Out-of-tree build (default):** `USE=kernel` runs
  `make -C kernel build-current` which ports `hid-asus.c` via
  `kernel/scripts/port-ux8406.py` against `/usr/src/linux` (or
  `KV_OUT_DIR`). Preflight refuses unsupported releases unless
  `ZENBOOK_KERNEL_FORCE=1`.
- **In-tree / manual:** apply the matching `ux8406-hid-asus.patch` to
  gentoo-sources of the same version if you prefer patching the tree
  instead of sideloading.

Keep these files in sync with `kernel/patches/` when regenerating patches
(`make -C kernel patches`).
