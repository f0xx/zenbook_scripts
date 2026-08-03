"""Apply a named user profile to hardware (shared by CLI and cron evaluate)."""

from __future__ import annotations

import logging
import shutil
import subprocess

from zenbook_kb.user_profiles import load

log = logging.getLogger("zenbook.profile_apply")


def apply_mode(mode: str) -> bool:
    doc = load()
    m = doc["modes"].get(mode) or {}
    if mode == "auto":
        for argv in (
            ["platform-fan-control", "mode", "auto"],
            ["platform-fan", "adaptive"],
        ):
            bin_ = shutil.which(argv[0])
            if not bin_:
                continue
            for prefix in (["sudo", "-n"], []):
                try:
                    r = subprocess.run(
                        [*prefix, bin_, *argv[1:]],
                        capture_output=True,
                        text=True,
                        timeout=12,
                        check=False,
                    )
                    if r.returncode == 0:
                        return True
                except OSError:
                    pass
        return False
    if mode == "night":
        if not m.get("enabled"):
            from zenbook_kb.night_mode import exit_night

            exit_night(force=False)
            return True
        from zenbook_kb.night_mode import enter_night, load_night_config

        nc = load_night_config()
        nc["enabled"] = True
        nc["blank_displays"] = bool((m.get("screen") or {}).get("power_off", True))
        return enter_night(nc, force=True)
    fan_profile = m.get("fan_profile")
    if not fan_profile:
        return False
    cli = shutil.which("platform-fan-control")
    if not cli:
        return False
    for prefix in (["sudo", "-n"], []):
        try:
            r = subprocess.run(
                [*prefix, cli, "apply", str(fan_profile)],
                capture_output=True,
                text=True,
                timeout=12,
                check=False,
            )
            if r.returncode == 0:
                pp = shutil.which("kb-platform-profile")
                mapping = {
                    "powersave": "quiet",
                    "balanced": "balanced",
                    "performance": "performance",
                }
                if pp and fan_profile in mapping:
                    subprocess.run(
                        [pp, "set", mapping[fan_profile]],
                        capture_output=True,
                        timeout=8,
                        check=False,
                    )
                return True
        except OSError:
            pass
    return False
