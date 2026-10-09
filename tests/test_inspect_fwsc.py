"""Synthetic envelope damage tests; no vendor data or transmission."""
import pathlib
import struct
import sys

import pytest

TOOLS = pathlib.Path(__file__).resolve().parents[1] / 'tools/jieli'
sys.path.insert(0, str(TOOLS))
from inspect_fwsc import crc16, header_decode, inspect  # noqa: E402


def envelope(mutate_entry=None):
    image = bytearray(0x4a0)
    tail = bytes(48) + b'JLUFW' + bytes(11)
    values = [(0, 'flash.bin', 0x400, b'FLASH'),
              (100, 'ota.bin', 0x420, b'OTA'),
              (251, 'script.ver', 0x440, b'encrypted'),
              (255, 'tail.bin', 0x460, tail)]
    table = bytearray()
    for ordinal, (kind, name, offset, payload) in enumerate(values):
        fields = [kind, ordinal, crc16(payload), 0, offset, len(payload), len(payload), bytes(44), name.encode()]
        if mutate_entry:
            mutate_entry(ordinal, fields)
        table += header_decode(struct.pack('<HHHHIII44s16s', *fields))
        image[offset:offset + len(payload)] = payload
    header = struct.pack('<HIHHI48s', crc16(table), len(image), 4, 4, 512, b'AC791N')
    image[:64] = header_decode(struct.pack('<H', crc16(header)) + header)
    image[64:64 + len(table)] = table
    identity = b'FM-1_015'
    raw = bytearray()
    for index in range(20):
        raw += image[index * 47:(index + 1) * 47]
        raw.append(identity[index] + index + 1 if index < len(identity) else 125)
    raw += image[940:]
    return bytes(raw)


def test_crc_known_vector_and_incomplete_evidence_labels():
    assert crc16(b'123456789') == 0x31c3
    assert header_decode(bytes(4)) == bytes.fromhex('ffdf9f1f')
    result = inspect(envelope())
    assert result['identity'] == 'FM-1_015'
    assert result['header_crc_verified'] and result['entry_list_crc_verified']
    assert result['status'] == 'inspected-incomplete' and result['packaging_ready'] is False
    assert len(result['pending']) == 4
    assert not result['entries'][2]['crc_verified']
    assert result['entries'][1]['physical_offset'] == 0x434


@pytest.mark.parametrize('offset,message', [(0, 'header CRC'), (68, 'entry-list CRC'),
                                             (0x400 + 20, 'payload CRC')])
def test_rejects_corrupt_checked_layers(offset, message):
    raw = bytearray(envelope())
    raw[offset] ^= 1
    with pytest.raises(ValueError, match=message):
        inspect(bytes(raw))


@pytest.mark.parametrize('field,value,message', [(4, 0x400, 'overlapping'),
                                                (4, 0x900, 'outside'),
                                                (6, 1, 'outside'),
                                                (0, 123, 'unsupported'),
                                                (1, 9, 'index'),
                                                (8, b'flash.bin', 'duplicate')])
def test_rejects_semantic_damage_even_with_repaired_outer_crcs(field, value, message):
    def mutate(ordinal, fields):
        if ordinal == 1:
            fields[field] = value
    with pytest.raises(ValueError, match=message):
        inspect(envelope(mutate))


def test_rejects_identity_truncation_and_bad_stock(tmp_path):
    with pytest.raises(ValueError, match='truncated'):
        inspect(b'x' * 959)
    changed = bytearray(envelope())
    changed[9 * 48 + 47] = 100
    with pytest.raises(ValueError, match='noncontiguous'):
        inspect(bytes(changed))
    with pytest.raises(ValueError, match='stock reference'):
        inspect(envelope(), tmp_path)
