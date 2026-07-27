#!/usr/bin/env python3
"""Unit tests for DMI model helpers (no real sysfs required)."""

from __future__ import annotations

import unittest
from unittest import mock

from zenbook_kb import dmi


class DmiModelTests(unittest.TestCase):
    def test_is_duo_chassis_ux8406(self) -> None:
        with mock.patch.object(dmi, "product_name", return_value="Zenbook Duo UX8406MA"):
            with mock.patch.object(dmi, "board_name", return_value="UX8406MA"):
                self.assertTrue(dmi.is_duo_chassis())
                self.assertTrue(dmi.is_ux8406())
                self.assertFalse(dmi.is_ux5400())

    def test_is_duo_chassis_ux581(self) -> None:
        with mock.patch.object(dmi, "product_name", return_value="ZenBook Pro Duo UX581GV"):
            with mock.patch.object(dmi, "board_name", return_value="UX581GV"):
                self.assertTrue(dmi.is_duo_chassis())

    def test_ux5400_not_duo(self) -> None:
        with mock.patch.object(dmi, "product_name", return_value="Zenbook Flip UX5400EA"):
            with mock.patch.object(dmi, "board_name", return_value="UX5400EA"):
                self.assertFalse(dmi.is_duo_chassis())
                self.assertTrue(dmi.is_ux5400())


if __name__ == "__main__":
    unittest.main()
