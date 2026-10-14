"""Logical SFC/header model tests; no target or flash access."""
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/native"))
sys.path.insert(0, str(ROOT / "tools/jieli"))
import app_header_crc_poison_model as model  # noqa: E402
from inspect_fwsc import crc16, sfc_decode  # noqa: E402


def raw_header():
    fields = struct.pack("<HHIIBBH16s", 0, 0xFFFF, 0x02000120, 0x1000,
                         0x83, 0, 0, b"app_area_head\0\0\0")
    decoded = bytearray(fields)
    struct.pack_into("<H", decoded, 0, crc16(decoded[2:]))
    return sfc_decode(bytes(decoded), 0)


class HeaderPoisonModelTests(unittest.TestCase):
    def test_plan_is_one_raw_crc_bit_and_always_disarmed(self):
        raw = raw_header()
        plan = model.plan_crc_poison(raw)
        # The selected raw CRC bit is represented by its byte offset and mask.
        bit_index = (plan.raw_byte_offset - 0x4000) * 8 + plan.bit_mask.bit_length() - 1
        changed = model.simulate_one_bit_clear(raw, bit_index)
        self.assertEqual(changed[plan.raw_byte_offset - 0x4000], plan.expected_raw_byte)
        self.assertFalse(plan.hardware_admitted)
        self.assertFalse(plan.installable)
        self.assertEqual(sfc_decode(changed, 0)[2:], sfc_decode(raw, 0)[2:])
        self.assertEqual(model.spl_route(raw, True, True), "ordinary_xip_selected")
        self.assertEqual(model.spl_route(changed, True, True), "rescue_scan_entry")

    def test_every_available_single_raw_crc_bit_clear_invalidates_only_crc(self):
        raw = raw_header()
        raw_crc = int.from_bytes(raw[:2], "little")
        available = [bit for bit in range(16) if raw_crc & (1 << bit)]
        self.assertTrue(available)
        for bit in available:
            with self.subTest(bit=bit):
                mutated = model.simulate_one_bit_clear(raw, bit)
                before = sfc_decode(raw, 0)
                after = sfc_decode(mutated, 0)
                self.assertEqual(after[2:], before[2:])
                self.assertNotEqual(crc16(after[2:]), int.from_bytes(after[:2], "little"))
                self.assertEqual((int.from_bytes(before[:2], "little") ^
                                  int.from_bytes(after[:2], "little")).bit_count(), 1)

    def test_poison_rejects_bad_header_wrong_bit_and_bad_extent(self):
        raw = raw_header()
        clear_bit = next(bit for bit in range(16)
                         if not (int.from_bytes(raw[:2], "little") & (1 << bit)))
        with self.assertRaisesRegex(ValueError, "already clear"):
            model.simulate_one_bit_clear(raw, clear_bit)
        with self.assertRaisesRegex(ValueError, "exact raw"):
            model.plan_crc_poison(raw[:31])
        damaged = bytearray(raw)
        damaged[2] ^= 1
        with self.assertRaisesRegex(ValueError, "header CRC"):
            model.plan_crc_poison(bytes(damaged))

    def test_rescue_is_only_reachable_after_verified_header_invalidation(self):
        raw = raw_header()
        first_set_bit = next(bit for bit in range(16)
                             if int.from_bytes(raw[:2], "little") & (1 << bit))
        poisoned = model.simulate_one_bit_clear(raw, first_set_bit)
        self.assertFalse(model.payload_mutation_permitted(
            poison_readback_invalid=False, rescue_record_valid=True,
            rescue_loader_valid=True))
        self.assertFalse(model.payload_mutation_permitted(
            poison_readback_invalid=True, rescue_record_valid=False,
            rescue_loader_valid=True))
        self.assertTrue(model.payload_mutation_permitted(
            poison_readback_invalid=True, rescue_record_valid=True,
            rescue_loader_valid=True))
        self.assertEqual(model.spl_route(raw, True, True), "ordinary_xip_selected")
        self.assertEqual(model.spl_route(poisoned, True, True), "rescue_scan_entry")
        self.assertEqual(model.spl_route(poisoned, True, False), "no_verified_entry")
        self.assertEqual(model.spl_route(poisoned, False, True), "no_verified_entry")


if __name__ == "__main__":
    unittest.main()
