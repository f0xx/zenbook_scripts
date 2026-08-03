"""Tests for user profiles schema."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from zenbook_kb.user_profiles import (  # noqa: E402
    default_document,
    normalize,
    reset_mode,
    set_active_mode,
)


class TestUserProfiles(unittest.TestCase):
    def test_normalize_builtin_modes(self) -> None:
        doc = normalize({"active_mode": "quiet"})
        self.assertIn("auto", doc["modes"])
        self.assertFalse(doc["modes"]["auto"]["editable"])
        self.assertTrue(doc["modes"]["quiet"]["editable"])

    def test_set_active_mode(self) -> None:
        doc = set_active_mode("performance")
        self.assertEqual(doc["active_mode"], "performance")

    def test_reset_mode(self) -> None:
        doc = default_document()
        doc["modes"]["quiet"]["schedule"]["enabled"] = True
        doc = reset_mode("quiet", doc)
        self.assertFalse(doc["modes"]["quiet"]["schedule"]["enabled"])


if __name__ == "__main__":
    unittest.main()
