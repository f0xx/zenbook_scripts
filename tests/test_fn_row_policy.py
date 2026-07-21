"""UX8406 fn_row_policy=7 — F4–F12 swap; F1–F3 firmware+EC (no invert).

Every chord is a full press/release sequence. After it ends, Meta must NOT be
held. A follow-up Fn+Fx must see a clean modifier state (no sticky Meta).

Run: python3 -m unittest tests.test_fn_row_policy -v
"""

from __future__ import annotations

import unittest
from dataclasses import dataclass, field
from enum import Enum


class Key(Enum):
    LEFTMETA = "LEFTMETA"
    F1 = "F1"
    F2 = "F2"
    F3 = "F3"
    F4 = "F4"
    F5 = "F5"
    F6 = "F6"
    F7 = "F7"
    F8 = "F8"
    F9 = "F9"
    F10 = "F10"
    F11 = "F11"
    F12 = "F12"
    MUTE = "MUTE"
    VOLUMEDOWN = "VOLUMEDOWN"
    VOLUMEUP = "VOLUMEUP"
    BRIGHTNESSDOWN = "BRIGHTNESSDOWN"
    BRIGHTNESSUP = "BRIGHTNESSUP"
    PROG1 = "PROG1"
    P = "P"
    MICMUTE = "MICMUTE"
    RFKILL = "RFKILL"
    F15 = "F15"
    EMOJI_PICKER = "EMOJI_PICKER"


@dataclass
class Ev:
    key: Key
    value: int


# ---------------------------------------------------------------------------
# ACTION TABLE (policy=7) — plain F1–F3 → KEY_Fn; Fn+F1–F3 EC vol; F4–F12 swap
# ---------------------------------------------------------------------------

ACTION_TABLE = """
| # | Action sequence              | Must observe                         | Must NOT |
|---|------------------------------|--------------------------------------|----------|
| 1 | plain F1                     | bare F1; Meta idle at end            | MUTE / Meta held |
| 2 | Fn+F1                        | MUTE pulse; Meta idle                | bare F1 / Meta+F1 |
| 3 | Meta+F1                      | Meta↓ F1↕ Meta↑; Meta idle at end    | sticky Meta |
| 4 | plain F7                     | bare F7; zero Meta events            | Meta flash |
| 5 | Fn+F7                        | Meta+P; Meta idle at end             | sticky Meta |
| 6 | Meta+F8 (+ trailing GUI)     | Meta↓ F8↕ Meta↑; no Super tap        | sticky / plain Meta |
| 7 | Super tap                    | Meta↕; Meta idle                     | sticky Meta |
| 8 | Meta+F1 → Fn+F5              | then BRIGHTNESSDOWN (not Meta+F5)    | sticky Meta |
| 9 | Meta+F1 → Fn+F1              | then bare F1 (not Meta+F1)           | sticky Meta |
|10 | Meta+F1 → plain F1           | then bare F1 (not Meta+F1)           | sticky Meta |
|11 | Fn+Meta+F1 (GUI+F1 if0)      | Meta↓ F1↕ Meta↑                      | sticky Meta |
|12 | Fn+F9                        | MICMUTE pulse                        | bare F9 / nothing |
|13 | plain F9                     | bare F9                              | MICMUTE |
|14 | Fn+F8                        | KEY_F15 (screen swap)                | RFKILL / bare F8 |
|15 | Meta+F9                      | Meta↓ F9↕ Meta↑; Meta idle           | sticky / Super tap |
|16 | plain F8                     | bare F8 (vendor 0x9c)                | F15 / RFKILL |
|17 | Fn+F10                       | RFKILL pulse                         | bare F10 |
"""


