"""The dev-board pipeline image bounds, offline: writer region and heap after DAC open."""
import importlib.util
import json
from pathlib import Path
import struct

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_ENTRY = 0x02000120


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT/path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BOUNDS = load('pipeline_bounds', 'tools/jieli/pipeline_bounds.py')


def synthetic_elf(sizes, heap, symbols=None):
    """A minimal ELF32 LE with the five load-image sections and the symbols
    pipeline_bounds reads; section contents are zeros."""
    names = ['.text', '.data', '.dynamic_data', '.ram0_data', '.cache_ram_data']
    lma = APP_ENTRY
    syms = {}
    for name, (lma_symbol) in zip(names, (None, 'data_lma', 'dynamic_data_lma', '_ram0_data_lma',
                                          'cache_ram_data_lma')):
        if lma_symbol:
            syms[lma_symbol] = lma
        lma += sizes[name]
    syms.update(HEAP_BEGIN=0x01C70000, HEAP_END=0x01C70000 + heap)
    syms.update(symbols or {})
    shstr = b'\0' + b'\0'.join(n.encode() for n in names + ['.symtab', '.strtab', '.shstrtab']) + b'\0'
    def shname(n):
        return shstr.index(b'\0' + n.encode() + b'\0') + 1
    strtab = b'\0'
    symtab = b'\0' * 16
    for name, value in syms.items():
        if value is None:
            continue
        symtab += struct.pack('<IIIBBH', len(strtab), value, 0, 0x10, 0, 1)
        strtab += name.encode() + b'\0'
    body = bytearray(52)
    sections = [struct.pack('<10I', *([0] * 10))]
    for name in names:
        offset = len(body)
        body += bytes(sizes[name])
        sections.append(struct.pack('<10I', shname(name), 1, 2, 0, offset, sizes[name], 0, 0, 4, 0))
    for name, blob, typ, link, entsize in (('.symtab', symtab, 2, 7, 16), ('.strtab', strtab, 3, 0, 0),
                                           ('.shstrtab', shstr, 3, 0, 0)):
        offset = len(body)
        body += blob
        sections.append(struct.pack('<10I', shname(name), typ, 0, 0, offset, len(blob), link, 0, 1, entsize))
    shoff = len(body)
    body += b''.join(sections)
    body[0:16] = b'\x7fELF\x01\x01\x01' + bytes(9)
    struct.pack_into('<HHIIIIIHHHHHH', body, 16, 2, 0, 1, APP_ENTRY, 0, shoff, 0, 52, 0, 0, 40,
                     len(sections), len(sections) - 1)
    return bytes(body)


def sizes(app):
    return {'.text': app - 3000, '.data': 0, '.dynamic_data': 0, '.ram0_data': 2000, '.cache_ram_data': 1000}


def test_bounds_are_the_writer_region_and_the_measured_heap():
    assert BOUNDS.APP_BYTES_LIMIT == 0x97000 - 0x4120 == 601824
    assert BOUNDS.HEAP_IN_USE_AFTER_OPEN == 43512 and BOUNDS.HEAP_MIN_AFTER_OPEN == 3700
    # V225, the last image the board ran: 598,140 app bytes, HEAP_SIZE 47,212,
    # 3,700 B left after DAC open (its boot and run logs).
    v225 = BOUNDS.measure(synthetic_elf(sizes(598140), 47212))
    assert v225['app_bytes'] == 598140 and v225['app_end'] == '0x9619c'
    assert v225['heap_after_open_predicted'] == 3700
    assert v225['writer_bound'] and v225['heap_bound']


# Heap 47,340 leaves 3,828 B predicted: the 3,700 floor plus 128.
@pytest.mark.parametrize('app,heap,writer,heap_ok,room', [
    (601696, 47340, True, True, True), (601697, 47340, True, True, False),
    (598140, 47339, True, True, False), (601823, 47212, True, True, False),
    (601824, 47212, False, True, False), (598140, 47211, True, False, False),
    (608380, 44460, False, False, False)])
def test_bounds_edges(tmp_path, app, heap, writer, heap_ok, room, capsys):
    report = BOUNDS.measure(synthetic_elf(sizes(app), heap))
    assert (report['writer_bound'], report['heap_bound']) == (writer, heap_ok)
    assert (report['writer_headroom'] and report['heap_headroom']) == room
    path = tmp_path/'sdk.elf'
    path.write_bytes(synthetic_elf(sizes(app), heap))
    assert BOUNDS.main([str(path)]) == (0 if room else 1)
    assert json.loads(capsys.readouterr().out)[str(path)]['app_bytes'] == app


def test_bounds_refuse_a_gap_or_a_missing_symbol():
    with pytest.raises(ValueError, match='does not follow'):
        BOUNDS.measure(synthetic_elf(sizes(598140), 47212, {'_ram0_data_lma': APP_ENTRY + 4}))
    with pytest.raises(ValueError, match='no HEAP_END'):
        BOUNDS.measure(synthetic_elf(sizes(598140), 47212, {'HEAP_END': None}))


def test_recorded_pipeline_images_meet_both_bounds():
    """The last measured native builds of every pipeline configuration
    (firmware/devkit/pipeline-image-sizes.json, written from pipeline_bounds.py
    output on aeon) stay inside both bounds; a preparer change that adds
    flash or SRAM must re-measure and update the record."""
    record = json.loads((ROOT/'firmware/devkit/pipeline-image-sizes.json').read_text())
    preparer = load('pipeline_prepare', 'tools/jieli/prepare-pipeline-devkit.py')
    assert record['app_bytes_limit'] == BOUNDS.APP_BYTES_LIMIT
    assert record['heap_min_after_open'] == BOUNDS.HEAP_MIN_AFTER_OPEN
    assert {'cap8-msfa', 'cap8-trunc12', 'fixed12-msfa'} <= set(record['images'])
    assert record['headroom'] == BOUNDS.HEADROOM == 128
    assert {'clk360-cap8-msfa', 'clk360-cap8-trunc12', 'clk360-fixed12-msfa'} <= set(record['images'])
    for name, image in record['images'].items():
        clk360 = name.startswith('clk360-')
        assert image['config'].get('sys_clk_hz', 320000000) == (360000000 if clk360 else 320000000), name
        assert image['app_bytes'] < BOUNDS.APP_BYTES_LIMIT, name
        assert image['heap_size'] - BOUNDS.HEAP_IN_USE_AFTER_OPEN >= BOUNDS.HEAP_MIN_AFTER_OPEN, name
        # The build gate's headroom: every image meets it in flash.
        assert image['app_margin'] == BOUNDS.APP_BYTES_LIMIT - image['app_bytes'] >= BOUNDS.HEADROOM, name
        assert image['heap_margin'] == image['heap_size'] - 43512 - 3700, name
        if image['heap_margin'] < BOUNDS.HEADROOM:
            # Only a 360 MHz image may fall short, and only as a recorded open
            # issue (pipeline_bounds.py still exits 1 for it).
            assert clk360 and 'open_issue' in image, name
        else:
            assert 'open_issue' not in image, name
        assert image['config']['policy'] in preparer.POLICIES
        assert image['config']['dx7_sine'] in ('msfa', 'trunc12')
    # The levers the record was measured with are still in the preparer.
    assert {f'{n}: {a.strip()[:-2]}' for n, a in preparer.PIPELINE_INIT_XIP} == set(record['init_xip_functions'])
    assert record['resampler_benchmark_linked'] is False
