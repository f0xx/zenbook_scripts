"""Dual-panel touch diagnosis / corner calibration math.

Inspired by ``xinput-val`` (4-corner targets + affine / bbox fit). On Plasma
Wayland we cannot apply Xorg ``TransformationMatrix``; this module is for
**observing** touch→screen mismatch (e.g. lower eDP touch warping to primary)
and emitting a report operators can file against KWin / libinput.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Sequence


Corner = tuple[float, float]  # (x, y) in the same coordinate space


@dataclass
class ScreenGeom:
    name: str
    x: int
    y: int
    w: int
    h: int
    primary: bool = False

    def contains(self, px: float, py: float, *, margin: float = 0.0) -> bool:
        return (
            self.x - margin <= px < self.x + self.w + margin
            and self.y - margin <= py < self.y + self.h + margin
        )

    def local(self, px: float, py: float) -> tuple[float, float]:
        return (px - self.x, py - self.y)

    def corner_targets(self, inset: float = 0.08) -> list[Corner]:
        """TL, TR, BR, BL in global coords (same order as xinput-val)."""
        ix = self.w * inset
        iy = self.h * inset
        return [
            (self.x + ix, self.y + iy),
            (self.x + self.w - ix, self.y + iy),
            (self.x + self.w - ix, self.y + self.h - iy),
            (self.x + ix, self.y + self.h - iy),
        ]


@dataclass
class TouchHit:
    global_x: float
    global_y: float
    screen_name: str  # QScreen / window that received the event
    source: str = "qt"  # qt|mouse|touch
    stamp_ms: int = 0


@dataclass
class JumpVerdict:
    hit_screen: str
    geom_screen: str | None
    jump: bool
    detail: str


def screen_containing(screens: Sequence[ScreenGeom], px: float, py: float) -> ScreenGeom | None:
    for s in screens:
        if s.contains(px, py):
            return s
    # Prefer primary if none match (degenerate / gap)
    for s in screens:
        if s.primary:
            return s
    return screens[0] if screens else None


def diagnose_hit(screens: Sequence[ScreenGeom], hit: TouchHit) -> JumpVerdict:
    """If the window that got the event disagrees with geometry under the point → jump."""
    geom = screen_containing(screens, hit.global_x, hit.global_y)
    geom_name = geom.name if geom else None
    if geom_name is None:
        return JumpVerdict(hit.screen_name, None, True, "point outside all screen geometries")
    if hit.screen_name != geom_name:
        return JumpVerdict(
            hit.screen_name,
            geom_name,
            True,
            f"event on '{hit.screen_name}' but coordinates map to '{geom_name}' "
            f"at ({hit.global_x:.1f},{hit.global_y:.1f})",
        )
    return JumpVerdict(hit.screen_name, geom_name, False, "event screen matches geometry")


def _solve_3x3(m: list[list[float]]) -> tuple[float, float, float] | None:
    """Gaussian elimination on 3x4 augmented matrix → (x0,x1,x2) or None."""
    a = [row[:] for row in m]
    for i in range(3):
        pivot = i
        for j in range(i + 1, 3):
            if abs(a[j][i]) > abs(a[pivot][i]):
                pivot = j
        if abs(a[pivot][i]) < 1e-12:
            return None
        if pivot != i:
            a[i], a[pivot] = a[pivot], a[i]
        d = a[i][i]
        for k in range(i, 4):
            a[i][k] /= d
        for j in range(3):
            if j == i:
                continue
            f = a[j][i]
            for k in range(i, 4):
                a[j][k] -= f * a[i][k]
    return (a[0][3], a[1][3], a[2][3])


def fit_affine_4pt(
    obs: Sequence[Corner],
    ref: Sequence[Corner],
) -> tuple[tuple[float, float, float, float, float, float], str] | None:
    """Map observed → reference: [x'] = [[a b c],[d e f]] [x y 1].

    Same spirit as xinput-val: least-squares via two 3x3 solves on 4 points;
    falls back to bbox scale+offset if singular.
    """
    if len(obs) != 4 or len(ref) != 4:
        return None

    # Build overdetermined system; use first 3 + average of 4th via normal eqs lite:
    # For x': a*x + b*y + c = x'  (3 unknowns, use 3 corners; validate 4th)
    def _fit_row(idxs: tuple[int, int, int]) -> tuple[float, float, float] | None:
        mx: list[list[float]] = []
        my: list[list[float]] = []
        for i in idxs:
            ox, oy = obs[i]
            rx, ry = ref[i]
            mx.append([ox, oy, 1.0, rx])
            my.append([ox, oy, 1.0, ry])
        sx = _solve_3x3(mx)
        sy = _solve_3x3(my)
        if sx is None or sy is None:
            return None
        return (sx[0], sx[1], sx[2], sy[0], sy[1], sy[2])

    for idxs in ((0, 1, 2), (0, 1, 3), (0, 2, 3), (1, 2, 3)):
        got = _fit_row(idxs)
        if got is not None:
            a, b, c, d, e, f = got
            # sanity: map corner 0 roughly near ref
            ox, oy = obs[0]
            px = a * ox + b * oy + c
            py = d * ox + e * oy + f
            rx, ry = ref[0]
            if abs(px - rx) < max(50.0, abs(rx) * 0.2) and abs(py - ry) < max(50.0, abs(ry) * 0.2):
                return ((a, b, c, d, e, f), "affine-3pt")

    # bbox fallback
    oxs = [p[0] for p in obs]
    oys = [p[1] for p in obs]
    rxs = [p[0] for p in ref]
    rys = [p[1] for p in ref]
    ow = max(oxs) - min(oxs) or 1.0
    oh = max(oys) - min(oys) or 1.0
    rw = max(rxs) - min(rxs) or 1.0
    rh = max(rys) - min(rys) or 1.0
    sx = rw / ow
    sy = rh / oh
    a, b, c = sx, 0.0, min(rxs) - sx * min(oxs)
    d, e, f = 0.0, sy, min(rys) - sy * min(oys)
    return ((a, b, c, d, e, f), "bbox-fallback")


def format_xorg_matrix(coeffs: tuple[float, float, float, float, float, float]) -> str:
    a, b, c, d, e, f = coeffs
    return (
        f'Option "TransformationMatrix" '
        f'"{a:.8f} {b:.8f} {c:.8f} {d:.8f} {e:.8f} {f:.8f} 0 0 1"'
    )


@dataclass
class CalSession:
    screen: ScreenGeom
    observed: list[Corner] = field(default_factory=list)
    hits: list[TouchHit] = field(default_factory=list)
    jumps: list[JumpVerdict] = field(default_factory=list)

    def targets(self) -> list[Corner]:
        return self.screen.corner_targets()

    def add_hit(self, hit: TouchHit, screens: Sequence[ScreenGeom]) -> JumpVerdict:
        self.hits.append(hit)
        v = diagnose_hit(screens, hit)
        self.jumps.append(v)
        return v

    def record_corner(self, global_x: float, global_y: float) -> int:
        """Append observed corner; return new count (1..4)."""
        if len(self.observed) >= 4:
            return 4
        self.observed.append((global_x, global_y))
        return len(self.observed)

    def solve(self) -> dict | None:
        if len(self.observed) < 4:
            return None
        ref = self.targets()
        fit = fit_affine_4pt(self.observed, ref)
        if fit is None:
            return None
        coeffs, method = fit
        return {
            "screen": asdict(self.screen),
            "method": method,
            "observed": list(self.observed),
            "reference": list(ref),
            "matrix": list(coeffs),
            "xorg_line": format_xorg_matrix(coeffs),
            "jump_count": sum(1 for j in self.jumps if j.jump),
            "hits": [asdict(h) for h in self.hits],
            "note": (
                "On Plasma Wayland, TransformationMatrix is not applied by this tool; "
                "use the jump_count / hit vs geom mismatch to file a KWin seat-routing bug. "
                "Xorg line is for comparison / nested X11 only."
            ),
        }
