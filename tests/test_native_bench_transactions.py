"""Offline native plans cannot expand into protected stock sectors."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from native.bench_transactions import (changed_ranges, APP_BASE,
                                       PROTECTED_END_START, FLASH_SIZE)


class RangeTests(unittest.TestCase):
    def test_old_larger_application_tail_is_included(self):
        before = bytes(FLASH_SIZE)
        after = bytearray(before)
        after[APP_BASE] = 1
        after[APP_BASE + 8192] = 1
        after[APP_BASE + 120000] = 1
        ranges = changed_ranges(before, bytes(after))
        self.assertEqual(ranges, [[APP_BASE, APP_BASE + 4096],
                                 [APP_BASE + 8192, APP_BASE + 12288],
                                 [APP_BASE + 118784, APP_BASE + 122880]])

    def test_protected_bootloader_or_config_change_refused(self):
        before = bytes(FLASH_SIZE)
        for address in (0, APP_BASE - 1, PROTECTED_END_START, FLASH_SIZE - 1):
            with self.subTest(address=address):
                after = bytearray(before)
                after[address] = 1
                with self.assertRaisesRegex(ValueError, 'Protected'):
                    changed_ranges(before, bytes(after))

    def test_application_byte_in_shared_config_sector_refused(self):
        before = bytes(FLASH_SIZE)
        after = bytearray(before)
        after[PROTECTED_END_START - 1] = 1
        with self.assertRaisesRegex(ValueError, 'overlaps protected'):
            changed_ranges(before, bytes(after))

    def test_incomplete_or_equal_images_do_not_create_scope(self):
        before = bytes(FLASH_SIZE)
        for after in (before, before[:-1], bytearray(before)):
            with self.subTest(size=len(after)):
                with self.assertRaises(ValueError):
                    changed_ranges(before, after)


if __name__ == '__main__':
    unittest.main()
