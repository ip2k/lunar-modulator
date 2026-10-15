"""Synthetic ELF layout faults; no vendor binary or hardware is required."""
from pathlib import Path
import struct
import sys

import unittest
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/native'))
from probe_artifact import FLASH, ENTRY_GUARD, flatten
import probe_artifact
from flash_layout import (FLASH_LAYOUTS, EXPANDED_D7000_STAGE_END,
                          EXPANDED_D7000_STAGE_START, app_budget, linker_script)


def fixture(pool=0x01C20000, pool_size=16, text_size=0x4C, hot_dsp_ram=False):
    text = (ENTRY_GUARD + bytes(0x4A - len(ENTRY_GUARD)) + bytes.fromhex('f79f')
            + bytes(text_size - 0x4C))
    rows = [('.text', FLASH, text, len(text), 1, 6, FLASH),
            ('.ram_text', 0x01C00000, b'RAM!', 4, 1, 6, FLASH + len(text))]
    if hot_dsp_ram:
        rows.append(('.ram_dsp', 0x01C00004, b'DSP!', 4, 1, 6, FLASH + len(text) + 4))
    data_load = FLASH + len(text) + 4 + (4 if hot_dsp_ram else 0)
    rows += [('.data', 0x01C08000, b'DATA', 4, 1, 3, data_load),
            ('.bss', 0x01C08004, b'', 16, 8, 3, 0),
            ('.pool', pool, b'', pool_size, 8, 3, 0),
            ('.noinit', 0x01C7C000, b'', 16, 8, 3, 0)]
    values = dict(_start=FLASH, _etext=FLASH + len(text), lunar_entry_rejected=FLASH + 0x4A,
                  _rt_start=0x01C00000, _rt_end=0x01C00004, _rt_load=FLASH + len(text),
                  _data_start=0x01C08000, _data_end=0x01C08004, _data_load=data_load,
                  _bss_start=0x01C08004, _bss_end=0x01C08014,
                  _pool_start=pool, _pool_end=pool + pool_size,
                  _guard0=0x01C74000, _ustack_lo=0x01C74100, _ustack_top=0x01C7A000,
                  _guard1=0x01C7A000, _sstack_lo=0x01C7A100, _sstack_top=0x01C7C000)
    if hot_dsp_ram:
        values.update(_rd_start=0x01C00004, _rd_end=0x01C00008,
                      _rd_load=FLASH + len(text) + 4)
    names, strings = {}, b'\0'
    for name in [r[0] for r in rows] + ['.shstrtab', '.strtab', '.symtab']:
        names[name] = len(strings)
        strings += name.encode() + b'\0'
    symbols, symbol_names = bytearray(16), b'\0'
    for name, value in values.items():
        symbols += struct.pack('<IIIBBH', len(symbol_names), value, 0, 0x10, 0, 1)
        symbol_names += name.encode() + b'\0'
    program_count = 4 if hot_dsp_ram else 3
    body, headers, programs = bytearray(52 + program_count * 32), bytearray(40), bytearray()
    for name, address, blob, size, kind, flags, load in rows:
        offset = len(body)
        headers += struct.pack('<10I', names[name], kind, flags, address, offset, size, 0, 0, 4, 0)
        body += blob
        if kind == 1:
            programs += struct.pack('<8I', 1, offset, address, load, size, size, 6 if name == '.data' else 5, 4)
    for name, blob, kind, link, entsize in [('.shstrtab', strings, 3, 0, 0),
                                          ('.strtab', symbol_names, 3, 0, 0),
                                          ('.symtab', symbols, 2, 8 + int(hot_dsp_ram), 16)]:
        headers += struct.pack('<10I', names[name], kind, 0, 0, len(body), len(blob), link, 0, 1, entsize)
        body += blob
    body[:52] = b'\x7fELF' + bytes([1, 1, 1]) + bytes(9) + struct.pack(
        '<HHIIIIIHHHHHH', 2, 0xF1, 1, FLASH, 52, len(body), 0, 52, 32, program_count, 40, 10 + int(hot_dsp_ram), 7)
    body[52:52 + len(programs)] = programs
    return bytes(body + headers)


def valid_layout():
    _, app = flatten(fixture())
    assert app[:len(ENTRY_GUARD)] == ENTRY_GUARD
    assert app[-8:] == b'RAM!DATA'


