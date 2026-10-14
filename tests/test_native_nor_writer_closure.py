import importlib.util
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).parents[1] / 'tools/native/verify_nor_writer_closure.py'
BUILDER = SCRIPT.parents[0] / 'build_application_probe.py'
ALLOWLIST_SCRIPT = SCRIPT.parents[0] / 'audit_ram_call_allowlist.py'
ALLOWLIST_SPEC = importlib.util.spec_from_file_location('audit_ram_call_allowlist', ALLOWLIST_SCRIPT)
ALLOWLIST = importlib.util.module_from_spec(ALLOWLIST_SPEC)
ALLOWLIST_SPEC.loader.exec_module(ALLOWLIST)
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

    def test_ram_call_audit_detects_writer_outcall(self):
        listing = 'fl_erase4k_ram:\n 1c00000: call 0 <xip_helper>\nfl_prog_ram:\n 1c00010: nop\n'
        calls, writer_calls = MODULE.audit_ram_calls(listing)
        self.assertEqual(len(calls), 1)
        self.assertEqual(writer_calls, calls)
        self.assertEqual(writer_calls[0]['function'], 'fl_erase4k_ram')


    def test_ram_call_audit_refuses_empty_or_missing_writer_disassembly(self):
        for listing, message in (
                ('', 'no instructions'),
                ('fl_erase4k_ram:\n 1c00000: nop\n', 'missing writer function')):
            with self.subTest(message=message):
                with self.assertRaisesRegex(ValueError, message):
                    MODULE.audit_ram_calls(listing)

    def test_ram_call_audit_refuses_unattributed_or_malformed_calls(self):
        for listing, message in (
                (' 1c00000: call 0 <helper>\n', 'no containing function'),
                ('call malformed\n', 'without an address'),
                ('fl_erase4k_ram:\nfl_prog_ram:\n 1c00010: nop\n',
                 'empty writer function'),
                ('fl_erase4k_ram:\n 1c00000: call\nfl_prog_ram:\n 1c00010: nop\n',
                 'target is malformed')):
            with self.subTest(message=message):
                with self.assertRaisesRegex(ValueError, message):
                    MODULE.audit_ram_calls(listing)

    def test_builder_allowlists_only_exact_checked_jedec_ram_call(self):
        disassembly = """Disassembly of section .ram_text:
fl_jedec_checked_ram:
 1c00004: nop
fl_jedec_ram:
 1c00184: call -394 <fl_jedec_checked_ram : 1c00004 >
 1c0018e: rts
"""
        symbols = """01c00004 l F .ram_text 00000180 fl_jedec_checked_ram
01c00184 l F .ram_text 00000016 fl_jedec_ram
"""
        result = ALLOWLIST.audit_ram_call_allowlist(disassembly, symbols)
        self.assertTrue(result['passed'])
        self.assertEqual(result['allowed_calls'][0]['target_address'], 0x1c00004)

    def test_builder_ram_allowlist_rejects_missing_malformed_and_untrusted_calls(self):
        base_symbols = """01c00004 l F .ram_text 00000004 fl_jedec_checked_ram
01c00008 l F .ram_text 00000004 fl_jedec_ram
"""
        cases = (
            ('', 'no instructions'),
            ('fl_jedec_checked_ram:\n 1c00004: nop\nfl_jedec_ram:\n 1c00008: rts\n',
             'expected exactly one'),
            ('fl_jedec_checked_ram:\n 1c00004: nop\nfl_jedec_ram:\n 1c00008: call r4\n',
             'malformed or indirect'),
            ('fl_jedec_checked_ram:\n 1c00004: nop\nfl_jedec_ram:\n 1c00008: nop\nother_ram:\n 1c00010: call 0 <fl_jedec_checked_ram : 1c00004 >\n',
             'unexpected RAM call caller'),
            ('fl_jedec_checked_ram:\n 1c00004: nop\nfl_jedec_ram:\n 1c00008: call 0 <xip_helper : 02001000 >\n',
             'unexpected RAM call target'),
            ('fl_jedec_checked_ram:\n 1c00004: nop\nfl_jedec_ram:\n 1c00008: call 0 <fl_jedec_checked_ram : 1c00010 >\n',
             'target address does not match'),
            # A forged function label cannot attribute an instruction outside
            # the symbol-table extent to the expected RAM function.
            ('fl_jedec_checked_ram:\n 1c00004: nop\nfl_jedec_ram:\n 1c00010: call 0 <fl_jedec_checked_ram : 1c00004 >\n',
             'instruction address outside linked RAM symbol fl_jedec_ram'),
            # The helper label is also checked against its linked extent.
            ('fl_jedec_checked_ram:\n 1c00010: nop\nfl_jedec_ram:\n 1c00008: call 0 <fl_jedec_checked_ram : 1c00004 >\n',
             'instruction address outside linked RAM symbol fl_jedec_checked_ram'),
        )
        for listing, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(ValueError, message):
                    ALLOWLIST.audit_ram_call_allowlist(listing, base_symbols)

    def test_builder_ram_allowlist_rejects_missing_required_symbol(self):
        with self.assertRaisesRegex(ValueError, 'missing RAM symbol'):
            ALLOWLIST.audit_ram_call_allowlist(
                'fl_jedec_ram:\n 1c00008: call 0 <fl_jedec_checked_ram : 1c00004 >\n',
                '01c00008 l F .ram_text 00000004 fl_jedec_ram\n')

    def test_dinghy_inventory_distinguishes_upstream_and_local_flash_header(self):
        import hashlib
        import json
        inventory = json.loads((SCRIPT.parents[2] / 'firmware/third_party/dinghy/inventory.json').read_text())
        name = 'hal/fm1_flash.h'
        record = inventory['local_modifications'][name]
        current = hashlib.sha256((SCRIPT.parents[2] / 'firmware/third_party/dinghy' / name).read_bytes()).hexdigest()
        self.assertEqual(inventory['files'][name], current)
        self.assertEqual(record['local_sha256'], current)
        self.assertEqual(record['upstream_sha256'], 'ee9700389d8bf842606b7210e52e125c085a44fbb5d30301cf189d823c4d5e90')
        self.assertNotEqual(record['upstream_sha256'], record['local_sha256'])
        self.assertIn('prior interrupt-enable', record['reason'])

    def test_overlay_copies_only_git_tracked_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'checkout'
            root.mkdir()
            subprocess.run(['git', 'init', '-q', str(root)], check=True)
            (root / 'tracked.txt').write_text('tracked')
            builder = root / 'tools/native/build_application_probe.py'
            builder.parent.mkdir(parents=True)
            builder.write_text('builder')
            (root / 'scratch').mkdir()
            (root / 'scratch/large.bin').write_bytes(b'x')
            subprocess.run(['git', '-C', str(root), 'add', 'tracked.txt',
                            'tools/native/build_application_probe.py'], check=True)
            destination = Path(directory) / 'overlay'
            original_root = MODULE.ROOT
            try:
                MODULE.ROOT = root
                MODULE.copy_tracked_source(destination)
            finally:
                MODULE.ROOT = original_root
            self.assertEqual((destination / 'tracked.txt').read_text(), 'tracked')
            self.assertFalse((destination / 'scratch').exists())

    def test_overlay_refuses_builder_source_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            copied = Path(directory) / 'builder.py'
            copied.write_text('not the pinned builder')
            with self.assertRaisesRegex(SystemExit, 'expected one exact anchor'):
                MODULE.patch_builder(copied)


if __name__ == '__main__':
    unittest.main()
