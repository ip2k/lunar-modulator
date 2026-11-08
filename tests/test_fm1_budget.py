"""The FM-1 size and SRAM budget gate (docs/18 M2), on synthetic ELFs only."""
import importlib.util
import json
from pathlib import Path
import struct

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('fm1_budget', ROOT/'tools/jieli/fm1_budget.py')
B = importlib.util.module_from_spec(spec)
spec.loader.exec_module(B)

SLOT = 581564


def synthetic_elf(sections, symbols=()):
    """ELF32 LE. sections: (name, addr, size, nobits); symbols: (name, value, size, section index)."""
    names = [s[0] for s in sections] + ['.symtab', '.strtab', '.shstrtab']
    shstr = b'\0' + b'\0'.join(n.encode() for n in names) + b'\0'
    def shname(n):
        return shstr.index(b'\0' + n.encode() + b'\0') + 1
    strtab = b'\0'
    symtab = b'\0' * 16
    for name, value, size, idx in symbols:
        symtab += struct.pack('<IIIBBH', len(strtab), value, size, 0x11, 0, idx)
        strtab += name.encode() + b'\0'
    body = bytearray(52)
    out = [struct.pack('<10I', *([0] * 10))]
    for name, addr, size, nobits in sections:
        off = len(body)
        if not nobits:
            body += bytes(size)
        out.append(struct.pack('<10I', shname(name), 8 if nobits else 1, 3, addr, off, size, 0, 0, 4, 0))
    symidx = len(out)
    for name, blob, typ, link, ent in (('.symtab', symtab, 2, symidx + 1, 16),
                                       ('.strtab', strtab, 3, 0, 0), ('.shstrtab', shstr, 3, 0, 0)):
        off = len(body)
        body += blob
        out.append(struct.pack('<10I', shname(name), typ, 0, 0, off, len(blob), link, 0, 1, ent))
    shoff = len(body)
    body += b''.join(out)
    body[0:16] = b'\x7fELF\x01\x01\x01' + bytes(9)
    struct.pack_into('<HHIIIIIHHHHHH', body, 16, 2, 0, 1, 0, 0, shoff, 0, 52, 0, 0, 40,
                     len(out), len(out) - 1)
    return bytes(body)


def image(text=1000, data=2000, bss=3000, heap=60000, cache=1000, bss_addr=None):
    """A kit-shaped ELF: .text, .ram0_data, .ram0_bss, cache RAM, HEAP_* symbols."""
    bss_addr = bss_addr or 0x01C00000 + data
    secs = [('.text', 0x02000120, text, False), ('.ram0_data', 0x01C00000, data, False),
            ('.ram0_bss', bss_addr, bss, True), ('.cache_ram_data', 0x01F28000, cache, False)]
    begin = bss_addr + bss
    syms = [('HEAP_BEGIN', begin, 0, 0xFFF1), ('HEAP_END', begin + heap, 0, 0xFFF1),
            ('big_table', 0x02000120, 400, 1), ('small_fn', 0x02000300, 8, 1),
            ('buf', bss_addr, 64, 3)]
    return secs, syms


def run(tmp_path, secs, syms, app=None, argv=(), capsys=None):
    elf = tmp_path/'sdk.elf'
    elf.write_bytes(synthetic_elf(secs, syms))
    size = app if app is not None else sum(s[2] for s in secs if not s[3] and s[0] != '.boot_info')
    binf = tmp_path/'app.bin'
    binf.write_bytes(bytes(size))
    rc = B.main([str(binf), '--elf', str(elf), '--json', *argv])
    return rc, json.loads(capsys.readouterr().out) if capsys else None


def test_constants_follow_the_documented_layout():
    assert B.APP_SLOT == 0x920DC - 0x4120 == SLOT
    assert B.STOCK_GAP == 0x01C7FD50 - 0x01C211FC == 387924


def test_a_small_image_passes_everything(tmp_path, capsys):
    rc, rep = run(tmp_path, *image(), capsys=capsys)
    assert rc == 0 and rep['pass']
    assert rep['app_margin'] == SLOT - 4000
    assert rep['ram_static_bytes'] == 5000 and rep['heap_bytes'] == 60000
    assert rep['elf_matches_app_bin'] and rep['cache_ram_used'] == 1000


@pytest.mark.parametrize('size,margin,rc', [
    (SLOT, 0, 0), (SLOT + 1, 0, 1), (SLOT - 100, 100, 0), (SLOT - 99, 100, 1)])
