"""Independent synthetic nested checks; no vendor bytes and no transmission."""
import os
import pathlib
import struct
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'tools/jieli'))
import inspect_stock_flash as nested  # noqa: E402
from inspect_fwsc import crc16, header_decode, sfc_decode  # noqa: E402


def jlfs(name, address, size, flags, terminal, data=None, crc=None):
    data_crc = crc16(data) if data is not None else 0xffff if crc is None else crc
    body = struct.pack('<HIIBBH16s', data_crc, address, size, flags, 0, terminal, name.encode())
    return struct.pack('<H', crc16(body)) + body


def synthetic_decoded():
    decoded = bytearray(0x93000)
    decoded[:32] = struct.pack('<H', crc16(bytes(30))) + bytes(30)
    blob = bytes([100] * 16) + bytes(100 ^ (0 if 0x980f & (1 << i) else 255) for i in range(16))
    cfg = blob + struct.pack('<H', crc16(blob)) + bytes(665)
    decoded[0x38d0:0x38d0 + 699] = cfg
    bank = bytes(14368)
    bank_head = struct.pack('<HHIIH', 1, len(bank), 0x01c02000, 16, crc16(bank))
    spl = bank_head + struct.pack('<H', crc16(bank_head)) + bank
    decoded[0xa0:0x38d0] = spl
    decoded[0x20:0xa0] = (
        jlfs('uboot.boot', 0xa0, len(spl), 0, 0, spl)
        + jlfs('isd_config.ini', 0x38d0, 699, 2, 0, cfg)
        + jlfs('app_dir_head', 0x4000, 0xffffffff, 0x81, 0)
        + jlfs('key_mac', 0xff000, 0x1000, 0x12, 0xffff))
    decoded[0x4120:0x4124] = b'CODE'
    decoded[0x4140:0x4142] = b'CF'
    children = [jlfs('app.bin', 0x120, 4, 0x82, 0, b'CODE'),
                jlfs('cfg_tool.bin', 0x140, 2, 0x82, 0, b'CF')]
    for index, name in enumerate(['VM', 'PRCT', 'BTIF', 'USR']):
        address, size, flags = nested.EXPECTED_RESERVED[name]
        children.append(jlfs(name, address, size, flags, int(index == 3)))
    decoded[0x4020:0x40e0] = b''.join(children)
    decoded[0x4000:0x4020] = jlfs('app_area_head', 0x02000120, 0x400, 0x83, 0, decoded[0x4020:0x4400])
    decoded[0x4440:0x4443] = b'EQ!'
    decoded[0x4420:0x4440] = jlfs('eq_cfg_hw.bin', 0x40, 3, 0x82, 1, b'EQ!')
    decoded[0x4400:0x4420] = jlfs('cfg', 0x20, 0x80, 0x83, 1, decoded[0x4420:0x4480])
    return decoded


def encode(decoded):
    raw = bytearray(decoded)
    for offset in [0, 0x20, 0x40, 0x60, 0x80]:
        raw[offset:offset + 32] = header_decode(decoded[offset:offset + 32])
    raw[0xa0:0xb0] = header_decode(decoded[0xa0:0xb0])
    raw[0xb0:0x38d0] = header_decode(decoded[0xb0:0x38d0])
    raw[0x4000:] = sfc_decode(decoded[0x4000:], 0)
    logical = bytearray(0x400) + raw
    result = bytearray()
    for index in range(20):
        result += logical[index * 47:(index + 1) * 47]
        result.append(b'FM-1_015'[index] + index + 1 if index < 8 else 125)
    return bytes(result + logical[940:])


def fake_outer(raw, stock):
    return {'identity': 'FM-1_015', 'entries': [{'name': 'flash.bin', 'offset': 0x400, 'bytes': 0x93000}]}


def stock_files(tmp_path, decoded):
    (tmp_path / 'top').mkdir()
    (tmp_path / 'files').mkdir()
    (tmp_path / 'top/uboot.boot').write_bytes(decoded[0xa0:0x38d0])
    (tmp_path / 'top/isd_config.ini').write_bytes(decoded[0x38d0:0x38d0 + 699])
    (tmp_path / 'files/cfg').write_bytes(decoded[0x4400:0x4480])
    (tmp_path / 'files/app.bin').write_bytes(decoded[0x4120:0x4124])
    (tmp_path / 'files/cfg_tool.bin').write_bytes(decoded[0x4140:0x4142])
    (tmp_path / 'files/eq_cfg_hw.bin').write_bytes(decoded[0x4440:0x4443])
    return tmp_path


def test_nested_synthetic_noop_and_binding(monkeypatch, tmp_path):
    decoded = synthetic_decoded()
    monkeypatch.setattr(nested, 'inspect', fake_outer)
    stock = stock_files(tmp_path, decoded)
    result = nested.inspect_nested(encode(decoded), stock)
    assert result['full_container_noop_identical'] and not result['packaging_ready']
    assert result['device_execution'] == 'unverified'
    assert result['spl_bank']['load_address'] == 0x01c02000
    assert result['top'][-1]['data_crc_verified'] is False
    assert set(result['nested_file_sha256']) == {'app.bin', 'cfg_tool.bin', 'eq_cfg_hw.bin'}
    (stock / 'files/cfg').write_bytes(b'changed')
    with pytest.raises(ValueError, match='guarded decoded component'):
        nested.inspect_nested(encode(decoded), stock)


