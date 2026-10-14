"""Offline gates use synthetic bytes; they never create hardware admission."""
import copy
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/native'))
import expanded_candidate as candidate
from tests.test_native_probe_artifact import fixture
from tests.test_raw_flash_profile import sample  # noqa: F401


def inputs(s, size=128, layout='combined'):
    elf = fixture(text_size=size)
    _, app = candidate.flatten(elf, layout, 'expanded-d9000')
    return dict(baseline_a=s['baseline'], baseline_b=s['baseline'], manifest=copy.deepcopy(s['manifest']),
                identity=copy.deepcopy(s['identity']), reference=s['reference'], app=app, elf=elf,
                baseline_profile='recorded-original-loader', ram_layout=layout)


@pytest.mark.parametrize('layout', ['legacy', 'combined'])
@pytest.mark.parametrize('size', [128, 581564, 838704, 868828])
def test_expanded_candidate_binds_exact_inputs(sample, layout, size):
    args = inputs(sample, size, layout)
    target, r = candidate.construct(**args)
    assert r['provenance_verified'] and r['elf_verified'] and r['geometry_verified']
    assert r['baseline_sha256'] == candidate.raw.digest(sample['baseline'])
    assert r['elf_sha256'] == candidate.raw.digest(args['elf'])
    assert r['app_sha256'] == candidate.raw.digest(args['app'])
    assert r['target_sha256'] == candidate.raw.digest(target)
    assert r['link_audit']['passed'] and not r['link_audit']['n_pending']
    assert r['link_audit']['runtime'] == 'sdk-free'
    assert r['allowed_sectors'][0] == r['directory_sector'] == 0x4000
    assert all(0x4000 <= s < 0xD9000 for s in r['allowed_sectors'])
    assert r['protected_ranges'] == [[0, 0x4000], [0xD9000, 0x100000]]
    assert target[:0x4000] == sample['baseline'][:0x4000]
    assert target[0xD9000:] == sample['baseline'][0xD9000:]
    for field in ('installable', 'hardware_admitted', 'physical_writer_ready', 'hardware_approval',
                  'settings_migration_verified', 'ota_package_verified', 'binary_emitted'):
        assert r[field] is False



@pytest.mark.parametrize('kind', ['baseline', 'truncated', 'manifest-hash', 'loader', 'duplicate',
                                 'identity', 'simulated', 'unit', 'unknown-profile', 'wrong-fixed-profile',
                                 'app', 'elf', 'layout', 'overflow', 'forbidden-constant', 'protected'])
def test_expanded_candidate_refuses_unbound_or_unsafe_inputs(sample, kind):
    args = inputs(sample)
    if kind == 'baseline': args['baseline_b'] = b'bad'
    elif kind == 'truncated': args['baseline_a'] = args['baseline_b'] = args['baseline_a'][:-1]
    elif kind == 'manifest-hash': args['manifest']['dumps'][0]['sha256'] = '0' * 64
    elif kind == 'loader': args['manifest']['loader_sha256'] = '0' * 64
    elif kind == 'duplicate': args['manifest']['dumps'].append(args['manifest']['dumps'][0])
    elif kind == 'identity': args['identity']['firmware'] = 'FM-1_015'
    elif kind == 'simulated': args['identity']['simulated'] = True
    elif kind == 'unit': args['identity']['unit_id'] = ''
    elif kind == 'unknown-profile': args['baseline_profile'] = 'sdk'
    elif kind == 'wrong-fixed-profile': args['baseline_profile'] = 'fixed-loader'
    elif kind == 'app': args['app'] = b'wrong'
    elif kind == 'elf': args['elf'] = b'bad'
    elif kind == 'layout': args['ram_layout'] = 'other'
    elif kind == 'overflow': args['elf'] = fixture(text_size=868836)
    elif kind == 'forbidden-constant':
        # Keep ELF/app correspondence while injecting the forbidden entry stub address.
        args['elf'] = args['elf'].replace(b'DATA', bytes.fromhex('2e010002'))
        _, args['app'] = candidate.flatten(args['elf'], 'combined', 'expanded-d9000')
    elif kind == 'protected':
        b = bytearray(args['baseline_a']); b[0] ^= 1
        args['baseline_a'] = args['baseline_b'] = bytes(b)
    with pytest.raises((ValueError, IndexError)):
        candidate.construct(**args)


@pytest.mark.parametrize('layout', ['legacy', 'combined'])
def test_d7000_candidate_binds_reserved_tail(sample, layout):
    args = inputs(sample, 845028, layout)
    args['flash_layout'] = 'expanded-d7000'
    target, receipt = candidate.construct(**args)
    assert receipt['flash_layout'] == 'expanded-d7000'
    assert receipt['records_end'] <= 0xD7000
    assert receipt['protected_ranges'] == [[0, 0x4000], [0xD7000, 0x100000]]
    assert all(0x4000 <= offset < 0xD7000 for offset in receipt['allowed_sectors'])
    assert target[0xD7000:] == sample['baseline'][0xD7000:]
    assert receipt['elf_verified'] and receipt['provenance_verified']
    for field in ('installable', 'hardware_admitted', 'physical_writer_ready',
                  'hardware_approval', 'settings_migration_verified', 'ota_package_verified'):
        assert receipt[field] is False


def test_d7000_candidate_rejects_app_that_only_fits_d9000(sample):
    args = inputs(sample, 860640)
    args['flash_layout'] = 'expanded-d7000'
    with pytest.raises(ValueError):
        candidate.construct(**args)