def test_slot_edges_and_margin(tmp_path, capsys, size, margin, rc):
    # An app.bin alone (no ELF) is checked against the slot.
    binf = tmp_path/'app.bin'
    binf.write_bytes(bytes(size))
    assert B.main([str(binf), '--margin', str(margin), '--json']) == rc
    rep = json.loads(capsys.readouterr().out)
    assert rep['app_margin'] == SLOT - size and 'ram_sections' not in rep


def test_overflowing_image_fails_with_the_overflow(tmp_path, capsys):
    secs, syms = image(text=SLOT - 3000 + 16352)
    rc, rep = run(tmp_path, secs, syms, capsys=capsys)
    assert rc == 1 and rep['app_margin'] == -16352 and not rep['pass']
    assert [c['check'] for c in rep['checks'] if not c['ok']] == ['app_slot']


def test_heap_floor_and_boot_info_bound(tmp_path, capsys):
    rc, rep = run(tmp_path, *image(heap=B.MIN_HEAP), capsys=capsys)
    assert rc == 0 and rep['heap_margin'] == 0
    rc, rep = run(tmp_path, *image(heap=B.MIN_HEAP - 1), capsys=capsys)
    assert rc == 1 and not [c for c in rep['checks'] if c['check'] == 'sram_budget'][0]['ok']
    # RAM that runs into boot_info fails whatever the heap symbols say.
    rc, rep = run(tmp_path, *image(bss=0x7FD4C - 2000 + 1, heap=B.MIN_HEAP), capsys=capsys)
    assert rc == 1
    rc, _ = run(tmp_path, *image(heap=B.MIN_HEAP - 1), argv=['--min-heap', '1000'], capsys=capsys)
    assert rc == 0


def test_heap_without_symbols_is_the_space_below_boot_info(tmp_path, capsys):
    secs, syms = image(data=0x1000, bss=0x1000)
    syms = [s for s in syms if not s[0].startswith('HEAP')]
    rc, rep = run(tmp_path, secs, syms, capsys=capsys)
    assert rep['heap_bytes'] == 0x7FD4C - 0x2000 and 'boot_info' in rep['heap_source']


def test_cache_ram_overflow_fails(tmp_path, capsys):
    rc, rep = run(tmp_path, *image(cache=28673), capsys=capsys)
    assert rc == 1 and rep['cache_ram_used'] == 28673


def test_spl_hole_is_reported_and_fatal_on_request(tmp_path, capsys):
    rc, rep = run(tmp_path, *image(data=0x6000), capsys=capsys)
    assert rc == 0 and rep['spl_hole_overlap'] == {'.ram0_data': 0x5820 - 0x2000}
    rc, rep = run(tmp_path, *image(data=0x6000), argv=['--spl-hole', 'fail'], capsys=capsys)
    assert rc == 1
    rc, rep = run(tmp_path, *image(data=0x1000, bss=0x400), argv=['--spl-hole', 'fail'], capsys=capsys)
    assert rc == 0 and rep['spl_hole_overlap'] == {}


def test_elf_and_app_bin_must_agree(tmp_path, capsys):
    rc, rep = run(tmp_path, *image(), app=4001, capsys=capsys)
    assert rc == 1 and not rep['elf_matches_app_bin']


def test_top_symbols_per_section(tmp_path, capsys):
    rc, rep = run(tmp_path, *image(), argv=['--top', '1'], capsys=capsys)
    top = rep['top_symbols']
    assert top['.text']['symbols'] == [{'name': 'big_table', 'size': 400}]
    assert top['.ram0_bss']['symbols'][0]['name'] == 'buf'


def test_text_output_and_usage_errors(tmp_path, capsys):
    secs, syms = image()
    elf = tmp_path/'sdk.elf'
    elf.write_bytes(synthetic_elf(secs, syms))
    binf = tmp_path/'app.bin'
    binf.write_bytes(bytes(4000))
    assert B.main([str(binf), '--elf', str(elf)]) == 0
    assert 'PASS sram_budget' in capsys.readouterr().out
    assert B.main([str(tmp_path/'missing.bin')]) == 2
    bad = tmp_path/'bad.elf'
    bad.write_bytes(b'not an elf')
    assert B.main([str(binf), '--elf', str(bad)]) == 2
    with pytest.raises(SystemExit) as e:
        B.main([str(binf), '--margin', '-1'])
    assert e.value.code == 2