def test_target_disassembly_command_selects_pi32v2_r3():
    assert probe_artifact.target_disassembly_command(
        Path('/toolchain/common/bin/objdump'), Path('/build/lunar-app-probe.elf')) == [
            '/toolchain/common/bin/objdump', '-d', '-mcpu=r3', '/build/lunar-app-probe.elf']


@pytest.mark.parametrize('profile', ['protected', 'expanded-d7000', 'expanded-d9000'])
@pytest.mark.parametrize('extra', [0, 1, 4, 8, 12])
def test_full_flash_load_budget(profile, extra):
    # Include the RAM-code/data initializers, not just XIP text, at the boundary.
    data = fixture(text_size=app_budget(profile) - 8 + extra)
    if extra:
        with pytest.raises(ValueError, match='bounds|flash load address'):
            flatten(data, flash_layout=profile)
    else:
        _, app = flatten(data, flash_layout=profile)
        assert len(app) == app_budget(profile)


def test_expansion_requires_explicit_selection():
    data = fixture(text_size=app_budget('protected'))
    with pytest.raises(ValueError, match='flash load address'):
        flatten(data)
    _, app = flatten(data, flash_layout='expanded-d9000')
    assert len(app) == app_budget('protected') + 8


def test_layout_budget_and_pinned_linker():
    source = (Path(__file__).resolve().parents[1] / 'firmware/native/app.ld').read_text()
    assert app_budget('expanded-d9000') == 868836
    assert app_budget('expanded-d9000') + 0x4120 + 384 + 2940 == 0xD9000
    assert FLASH_LAYOUTS == ('protected', 'expanded-d7000', 'expanded-d9000')
    assert app_budget() == app_budget('protected')
    assert app_budget('expanded-d7000') == 860644
    assert app_budget('expanded-d7000') + 0x4120 + 384 + 2940 == EXPANDED_D7000_STAGE_START
    assert EXPANDED_D7000_STAGE_END - EXPANDED_D7000_STAGE_START == 2 * 4096
    assert linker_script(source) == source
    expected_d7000 = source.replace('LENGTH = 0x8DFBC', 'LENGTH = 0xD21E4', 1)
    assert linker_script(source, 'expanded-d7000') == expected_d7000
    expected_d9000 = source.replace('LENGTH = 0x8DFBC', 'LENGTH = 0xD41E4', 1)
    assert linker_script(source, 'expanded-d9000') == expected_d9000
    for bad in ('unknown', '', None):
        with pytest.raises(ValueError, match='Unknown flash layout'):
            flatten(fixture(), flash_layout=bad)
        with pytest.raises(ValueError, match='Unknown flash layout'):
            linker_script(source, bad)
    for bad_source in (source.replace('0x8DFBC', '0x8DFB8'), source + source):
        with pytest.raises(ValueError, match='Pinned XIP'):
            linker_script(bad_source, 'expanded-d7000')
        with pytest.raises(ValueError, match='Pinned XIP'):
            linker_script(bad_source, 'expanded-d9000')


@pytest.mark.parametrize('section,load', [('.text', '_start'), ('.ram_text', '_rt_load')])
def test_relative_call_flat_mapping(section, load, monkeypatch):
    image, app = flatten(fixture())
    instruction = bytes.fromhex('80ff00370100')
    offset = image.symbol_value(load) - FLASH + 2
    app = app[:offset - 2] + instruction + app[offset + 4:]
    proof = dict(address=0, bytes=instruction.hex(), target=0, symbol='target')
    monkeypatch.setattr(probe_artifact, 'relative_call_payloads',
                        lambda *args: {('native-probe.elf:' + section, 2): proof})
    proofs = probe_artifact.artifact_call_payloads(image, app, '')
    assert proofs[('app.bin', offset)] == proof
    changed = bytearray(app)
    changed[offset] ^= 1
    with pytest.raises(ValueError, match='does not match flattened'):
        probe_artifact.artifact_call_payloads(image, bytes(changed), '')



@pytest.mark.parametrize('section,load', [('.text', '_start'), ('.ram_text', '_rt_load'),
                                          ('.ram_dsp', '_rd_load')])
