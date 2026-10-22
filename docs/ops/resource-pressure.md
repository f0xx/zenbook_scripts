# Resource pressure — UX5400 / Gentoo desktop

When the machine feels sluggish (Cursor, Plasma, SSH lag) but `top` shows low
CPU, check **memory**, **swap**, and **background compile jobs** — not only
zenbook daemons.

## Quick diagnosis

```bash
free -h
vmstat 1 5                    # si/so columns = swap in/out (pain)
cat /proc/pressure/memory     # PSI (kernel 4.20+); some kernels omit this
ps aux --sort=-%mem | head -20
ps aux --sort=-%cpu | head -15
pgrep -af 'emerge|make|gcc|cc1|ld '
for f in /proc/[0-9]*/status; do
  awk '/^Name:|^VmSwap:/{printf $2" "} END{print ""}' "$f"
done | awk '$2+0>1024{print $2/1024" MiB", $1}' | sort -rn | head -15
```

## UX5400 snapshot (2026-08-03)

| Signal | Value | Notes |
|--------|-------|-------|
| RAM | 16 GiB, ~11 GiB available | Not RAM-starved at check time |
| Swap used | ~858 MiB | Residual — not active churn (`vmstat si/so` ≈ 0) |
| Load | ~0.25 | Low |
| emerge/make | **not running** | Last log entry: `qemu-10.2.2` finished |
| Top swap holders | mariadbd ~104 MiB, gitea ~84 MiB, dockerd, kwin | Long-running **Docker stack** (gitea/mariadb/php, “Up 3 years”) |
| zenbook | touchpad filter ~0.2% CPU; GUI ~1.6% after timer fix | Not the bottleneck |
| Cursor | not running on box during check | Slowness may be intermittent (during `emerge`) or on another host |

**Conclusion:** day-to-day zenbook daemons are negligible. Swap use points at
**always-on Docker/DB services** and past memory pressure (likely compiles or
browser + containers). When **`emerge -jN @world`** runs, Portage/Make can
monopolize CPU, disk, and RAM regardless of load average.

## Limiting Portage / compile pressure (Gentoo)

### Nice level (simplest)

In `/etc/portage/make.conf`:

```bash
PORTAGE_NICENESS=15
PORTAGE_IONICE_COMMAND="ionice -c3"
MAKEOPTS="-j4"    # cap parallelism; tune to cores − 1 for desktop use
```

Or one-shot:

```bash
sudo nice -n 19 ionice -c3 emerge -av1 some/package
```

### cgroup v2 memory + CPU cap (recommended for heavy merges)

Create `/etc/portage/emerge.slice` (systemd user session not required — use
`systemd-run` from root):

```ini
[Slice]
CPUWeight=20
MemoryMax=8G
MemoryHigh=6G
```

Run emerge inside the slice:

```bash
sudo systemd-run --scope -p Slice=emerge.slice -p CPUQuota=50% \
  emerge -av1 @world
```

Without systemd, a **manual cgroup v2** wrapper:

```bash
sudo mkdir -p /sys/fs/cgroup/zenbook-portage
echo "+memory +cpu" | sudo tee /sys/fs/cgroup/cgroup.subtree_control
echo 8G | sudo tee /sys/fs/cgroup/zenbook-portage/memory.max
echo 50000 | sudo tee /sys/fs/cgroup/zenbook-portage/cpu.max   # 50% of one core quota syntax varies
sudo sh -c 'echo $$ > /sys/fs/cgroup/zenbook-portage/cgroup.procs && nice -n 19 emerge -av1 foo'
```

See `contrib/cgroups/README.md` for copy-paste examples.

### When you need the desktop responsive

1. Pause or stop non-essential containers: `docker stop …`
2. Cap emerge as above; avoid `-j$(nproc)` during interactive work
3. Close heavy Chrome tabs (often top RSS after plasmashell)
4. Restart `platform-touchpad-gui` after upgrading — old builds polled `/proc`
   every 250 ms (~13% CPU); fixed in branch `feature/0.0.4-touch-map-calibrate`

## OOM / suspend noise

`dmesg | grep -i oom` may show **OOM killer disabled/enabled** around
suspend/resume — that is normal elogind sleep chatter, not necessarily a kill
storm. Look for `Killed process` lines to confirm real OOM events.

## Related

- [../daemons/touchpad.md](../daemons/touchpad.md) — stuck cursor / filter
- [../daemons/fan-control.md](../daemons/fan-control.md) — adaptive fan daemon
