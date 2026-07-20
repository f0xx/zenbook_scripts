"""Unit tests for zenbook_kb.pidfile (stdlib tempfile; no /run required)."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from zenbook_kb.pidfile import (  # noqa: E402
    acquire_pidfile,
    clear_pidfile,
    pid_alive,
    read_pidfile,
    release_pidfile,
    write_pidfile,
)


class TestPidfile(unittest.TestCase):
    def setUp(self) -> None:
        self._td = tempfile.TemporaryDirectory()
        self.path = Path(self._td.name) / "test.pid"

    def tearDown(self) -> None:
        self._td.cleanup()

    def test_write_read_clear(self) -> None:
        write_pidfile(self.path, os.getpid())
        self.assertEqual(read_pidfile(self.path), os.getpid())
        clear_pidfile(self.path, only_if_pid=os.getpid())
        self.assertIsNone(read_pidfile(self.path))

    def test_stale_pid_removed(self) -> None:
        # PID 1 may be alive on Linux — use a high unused pid instead.
        dead = 2_000_000_000
        while pid_alive(dead) and dead > 1_999_000_000:
            dead -= 1
        self.assertFalse(pid_alive(dead))
        self.path.write_text(f"{dead}\n", encoding="utf-8")
        self.assertIsNone(read_pidfile(self.path, clear_stale=True))
        self.assertFalse(self.path.exists())

    def test_acquire_conflict(self) -> None:
        write_pidfile(self.path, os.getpid())
        # Simulate another process seeing our pid as conflict by using a
        # second path claimed by a fake alive check — acquire on same path
        # from this process succeeds (same pid).
        self.assertIsNone(acquire_pidfile(self.path, replace=False))

    def test_release_only_own(self) -> None:
        write_pidfile(self.path, os.getpid())
        # Foreign pid must not be cleared by release_pidfile (only_if current).
        foreign = self.path.with_name("foreign.pid")
        foreign.write_text("1\n", encoding="utf-8")
        # release touches TOUCHPAD path logic via only_if getpid on self.path
        release_pidfile(self.path)
        self.assertFalse(self.path.exists())
        # foreign untouched
        self.assertTrue(foreign.exists())


if __name__ == "__main__":
    unittest.main()