def test_call_boundary_flat_mapping(section, load, monkeypatch):
    hot_dsp_ram = section == '.ram_dsp'
    image, app = flatten(fixture(hot_dsp_ram=hot_dsp_ram), hot_dsp_ram=hot_dsp_ram)
    instructions = bytes.fromhex('80ff0c2e01000215')
    offset = image.symbol_value(load) - FLASH + 3
    app = app[:offset - 3] + instructions + app[offset + 5:]
    proof = dict(call=dict(bytes=instructions[:6].hex()), following_bytes='0215')
    monkeypatch.setattr(probe_artifact, 'stub_call_boundary_patterns',
                        lambda *args: {('native-probe.elf:' + section, 3): proof})
    proofs = probe_artifact.artifact_stub_boundaries(image, app, '')
    assert proofs[('app.bin', offset)] == proof
    for index in range(8):
        changed = bytearray(app)
        changed[offset - 3 + index] ^= 1
        with pytest.raises(ValueError, match='does not match flattened'):
            probe_artifact.artifact_stub_boundaries(image, bytes(changed), '')


def damaged_contract(fault):
    data = bytearray(fixture())
    shoff = struct.unpack_from('<I', data, 32)[0]
    # Each fault targets a separate contract: entry, architecture, load mapping,
    # flags, memory reservation, startup symbols, completeness or contiguity.
    mutations = [(24, FLASH + 2), (16, 0), (52 + 12, FLASH + 4),
                 (52 + 16, 0), (52 + 24, 6),
                 (shoff + 40 + 8, 3), (shoff + 80 + 12, 0x01C06000),
                 (shoff + 120 + 4, 8), (shoff + 160 + 12, 0x01C7FE00),
                 (shoff + 200 + 20, 0x60000), (shoff + 240 + 12, 0x01C7FD50),
                 (shoff + 160 + 8, 0), (shoff + 240, 1), (52 + 32 + 12, FLASH + 8),
                 (52 + 8, FLASH + 1), (shoff + 120 + 16, len(data) + 100)]
    offset, value = mutations[fault]
    struct.pack_into('<I', data, offset, value)
    with unittest.TestCase().assertRaises((ValueError, struct.error, IndexError)):
        flatten(bytes(data))


class ArtifactTests(unittest.TestCase):
    def test_hot_dsp_ram_is_explicit_and_bounded(self):
        data = fixture(hot_dsp_ram=True)
        with self.assertRaisesRegex(ValueError, 'Unexpected allocated section'):
            flatten(data)
        image, app = flatten(data, hot_dsp_ram=True)
        self.assertEqual(image.read(0x01C00004, 4), b'DSP!')
        self.assertEqual(app[0x4C:0x50], b'RAM!')
        self.assertEqual(app[0x50:0x54], b'DSP!')

    def test_hot_dsp_ram_refuses_missing_or_overlapping_extent(self):
        with self.assertRaisesRegex(ValueError, 'Missing required sections'):
            flatten(fixture(), hot_dsp_ram=True)
        data = bytearray(fixture(hot_dsp_ram=True))
        shoff = struct.unpack_from('<I', data, 32)[0]
        # .ram_dsp is section 3 after NULL, .text and .ram_text; force it to
        # overlap .ram_text and ensure range checks refuse the image.
        struct.pack_into('<I', data, shoff + 3 * 40 + 12, 0x01C00000)
        with self.assertRaisesRegex(ValueError, 'Startup copy/zero bounds disagree: .ram_dsp'):
            flatten(bytes(data), hot_dsp_ram=True)

    def test_combined_exact_fill(self):
        data = fixture(0x01C08020, 0x01C74000 - 0x01C08020)
        flatten(data, 'combined')
        with self.assertRaises(ValueError):
            flatten(data)  # The legacy contract stays narrow.

    def test_combined_guards(self):
        for pool, size in ((0x01C08020, 0x01C74000 - 0x01C08020 + 16),
                           (0x01C08021, 16), (0x01C08010, 16),
                           (0x01C06000, 16)):
            with self.assertRaises(ValueError):
                flatten(fixture(pool, size), 'combined')

    def test_unknown_layout(self):
        with self.assertRaises(ValueError):
            flatten(fixture(), 'unknown')

    def test_valid(self):
        valid_layout()

    def test_guard_bytes(self):
        original = fixture()
        shoff = struct.unpack_from('<I', original, 32)[0]
        offset = struct.unpack_from('<I', original, shoff + 40 + 16)[0]
        for i in list(range(len(ENTRY_GUARD))) + [0x4A, 0x4B]:
            changed = bytearray(original)
            changed[offset + i] ^= 1
            with self.assertRaisesRegex(ValueError, 'entry guard'):
                flatten(bytes(changed))


for _fault in range(16):
    setattr(ArtifactTests, 'test_fault_%02d' % _fault,
            lambda self, fault=_fault: damaged_contract(fault))
