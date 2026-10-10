"""Independent synthetic modified-image verification, no vendor bytes/device."""
import os
import pathlib
import struct
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'tools/jieli'))
import inspect_fwsc as outer
import inspect_stock_flash as nested
import model_app_replacement as model
from tests.test_inspect_stock_flash import synthetic_decoded, stock_files, encode, jlfs


def fix_envelope(image):
    count = 3
    for index in range(count):
        offset = 64 + index * 80
        entry = bytearray(outer.header_decode(image[offset:offset + 80]))
        start, size = struct.unpack_from('<II', entry, 8)
        struct.pack_into('<H', entry, 4, outer.crc16(image[start:start + size]))
        image[offset:offset + 80] = outer.header_decode(entry)
    header = bytearray(outer.header_decode(image[:64]))
    struct.pack_into('<H', header, 2, outer.crc16(image[64:64 + count * 80]))
    struct.pack_into('<H', header, 0, outer.crc16(header[2:]))
    image[:64] = outer.header_decode(header)


@pytest.fixture
def source(tmp_path, monkeypatch):
    # Only synthetic package_guard hash pin is bypassed, not format readers.
    monkeypatch.setattr(outer, 'check_package', lambda *args: {'passed': True})
    decoded = synthetic_decoded()
    stock = stock_files(tmp_path, decoded)
    (stock / 'ota.bin').write_bytes(b'OTA')
    raw = encode(decoded)
    image = model.logical(raw)
    image += b'OTA' + bytes(29) + bytes(48) + b'JLUFW' + bytes(11)
    values = [(0, 'flash.bin', 0x400, 0x93000),
              (100, 'ota.bin', 0x93400, 3), (255, 'tail.bin', 0x93420, 64)]
    for ordinal, (kind, name, start, length) in enumerate(values):
        fields = (kind, ordinal, outer.crc16(image[start:start + length]), 0,
                  start, length, length, bytes(44), name.encode())
        image[64 + ordinal * 80:144 + ordinal * 80] = outer.header_decode(struct.pack('<HHHHIII44s16s', *fields))
    header = struct.pack('<HIHHI48s', outer.crc16(image[64:304]), len(image), 3, 4, 512, b'AC791N')
    image[:64] = outer.header_decode(struct.pack('<H', outer.crc16(header)) + header)
    return model.physical(image, raw), stock


def mutate_flash(candidate, mutation):
    image = model.logical(candidate)
    decoded = bytearray(outer.sfc_decode(image[0x4400:0x93400], 0))
    mutation(decoded)
    image[0x4400:0x93400] = outer.sfc_decode(decoded, 0)
    fix_envelope(image)
    return model.physical(image, candidate)


def test_model_changes_app_preserves_tail_layout_and_strict_stock_gate(source):
    raw, stock = source
    candidate = model._build(raw, stock, b'HI')
    result = model.verify_replacement(raw, candidate, stock, b'HI')
    assert result['status'] == 'offline-app-replacement-model-verified'
    assert not result['packaging_ready'] and not result['binary_emitted']
    assert not result['identity_changed'] and result['device_execution'] == 'unverified'
    assert result['stock_extent_bytes'] == 4 and result['replacement_bytes'] == 2
    assert result['preserved_unused_app_tail_bytes'] == 2
    assert result['entry'] == 0x02000120 and result['app_image_offset'] == 0x4120
    assert result['modified_nested_check']['status'] == 'modified-app-inspected-model-only'
    with pytest.raises(ValueError, match='files/app.bin'):
        nested.inspect_nested(candidate, stock)
    assert len(raw) == len(candidate)
    decoded = outer.sfc_decode(model.logical(candidate)[0x4400:0x93400], 0)
    assert decoded[0x120:0x124] == b'HIDE'


@pytest.mark.parametrize('app', [b'', b'12345'])
def test_rejects_empty_or_growing_replacement(source, app):
    raw, stock = source
    with pytest.raises(ValueError, match='original app extent'):
        model._build(raw, stock, app)


def test_rejects_oversized_app_even_when_valid_directory_and_crcs_fit(source):
    raw, stock = source
    candidate = model._build(raw, stock, b'HI')
    app = b'X' * 20  # Fits the synthetic gap before cfg_tool, but exceeds old extent 4.
    def mutate(data):
        data[0x120:0x134] = app
        data[32:64] = jlfs('app.bin', 0x120, len(app), 0x82, 0, app)
        data[:32] = jlfs('app_area_head', 0x02000120, 0x400, 0x83, 0, data[32:0x400])
    damaged = mutate_flash(candidate, mutate)
    nested._inspect_app_replacement(damaged, stock, app)
    with pytest.raises(ValueError, match='original app extent'):
        model.verify_replacement(raw, damaged, stock, app)


def test_rejects_relocated_app_and_partition_changes_with_repaired_crcs(source):
    raw, stock = source
    candidate = model._build(raw, stock, b'HI')
    def relocate(data):
        data[0x130:0x132] = b'HI'
        data[32:64] = jlfs('app.bin', 0x130, 2, 0x82, 0, b'HI')
        data[:32] = jlfs('app_area_head', 0x02000120, 0x400, 0x83, 0, data[32:0x400])
    with pytest.raises(ValueError, match='entry disagrees'):
        model.verify_replacement(raw, mutate_flash(candidate, relocate), stock, b'HI')
    def partition(data):
        data[0x60:0x80] = jlfs('VM', 0x92000, 0x56000, 0x12, 0)
        data[:32] = jlfs('app_area_head', 0x02000120, 0x400, 0x83, 0, data[32:0x400])
    with pytest.raises(ValueError, match='reserved descriptor differs'):
        model.verify_replacement(raw, mutate_flash(candidate, partition), stock, b'HI')


