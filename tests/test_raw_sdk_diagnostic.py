"""SDK/raw guard boundary tests; private actual ELF cases require explicit input."""
import copy
import json
import os
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/jieli'))
import build_raw_diagnostic as old
import build_raw_sdk_diagnostic as builder
import raw_flash_profile as raw
import raw_sdk_diagnostic as sdk
from tests.test_raw_flash_profile import sample, encode, repair_app  # noqa: F401


def fixed_inputs(s):
    manifest = copy.deepcopy(s['manifest'])
    usb = dict(path='3-2', busnum='3', devnum='99', vid='4c4a', pid='8057')
    manifest.update(schema=1, kind='fm1-fixed-loader-backup',
        loader_sha256=raw.FIXED_LOADER_SHA256, original_loader_sha256=raw.LOADER_SHA256,
        loader_profile_sha256=raw.FIXED_PROFILE_SHA256,
        profile_source_sha256=raw.FIXED_PROFILE_SOURCE_SHA256,
        dependency_sha256={'fm1_uboot_read.py': raw.FIXED_READER_SHA256},
        unit_identity='FM-1_092', command_completions=True, flash_readback_only=True,
        commands=8757, adapter_sha256='a'*64, campaign_sha256='b'*64,
        entry_log_sha256='c'*64, request_inventory_sha256=raw.FIXED_REQUEST_INVENTORY_SHA256,
        usb_binding=usb)
    for item in manifest['dumps']:
        item['complete'] = True
    identity = dict(s['identity'], usb_binding=usb, entry_log_sha256='c'*64)
    return manifest, identity


def test_fixed_loader_provenance_is_distinct_and_never_relabels_original(sample):
    s = sample
    manifest, identity = fixed_inputs(s)
    profile = raw.profile_dump_fixed_loader(s['baseline'], s['baseline'], manifest, identity, s['reference'])
    assert profile['loader_sha256'] == raw.FIXED_LOADER_SHA256
    assert not profile['physical_writer_ready']
    with pytest.raises(ValueError, match='manifest'):
        raw.profile_dump(s['baseline'], s['baseline'], manifest, identity, s['reference'])
    with pytest.raises(ValueError, match='manifest'):
        raw.profile_dump_fixed_loader(s['baseline'], s['baseline'], s['manifest'], s['identity'], s['reference'])


@pytest.mark.parametrize('field', ['loader_sha256', 'original_loader_sha256', 'loader_profile_sha256',
    'profile_source_sha256', 'dependency_sha256', 'command_completions', 'flash_readback_only',
    'commands', 'adapter_sha256', 'campaign_sha256', 'entry_log_sha256', 'request_inventory_sha256',
    'unit_identity', 'usb_binding', 'dumps'])
def test_fixed_backup_provenance_rejects_missing_or_changed_evidence(sample, field):
    manifest, identity = fixed_inputs(sample)
    del manifest[field]
    with pytest.raises(ValueError):
        raw.profile_dump_fixed_loader(sample['baseline'], sample['baseline'], manifest, identity, sample['reference'])


@pytest.mark.parametrize('mutation', ['entry', 'usb', 'complete', 'dump_hash', 'inventory', 'command_bool'])
def test_fixed_backup_rejects_inconsistent_bindings(sample, mutation):
    manifest, identity = fixed_inputs(sample)
    if mutation == 'entry':
        identity['entry_log_sha256'] = 'd'*64
    elif mutation == 'usb':
        identity['usb_binding'] = dict(identity['usb_binding'], devnum='100')
    elif mutation == 'complete':
        manifest['dumps'][0]['complete'] = False
    elif mutation == 'dump_hash':
        manifest['dumps'][0]['sha256'] = 'd'*64
    elif mutation == 'inventory':
        manifest['request_inventory_sha256'] = 'd'*64
    else:
        manifest['commands'] = True
    with pytest.raises(ValueError):
        raw.profile_dump_fixed_loader(sample['baseline'], sample['baseline'], manifest, identity, sample['reference'])


