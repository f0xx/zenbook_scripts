#!/usr/bin/env python3
"""Unit tests for UX581 lightbar report builders (no hardware)."""

from __future__ import annotations

import unittest

from zenbook_kb.lightbar import (
    BRICK_REGISTER,
    REPORT_ID_COLOR,
    assert_report_safe,
    build_report_0x20,
    format_report_hex,
    hidapitester_cmdline,
    is_ux581_family,
)


class LightbarTests(unittest.TestCase):
    def test_build_safe(self) -> None:
        r = build_report_0x20(anim=1, loop=2, brightness=64, led_count=7)
        self.assertEqual(r[0], REPORT_ID_COLOR)
        self.assertEqual(len(r), 33)
        self.assertEqual(r[BRICK_REGISTER], 0)
        assert_report_safe(r)

    def test_brick_byte_rejected(self) -> None:
        r = bytearray(build_report_0x20())
        r[BRICK_REGISTER] = 1
        with self.assertRaises(ValueError):
            assert_report_safe(bytes(r))

    def test_family_detect(self) -> None:
        self.assertTrue(is_ux581_family("ZenBook Pro Duo UX581GV", "UX581GV"))
        self.assertTrue(is_ux581_family("UX582", ""))
        self.assertFalse(is_ux581_family("UX8406MA", "UX8406MA"))

    def test_hidapitester_line(self) -> None:
        r = build_report_0x20(anim=16)
        line = hidapitester_cmdline(r)
        self.assertIn("0B05/0124", line)
        self.assertIn(format_report_hex(r), line)


if __name__ == "__main__":
    unittest.main()
