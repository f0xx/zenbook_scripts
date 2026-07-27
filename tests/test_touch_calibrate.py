#!/usr/bin/env python3
"""Tests for dual-eDP touch calibration math."""

from __future__ import annotations

import unittest

from zenbook_kb.touch_calibrate import (
    ScreenGeom,
    TouchHit,
    diagnose_hit,
    fit_affine_4pt,
    format_xorg_matrix,
)


class TouchCalibrateTests(unittest.TestCase):
    def test_diagnose_consistent(self) -> None:
        screens = [
            ScreenGeom("eDP-1", 0, 0, 1920, 1080, primary=True),
            ScreenGeom("eDP-2", 0, 1080, 1920, 1080),
        ]
        hit = TouchHit(100, 1200, "eDP-2")
        v = diagnose_hit(screens, hit)
        self.assertFalse(v.jump)

    def test_diagnose_jump(self) -> None:
        screens = [
            ScreenGeom("eDP-1", 0, 0, 1920, 1080, primary=True),
            ScreenGeom("eDP-2", 0, 1080, 1920, 1080),
        ]
        # Event delivered to primary window but coords are on lower panel
        hit = TouchHit(100, 1200, "eDP-1")
        v = diagnose_hit(screens, hit)
        self.assertTrue(v.jump)
        self.assertEqual(v.geom_screen, "eDP-2")

    def test_affine_identity(self) -> None:
        ref = [(10.0, 10.0), (90.0, 10.0), (90.0, 90.0), (10.0, 90.0)]
        obs = list(ref)
        fit = fit_affine_4pt(obs, ref)
        self.assertIsNotNone(fit)
        coeffs, method = fit  # type: ignore[misc]
        self.assertIn(method, ("affine-3pt", "bbox-fallback"))
        a, b, c, d, e, f = coeffs
        # near identity
        self.assertAlmostEqual(a, 1.0, places=4)
        self.assertAlmostEqual(e, 1.0, places=4)
        line = format_xorg_matrix(coeffs)
        self.assertIn("TransformationMatrix", line)

    def test_corner_order(self) -> None:
        s = ScreenGeom("eDP-2", 0, 1080, 1000, 1000)
        t = s.corner_targets(inset=0.1)
        self.assertEqual(len(t), 4)
        # TL has smaller x+y than BR
        self.assertLess(t[0][0] + t[0][1], t[2][0] + t[2][1])


if __name__ == "__main__":
    unittest.main()