def test_rejects_repaired_crc_unused_tail_modification(source):
    raw, stock = source
    candidate = model._build(raw, stock, b'HI')
    def mutate(data):
        data[0x123] ^= 1
        data[:32] = jlfs('app_area_head', 0x02000120, 0x400, 0x83, 0, data[32:0x400])
    damaged = mutate_flash(candidate, mutate)
    # Still passes modified app binding and every CRC, but violates tail preservation.
    nested._inspect_app_replacement(damaged, stock, b'HI')
    with pytest.raises(ValueError, match='outside replacement contract'):
        model.verify_replacement(raw, damaged, stock, b'HI')


def test_rejects_repaired_crc_resource_modification(source):
    raw, stock = source
    candidate = model._build(raw, stock, b'HI')
    def mutate(data):
        data[0x140:0x142] = b'NO'
        data[0x40:0x60] = jlfs('cfg_tool.bin', 0x140, 2, 0x82, 0, b'NO')
        data[:32] = jlfs('app_area_head', 0x02000120, 0x400, 0x83, 0, data[32:0x400])
    with pytest.raises(ValueError, match='cfg_tool.bin'):
        model.verify_replacement(raw, mutate_flash(candidate, mutate), stock, b'HI')


def test_rejects_repaired_outer_metadata_change(source):
    raw, stock = source
    candidate = model._build(raw, stock, b'HI')
    image = model.logical(candidate)
    header = bytearray(outer.header_decode(image[:64]))
    struct.pack_into('<I', header, 12, 513)
    struct.pack_into('<H', header, 0, outer.crc16(header[2:]))
    image[:64] = outer.header_decode(header)
    changed = model.physical(image, candidate)
    outer.inspect(changed, stock)
    with pytest.raises(ValueError, match='outer metadata changed'):
        model.verify_replacement(raw, changed, stock, b'HI')


def test_rejects_repaired_padding_and_trailer_change(source):
    raw, stock = source
    candidate = model._build(raw, stock, b'HI')
    image = model.logical(candidate)
    image[-20] ^= 1
    fix_envelope(image)
    changed = model.physical(image, candidate)
    outer.inspect(changed, stock)
    with pytest.raises(ValueError, match='non-flash entry changed'):
        model.verify_replacement(raw, changed, stock, b'HI')
    image = model.logical(candidate)
    image[500] ^= 1
    with pytest.raises(ValueError, match='padding/auxiliary/trailer'):
        model.verify_replacement(raw, model.physical(image, candidate), stock, b'HI')


def test_rejects_wrong_expected_app_and_unvalidated_elf(source):
    raw, stock = source
    candidate = model._build(raw, stock, b'HI')
    with pytest.raises(ValueError, match='files/app.bin'):
        model.verify_replacement(raw, candidate, stock, b'NO')
    with pytest.raises(ValueError):
        model.model(raw, stock, bytes(64), b'HI')


def test_cli_has_no_binary_output_and_refuses_report_overwrite(tmp_path, monkeypatch):
    report_path = tmp_path / 'report.json'
    report_path.write_text('preserve me')
    for name in ('fwsc', 'elf', 'app'):
        (tmp_path / name).write_bytes(b'input')
    args = ['model_app_replacement', str(tmp_path / 'fwsc'), '--stock', str(tmp_path),
            '--elf', str(tmp_path / 'elf'), '--app', str(tmp_path / 'app'),
            '--json', str(report_path)]
    monkeypatch.setattr(model, 'model', lambda *args: {'identity': 'FM-1_015'})
    monkeypatch.setattr(sys, 'argv', args)
    with pytest.raises(SystemExit) as error:
        model.main()
    assert error.value.code == 1 and report_path.read_text() == 'preserve me'
    monkeypatch.setattr(sys, 'argv', args + ['--out', str(tmp_path / 'candidate.fwsc')])
    with pytest.raises(SystemExit) as error:
        model.main()
    assert error.value.code == 2 and not (tmp_path / 'candidate.fwsc').exists()


@pytest.mark.skipif(not all(os.environ.get(name) for name in
                          ('FM1_STOCK_FWSC', 'FM1_STOCK_UNPACK', 'FM1_DIAGNOSTIC_ELF', 'FM1_DIAGNOSTIC_APP')),
                    reason='optional actual stock and linked diagnostic validation')
def test_actual_stock_diagnostic_model_and_all_guards():
    raw = pathlib.Path(os.environ['FM1_STOCK_FWSC']).read_bytes()
    stock = pathlib.Path(os.environ['FM1_STOCK_UNPACK'])
    elf = pathlib.Path(os.environ['FM1_DIAGNOSTIC_ELF']).read_bytes()
    app = pathlib.Path(os.environ['FM1_DIAGNOSTIC_APP']).read_bytes()
    result = model.model(raw, stock, elf, app)
    assert result['link_audit']['passed'] and result['link_audit']['runtime'] == 'sdk-free'
    assert result['replacement_bytes'] == result['diagnostic_layout']['flash_bytes']
    assert result['stock_extent_bytes'] == 581564 and result['entry'] == 0x02000120
    assert not result['binary_emitted']