@dataclass
class Sim:
    """Mirror of deferred-GUI + synthetic-Meta policy (policy=7)."""

    policy: int = 7  # F4–F12 swap; F1–F3 bits ignored
    mods: int = 0
    gui_deferred: bool = False
    gui_suppress_tap: bool = False
    meta_synthetic: bool = False  # we injected Meta↓ — must Meta↑ ourselves
    out: list[Ev] = field(default_factory=list)
    prev: bytes = b"\x00" * 8

    GUI = 0x08
    HID_P = 0x13

    def _bit(self, n: int) -> bool:
        return bool(self.policy & (1 << n))

    def emit(self, key: Key, value: int) -> None:
        self.out.append(Ev(key, value))

    def emit_pulse(self, key: Key) -> None:
        self.emit(key, 1)
        self.emit(key, 0)

    def meta_held(self) -> bool:
        n = 0
        for e in self.out:
            if e.key == Key.LEFTMETA:
                n += 1 if e.value == 1 else -1
        return n > 0

    def emit_meta_down(self) -> None:
        if self.meta_held():
            return
        self.emit(Key.LEFTMETA, 1)
        self.meta_synthetic = True

    def clear_meta(self) -> None:
        if self.meta_held():
            self.emit(Key.LEFTMETA, 0)
        self.meta_synthetic = False

    def emit_meta_tap(self) -> None:
        self.emit(Key.LEFTMETA, 1)
        self.emit(Key.LEFTMETA, 0)
        self.meta_synthetic = False

    def ensure_meta_for_workspace(self) -> None:
        if self.gui_deferred:
            self.gui_deferred = False
            self.emit_meta_down()

    def _release_synthetic_meta(self) -> None:
        if self.meta_synthetic:
            self.clear_meta()

    def meta_emit_fkey(self, bit: int) -> None:
        self.ensure_meta_for_workspace()
        self.emit_pulse(Key[f"F{bit + 1}"])

    def keys_empty(self, data: bytes) -> bool:
        return all(b == 0 for b in data[2:8])

    def feed_if0(self, data: bytes) -> None:
        """Main keyboard report (modifiers + usages)."""
        assert len(data) == 8
        gui = bool(data[0] & self.GUI)
        prev_gui = bool(self.prev[0] & self.GUI)
        self.mods = data[0]

        # Rising GUI-only → defer (may be Win+P or Meta+Fx precursor)
        if gui and self.keys_empty(data) and not prev_gui:
            if self.meta_synthetic:
                self.prev = data
                return
            self.gui_deferred = True
            self.prev = data
            return

        # GUI release / idle clear — synthetic Meta↑ (HID will not clear inject)
        if not gui:
            if self.gui_suppress_tap:
                self.gui_suppress_tap = False
                self.gui_deferred = False
                self._release_synthetic_meta()
                self.prev = data
                return
            if self.gui_deferred:
                self.gui_deferred = False
                if self.keys_empty(data):
                    self.emit_meta_tap()
                self.prev = data
                return
            if prev_gui or self.meta_synthetic:
                self._release_synthetic_meta()
                self.prev = data
                return

        # Meta+P (firmware plain F7) → bare F7 when bit 6 clear
        if gui and data[2] == self.HID_P and not self._bit(6):
            if self.gui_deferred:
                self.gui_deferred = False
            self.emit_pulse(Key.F7)
            self.gui_suppress_tap = True
            self.prev = data
            return

        # Meta+Fx usages on if0
        if gui and data[2] != 0:
            hid = data[2]
            if 0x3A <= hid <= 0x45:  # F1-F12
                bit = hid - 0x3A
                if bit != 3:  # F4 via vendor
                    self.ensure_meta_for_workspace()
                    self.emit_pulse(Key[f"F{bit + 1}"])
            self.prev = data
            return

        self.prev = data

    def feed_if3_media(self, bit: int) -> None:
        # Plain F1–F3: if3 media → KEY_Fn. Meta → workspace KEY_Fn.
        if self.mods & self.GUI:
            self.meta_emit_fkey(bit)
            return
        self.emit_pulse(Key[f"F{bit + 1}"])

    def feed_if4_vendor_plain(self, code: int) -> None:
        table = {
            0xC7: (3, Key.F4),
            0x10: (4, Key.F5),
            0x20: (5, Key.F6),
            0x35: (6, Key.F7),
            0x9C: (7, Key.F8),
            0x7C: (8, Key.F9),
            0x88: (9, Key.F10),
            0x7E: (10, Key.F11),
            0x86: (11, Key.F12),
        }
        bit, fkey = table[code]
        if self.mods & self.GUI:
            self.ensure_meta_for_workspace()
            self.emit_pulse(fkey)
            return
        if not self._bit(bit):
            self.emit_pulse(fkey)

    def feed_fn_special(self, bit: int) -> None:
        # F1–F3: Mode B if0 KEY_Fn → media (always when policy on).
        if bit == 0:
            self.emit_pulse(Key.MUTE)
            return
        if bit == 1:
            self.emit_pulse(Key.VOLUMEDOWN)
            return
        if bit == 2:
            self.emit_pulse(Key.VOLUMEUP)
            return
        if bit == 4:
            self.emit_pulse(Key.BRIGHTNESSDOWN)
        elif bit == 5:
            self.emit_pulse(Key.BRIGHTNESSUP)
        elif bit == 6:
            self.emit(Key.LEFTMETA, 1)
            self.emit(Key.P, 1)
            self.emit(Key.P, 0)
            self.emit(Key.LEFTMETA, 0)
            self.meta_synthetic = False
        elif bit == 7:
            self.emit_pulse(Key.F15)
        elif bit == 8:
            self.emit_pulse(Key.MICMUTE)
        elif bit == 9:
            self.emit_pulse(Key.RFKILL)
        elif bit == 10:
            self.emit_pulse(Key.EMOJI_PICKER)
        elif bit == 11:
            self.emit_pulse(Key.PROG1)

    def chord_plain_f1(self) -> None:
        self.feed_if3_media(0)

    def chord_fn_f1(self) -> None:
        self.feed_fn_special(0)

    def chord_meta_f1(self) -> None:
        self.feed_if0(bytes([0x08, 0, 0, 0, 0, 0, 0, 0]))
        self.feed_if3_media(0)
        self.feed_if0(bytes(8))

    def chord_plain_f7(self) -> None:
        self.feed_if0(bytes([0x08, 0, 0, 0, 0, 0, 0, 0]))
        self.feed_if0(bytes([0x08, 0, 0x13, 0, 0, 0, 0, 0]))
        self.feed_if0(bytes([0x08, 0, 0, 0, 0, 0, 0, 0]))
        self.feed_if0(bytes(8))

    def chord_fn_f7(self) -> None:
        self.feed_fn_special(6)

    def chord_meta_f8(self) -> None:
        self.feed_if0(bytes([0x08, 0, 0, 0, 0, 0, 0, 0]))
        self.feed_if0(bytes([0x08, 0, 0x41, 0, 0, 0, 0, 0]))
        self.feed_if0(bytes([0x08, 0, 0, 0, 0, 0, 0, 0]))
        self.feed_if0(bytes(8))

    def chord_meta_f9(self) -> None:
        self.feed_if0(bytes([0x08, 0, 0, 0, 0, 0, 0, 0]))
        self.feed_if0(bytes([0x08, 0, 0x42, 0, 0, 0, 0, 0]))
        self.feed_if0(bytes([0x08, 0, 0, 0, 0, 0, 0, 0]))
        self.feed_if0(bytes(8))

    def chord_fn_f8(self) -> None:
        self.feed_fn_special(7)

    def chord_fn_f9(self) -> None:
        self.feed_fn_special(8)

    def chord_plain_f9(self) -> None:
        self.feed_if4_vendor_plain(0x7C)

    def chord_plain_f8(self) -> None:
        self.feed_if4_vendor_plain(0x9C)

    def chord_fn_f10(self) -> None:
        self.feed_fn_special(9)

    def chord_meta_f5(self) -> None:
        self.feed_if0(bytes([0x08, 0, 0, 0, 0, 0, 0, 0]))
        self.mods = self.GUI
        self.feed_if4_vendor_plain(0x10)
        self.feed_if0(bytes(8))

    def chord_fn_f5(self) -> None:
        self.feed_fn_special(4)

    def chord_super_tap(self) -> None:
        self.feed_if0(bytes([0x08, 0, 0, 0, 0, 0, 0, 0]))
        self.feed_if0(bytes(8))

    def chord_fn_meta_f1(self) -> None:
        self.feed_if0(bytes([0x08, 0, 0, 0, 0, 0, 0, 0]))
        self.feed_if0(bytes([0x08, 0, 0x3A, 0, 0, 0, 0, 0]))
        self.feed_if0(bytes(8))


