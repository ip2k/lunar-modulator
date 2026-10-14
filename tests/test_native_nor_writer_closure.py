import importlib.util
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from nor_writer_target_fixture import TARGET_SYMBOLS, TARGET_DISASSEMBLY, TARGET_RAM_DISASSEMBLY

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

    def test_prepared_profile_file_is_forwarded_as_builder_directory(self):
        profile = Path('/private/selection/prepared/profile.json')
        self.assertEqual(MODULE.prepared_input_directory(profile),
                         Path('/private/selection/prepared'))
        with self.assertRaisesRegex(ValueError, 'named profile.json'):
            MODULE.prepared_input_directory(Path('/private/selection/prepared/other.json'))

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

    def test_linked_writer_audit_requires_real_commands_and_resolved_ram_paths(self):
        symbols = """01c00000 l F .ram_text 00000040 fl_erase4k_ram
01c00040 l F .ram_text 00000040 fl_prog_ram
01c00080 l F .ram_text 00000010 fl_read_ram
01c00090 l F .ram_text 00000010 fl_status_checked_ram
01c000a0 l F .ram_text 00000010 fl_jedec_checked_ram
01c000b0 l F .ram_text 00000010 fl_jedec_ram
0204ebfc l F .text 0000000a fm1_wdt_feed
0204e820 l F .text 00000020 fl_erase4k
0204e840 l F .text 00000044 fl_write
0204e808 l F .text 0000000e irq_save
"""
        disassembly = """fl_erase4k_ram:
 1c00000: [r6+8] = 0x6
 1c00002: [r6+8] = 0x20
 1c00004: [r6+8] = 0x5
 1c00006: goto 2 <fl_erase4k_ram+0x8 : 1c00008 >
 1c00008: rts
fl_prog_ram:
 1c00040: [r7+8] = 0x6
 1c00042: [r7+8] = 0x2
 1c00044: [r7+8] = 0x5
fl_read_ram:
 1c00080: rts
fl_status_checked_ram:
 1c00090: [r5+8] = 0x5
fl_jedec_checked_ram:
 1c000a0: [r5+8] = 0x9F
fl_jedec_ram:
 1c000b0: call 0 <fl_jedec_checked_ram : 1c000a0 >
"""
        result = MODULE.audit_linked_writer(
            disassembly, symbols, "elf: file format ELF32-pi32v2\n", "Sections:\n")
        self.assertTrue(result["passed_static_writer_checks"])
        self.assertTrue(result["static_relocations_absent"])
        self.assertFalse(result["static_data_closure_complete"])
        self.assertTrue(result["direct_branch_bounds_complete"])
        self.assertFalse(result["control_flow_closure_complete"])
        self.assertFalse(result["runtime_pointer_residency_proven"])
        self.assertEqual(result["ram_calls"][0]["function"], "fl_jedec_ram")
        self.assertFalse(result["watchdog_feed_in_ram"])
        self.assertEqual(result["watchdog_symbols"]["fm1_wdt_feed"]["section"], ".text")
        self.assertEqual(result["xip_wrapper_symbols"]["fl_erase4k"]["address"], 0x0204E820)
        self.assertEqual(result["xip_wrapper_symbols"]["fl_write"]["section"], ".text")
        self.assertEqual(result["xip_wrapper_symbols"]["irq_save"]["section"], ".text")

    def test_linked_wrapper_audit_binds_ram_dispatch_and_staged_page(self):
        result = MODULE.audit_writer_callers(TARGET_RAM_DISASSEMBLY + "\n" + TARGET_DISASSEMBLY, TARGET_SYMBOLS)
        self.assertTrue(result["passed_linked_wrapper_checks"])
        self.assertTrue(result["runtime_stack_guard_before_critical_section_verified"])
        self.assertEqual(result["minimum_stack_headroom_bytes"], 1024)
        self.assertEqual(result["program_page_stack_offset"], 4)
        self.assertEqual(result["program_elapsed_word_stack_offset"], 260)
        self.assertEqual(result["linked_wrapper_frame_bytes"], {
            "fl_write_local": 272, "fl_write_saved_registers": 32,
            "fl_erase4k_local": 12, "fl_erase4k_saved_registers": 20})
        self.assertEqual(result["max_synchronous_stack_decrease_after_guard_bytes"], {
            "fl_write_to_fl_prog_ram": 408,
            "fl_erase4k_to_fl_erase4k_ram": 136})
        self.assertEqual(result["guard_sp_measurement_point"],
                         "after XIP wrapper prologue and page copy, before IRQ mask/WDT stop")
        self.assertEqual(result["guarded_headroom_after_program_ram_entry_bytes"], 920)
        self.assertEqual(result["guarded_headroom_after_erase_ram_entry_bytes"], 920)
        self.assertTrue(result["writer_ram_stack_paths_have_no_calls_or_dynamic_sp_adjustments"])
        self.assertFalse(result["runtime_stack_address_in_sram_proven"])

    def test_linked_wrapper_audit_rejects_guard_and_dispatch_mutations(self):
        cases = []
        cases.append((TARGET_DISASSEMBLY.replace(
            "r8 = 29361536 <fl_prog_ram : 1c00580 >",
            "r8 = 33558528 <flash_helper : 2001000 >"),
            "fl_prog_ram is not a linked RAM target|missing ordered target evidence"))
        cases.append((TARGET_DISASSEMBLY.replace(
            "r2 = sp + 4", "r2 = sp + 8"), "fl_write missing ordered target evidence"))
        cases.append((TARGET_DISASSEMBLY.replace(
            "r3 = sp + 260", "r3 = sp + 256"),
            "fl_write missing ordered target evidence"))
        stack_call = next(line for line in TARGET_DISASSEMBLY.splitlines()
                          if "call" in line and "<fl_stack_region :" in line
                          and "204eb" in line)
        irq_call = next(line for line in TARGET_DISASSEMBLY.splitlines()
                        if "call" in line and "<irq_save :" in line
                        and "204eb" in line)
        moved = TARGET_DISASSEMBLY.replace(stack_call + "\n", "", 1)
        moved = moved.replace(irq_call, irq_call + "\n" + stack_call, 1)
        cases.append((moved, "fl_write missing ordered target evidence"))
        cases.append((TARGET_DISASSEMBLY.replace(
            "if (r0 < 1024)", "if (r0 < 512)"),
            "fl_write missing ordered target evidence"))
        far_clobber = TARGET_DISASSEMBLY.replace(
            "r0 = [sp]\n", "r0 = [sp]\n 204e9ce: r0 = r4\n", 1)
        cases.append((far_clobber, "fl_far is not the exact stack-preserving"))
        for listing, expected in cases:
            with self.subTest(expected=expected):
                with self.assertRaisesRegex(ValueError, expected):
                    MODULE.audit_writer_callers(TARGET_RAM_DISASSEMBLY + "\n" + listing, TARGET_SYMBOLS)
        bad_bounds = TARGET_SYMBOLS.replace("01c7a100", "01c7a000")
        with self.assertRaisesRegex(ValueError, "linker stack bounds differ"):
            MODULE.audit_writer_callers(TARGET_RAM_DISASSEMBLY + "\n" + TARGET_DISASSEMBLY, bad_bounds)

    def test_linked_stack_bound_rejects_unknown_ram_frames_or_calls(self):
        mutations = [
            (TARGET_RAM_DISASSEMBLY.replace("sp += -52", "sp += -56", 1),
             "unknown local stack allocation"),
            (TARGET_RAM_DISASSEMBLY.replace("sp += -52", "sp += -52\n 1c00003: call r7", 1),
             "unbounded nested call"),
            (TARGET_RAM_DISASSEMBLY.replace("[--sp] = {rets, r15-r4}",
                                            "[--sp] = {rets, r14-r4}", 1),
             "unknown register-save prologue"),
        ]
        for listing, expected in mutations:
            with self.subTest(expected=expected):
                with self.assertRaisesRegex(ValueError, expected):
                    MODULE.audit_writer_callers(listing + "\n" + TARGET_DISASSEMBLY,
                                                TARGET_SYMBOLS)

    def test_linked_writer_audit_rejects_nonempty_stubs_and_xip_outcalls(self):
        symbols = """01c00000 l F .ram_text 00000040 fl_erase4k_ram
01c00040 l F .ram_text 00000040 fl_prog_ram
01c00080 l F .ram_text 00000010 fl_read_ram
01c00090 l F .ram_text 00000010 fl_status_checked_ram
01c000a0 l F .ram_text 00000010 fl_jedec_checked_ram
01c000b0 l F .ram_text 00000010 fl_jedec_ram
"""
        base = """fl_erase4k_ram:
 1c00000: nop
fl_prog_ram:
 1c00040: nop
fl_read_ram:
 1c00080: nop
fl_status_checked_ram:
 1c00090: [r5+8] = 0x5
fl_jedec_checked_ram:
 1c000a0: [r5+8] = 0x9f
fl_jedec_ram:
 1c000b0: call 0 <fl_jedec_checked_ram : 1c000a0 >
"""
        with self.assertRaisesRegex(ValueError, "opcode evidence missing"):
            MODULE.audit_linked_writer(base, symbols, "", "")
        real_ops = base.replace("1c00000: nop", "1c00000: [r6+8] = 0x6\n 1c00002: [r6+8] = 0x20\n 1c00004: [r6+8] = 0x5")
        real_ops = real_ops.replace("1c00040: nop", "1c00040: [r7+8] = 0x6\n 1c00042: [r7+8] = 0x2\n 1c00044: [r7+8] = 0x5")
        xip = real_ops.replace(
            "call 0 <fl_jedec_checked_ram : 1c000a0 >",
            "call 0 <xip_helper : 02001000 >")
        with self.assertRaisesRegex(ValueError, "does not resolve to linked RAM symbol"):
            MODULE.audit_linked_writer(xip, symbols, "", "")

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
        self.assertIn('caller source spans', record['reason'])
        self.assertIn('stages each program page in aligned SRAM', record['reason'])
        upstream = (SCRIPT.parents[2] / 'firmware/third_party/dinghy/UPSTREAM.md').read_text()
        self.assertIn('aligned page-staging changes', upstream)

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
