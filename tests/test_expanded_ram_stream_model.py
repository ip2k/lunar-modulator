"""Standard-library model tests; offline only, with synthetic NOR bytes."""
import hashlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/native"))
import expanded_ram_stream_model as stream
import expanded_flash_profile as expanded
import raw_flash_profile as raw


def fixture():
    baseline = bytes([0xFF]) * raw.FLASH_BYTES
    target = bytearray(baseline)
    # Two changed app sectors force the directory sector to be scheduled last.
    target[0x4000:0x5000] = bytes([0xA5]) * 4096
    target[0x5000:0x6000] = bytes([0x5A]) * 4096
    target = bytes(target)
    manifest = dict(
        schema=1, status="offline-expanded-transport-manifest",
        profile=stream.PROFILE, target_sha256=hashlib.sha256(target).hexdigest(),
        target_bytes=len(target), baseline_sha256=hashlib.sha256(baseline).hexdigest(),
        changed_sectors=[0x4000, 0x5000], sector_order=[0x5000, 0x4000],
        directory_sector=0x4000, protected_ranges=[[0, 0x4000],
                                                    [expanded.AREA_END, raw.FLASH_BYTES]],
        geometry_verified=True, receipt_correspondence_verified=True,
        hardware_admitted=False, physical_writer_ready=False,
        settings_migration_verified=False, recovery_verified=False,
        installable=False, device_io_performed=False)
    pin = hashlib.sha256(stream.canonical_json(manifest)).hexdigest()
    return baseline, target, manifest, pin


class ExpandedRamStreamModelTests(unittest.TestCase):
    def test_bounded_sequential_directory_last_responses(self):
        baseline, target, manifest, pin = fixture()
        model = stream.ExpandedRamStreamModel(baseline, target, manifest, pin)
        self.assertEqual(model.max_response_bytes, 512)
        self.assertEqual(model.sector_order, (0x5000, 0x4000))
        self.assertFalse(hasattr(model, "flash"))
        reconstructed = bytearray()
        while not model.complete:
            request = model.next_request()
            self.assertEqual(request.length, 512)
            self.assertLessEqual(request.length, model.max_response_bytes)
            self.assertLessEqual(request.image_offset + request.length,
                                 request.sector_offset + 4096)
            reconstructed.extend(model.respond(request))
        self.assertIsNone(model.next_request())
        self.assertEqual(bytes(reconstructed[:4096]), target[0x5000:0x6000])
        self.assertEqual(bytes(reconstructed[4096:]), target[0x4000:0x5000])

    def test_rejects_unpinned_stale_and_protected_changes(self):
        baseline, target, manifest, pin = fixture()
        with self.assertRaisesRegex(ValueError, "pinned hash"):
            stream.ExpandedRamStreamModel(baseline, target, manifest, "0" * 64)
        stale = target[:-1] + bytes([target[-1] ^ 1])
        with self.assertRaisesRegex(ValueError, "another image"):
            stream.ExpandedRamStreamModel(baseline, stale, manifest, pin)
        altered = bytearray(target)
        altered[0] ^= 1
        altered = bytes(altered)
        value = dict(manifest, target_sha256=hashlib.sha256(altered).hexdigest())
        altered_pin = hashlib.sha256(stream.canonical_json(value)).hexdigest()
        with self.assertRaisesRegex(ValueError, "outside the expanded app region"):
            stream.ExpandedRamStreamModel(baseline, altered, value, altered_pin)

    def test_rejects_admission_foreign_sector_and_reordered_plan(self):
        baseline, target, manifest, _ = fixture()
        for mutation in ("admitted", "foreign", "order"):
            value = dict(manifest)
            if mutation == "admitted":
                value["installable"] = True
            elif mutation == "foreign":
                value["changed_sectors"] = [0x4000, 0x5000, 0xD9000]
                value["sector_order"] = [0x5000, 0xD9000, 0x4000]
            else:
                value["sector_order"] = [0x4000, 0x5000]
            value_pin = hashlib.sha256(stream.canonical_json(value)).hexdigest()
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                stream.ExpandedRamStreamModel(baseline, target, value, value_pin)

    def test_rejects_replay_and_out_of_order_response(self):
        baseline, target, manifest, pin = fixture()
        model = stream.ExpandedRamStreamModel(baseline, target, manifest, pin)
        first = model.next_request()
        second = model._requests[1]
        with self.assertRaisesRegex(ValueError, "next authorized"):
            model.respond(second)
        model.respond(first)
        with self.assertRaisesRegex(ValueError, "next authorized"):
            model.respond(first)


if __name__ == "__main__":
    unittest.main()