def _downs(sim: Sim) -> list[Key]:
    return [e.key for e in sim.out if e.value == 1]


def _has_meta_with(sim: Sim, key: Key) -> bool:
    meta = 0
    for e in sim.out:
        if e.key == Key.LEFTMETA:
            meta += 1 if e.value == 1 else -1
        elif e.key == key and e.value == 1 and meta > 0:
            return True
    return False


class TestActionTable(unittest.TestCase):
    def test_doc(self) -> None:
        self.assertIn("KEY_F15", ACTION_TABLE)

    def test_01_plain_f1(self) -> None:
        s = Sim()
        s.chord_plain_f1()
        self.assertEqual(_downs(s), [Key.F1])
        self.assertFalse(s.meta_held(), s.out)

    def test_02_fn_f1(self) -> None:
        s = Sim()
        s.chord_fn_f1()
        self.assertEqual(_downs(s), [Key.MUTE])
        self.assertFalse(s.meta_held(), s.out)
        self.assertFalse(_has_meta_with(s, Key.MUTE))

    def test_03_meta_f1(self) -> None:
        s = Sim()
        s.chord_meta_f1()
        self.assertTrue(_has_meta_with(s, Key.F1), s.out)
        self.assertFalse(s.meta_held(), f"STICKY META after Meta+F1: {s.out}")
        self.assertFalse(s.meta_synthetic)

    def test_04_plain_f7(self) -> None:
        s = Sim()
        s.chord_plain_f7()
        self.assertEqual(_downs(s), [Key.F7])
        self.assertFalse(any(e.key == Key.LEFTMETA for e in s.out), s.out)
        self.assertFalse(s.meta_held())

    def test_05_fn_f7(self) -> None:
        s = Sim()
        s.chord_fn_f7()
        self.assertEqual(_downs(s), [Key.LEFTMETA, Key.P])
        self.assertFalse(s.meta_held(), s.out)

    def test_06_meta_f8(self) -> None:
        s = Sim()
        s.chord_meta_f8()
        self.assertTrue(_has_meta_with(s, Key.F8), s.out)
        self.assertFalse(s.meta_held(), f"STICKY META after Meta+F8: {s.out}")
        meta_downs = sum(1 for e in s.out if e.key == Key.LEFTMETA and e.value == 1)
        self.assertEqual(meta_downs, 1, s.out)

    def test_12_fn_f9_micmute(self) -> None:
        s = Sim()
        s.chord_fn_f9()
        self.assertEqual(_downs(s), [Key.MICMUTE])
        self.assertFalse(s.meta_held())

    def test_13_plain_f9(self) -> None:
        s = Sim()
        s.chord_plain_f9()
        self.assertEqual(_downs(s), [Key.F9])

    def test_14_fn_f8_screen_swap(self) -> None:
        s = Sim()
        s.chord_fn_f8()
        self.assertEqual(_downs(s), [Key.F15])

    def test_15_meta_f9_no_super_tap(self) -> None:
        s = Sim()
        s.chord_meta_f9()
        self.assertTrue(_has_meta_with(s, Key.F9), s.out)
        self.assertFalse(s.meta_held(), s.out)
        meta_downs = sum(1 for e in s.out if e.key == Key.LEFTMETA and e.value == 1)
        self.assertEqual(meta_downs, 1, s.out)

    def test_16_plain_f8(self) -> None:
        s = Sim()
        s.chord_plain_f8()
        self.assertEqual(_downs(s), [Key.F8])

    def test_17_fn_f10_rfkill(self) -> None:
        s = Sim()
        s.chord_fn_f10()
        self.assertEqual(_downs(s), [Key.RFKILL])

    def test_07_super_tap(self) -> None:
        s = Sim()
        s.chord_super_tap()
        self.assertEqual(
            [(e.key, e.value) for e in s.out if e.key == Key.LEFTMETA],
            [(Key.LEFTMETA, 1), (Key.LEFTMETA, 0)],
        )
        self.assertFalse(s.meta_held())

    def test_08_meta_f1_then_fn_f5_not_sticky(self) -> None:
        s = Sim()
        s.chord_meta_f1()
        self.assertFalse(s.meta_held(), f"sticky before Fn+F5: {s.out}")
        before = len(s.out)
        s.chord_fn_f5()
        after = s.out[before:]
        self.assertEqual([e.key for e in after if e.value == 1], [Key.BRIGHTNESSDOWN])
        self.assertFalse(any(e.key == Key.LEFTMETA for e in after), after)
        self.assertFalse(s.meta_held(), s.out)

    def test_09_meta_f1_then_fn_f1_not_meta(self) -> None:
        s = Sim()
        s.chord_meta_f1()
        before = len(s.out)
        s.chord_fn_f1()
        after = s.out[before:]
        self.assertEqual([e.key for e in after if e.value == 1], [Key.MUTE])
        self.assertFalse(any(e.key == Key.LEFTMETA for e in after))
        self.assertFalse(s.meta_held())

    def test_10_meta_f1_then_plain_f1(self) -> None:
        s = Sim()
        s.chord_meta_f1()
        before = len(s.out)
        s.chord_plain_f1()
        after = s.out[before:]
        self.assertEqual([e.key for e in after if e.value == 1], [Key.F1])
        self.assertFalse(s.meta_held())

    def test_11_fn_meta_f1(self) -> None:
        s = Sim()
        s.chord_fn_meta_f1()
        self.assertTrue(_has_meta_with(s, Key.F1), s.out)
        self.assertFalse(s.meta_held(), f"STICKY after Fn+Meta+F1: {s.out}")

    def test_meta_f5_then_fn_f5(self) -> None:
        s = Sim()
        s.chord_meta_f5()
        self.assertFalse(s.meta_held(), s.out)
        before = len(s.out)
        s.chord_fn_f5()
        after = s.out[before:]
        self.assertEqual([e.key for e in after if e.value == 1], [Key.BRIGHTNESSDOWN])


class TestStickyRegressionWithoutRelease(unittest.TestCase):
    def test_missing_release_leaves_sticky(self) -> None:
        s = Sim()
        s.gui_deferred = True
        s.mods = Sim.GUI
        s.meta_emit_fkey(0)
        self.assertTrue(s.meta_held())
        s.feed_if0(bytes(8))
        self.assertFalse(s.meta_held(), s.out)


if __name__ == "__main__":
    print(ACTION_TABLE)
    unittest.main(verbosity=2)
