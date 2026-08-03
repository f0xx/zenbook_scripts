# cgroup recipes — cap Portage / compile load

Gentoo `emerge` and `make` can freeze a Plasma session even when load average
looks modest (I/O wait, memory reclaim). Use **nice**, **ionice**, and **cgroup
v2 limits** together.

## /etc/portage/make.conf (baseline)

```bash
PORTAGE_NICENESS=15
PORTAGE_IONICE_COMMAND="ionice -c3"
# Desktop-friendly: leave headroom
MAKEOPTS="-j4 -l4"
```

## systemd-run scope (if systemd is present)

```bash
sudo systemd-run --scope \
  -p CPUWeight=20 \
  -p MemoryMax=8G \
  -p MemoryHigh=6G \
  emerge -av1 @world
```

Adjust `MemoryMax` to ~50–60% of RAM on a 16 GiB machine if you still need
Chrome + Plasma.

## cgroup v2 manual (OpenRC / elogind — no systemd)

```bash
CG=/sys/fs/cgroup/zenbook-portage
sudo mkdir -p "$CG"
# Enable controllers on parent (once per boot if needed):
echo '+memory +cpu' | sudo tee /sys/fs/cgroup/cgroup.subtree_control

echo 8589934592 | sudo tee "$CG/memory.max"    # 8 GiB
echo 50000       | sudo tee "$CG/cpu.max"     # ~50% (100000 = 100%)

sudo sh -c "
  echo \$$ > $CG/cgroup.procs
  exec nice -n 19 ionice -c3 emerge -av1 \"\$@\"
" sh "$@"
```

## Docker stack (UX5400)

Long-running `gitea` + `mariadb` containers held ~180 MiB in swap in field
checks. For dev sessions:

```bash
docker stop androidcast_local-mariadb-1 androidcast_local-gitea-1
# or set compose memory limits
```

See [../../docs/ops/resource-pressure.md](../../docs/ops/resource-pressure.md).