@pytest.mark.parametrize('offset,message', [(2, 'flash header CRC'), (0x22, 'JLFS header CRC'),
                                            (0xa2, 'SPL bank header CRC'), (0xb0, 'SPL bank data CRC'),
                                            (0x38f3, 'JLFS data CRC'), (0x4120, 'JLFS data CRC')])
def test_nested_damage_survives_repaired_outer_crc(monkeypatch, tmp_path, offset, message):
    decoded = synthetic_decoded()
    stock = stock_files(tmp_path, decoded)
    decoded[offset] ^= 1
    monkeypatch.setattr(nested, 'inspect', fake_outer)
    with pytest.raises(ValueError, match=message):
        nested.inspect_nested(encode(decoded), stock)


def test_helpers_reject_unchecked_ranges_names_and_reserved_layout():
    with pytest.raises(ValueError, match='outside'):
        nested.bounded(b'x', 1, 2)
    with pytest.raises(ValueError, match='stock reserved descriptor differs'):
        item = nested.record(jlfs('USR', 0xea000, 1, 0x92, 1), 0)
        nested.reserved(item, set())
    with pytest.raises(ValueError, match='invalid JLFS name'):
        nested.record(jlfs('ABCDEFGHIJKLMNOP', 0, 0, 0x82, 1), 0)
    with pytest.raises(ValueError, match='stock chip-key blob CRC'):
        nested.stock_key(bytes(34)[:-1] + b'x')


@pytest.mark.parametrize('name,offset,size,header', [('app.bin', 0x4120, 4, 0x4020),
                                                   ('cfg_tool.bin', 0x4140, 2, 0x4040),
                                                   ('eq_cfg_hw.bin', 0x4440, 3, 0x4420)])
def test_rejects_changed_files_after_all_nested_crcs_repaired(monkeypatch, tmp_path, name, offset, size, header):
    decoded = synthetic_decoded()
    stock = stock_files(tmp_path, decoded)
    decoded[offset:offset + size] = b'X' * size
    block = 0x4400 if name == 'eq_cfg_hw.bin' else 0x4000
    decoded[header:header + 32] = jlfs(name, offset - block, size, 0x82,
                                     int(name == 'eq_cfg_hw.bin'), b'X' * size)
    decoded[block:block + 32] = jlfs('cfg' if block == 0x4400 else 'app_area_head',
                                   0x20 if block == 0x4400 else 0x02000120,
                                   0x80 if block == 0x4400 else 0x400, 0x83,
                                   int(block == 0x4400), decoded[block + 32:block + (0x80 if block == 0x4400 else 0x400)])
    monkeypatch.setattr(nested, 'inspect', fake_outer)
    with pytest.raises(ValueError, match='guarded decoded component differs'):
        nested.inspect_nested(encode(decoded), stock)


def test_eq_file_reference_is_required_even_when_cfg_block_matches(monkeypatch, tmp_path):
    decoded = synthetic_decoded()
    stock = stock_files(tmp_path, decoded)
    (stock / 'files/eq_cfg_hw.bin').write_bytes(b'bad')
    monkeypatch.setattr(nested, 'inspect', fake_outer)
    with pytest.raises(ValueError, match='files/eq_cfg_hw.bin'):
        nested.inspect_nested(encode(decoded), stock)


@pytest.mark.skipif(not os.environ.get('FM1_STOCK_FWSC') or not os.environ.get('FM1_STOCK_UNPACK'),
                    reason='optional real stock container/component validation')
def test_real_stock_nested_crc_binding_and_noop():
    result = nested.inspect_nested(pathlib.Path(os.environ['FM1_STOCK_FWSC']).read_bytes(),
                                   pathlib.Path(os.environ['FM1_STOCK_UNPACK']))
    assert result['full_container_noop_identical']
    assert result['bound_component_sha256']['top/uboot.boot'] == (
        '730e54f0a439f58d147be4364ad21e19566945ada9d3a7bbc8371dce5068d3ef')


@pytest.mark.parametrize('address,message', [(0x120, 'overlapping nested files'),
                                            (0x1000, 'outside directory data')])
def test_rejects_file_geometry_with_repaired_nested_crcs(monkeypatch, tmp_path, address, message):
    decoded = synthetic_decoded()
    stock = stock_files(tmp_path, decoded)
    decoded[0x4040:0x4060] = jlfs('cfg_tool.bin', address, 4, 0x82, 0, b'CODE')
    decoded[0x4000:0x4020] = jlfs('app_area_head', 0x02000120, 0x400, 0x83, 0, decoded[0x4020:0x4400])
    monkeypatch.setattr(nested, 'inspect', fake_outer)
    with pytest.raises(ValueError, match=message):
        nested.inspect_nested(encode(decoded), stock)
