"""SQLite time-series for fan RPM / package temp (stdlib sqlite3)."""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

from zenbook_kb.fan_control import read_rpm, read_temp_c
from zenbook_kb.users import resolve_user_home

SCHEMA = """
CREATE TABLE IF NOT EXISTS samples (
  ts REAL NOT NULL,
  rpm INTEGER,
  temp_c REAL,
  pwm_mode INTEGER,
  profile TEXT
);
CREATE INDEX IF NOT EXISTS idx_samples_ts ON samples(ts);
CREATE TABLE IF NOT EXISTS events (
  ts REAL NOT NULL,
  kind TEXT NOT NULL,
  metric TEXT NOT NULL,
  value REAL,
  note TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);
"""

# asus-nb-wmi pwm1_enable: 0=full-on, 2=auto (common on UX8406/5400)
PWM_LABELS = {0: "full", 1: "manual", 2: "auto"}

# Graph display: quiet ±1°C sensor chatter around a long-window baseline.
TEMP_SMOOTH_WINDOW = 7  # odd; rolling median of raw samples
TEMP_BASELINE_WINDOW = 61  # ~1 min at 1s sampling
TEMP_DEADBAND_C = 3.0  # flatten when |smooth − baseline| < this
TEMP_POI_DELTA_C = 3.0  # consecutive-sample POI; match deadband
RPM_POI_DELTA = 800


def pwm_label(mode: int | None) -> str:
    if mode is None:
        return "n/a"
    return PWM_LABELS.get(mode, f"pwm={mode}")


def default_db_path() -> Path:
    env = Path.home()  # may be wrong under sudo — prefer resolve
    try:
        base = resolve_user_home() / ".local" / "share" / "zenbook-scripts"
    except Exception:
        base = env / ".local" / "share" / "zenbook-scripts"
    base.mkdir(parents=True, exist_ok=True)
    return base / "metrics.sqlite3"


@dataclass
class Sample:
    ts: float
    rpm: int | None
    temp_c: float | None
    pwm_mode: int | None
    profile: str | None


@dataclass
class DisplayPoint:
    """One plot point after temp smooth + deadband (rpm unchanged)."""

    ts: float
    temp_c: float | None
    rpm: int | None
    temp_raw: float | None = None
    temp_baseline: float | None = None


