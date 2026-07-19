#!/usr/bin/env python3
"""Preflight checks for out-of-tree UX8406 hid-asus (no prebuilt .ko delivery).

Exit codes (CLI):
  0  eligible + supported (safe to build)
  1  ineligible (cannot/should not replace hid-asus)
  2  eligible but risky (wrong KV / MODVERSIONS) — needs --force
  3  eligible but kernel source / headers missing
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

# Kernel releases we maintain port/patches for (uname -r / kernel.release).
SUPPORTED_RELEASES = (
    "7.0.12-gentoo-r1",
    "7.1.3-gentoo",
)

SUPPORTED_PATCH_DIRS = (
    "linux-7.0.12-gentoo-r1",
    "linux-7.1.3-gentoo",
)

SKIP_FEATURES_MSG = (
    "oot hid-asus was not built/installed. Docked UX8406 keyboard backlight, "
    "fn_row_policy, and related HID features are not guaranteed with mainline "
    "hid-asus alone."
)


@dataclass
class PreflightResult:
    eligible: bool
    supported: bool
    risky: bool
    has_source: bool
    can_build: bool
    force_required: bool
    kver: str = ""
    kdir: str = ""
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    config: dict[str, str] = field(default_factory=dict)

    @property
    def exit_code(self) -> int:
        if not self.eligible:
            return 1
        if not self.has_source:
            return 3
        if self.force_required:
            return 2
        return 0

    def summary_lines(self) -> list[str]:
        lines = [
            f"kernel:     {self.kver or '?'}",
            f"kdir:       {self.kdir or '(none)'}",
            f"eligible:   {self.eligible}",
            f"supported:  {self.supported}",
            f"has_source: {self.has_source}",
            f"can_build:  {self.can_build}",
            f"force:      {self.force_required}",
        ]
        for key in ("CONFIG_MODULES", "CONFIG_HID_ASUS", "CONFIG_MODVERSIONS"):
            if key in self.config:
                lines.append(f"{key}={self.config[key]}")
        for w in self.warnings:
            lines.append(f"warning: {w}")
        for r in self.reasons:
            lines.append(f"reason:  {r}")
        return lines


def running_release() -> str:
    try:
        return subprocess.check_output(["uname", "-r"], text=True).strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def resolve_kdir(explicit: str | Path | None = None) -> Path | None:
    if explicit:
        p = Path(explicit).expanduser().resolve()
        return p if p.is_dir() else None
    env = os.environ.get("KDIR") or os.environ.get("KERNEL_DIR")
    if env:
        p = Path(env).expanduser().resolve()
        if p.is_dir():
            return p
    kver = running_release()
    candidates: list[Path] = []
    if kver:
        candidates.append(Path(f"/lib/modules/{kver}/build"))
        candidates.append(Path(f"/lib/modules/{kver}/source"))
    candidates.append(Path("/usr/src/linux"))
    for c in candidates:
        try:
            if c.is_dir():
                return c.resolve()
        except OSError:
            continue
    return None


def _parse_config_text(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            m = re.match(r"#\s*(CONFIG_\w+)\s+is not set", line)
            if m:
                out[m.group(1)] = "n"
            continue
        if "=" in line:
            k, _, v = line.partition("=")
            out[k.strip()] = v.strip().strip('"')
    return out


def load_kernel_config(kdir: Path | None, kver: str) -> dict[str, str]:
    merged: dict[str, str] = {}
    paths: list[Path] = []
    if kdir:
        paths.append(kdir / ".config")
    if kver:
        paths.append(Path(f"/boot/config-{kver}"))
    for path in paths:
        if not path.is_file():
            continue
        try:
            merged.update(_parse_config_text(path.read_text(errors="replace")))
        except OSError:
            continue
    proc = Path("/proc/config.gz")
    if not merged and proc.is_file():
        try:
            with gzip.open(proc, "rt", errors="replace") as fh:
                merged.update(_parse_config_text(fh.read()))
        except OSError:
            pass
    return merged


def kernel_release_from_kdir(kdir: Path) -> str:
    rel = kdir / "include" / "config" / "kernel.release"
    if rel.is_file():
        try:
            return rel.read_text().strip()
        except OSError:
            pass
    name = kdir.name
    if name.startswith("linux-"):
        return name[len("linux-") :]
    return running_release()


def is_supported_release(kver: str) -> bool:
    if not kver:
        return False
    if kver in SUPPORTED_RELEASES:
        return True
    for d in SUPPORTED_PATCH_DIRS:
        if d == f"linux-{kver}" or kver == d.removeprefix("linux-"):
            return True
    return False


def find_patch_dir(repo_root: Path | None, kver: str) -> Path | None:
    if not repo_root or not kver:
        return None
    names = [f"linux-{kver}"]
    if kver.startswith("linux-"):
        names.append(kver)
    roots = [
        repo_root / "kernel" / "patches",
        repo_root / "packaging" / "gentoo" / "files" / "patches",
    ]
    for root in roots:
        for name in names:
            p = root / name / "ux8406-hid-asus.patch"
            if p.is_file():
                return p.parent
    return None


def hid_asus_builtin(kver: str) -> bool | None:
    """True if hid-asus is built-in; False if modular/absent; None unknown."""
    if not kver:
        return None
    builtin = Path(f"/lib/modules/{kver}/modules.builtin")
    if not builtin.is_file():
        return None
    try:
        text = builtin.read_text(errors="replace")
    except OSError:
        return None
    return "hid-asus.ko" in text


def run_preflight(
    *,
    kdir: Path | str | None = None,
    kver: str | None = None,
    repo_root: Path | str | None = None,
    force: bool = False,
) -> PreflightResult:
    root = Path(repo_root).resolve() if repo_root else None
    resolved = resolve_kdir(kdir)
    kver = kver or running_release()
    if resolved:
        tree_rel = kernel_release_from_kdir(resolved)
        if tree_rel:
            kver = tree_rel

    cfg = load_kernel_config(resolved, kver or "")
    reasons: list[str] = []
    warnings: list[str] = []

    modules = cfg.get("CONFIG_MODULES", "")
    hid = cfg.get("CONFIG_HID_ASUS", "")
    modversions = cfg.get("CONFIG_MODVERSIONS", "n")

    eligible = True
    if modules == "n":
        eligible = False
        reasons.append("CONFIG_MODULES is disabled (cannot load modules)")
    if hid == "y":
        eligible = False
        reasons.append("CONFIG_HID_ASUS=y (built-in; cannot replace with sideload)")
    if hid_asus_builtin(kver or "") is True:
        eligible = False
        reasons.append("hid-asus is listed in modules.builtin")

    if hid == "" and eligible:
        warnings.append(
            "CONFIG_HID_ASUS not found in config; assuming modular if sources exist"
        )
    elif hid not in ("m", "y", "") and eligible:
        warnings.append(f"unexpected CONFIG_HID_ASUS={hid}")

    has_source = False
    if resolved is not None:
        hid_c = resolved / "drivers" / "hid" / "hid-asus.c"
        if hid_c.is_file() and (resolved / "Makefile").is_file():
            has_source = True
        else:
            reasons.append(
                f"kernel tree incomplete at {resolved} (need drivers/hid/hid-asus.c)"
            )
    else:
        reasons.append(
            "no kernel build tree (set KDIR or install matching linux-sources)"
        )

    supported = is_supported_release(kver or "")
    if root and kver and find_patch_dir(root, kver):
        supported = True
    if not supported and kver:
        warnings.append(
            f"kernel {kver} is not in the supported list "
            f"({', '.join(SUPPORTED_RELEASES)}); port may fail"
        )

    if modversions in ("y", "1"):
        warnings.append(
            "CONFIG_MODVERSIONS=y — symbol CRC mismatches are more likely on oot builds"
        )

    run = running_release()
    if run and kver and run != kver:
        warnings.append(f"build targets {kver} but running kernel is {run}")

    if not cfg and has_source:
        warnings.append("could not read kernel .config")

    risky = False
    for w in warnings:
        if any(
            s in w
            for s in (
                "MODVERSIONS",
                "not in the supported",
                "running kernel",
                "could not read",
                "CONFIG_HID_ASUS not found",
            )
        ):
            risky = True
            break
    if not supported:
        risky = True

    force_required = bool(eligible and has_source and risky and not force)
    can_build = bool(eligible and has_source and (not risky or force))

    if eligible and has_source and risky and force:
        warnings.append("proceeding with force despite warnings")

    return PreflightResult(
        eligible=eligible,
        supported=supported,
        risky=risky,
        has_source=has_source,
        can_build=can_build,
        force_required=force_required,
        kver=kver or "",
        kdir=str(resolved) if resolved else "",
        reasons=reasons,
        warnings=warnings,
        config={
            k: cfg[k]
            for k in (
                "CONFIG_MODULES",
                "CONFIG_HID_ASUS",
                "CONFIG_MODVERSIONS",
                "CONFIG_ASUS_WMI",
            )
            if k in cfg
        },
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Preflight for oot hid-asus build")
    parser.add_argument("--kdir", default=None, help="Kernel build tree (default: auto)")
    parser.add_argument("--kver", default=None, help="Override kernel release string")
    parser.add_argument(
        "--repo-root",
        default=str(Path(__file__).resolve().parents[1]),
        help="Repo root (for kernel/patches lookup)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Allow risky builds (wrong KV / MODVERSIONS)",
    )
    parser.add_argument("--json", action="store_true", help="JSON on stdout")
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Only print a one-liner on failure",
    )
    args = parser.parse_args(argv)

    force = args.force or os.environ.get("ZENBOOK_KERNEL_FORCE", "").strip().lower() in (
        "1",
        "yes",
        "true",
    )
    result = run_preflight(
        kdir=args.kdir,
        kver=args.kver,
        repo_root=args.repo_root,
        force=force,
    )
    if args.json:
        print(json.dumps(asdict(result), indent=2))
    elif not args.quiet:
        print("\n".join(result.summary_lines()))
    elif result.exit_code != 0:
        msg = "; ".join(result.reasons + result.warnings) or "preflight failed"
        print(msg, file=sys.stderr)
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
