"""MIT. Actual offline checker tests; synthetic fixtures are not native proof."""
import json
import os
from pathlib import Path
import struct
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/jieli'))
import rom_witness_return as w


def fixture():
    """Small synthetic ELF for directed refusals, never a target artifact."""
    names = b'\0.witness_return\0.shstrtab\0.symtab\0.strtab\0'
    strings = b'\0_start\0__image_end\0'
    symbols = bytes(16) + struct.pack('<IIIBBH', 0, w.ENTRY, 0, 3, 0, 1)
    symbols += struct.pack('<IIIBBH', 1, w.ENTRY, 2, 0x12, 0, 1)
    symbols += struct.pack('<IIIBBH', 8, w.ENTRY + 2, 0, 0x10, 0, 1)
    data = bytearray(52)
    offsets = []
    blobs = [w.CODE, names, symbols, strings]
    for blob in blobs:
        offsets.append(len(data))
        data.extend(blob)
    shoff = len(data)
    data.extend(bytes(40))
    for i, (name, typ, flags, address) in enumerate([
        ('.witness_return', 1, 6, w.ENTRY), ('.shstrtab', 3, 0, 0),
        ('.symtab', 2, 0, 0), ('.strtab', 3, 0, 0)]):
        data.extend(struct.pack('<IIIIIIIIII', names.index(name.encode()), typ, flags,
                                address, offsets[i], len(blobs[i]),
                                4 if typ == 2 else 0, 2 if typ == 2 else 0,
                                1, 16 if typ == 2 else 0))
    data[:16] = bytes.fromhex('7f454c46010101000000000000000000')
    struct.pack_into('<HHIIIIIHHHHHH', data, 16, 2, 0xf1, 1, w.ENTRY, 0,
                     shoff, 0, 52, 0, 0, 40, 5, 2)
    listing = f'Disassembly of section .witness_return:\n {w.ENTRY:x}: 80 00\trts\n'
    return bytes(data), w.CODE, listing, w.CODE + bytes(510)


def test_exact_candidate_has_only_offline_acceptance():
    report = w.audit(*fixture())
    assert report['offline_audit_passed'] is True
    assert report['entry'] == 0x01c02000
    assert report['footprint'] == 512 and report['code_size'] == 2
    for key in ('hardware_admitted', 'rom_abi_qualified', 'watchdog_lease_qualified',
                'fetch_coherence_qualified'):
        assert report[key] is False
    w.check_sources()


def test_every_envelope_byte_mutation_and_wrong_sizes_refused():
    elf, code, text, payload = fixture()
    for i in range(512):
        changed = bytearray(payload)
        changed[i] ^= 1
        with pytest.raises(ValueError, match='plaintext/padding'):
            w.audit(elf, code, text, bytes(changed))
    for changed in (payload[:-1], payload + b'\0', code, bytes(512)):
        with pytest.raises(ValueError, match='plaintext/padding'):
            w.audit(elf, code, text, changed)


@pytest.mark.parametrize('code', [b'', b'\x00\x00', b'\x60\x00', b'\x80\x00\x00\x00'])
def test_extra_or_changed_code_refused(code):
    elf, _, text, _ = fixture()
    with pytest.raises(ValueError, match='two-byte code'):
        w.audit(elf, code, text, code + bytes(512 - len(code)))


@pytest.mark.parametrize('old,new', [
    ('rts', 'rti'), ('rts', 'cli'), ('rts', 'r0 = rets'), ('rts', 'goto r0'),
    ('rts', 'rts <foreign : ffc00000>'), ('80 00', '00 00'),
    ('1c02000:', '1c02002:'), ('.witness_return:', '.text:')])
def test_listing_changes_refused(old, new):
    elf, code, text, payload = fixture()
    with pytest.raises(ValueError, match='one-return'):
        w.audit(elf, code, text.replace(old, new), payload)


def test_extra_or_unparsed_listing_instruction_refused():
    elf, code, text, payload = fixture()
    for extra in (' 1c02002: 00 00 nop\n', ' 1c02002: unparsed\n',
                  'Disassembly of section .text:\n'):
        with pytest.raises(ValueError):
            w.audit(elf, code, text + extra, payload)


@pytest.mark.parametrize('field,size,value', [
    (16, 'H', 1), (18, 'H', 3), (20, 'I', 0), (24, 'I', 0x02000120),
    (36, 'I', 1), (40, 'H', 48),
    (32, 'I', 0), (46, 'H', 39), (48, 'H', 6), (50, 'H', 4)])
def test_elf_entry_machine_type_and_table_geometry_refused(field, size, value):
    elf, code, text, payload = fixture()
    changed = bytearray(elf)
    struct.pack_into('<' + size, changed, field, value)
    with pytest.raises(ValueError):
        w.audit(bytes(changed), code, text, payload)


