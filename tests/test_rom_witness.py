"""MIT. Focused offline tests. Synthetic ELF cases do not prove target execution."""
import json
import os
from pathlib import Path
import struct
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/jieli'))
import rom_witness as w


def listing():
    m = w.manifest()
    lines = ['Disassembly of section .witness:']
    for row in m['instructions']:
        target = '' if row['target'] is None else f" <local : {row['target']:x} >"
        lines.append(f" {m['entry'] + row['offset']:x}: {' '.join(row['hex'][i:i+2] for i in range(0,len(row['hex']),2))}\t{row['operation']}{target}")
    return '\n'.join(lines)


def fixture():
    """A minimal ELF fixture for parser refusal cases, separate from native build."""
    m = w.manifest()
    code = b''.join(bytes.fromhex(r['hex']) for r in m['instructions'])
    names = b'\0.witness\0.shstrtab\0.symtab\0.strtab\0'
    strings = b'\0' + b'\0'.join(n.encode() for n in m['symbols']) + b'\0'
    symbol_rows = bytes(16)
    for name, value in m['symbols'].items():
        symbol_rows += struct.pack('<IIIBBH', strings.index(name.encode()), value,
                                   len(code) if name == '_start' else 0,
                                   0x12 if name == '_start' else 0x10, 0, 1)
    data = bytearray(52)
    offsets = []
    for blob in (code, names, symbol_rows, strings):
        offsets.append(len(data)); data.extend(blob)
    shoff = len(data)
    data.extend(bytes(40))
    for i, (name, typ, flags, address, blob) in enumerate([
        ('.witness', 1, 6, m['entry'], code), ('.shstrtab', 3, 0, 0, names),
        ('.symtab', 2, 0, 0, symbol_rows), ('.strtab', 3, 0, 0, strings)]):
        data.extend(struct.pack('<IIIIIIIIII', names.index(name.encode()), typ, flags,
                                address, offsets[i], len(blob), 4 if typ == 2 else 0,
                                1 if typ == 2 else 0, 1, 16 if typ == 2 else 0))
    data[:16] = bytes.fromhex('7f454c46010101000000000000000000')
    struct.pack_into('<HHIIIIIHHHHHH', data, 16, 2, 0xf1, 1, m['entry'], 0,
                     shoff, 0, 52, 0, 0, 40, 5, 2)
    return bytes(data), code, listing(), code + bytes(512 - len(code))


def test_fixed_program_and_offline_receipt():
    args = fixture()
    report = w.audit(*args)
    assert report['offline_audit_passed'] is True
    assert report['hardware_admitted'] is False
    assert report['footprint'] == 512 and report['code_size'] == 202
    m = w.manifest()
    assert m['instructions'][:3] == [
        {'offset': 0, 'hex': '6000', 'operation': 'cli', 'target': None},
        {'offset': 2, 'hex': '64e00016', 'operation': 'r1 = cnum', 'target': None},
        {'offset': 6, 'hex': 'b140', 'operation': 'if (r1 != 0) goto 192', 'target': 0x1c020c8}]
    # Every memory operation has exactly one PA2 bit mask; no register-indirect
    # calls, SP/SSP, data-memory stores, flash or SDK instruction sequence.
    memory = [r['operation'] for r in m['instructions'] if '[' in r['operation']]
    assert memory == ['[r0+0] |= 0x4', '[r1+0] &= 0xFFFFFFFB'] + [
        op for _ in range(6) for op in ('[r0+0] &= 0xFFFFFFFB', '[r0+0] |= 0x4')]
    assert m['signature']['active_low_width_units'] == [1, 3, 1, 2, 3, 2]
    assert m['signature']['delay_units_total'] == 20
    assert m['signature']['elapsed_time_verified'] is False


def test_all_code_and_padding_byte_changes_rejected():
    elf, code, text, payload = fixture()
    for i in range(512):
        changed = bytearray(payload); changed[i] ^= 1
        with pytest.raises(ValueError):
            w.audit(elf, bytes(changed[:len(code)]), text, bytes(changed))
    for bad in (payload[:-1], payload + b'\0', code):
        with pytest.raises(ValueError):
            w.audit(elf, code, text, bad)


@pytest.mark.parametrize('old,new', [
    ('cli', 'sti'), ('0xFFFFFFFB', '0xFFFFFFF3'), ('0x4', '0x8'),
    ('1c020c8 >', '1c02000 >'), ('r1 = cnum', 'r1 = sp'),
    ('r2 += -1', 'call 0xffc00000'), ('.witness:', '.text:'),
    ('r0 = 0x50000', 'r0 = 0x10000')])
def test_listing_changes_rejected(old, new):
    elf, code, text, payload = fixture()
    with pytest.raises(ValueError):
        w.audit(elf, code, text.replace(old, new), payload)


@pytest.mark.parametrize('field,value', [(16, 1), (18, 3), (24, 0x02000120),
                                         (36, 1), (46, 39), (48, 6)])
def test_elf_entry_machine_and_geometry_rejected(field, value):
    elf, code, text, payload = fixture()
    changed = bytearray(elf)
    struct.pack_into('<H' if field in (16,18,46,48) else '<I', changed, field, value)
    with pytest.raises(ValueError):
        w.audit(bytes(changed), code, text, payload)


def test_writable_or_extra_allocated_section_rejected():
    elf, code, text, payload = fixture()
    shoff = struct.unpack_from('<I', elf, 32)[0]
    for section, flags in [(1, 7), (2, 2), (3, 3)]:
        changed = bytearray(elf)
        struct.pack_into('<I', changed, shoff + 40 * section + 8, flags)
        with pytest.raises(ValueError):
            w.audit(bytes(changed), code, text, payload)


