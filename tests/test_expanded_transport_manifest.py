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
from build_demo_image import SHAPES8_TABLES, WAVETABLE_PROFILE, SHAPES8_WAVETABLE_PROFILE, TARGET_STORAGE
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
                 module_selection=dict(selected=['trio']),
                 wavetable_profile=WAVETABLE_PROFILE, compressed_wave_tables=[],
                 indexed_tft=True, flash_plaits_wavetables=True, shapes_voices=12,
                 instance_pool_bytes=249088, target_app_storage=dict(TARGET_STORAGE),
                 runtime_configuration=dict(runtime_mode='song-diagnostic',
                                            return_to_rom_seconds=120,
                                            define='-DLUNAR_RETURN_TO_ROM_SECONDS=120',
                                            release_accepted=False),
                 project_save_service=dict(linked=True,
                                           compile_definition='LUNAR_PROJECT_SAVE_SERVICE=1',
                                           storage_admitted=False, flash_io_bound=False,
                                           save_service_armed=False, runtime_verified=False,
                                           hardware_tested=False),
                 state_bin_codec=dict(mode='compact-writer',
                                      source='/src/engines/state/state_bin.c',
                                      source_sha256='a' * 64,
                                      cached_object='/catalogue/obj/state_bin.o',
                                      cached_object_sha256='b' * 64,
                                      fresh_object='/out/state_bin.o',
                                      fresh_object_sha256='c' * 64,
                                      compile_flags=['-target', 'pi32v2',
                                                     '-DFM1_STATE_BIN_COMPACT_WRITER=1'],
                                      compile_definition='FM1_STATE_BIN_COMPACT_WRITER=1',
                                      replaced_exactly_one=True),
                 verification_sha256='d' * 64, artifact_receipt_sha256='e' * 64,
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
    assert result['wavetable_profile'] == WAVETABLE_PROFILE
    assert result['wavetable_receipt_verified'] is True
    assert result['runtime_configuration']['return_to_rom_seconds'] == 120
    assert result['project_save_service']['save_service_armed'] is False
    assert result['state_bin_codec']['replaced_exactly_one'] is True
    assert result['verification_sha256'] == image['verification_sha256']
    assert result['artifact_receipt_sha256'] == image['artifact_receipt_sha256']
    assert result['device_io_performed'] is False
    assert result['physical_writer_ready'] is False
    assert result['settings_migration_verified'] is False
    assert result['installable'] is False


def test_manifest_accepts_exact_reviewed_shapes8_compressed_ram_profile(sample):
    baseline, target, app, elf, candidate_receipt, image, selection = prepared(sample)
    image['module_selection'] = dict(selected=['macro', 'shapes'])
    image.update(wavetable_profile=SHAPES8_WAVETABLE_PROFILE,
                 compressed_wave_tables=[dict(row) for row in SHAPES8_TABLES],
                 indexed_tft=True, flash_plaits_wavetables=False, shapes_voices=8,
                 instance_pool_bytes=165376, target_app_storage=dict(TARGET_STORAGE))
    result = manifest.build_manifest(baseline, target, sample['reference'], app, elf,
                                     candidate_receipt, image, selection)
    assert result['wavetable_profile'] == SHAPES8_WAVETABLE_PROFILE
    assert result['wavetable_receipt_verified'] is True
    assert result['installable'] is False
    assert result['hardware_admitted'] is False


@pytest.mark.parametrize('fault', [
    'target-hash', 'app-hash', 'elf-hash', 'wrong-profile', 'admitted',
    'image-app', 'image-elf', 'stale-size', 'request', 'selection-profile',
    'startup', 'foreign-sector', 'unsorted-sector', 'range-map', 'protected',
    'wavetable-voice', 'wavetable-pool', 'wavetable-row', 'wavetable-profile',
    'runtime-mode', 'runtime-seconds', 'save-linked', 'save-armed',
    'codec-mode', 'codec-replacement', 'codec-definition', 'codec-hash',
    'codec-flags', 'verification-digest', 'artifact-digest',
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
    elif fault == 'wavetable-voice': image['shapes_voices'] = 8
    elif fault == 'wavetable-pool': image['instance_pool_bytes'] = 165376
    elif fault == 'wavetable-row': image['compressed_wave_tables'] = [dict(SHAPES8_TABLES[0])]
    elif fault == 'wavetable-profile': image['wavetable_profile'] = SHAPES8_WAVETABLE_PROFILE
    elif fault == 'runtime-mode': image['runtime_configuration']['runtime_mode'] = 'diagnostic'
    elif fault == 'runtime-seconds': image['runtime_configuration']['return_to_rom_seconds'] = 20
    elif fault == 'save-linked': image['project_save_service']['linked'] = False
    elif fault == 'save-armed': image['project_save_service']['save_service_armed'] = True
    elif fault == 'codec-mode': image['state_bin_codec']['mode'] = 'legacy'
    elif fault == 'codec-replacement': image['state_bin_codec']['replaced_exactly_one'] = False
    elif fault == 'codec-definition': image['state_bin_codec']['compile_definition'] = 'FM1_STATE_BIN_COMPACT_WRITER=0'
    elif fault == 'codec-hash': image['state_bin_codec']['fresh_object_sha256'] = 'z' * 64
    elif fault == 'codec-flags': image['state_bin_codec']['compile_flags'].remove('-DFM1_STATE_BIN_COMPACT_WRITER=1')
    elif fault == 'verification-digest': image['verification_sha256'] = 'z' * 64
    elif fault == 'artifact-digest': image['artifact_receipt_sha256'] = 'z' * 64
    with pytest.raises(ValueError):
        manifest.build_manifest(baseline, target, sample['reference'], app, elf,
                                candidate_receipt, image, selection)
