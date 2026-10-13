"""Synthetic ELF layout faults; no vendor binary or hardware is required."""
from pathlib import Path
import struct
import sys

import unittest
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/native'))
from probe_artifact import FLASH, ENTRY_GUARD, flatten
import probe_artifact


def fixture(pool=0x01C20000, pool_size=16):
    text = ENTRY_GUARD + bytes(0x4A - len(ENTRY_GUARD)) + bytes.fromhex('f79f')
    rows = [('.text', FLASH, text, len(text), 1, 6, FLASH),
            ('.ram_text', 0x01C00000, b'RAM!', 4, 1, 6, FLASH + len(text)),
            ('.data', 0x01C08000, b'DATA', 4, 1, 3, FLASH + len(text) + 4),
            ('.bss', 0x01C08004, b'', 16, 8, 3, 0),
            ('.pool', pool, b'', pool_size, 8, 3, 0),
            ('.noinit', 0x01C7C000, b'', 16, 8, 3, 0)]
    values = dict(_start=FLASH, _etext=FLASH + len(text), lunar_entry_rejected=FLASH + 0x4A,
                  _rt_start=0x01C00000, _rt_end=0x01C00004, _rt_load=FLASH + len(text),
                  _data_start=0x01C08000, _data_end=0x01C08004, _data_load=FLASH + len(text) + 4,
                  _bss_start=0x01C08004, _bss_end=0x01C08014,
                  _pool_start=pool, _pool_end=pool + pool_size,
                  _guard0=0x01C74000, _ustack_lo=0x01C74100, _ustack_top=0x01C7A000,
                  _guard1=0x01C7A000, _sstack_lo=0x01C7A100, _sstack_top=0x01C7C000)
    names, strings = {}, b'\0'
    for name in [r[0] for r in rows] + ['.shstrtab', '.strtab', '.symtab']:
        names[name] = len(strings)
        strings += name.encode() + b'\0'
    symbols, symbol_names = bytearray(16), b'\0'
    for name, value in values.items():
        symbols += struct.pack('<IIIBBH', len(symbol_names), value, 0, 0x10, 0, 1)
        symbol_names += name.encode() + b'\0'
    body, headers, programs = bytearray(52 + 3 * 32), bytearray(40), bytearray()
    for name, address, blob, size, kind, flags, load in rows:
        offset = len(body)
        headers += struct.pack('<10I', names[name], kind, flags, address, offset, size, 0, 0, 4, 0)
        body += blob
        if kind == 1:
            programs += struct.pack('<8I', 1, offset, address, load, size, size, 6 if name == '.data' else 5, 4)
    for name, blob, kind, link, entsize in [('.shstrtab', strings, 3, 0, 0),
                                          ('.strtab', symbol_names, 3, 0, 0),
                                          ('.symtab', symbols, 2, 8, 16)]:
        headers += struct.pack('<10I', names[name], kind, 0, 0, len(body), len(blob), link, 0, 1, entsize)
        body += blob
    body[:52] = b'\x7fELF' + bytes([1, 1, 1]) + bytes(9) + struct.pack(
        '<HHIIIIIHHHHHH', 2, 0xF1, 1, FLASH, 52, len(body), 0, 52, 32, 3, 40, 10, 7)
    body[52:148] = programs
    return bytes(body + headers)


def valid_layout():
    _, app = flatten(fixture())
    assert app[:len(ENTRY_GUARD)] == ENTRY_GUARD
    assert app[-8:] == b'RAM!DATA'


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