def test_sdk_path_cannot_accept_sdk_free_elf_or_unknown_backup_profile(sample, tmp_path):
    s = sample
    args = (s['baseline'], s['baseline'], s['manifest'], s['identity'], s['reference'], s['app'], s['elf'])
    with pytest.raises(ValueError):
        builder.construct(*args)
    with pytest.raises(ValueError, match='provenance'):
        builder.construct(*args, baseline_profile='sdk')
    assert not (tmp_path / 'output').exists()


@pytest.fixture
def actual_sdk():
    path = os.environ.get('LUNAR_SDK_ELF')
    if not path:
        pytest.skip('Set LUNAR_SDK_ELF to the private reviewed native candidate')
    elf = Path(path).read_bytes()
    app, _ = sdk.native.reconstruct(sdk.Elf(elf))
    return elf, app


def construct_actual(s, candidate, **kwargs):
    elf, app = candidate
    return builder.construct(s['baseline'], s['baseline'], s['manifest'], s['identity'],
                             s['reference'], app, elf, **kwargs)


def test_actual_sdk_constructs_exact_image_and_old_gate_remains_closed(sample, actual_sdk, tmp_path):
    elf, app = actual_sdk
    target, receipt = construct_actual(sample, actual_sdk)
    independently_built = bytearray(sample['decoded'])
    repair_app(independently_built, app)
    assert target == encode(independently_built)
    assert receipt['diagnostic_profile'] == 'sdk-dual-core-private'
    assert receipt['native_scheduling_checked']
    assert receipt['link_audit']['runtime'] == 'sdk'
    assert not receipt['hardware_approval'] and not receipt['physical_writer_ready']
    assert not receipt['diagnostic_layout']['flashable']
    assert receipt['protected_raw_bytes_identical'] and receipt['original_app_tail_identical']
    with pytest.raises(ValueError):
        old.construct(sample['baseline'], sample['baseline'], sample['manifest'], sample['identity'],
                      sample['reference'], app, elf)
    with pytest.raises(ValueError):
        old.emit(tmp_path / 'old', target, receipt)
    result = builder.emit(tmp_path / 'sdk', target, receipt)
    assert result['binary_emitted']
    assert json.loads((tmp_path / 'sdk/receipt.json').read_bytes()) == result


@pytest.mark.parametrize('mutation', ['protected', 'tail', 'gap', 'app', 'elf', 'audit'])
def test_actual_sdk_rejects_extra_changes_and_unbound_audits(sample, actual_sdk, mutation):
    elf, app = actual_sdk
    target, receipt = construct_actual(sample, actual_sdk)
    options = {}
    if mutation == 'protected':
        data = bytearray(target); data[raw.CFG_TOOL_OFFSET] ^= 1; target = bytes(data)
    elif mutation in ('tail', 'gap'):
        data, _ = raw._parse(target, sample['reference'], replacement=app)
        data = bytearray(data)
        data[0x4120 + len(app) if mutation == 'tail' else 0x4100] ^= 1
        repair_app(data, app)
        target = encode(data)
    elif mutation == 'app':
        app = app[:-1] + bytes([app[-1] ^ 1])
    elif mutation == 'elf':
        native = sdk.Elf(elf)
        addr = native.symbol_value('p33_lock')
        section = next(s for s in native.sections if s['addr'] <= addr < s['addr'] + s['size'])
        data = bytearray(elf); data[section['offset'] + addr - section['addr']] ^= 1; elf = bytes(data)
    else:
        options['expected_native_audit'] = dict(passed=True, flashable=False)
    with pytest.raises(ValueError):
        sdk.validate_target(sample['baseline'], sample['baseline'], target, sample['manifest'],
            sample['identity'], sample['reference'], app, elf, **options)


def test_actual_sdk_with_fixed_loader_backups_retains_actual_provenance(sample, actual_sdk):
    elf, app = actual_sdk
    manifest, identity = fixed_inputs(sample)
    target, receipt = builder.construct(sample['baseline'], sample['baseline'], manifest, identity,
        sample['reference'], app, elf, baseline_profile='fixed-loader')
    assert receipt['profile']['loader_sha256'] == raw.FIXED_LOADER_SHA256
    assert receipt['baseline_profile'] == 'fixed-loader'
