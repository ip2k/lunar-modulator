"""Synthetic expanded NOR records; no vendor binary or device is used."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/jieli'))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/native'))
import expanded_flash_profile as expanded
import raw_flash_profile as stock
from flash_layout import app_budget
from tests.test_raw_flash_profile import sample


@pytest.mark.parametrize('size', [4, 581564, 838712, 868836])
def test_expanded_geometry_roundtrip(sample, size):
    app = b'A' * size
    target, receipt = expanded.construct_geometry(sample['baseline'], sample['baseline'], sample['reference'], app)
    assert receipt['geometry_verified'] and not receipt['installable']
    assert receipt['records_end'] <= 0xD9000
    assert target[:0x4000] == sample['baseline'][:0x4000]
    assert target[0xD9000:] == sample['baseline'][0xD9000:]
    assert expanded.validate_geometry(sample['baseline'], target, sample['reference'], app) == receipt
    # Existing strict unchanged-layout parser must refuse this new allocation.
    with pytest.raises(ValueError):
        stock._parse(target, sample['reference'], app)


@pytest.mark.parametrize('size', [0, 1, 3, 868840])
def test_expanded_budget_refusals(size):
    assert expanded.APP_BUDGET == app_budget('expanded-d9000')
    with pytest.raises(ValueError, match='aligned named budget'):
        expanded.extents(b'A' * size)


@pytest.mark.parametrize('offset', [0, 0x1000, 0x38D0, 0xD9000, 0xE9000, 0xEA000, 0xFF000])
def test_protected_physical_refusals(sample, offset):
    app = b'A' * 838712
    target, _ = expanded.construct_geometry(sample['baseline'], sample['baseline'], sample['reference'], app)
    changed = bytearray(target); changed[offset] ^= 1
    with pytest.raises(ValueError, match='Protected physical'):
        expanded.validate_geometry(sample['baseline'], bytes(changed), sample['reference'], app)


@pytest.mark.parametrize('offset', [0x4000, 0x4020, 0x4040, 0x4060, 0x40E0, 0x4120, 0xD8FFF])
def test_cipher_crc_and_padding_refusals(sample, offset):
    app = b'A' * 838712
    target, _ = expanded.construct_geometry(sample['baseline'], sample['baseline'], sample['reference'], app)
    changed = bytearray(target); changed[offset] ^= 1
    with pytest.raises(ValueError):
        expanded.validate_geometry(sample['baseline'], bytes(changed), sample['reference'], app)


def test_mismatched_backup_refusal(sample):
    changed = bytearray(sample['baseline']); changed[-1] ^= 1
    with pytest.raises(ValueError, match='Baseline copies differ'):
        expanded.construct_geometry(sample['baseline'], bytes(changed), sample['reference'], b'AAAA')


@pytest.mark.parametrize('change', ['tool', 'cfg', 'reserved', 'entry', 'tool-address', 'padding'])
def test_rechecks_contents_after_crc_repair(sample, change):
    app = b'A' * 838712
    target, receipt = expanded.construct_geometry(sample['baseline'], sample['baseline'], sample['reference'], app)
    decoded = bytearray(target)
    decoded[0x4000:expanded.AREA_END] = stock.sfc_decode(target[0x4000:expanded.AREA_END], 0)
    tool, cfg = receipt['tool_start'], receipt['cfg_start']
    if change == 'tool':
        decoded[tool] ^= 1
        expanded._patch_record(decoded, 0x4040, crc16=stock.crc16(decoded[tool:tool + 383]))
    elif change == 'cfg':
        decoded[cfg + 64] ^= 1
        expanded._patch_record(decoded, cfg + 32, crc16=stock.crc16(decoded[cfg + 64:cfg + stock.CFG_BYTES]))
        expanded._patch_record(decoded, cfg, crc16=stock.crc16(decoded[cfg + 32:cfg + stock.CFG_BYTES]))
    elif change == 'reserved':
        expanded._patch_record(decoded, 0x4060, address=0xD8000)
    elif change == 'entry':
        expanded._patch_record(decoded, 0x4020, address=0x124)
    elif change == 'tool-address':
        expanded._patch_record(decoded, 0x4040, address=tool - 0x4000 + 4)
    else:
        decoded[tool + 383] = 0
    expanded._patch_record(decoded, 0x4000, crc16=stock.crc16(decoded[0x4020:cfg]))
    changed = target[:0x4000] + stock.sfc_decode(decoded[0x4000:expanded.AREA_END], 0) + target[expanded.AREA_END:]
    with pytest.raises(ValueError):
        expanded.validate_geometry(sample['baseline'], changed, sample['reference'], app)


@pytest.mark.parametrize('size', [4, 845036, 860644])
def test_d7000_geometry_preserves_reserved_tail(sample, size):
    app = b'A' * size
    baseline = sample['baseline']
    target, receipt = expanded.construct_geometry(
        baseline, baseline, sample['reference'], app, 'expanded-d7000')
    assert receipt['profile'] == 'expanded-d7000-recorded-092'
    assert receipt['records_end'] <= 0xD7000
    assert target[0xD7000:] == baseline[0xD7000:]
    assert not receipt['installable'] and not receipt['hardware_admitted']
    assert expanded.validate_geometry(
        baseline, target, sample['reference'], app, 'expanded-d7000') == receipt
    for offset in (0xD7000, 0xD8000, 0xD8FFF):
        changed = bytearray(target)
        changed[offset] ^= 1
        with pytest.raises(ValueError, match='Protected physical'):
            expanded.validate_geometry(
                baseline, bytes(changed), sample['reference'], app, 'expanded-d7000')


def test_d7000_geometry_rejects_tail_overlap_and_unknown_profiles():
    assert 860644 == app_budget('expanded-d7000')
    with pytest.raises(ValueError, match='aligned named budget'):
        expanded.extents(b'A' * 860648, 'expanded-d7000')
    for profile in ('protected', 'expanded', None, []):
        with pytest.raises(ValueError, match='Unknown expanded flash layout'):
            expanded.extents(b'AAAA', profile)
