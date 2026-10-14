import importlib.util
from pathlib import Path
import shutil
import tempfile
import unittest

SCRIPT = Path(__file__).parents[1] / 'tools/native/verify_nor_writer_closure.py'
BUILDER = SCRIPT.parents[0] / 'build_application_probe.py'
SPEC = importlib.util.spec_from_file_location('verify_nor_writer_closure', SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class NorWriterClosureAnalysisTests(unittest.TestCase):
    def test_hypothetical_extents_do_not_cross_reserved_ranges(self):
        MODULE.validate_extents()
        self.assertTrue(MODULE.in_extent(0xD9000, 4096))
        self.assertTrue(MODULE.in_extent(0xEA000, 4096))
        self.assertFalse(MODULE.in_extent(0xE4FFF, 2))
        self.assertFalse(MODULE.in_extent(0xE8FFF, 2))
        self.assertFalse(MODULE.in_extent(0xE9FFF, 2))
        self.assertFalse(MODULE.in_extent(0xF5FFF, 2))
        self.assertFalse(MODULE.in_extent(0xFFFFFFFF, 2))

    def test_overlay_retains_real_writer_and_suppresses_package_generation(self):
        with tempfile.TemporaryDirectory() as directory:
            copied = Path(directory) / 'build_application_probe.py'
            shutil.copyfile(BUILDER, copied)
            _, patched = MODULE.patch_builder(copied)
        self.assertIn(MODULE.MACRO, patched)
        self.assertIn('lunar_nor_closure_analysis_force_retain', patched)
        self.assertIn('analysis-only.json', patched)
        self.assertNotIn('probe_artifact.py', patched)
        self.assertNotIn('Timed probe: no NOR writes', patched)
        self.assertIn('force_source = ', patched)

    def test_ram_call_audit_attributes_calls_to_ram_function(self):
        listing = """Disassembly of section .ram_text:
fl_erase4k_ram:
 1c00000:    nop
fl_prog_ram:
 1c00020:    nop
fl_jedec_ram:
 1c00040:    call 4 <fl_jedec_checked_ram : 1c00050 >
fl_jedec_checked_ram:
 1c00050:    nop
"""
        calls, writer_calls = MODULE.audit_ram_calls(listing)
        self.assertEqual(writer_calls, [])
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]['function'], 'fl_jedec_ram')
        self.assertIn('fl_jedec_checked_ram', calls[0]['target'])

    def test_overlay_refuses_builder_source_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            copied = Path(directory) / 'builder.py'
            copied.write_text('not the pinned builder')
            with self.assertRaisesRegex(SystemExit, 'expected one exact anchor'):
                MODULE.patch_builder(copied)


if __name__ == '__main__':
    unittest.main()
