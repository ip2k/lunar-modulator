"""Offline expanded manifest checks; no device transports are instantiated."""
from copy import deepcopy
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/native'))
import expanded_candidate
import expanded_flash_profile as expanded
import expanded_transport_manifest as manifest
from tests.test_native_probe_artifact import fixture
from tests.test_raw_flash_profile import sample  # noqa: F401


def prepared(sample):
    # Span multiple erase sectors so directory-last ordering is exercised.
    elf = fixture(text_size=9000)
    _, app = expanded_candidate.flatten(elf, 'combined', 'expanded-d9000')
    target, candidate_receipt = expanded_candidate.construct(
        sample['baseline'], sample['baseline'], deepcopy(sample['manifest']),
        deepcopy(sample['identity']), sample['reference'], app, elf,
        'recorded-original-loader', ram_layout='combined')
    selection = dict(version=1, status='prepared-build-inputs',
                     request_sha256='1' * 64, prepared_profile_sha256='2' * 64,
                     project_ids=['event-horizon-showcase', 'other-song'],
                     startup_index=0, startup_project_id='event-horizon-showcase',
                     installable=False)
    image = dict(version=1, status='linked-private-diagnostic',
                 request_sha256=selection['request_sha256'],
                 prepared_profile_sha256=selection['prepared_profile_sha256'],
                 project_ids=selection['project_ids'], startup_index=0,
                 startup_project_id=selection['startup_project_id'],
                 app_sha256=manifest._sha256(app), elf_sha256=manifest._sha256(elf),
                 app_bytes=len(app), app_budget_bytes=expanded.APP_BUDGET,
                 installable=False, hardware_admitted=False, hardware_tested=False)
    return sample['baseline'], target, app, elf, candidate_receipt, image, selection


def test_manifest_rechecks_geometry_binds_receipts_and_puts_directory_last(sample):
    baseline, target, app, elf, candidate_receipt, image, selection = prepared(sample)
    result = manifest.build_manifest(baseline, target, sample['reference'], app, elf,
                                     candidate_receipt, image, selection)
    assert result['profile'] == 'expanded-d9000-recorded-092'
    assert result['app_bytes'] == len(app)
    assert result['app_sha256'] == manifest._sha256(app)
    assert result['elf_sha256'] == manifest._sha256(elf)
    assert result['request_sha256'] == selection['request_sha256']
    assert result['prepared_profile_sha256'] == selection['prepared_profile_sha256']
    assert result['sector_order'][:-1] == [s for s in result['changed_sectors']
                                           if s != result['directory_sector']]
    assert result['sector_order'][-1] == result['directory_sector'] == 0x4000
    assert result['protected_ranges'] == [[0, 0x4000], [0xD9000, 0x100000]]
    assert result['device_io_performed'] is False
    assert result['physical_writer_ready'] is False
    assert result['settings_migration_verified'] is False
    assert result['installable'] is False


@pytest.mark.parametrize('fault', [
    'target-hash', 'app-hash', 'elf-hash', 'wrong-profile', 'admitted',
    'image-app', 'image-elf', 'stale-size', 'request', 'selection-profile',
    'startup', 'foreign-sector', 'unsorted-sector', 'range-map', 'protected',
])
def test_manifest_refuses_stale_or_unsafe_receipt_and_sector_inputs(sample, fault):
    values = list(prepared(sample))
    baseline, target, app, elf, candidate_receipt, image, selection = values
    if fault == 'target-hash': candidate_receipt['target_sha256'] = '0' * 64
    elif fault == 'app-hash': candidate_receipt['app_sha256'] = '0' * 64
    elif fault == 'elf-hash': candidate_receipt['elf_sha256'] = '0' * 64
    elif fault == 'wrong-profile': candidate_receipt['profile'] = 'protected'
    elif fault == 'admitted': candidate_receipt['installable'] = True
    elif fault == 'image-app': image['app_sha256'] = '0' * 64
    elif fault == 'image-elf': image['elf_sha256'] = '0' * 64
    elif fault == 'stale-size': image['app_bytes'] += 4
    elif fault == 'request': image['request_sha256'] = '3' * 64
    elif fault == 'selection-profile': image['prepared_profile_sha256'] = '4' * 64
    elif fault == 'startup': image['startup_index'] = 1
    elif fault == 'foreign-sector': candidate_receipt['allowed_sectors'].append(0xD9000)
    elif fault == 'unsorted-sector': candidate_receipt['allowed_sectors'].reverse()
    elif fault == 'range-map': candidate_receipt['writable_ranges'][0][1] -= 4096
    elif fault == 'protected':
        altered = bytearray(target)
        altered[0xD9000] ^= 1
        target = bytes(altered)
    with pytest.raises(ValueError):
        manifest.build_manifest(baseline, target, sample['reference'], app, elf,
                                candidate_receipt, image, selection)