@pytest.mark.parametrize('section,field,value', [
    (1, 8, 7), (2, 8, 2), (3, 8, 3),  # writable or extra allocation
    (1, 12, w.ENTRY + 2), (1, 20, 4),  # moved / extra code
    (2, 4, 8), (2, 4, 4), (2, 4, 9),  # BSS / RELA / REL
    (1, 16, 0), (1, 16, 0xffffffff),  # outside file
    (3, 24, 9), (3, 36, 8), (3, 20, 63)])
def test_section_relocation_and_symbol_table_shapes_refused(section, field, value):
    elf, code, text, payload = fixture()
    changed = bytearray(elf)
    shoff = struct.unpack_from('<I', elf, 32)[0]
    struct.pack_into('<I', changed, shoff + 40 * section + field, value)
    with pytest.raises(ValueError):
        w.audit(bytes(changed), code, text, payload)


@pytest.mark.parametrize('field,size,value', [
    (4, 'I', w.ENTRY + 2), (8, 'I', 4), (12, 'B', 0x10),
    (12, 'B', 0x22), (14, 'H', 0), (14, 'H', 2), (0, 'I', 8)])
def test_wrong_function_extent_undefined_and_foreign_symbols_refused(field, size, value):
    elf, code, text, payload = fixture()
    changed = bytearray(elf)
    shoff = struct.unpack_from('<I', elf, 32)[0]
    symoff = struct.unpack_from('<I', elf, shoff + 3 * 40 + 16)[0]
    struct.pack_into('<' + size, changed, symoff + 2 * 16 + field, value)
    with pytest.raises(ValueError):
        w.audit(bytes(changed), code, text, payload)


def test_elf_bytes_extra_trailer_and_truncation_refused():
    elf, code, text, payload = fixture()
    changed = bytearray(elf)
    changed[52] ^= 1  # same listing/export, changed actual executable bytes
    for bad in (bytes(changed), elf + b'\0', elf[:-1], elf[:20]):
        with pytest.raises(ValueError):
            w.audit(bad, code, text, payload)


def test_manifest_admission_or_geometry_change_refused(tmp_path, monkeypatch):
    p = tmp_path / 'manifest.json'
    for key, value in [('hardware_admitted', True), ('entry', w.ENTRY + 2),
                       ('footprint', 1024)]:
        p.write_text(json.dumps({**w.manifest(), key: value}))
        with monkeypatch.context() as patch:
            patch.setattr(w, 'MANIFEST', p)
            with pytest.raises(ValueError, match='manifest changed'):
                w.audit(*fixture())


def test_each_changed_source_refused_before_build(tmp_path, monkeypatch):
    sources = w.manifest()['sources']
    for relative in sources:
        p = tmp_path / relative
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes((w.ROOT / relative).read_bytes())
    for relative in sources:
        p = tmp_path / relative
        original = p.read_bytes()
        p.write_bytes(original + b'\n')
        with monkeypatch.context() as patch:
            patch.setattr(w, 'ROOT', tmp_path)
            with pytest.raises(ValueError, match='source differs'):
                w.build(tmp_path / 'missing-tools', tmp_path / 'out')
        assert not (tmp_path / 'out').exists()
        p.write_bytes(original)


def test_tool_pin_mismatch_prevents_process_and_output(tmp_path, monkeypatch):
    for relative in w.manifest()['tools']:
        p = tmp_path / relative
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b'wrong executable')
    monkeypatch.setattr(w.subprocess, 'run', lambda *a, **k: pytest.fail('process started'))
    with pytest.raises(ValueError, match='tool differs'):
        w.build(tmp_path, tmp_path / 'out')
    assert not (tmp_path / 'out').exists()


def test_original_w01_is_a_separate_unchanged_contract():
    import rom_witness
    rom_witness.check_sources()
    assert rom_witness.manifest()['candidate'] == 'pa2-w01'
    assert rom_witness.MANIFEST != w.MANIFEST
    assert rom_witness.manifest()['payload_sha256'] == 'f45330e5f5428260750c1863ae485a5504587323b8c23af2e2017df0c38b55f4'


def test_real_native_artifacts_only_when_explicitly_supplied():
    raw = os.environ.get('LUNAR_ROM_RETURN_NATIVE_DIR')
    if not raw:
        pytest.skip('native build separately allocated; synthetic fixtures are not native evidence')
    p = Path(raw)
    report = w.audit((p / 'witness.elf').read_bytes(), (p / 'witness.code').read_bytes(),
                     (p / 'witness.listing').read_text(), (p / 'witness.payload').read_bytes())
    assert report['offline_audit_passed'] and not report['hardware_admitted']