def test_manifest_tampering_refused(tmp_path, monkeypatch):
    fake = tmp_path / 'manifest.json'
    fake.write_text(json.dumps({**w.manifest(), 'hardware_admitted': True}))
    monkeypatch.setattr(w, 'MANIFEST', fake)
    with pytest.raises(ValueError, match='manifest changed'):
        w.manifest()


def test_sources_and_tool_pins_checked_before_build(tmp_path):
    w.check_sources()
    with pytest.raises(FileNotFoundError):
        w.build(tmp_path / 'missing-toolchain', tmp_path / 'out')
    assert not (tmp_path / 'out').exists()


def test_real_native_artifacts_when_requested():
    raw = os.environ.get('LUNAR_ROM_WITNESS_NATIVE_DIR')
    if not raw:
        pytest.skip('set LUNAR_ROM_WITNESS_NATIVE_DIR for actual pinned native output')
    p = Path(raw)
    report = w.audit((p/'witness.elf').read_bytes(), (p/'witness.code').read_bytes(),
                     (p/'witness.listing').read_text(), (p/'witness.payload').read_bytes())
    assert report['offline_audit_passed'] and not report['hardware_admitted']


def model_native(core, out_word, dir_word):
    """Bounded symbolic interpretation of frozen vendor operations, not ISA proof.

    Summarize the strictly decreasing two-instruction r2 loops algebraically.
    Unknown operations or nonlocal/control-flow shapes fail this model.
    """
    import re
    m = w.manifest()
    rows = {m['entry'] + r['offset']: r for r in m['instructions']}
    registers = {}; memory = {0x50000: out_word, 0x50008: dir_word}
    writes = []; elapsed_loops = 0; pc = m['entry']; steps = 0
    while steps < 100:
        steps += 1
        row = rows[pc]; op = row['operation']
        next_pc = pc + len(bytes.fromhex(row['hex']))
        if op in ('cli', 'csync'):
            pass
        elif op == 'r1 = cnum':
            registers['r1'] = core
        elif op == 'if (r1 != 0) goto 192':
            if registers['r1']:
                next_pc = row['target']
        elif op.startswith('goto'):
            assert row['target'] == pc
            return memory, writes, elapsed_loops, pc
        elif op == 'r2 += -1':
            branch = rows[next_pc]
            assert branch['operation'] == 'if (r2 != 0) goto -4' and branch['target'] == pc
            assert 0 < registers['r2'] <= 3 * 1048576
            elapsed_loops += registers['r2']
            registers['r2'] = 0
            next_pc += len(bytes.fromhex(branch['hex']))
        elif match := re.fullmatch(r'(r[012]) = (0x[0-9a-fA-F]+|[0-9]+)', op):
            registers[match[1]] = int(match[2], 0)
        elif match := re.fullmatch(r'\[(r[01])\+0\] ([|&])= (0x[0-9a-fA-F]+)', op):
            address = registers[match[1]]
            assert address in memory
            mask = int(match[3], 16)
            memory[address] = (memory[address] | mask if match[2] == '|' else memory[address] & mask)
            writes.append((address, memory[address], elapsed_loops))
        else:
            raise AssertionError('unmodeled operation: ' + op)
        pc = next_pc
    raise AssertionError('nonterminal control flow')


@pytest.mark.parametrize('core', [1, 2, 255, 0xffffffff])
def test_nonprimary_path_stops_before_mmio(core):
    memory, writes, loops, stop = model_native(core, 0x1234, 0x5678)
    assert memory == {0x50000: 0x1234, 0x50008: 0x5678}
    assert writes == [] and loops == 0 and stop == 0x1c020c8


@pytest.mark.parametrize('out_word,dir_word', [(0, 0), (0xffffffff, 0xffffffff),
                                            (0xaaaa5555, 0x5555aaaa), (4, 4)])
def test_primary_signature_is_finite_and_preserves_unrelated_bits(out_word, dir_word):
    memory, writes, loops, stop = model_native(0, out_word, dir_word)
    for address, value, _ in writes:
        original = out_word if address == 0x50000 else dir_word
        assert (value & ~4) == (original & ~4)
    assert writes[0][:2] == (0x50000, out_word | 4)  # inactive first
    assert writes[1][:2] == (0x50008, dir_word & ~4)  # then output
    optical = writes[2:]
    widths = [(optical[i+1][2] - optical[i][2]) // 1048576 for i in range(0, 12, 2)]
    assert widths == [1, 3, 1, 2, 3, 2]
    assert [v & 4 for _,v,_ in optical] == [0,4] * 6
    assert loops == 20 * 1048576 and stop == 0x1c020c6
    assert memory == {0x50000: out_word | 4, 0x50008: dir_word & ~4}


def test_changed_source_is_refused(tmp_path, monkeypatch):
    for relative in w.manifest()['sources']:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((w.ROOT / relative).read_bytes())
    path.write_bytes(path.read_bytes() + b'\n')
    monkeypatch.setattr(w, 'ROOT', tmp_path)
    with pytest.raises(ValueError, match='source differs'):
        w.check_sources()


def test_changed_tool_is_refused_before_creating_output(tmp_path):
    for relative in w.manifest()['tools']:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'changed tool')
    with pytest.raises(ValueError, match='tool differs'):
        w.build(tmp_path, tmp_path / 'out')
    assert not (tmp_path / 'out').exists()