def _rolling_median(values: list[float | None], window: int) -> list[float | None]:
    """Centered-ish rolling median; uses available neighbours at edges."""
    n = len(values)
    if n == 0:
        return []
    half = max(1, window // 2)
    out: list[float | None] = []
    for i in range(n):
        chunk = [v for v in values[max(0, i - half) : i + half + 1] if v is not None]
        if not chunk:
            out.append(None)
            continue
        chunk.sort()
        out.append(chunk[len(chunk) // 2])
    return out


def display_series(
    samples: list[Sample],
    *,
    smooth_window: int = TEMP_SMOOTH_WINDOW,
    baseline_window: int = TEMP_BASELINE_WINDOW,
    deadband_c: float = TEMP_DEADBAND_C,
) -> list[DisplayPoint]:
    """Pre-smooth temps and flatten noise inside ``±deadband_c`` of baseline.

    RPM is passed through unchanged. Raw samples in SQLite are not modified.
    """
    if not samples:
        return []
    raw = [s.temp_c for s in samples]
    smooth = _rolling_median(raw, smooth_window)
    baseline = _rolling_median(smooth, baseline_window)
    points: list[DisplayPoint] = []
    for s, sm, base in zip(samples, smooth, baseline, strict=True):
        disp = sm
        if sm is not None and base is not None and abs(sm - base) < deadband_c:
            disp = base
        points.append(
            DisplayPoint(
                ts=s.ts,
                temp_c=disp,
                rpm=s.rpm,
                temp_raw=s.temp_c,
                temp_baseline=base,
            )
        )
    return points


@dataclass
class Event:
    ts: float
    kind: str
    metric: str
    value: float | None
    note: str


@dataclass
class PoiDetail:
    """Absolute + relative-to-previous snapshot for a POI tooltip."""

    event: Event
    sample: Sample | None
    previous: Sample | None

    def lines(self) -> list[str]:
        ev = self.event
        cur = self.sample
        prev = self.previous
        when = time.strftime("%H:%M:%S", time.localtime(ev.ts))
        lines = [
            f"POI · {when}",
            f"kind: {ev.kind} / {ev.metric}"
            + (f" · {ev.note}" if ev.note else ""),
        ]
        if cur is None:
            lines.append("(no sample snapshot at this timestamp)")
            return lines

        lines.append(_rel_num("fan", cur.rpm, prev.rpm if prev else None, "{:.0f}", " rpm"))
        lines.append(
            _rel_str(
                "mode",
                pwm_label(cur.pwm_mode),
                pwm_label(prev.pwm_mode) if prev else None,
            )
        )
        lines.append(
            _rel_str(
                "profile",
                cur.profile or "n/a",
                (prev.profile or "n/a") if prev else None,
            )
        )
        lines.append(
            _rel_num("temp", cur.temp_c, prev.temp_c if prev else None, "{:.1f}", "°C")
        )
        if ev.value is not None and ev.metric in ("temp_c", "rpm", "pwm"):
            lines.append(f"trigger value: {ev.value:g}")
        return lines

    def rich_text(self) -> str:
        return "<br/>".join(
            line.replace("&", "&amp;").replace("<", "&lt;") for line in self.lines()
        )


def _rel_num(
    label: str,
    cur: float | int | None,
    prev: float | int | None,
    fmt: str,
    unit: str,
) -> str:
    if cur is None:
        return f"{label}: n/a"
    abs_s = fmt.format(float(cur)) + unit
    if prev is None:
        return f"{label}: {abs_s}"
    d = float(cur) - float(prev)
    sign = "+" if d >= 0 else ""
    return f"{label}: {abs_s} ({sign}{fmt.format(d)}{unit})"


def _rel_str(label: str, cur: str, prev: str | None) -> str:
    if prev is None:
        return f"{label}: {cur}"
    if prev == cur:
        return f"{label}: {cur} (=)"
    return f"{label}: {cur} (was {prev})"


class MetricsStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_db_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path), timeout=5)
        self._conn.executescript(SCHEMA)
        self._conn.commit()
        self._last: Sample | None = None

    def close(self) -> None:
        self._conn.close()

    def record_sample(
        self,
        *,
        rpm: int | None,
        temp_c: float | None,
        pwm_mode: int | None = None,
        profile: str | None = None,
        ts: float | None = None,
    ) -> Sample:
        sample = Sample(
            ts=ts if ts is not None else time.time(),
            rpm=rpm,
            temp_c=temp_c,
            pwm_mode=pwm_mode,
            profile=profile,
        )
        self._conn.execute(
            "INSERT INTO samples(ts,rpm,temp_c,pwm_mode,profile) VALUES(?,?,?,?,?)",
            (sample.ts, sample.rpm, sample.temp_c, sample.pwm_mode, sample.profile),
        )
        self._detect_pois(sample)
        self._conn.commit()
        self._last = sample
        return sample

    def add_event(
        self,
        kind: str,
        metric: str,
        value: float | None = None,
        note: str = "",
        ts: float | None = None,
    ) -> None:
        self._conn.execute(
            "INSERT INTO events(ts,kind,metric,value,note) VALUES(?,?,?,?,?)",
            (ts if ts is not None else time.time(), kind, metric, value, note),
        )
        self._conn.commit()

    def _detect_pois(self, sample: Sample) -> None:
        prev = self._last
        if not prev:
            return
        if sample.temp_c is not None and prev.temp_c is not None:
            d = sample.temp_c - prev.temp_c
            if d >= TEMP_POI_DELTA_C:
                self.add_event(
                    "rise",
                    "temp_c",
                    sample.temp_c,
                    f"temp +{d:.1f}°C",
                    ts=sample.ts,
                )
            elif d <= -TEMP_POI_DELTA_C:
                self.add_event(
                    "fall",
                    "temp_c",
                    sample.temp_c,
                    f"temp {d:.1f}°C",
                    ts=sample.ts,
                )
        if sample.rpm is not None and prev.rpm is not None:
            d = sample.rpm - prev.rpm
            if d >= RPM_POI_DELTA:
                self.add_event(
                    "rise",
                    "rpm",
                    float(sample.rpm),
                    f"rpm +{d}",
                    ts=sample.ts,
                )
            elif d <= -RPM_POI_DELTA:
                self.add_event(
                    "fall",
                    "rpm",
                    float(sample.rpm),
                    f"rpm {d}",
                    ts=sample.ts,
                )
        if (
            sample.pwm_mode is not None
            and prev.pwm_mode is not None
            and sample.pwm_mode != prev.pwm_mode
        ):
            self.add_event(
                "mode",
                "pwm",
                float(sample.pwm_mode),
                f"pwm {pwm_label(prev.pwm_mode)}→{pwm_label(sample.pwm_mode)}",
                ts=sample.ts,
            )
        if sample.profile and prev.profile and sample.profile != prev.profile:
            self.add_event(
                "mode",
                "profile",
                None,
                f"profile {prev.profile}→{sample.profile}",
                ts=sample.ts,
            )

    def sample_now(self) -> Sample:
        from pathlib import Path as P

        pwm = None
        hw = P("/sys/devices/platform/asus-nb-wmi/hwmon")
        if hw.is_dir():
            for d in hw.iterdir():
                en = d / "pwm1_enable"
                if en.is_file():
                    try:
                        pwm = int(en.read_text().strip())
                    except (OSError, ValueError):
                        pwm = None
                    break
        profile = None
        pp = P("/sys/firmware/acpi/platform_profile")
        if pp.is_file():
            try:
                profile = pp.read_text().strip()
            except OSError:
                profile = None
        return self.record_sample(
            rpm=read_rpm(),
            temp_c=read_temp_c(),
            pwm_mode=pwm,
            profile=profile,
        )

    def history(self, *, since_ts: float | None = None, limit: int = 500) -> list[Sample]:
        if since_ts is None:
            since_ts = time.time() - 3600
        rows = self._conn.execute(
            "SELECT ts,rpm,temp_c,pwm_mode,profile FROM samples "
            "WHERE ts>=? ORDER BY ts ASC LIMIT ?",
            (since_ts, limit),
        ).fetchall()
        return [
            Sample(ts=r[0], rpm=r[1], temp_c=r[2], pwm_mode=r[3], profile=r[4])
            for r in rows
        ]

    def events(self, *, since_ts: float | None = None, limit: int = 100) -> list[Event]:
        if since_ts is None:
            since_ts = time.time() - 3600
        rows = self._conn.execute(
            "SELECT ts,kind,metric,value,note FROM events "
            "WHERE ts>=? ORDER BY ts ASC LIMIT ?",
            (since_ts, limit),
        ).fetchall()
        return [
            Event(ts=r[0], kind=r[1], metric=r[2], value=r[3], note=r[4] or "")
            for r in rows
        ]

    def nearest_sample(self, ts: float, *, max_delta: float = 2.5) -> Sample | None:
        """Sample closest to *ts* within *max_delta* seconds."""
        row = self._conn.execute(
            "SELECT ts,rpm,temp_c,pwm_mode,profile FROM samples "
            "ORDER BY ABS(ts-?) ASC LIMIT 1",
            (ts,),
        ).fetchone()
        if not row:
            return None
        if abs(row[0] - ts) > max_delta:
            return None
        return Sample(ts=row[0], rpm=row[1], temp_c=row[2], pwm_mode=row[3], profile=row[4])

    def previous_sample(self, ts: float) -> Sample | None:
        row = self._conn.execute(
            "SELECT ts,rpm,temp_c,pwm_mode,profile FROM samples "
            "WHERE ts<? ORDER BY ts DESC LIMIT 1",
            (ts,),
        ).fetchone()
        if not row:
            return None
        return Sample(ts=row[0], rpm=row[1], temp_c=row[2], pwm_mode=row[3], profile=row[4])

    def poi_detail(self, event: Event, *, max_delta: float = 2.5) -> PoiDetail:
        sample = self.nearest_sample(event.ts, max_delta=max_delta)
        if sample is not None:
            prev = self.previous_sample(sample.ts)
        else:
            prev = self.previous_sample(event.ts)
        return PoiDetail(event=event, sample=sample, previous=prev)

    def prune(self, *, older_than_sec: float = 7 * 86400) -> None:
        cut = time.time() - older_than_sec
        self._conn.execute("DELETE FROM samples WHERE ts<?", (cut,))
        self._conn.execute("DELETE FROM events WHERE ts<?", (cut,))
        self._conn.commit()
