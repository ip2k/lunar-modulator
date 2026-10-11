"""Persistent NOR recovery model checks; no physical-device validation (MIT)."""

import binascii
import hashlib
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from fm1_simulated_device import (
    CHUNK, FLASH_SIZE, JEDEC, LOADER_SIZE, RAM, SECTOR_BYTES,
    SimulatedAckLoss, SimulatedDevice, SimulatedDisconnect, SimulatedPowerLoss,
    simulated_request,
)
from fm1_uboot_read import request
from fm1_uboot_restore_test import PATTERN, SECTOR, restore_request


# Entirely synthetic; matching the real metadata length does not audit this blob.
LOADER = bytes((i*37+13) & 255 for i in range(LOADER_SIZE))
LOADER_HASH = hashlib.sha256(LOADER).hexdigest()
APP = (0x4000, 0x6000)
BASELINE = b'\x51'*APP[0]+b'\xff'*(APP[1]-APP[0])+b'\x93'*(FLASH_SIZE-APP[1])


def device(tmp_path=None, flash=BASELINE, **kwargs):
    return SimulatedDevice(
        flash, path=tmp_path/'device' if tmp_path else None,
        writable_ranges=[APP], protected_ranges=[(0, APP[0]), (APP[1], FLASH_SIZE)],
        app_range=APP, simulator_loader_sha256=LOADER_HASH, **kwargs,
    )


def test_new_state_requires_full_geometry_and_explicit_write_permission():
    with pytest.raises(ValueError):
        SimulatedDevice(bytes(FLASH_SIZE-1))
    d = SimulatedDevice(BASELINE, simulator_loader_sha256=LOADER_HASH)
    s = d.recovery_session(LOADER)
    assert s.identity() == {'unit_id': 'sim-fm1-001', 'flash_size': FLASH_SIZE,
                            'sector_size': SECTOR_BYTES, 'page_size': CHUNK,
                            'jedec': JEDEC, 'simulated': True}
    with pytest.raises(ValueError, match='unallowed'):
        s.erase(APP[0])
    assert d.flash == BASELINE


def test_default_loader_pin_cannot_accept_synthetic_loader():
    d = SimulatedDevice(BASELINE)
    d.soft_key()
    s = d.open_session()
    with pytest.raises(ValueError, match='audit pin'):
        s.load(LOADER)
    assert not [event for event in d.events if event['event'] == 'command']


def test_boot_rom_upload_jump_online_and_real_cdb_layout():
    d = device()
    original = d.open_session()
    assert d.mode == 'app'
    with pytest.raises(ValueError):
        original.cmd(0xFC0A)
    d.soft_key()
    with pytest.raises(SimulatedDisconnect):
        original.identity()
    s = d.open_session()
    assert s.cmd(0x12)[8:32] == b'WL82    UBOOT1.00       '
    with pytest.raises(ValueError, match='every loader block'):
        s.cmd(0xFB08, address=RAM)
    s.load(LOADER)
    assert d.mode == 'loader' and s.online() == (3, JEDEC)
    uploads = [e for e in d.events if e.get('operation') == 'upload']
    assert len(uploads) == 47
    assert [e['address'] for e in uploads] == list(range(RAM, RAM+LOADER_SIZE, 512))
    for op, address, payload in [(0xFC0A, 0, b''), (0xFD05, APP[0], b'')]:
        assert s.build_request(op, address, payload) == request(op, 'loader', address=address, payload=payload)
    assert s.read(0, FLASH_SIZE) == BASELINE


def test_complete_upload_with_wrong_digest_cannot_jump():
    d = device()
    d.usb_key()
    s = d.open_session()
    for offset in range(0, LOADER_SIZE, 512):
        s.cmd(0xFB06, address=RAM+offset, payload=bytes(512))
    with pytest.raises(ValueError, match='approved simulator hash'):
        s.cmd(0xFB08, address=RAM)
    assert d.mode == 'rom'


def test_crc_padding_and_length_are_checked_at_wire_boundary():
    d = device()
    d.usb_key()
    s = d.open_session()
    cdb, payload, size = request(0xFB06, 'rom', address=RAM, payload=LOADER[:512])
    for position in (9, 15):
        broken = bytearray(cdb)
        broken[position] ^= 1
        with pytest.raises(ValueError, match='Malformed'):
            s.execute(bytes(broken), payload, size)
    with pytest.raises(ValueError):
        s.execute(cdb, payload, 16)
    assert not d._uploaded
    s.load(LOADER)
    cdb, payload, size = simulated_request(0xFB04, 'loader', address=APP[0], payload=bytes(256))
    assert cdb[9:11] == binascii.crc_hqx(payload, 0).to_bytes(2, 'little')
    broken = bytearray(cdb)
    broken[9] ^= 1
    with pytest.raises(ValueError, match='Malformed'):
        s.execute(bytes(broken), payload, size)
    assert d.flash == BASELINE


@pytest.mark.parametrize('op', [0xFC12, 0xFB00, 0xFB02, 0xFC0C, 0xFC0D, 0xA1])
def test_forbidden_chip_erase_config_and_efuse_operations(op):
    s = device().recovery_session(LOADER)
    with pytest.raises(ValueError, match='Forbidden'):
        s.cmd(op)


@pytest.mark.parametrize('address', [-4096, 0, APP[0]+1, APP[1], FLASH_SIZE])
def test_erase_alignment_bounds_and_protected_ranges(address):
    d = device()
    s = d.recovery_session(LOADER)
    with pytest.raises(ValueError):
        s.erase(address)
    assert d.flash == BASELINE


def test_protected_range_overrides_wider_write_permission():
    d = SimulatedDevice(BASELINE, writable_ranges=[(0, FLASH_SIZE)],
                        protected_ranges=[(APP[0]+256, APP[0]+512)],
                        simulator_loader_sha256=LOADER_HASH)
    s = d.recovery_session(LOADER)
    with pytest.raises(ValueError, match='protected'):
        s.erase(APP[0])
    s.program(APP[0], bytes(256))
    with pytest.raises(ValueError, match='protected'):
        s.program(APP[0]+256, bytes(256))


def test_program_nor_one_to_zero_and_erase_restores_all_bits(tmp_path):
    d = device(tmp_path)
    s = d.recovery_session(LOADER)
    s.program(APP[0], b'\x0f'*256)
    s.program(APP[0], b'\xf0'*256)
    assert s.read(APP[0], 256) == bytes(256)
    s.program(APP[0], b'\xff'*256)
    assert s.read(APP[0], 256) == bytes(256)  # Programming cannot restore bits.
    reopened = SimulatedDevice(path=tmp_path/'device')
    assert reopened.flash[APP[0]:APP[0]+256] == bytes(256)
    assert reopened.mode == 'app_unavailable'
    reopened.recovery_session(LOADER).erase(APP[0])
    reopened.reset()
    assert reopened.mode == 'app' and reopened.flash == BASELINE


@pytest.mark.parametrize('address,size', [(0, 0), (1, 256), (0, 255), (-256, 256), (FLASH_SIZE, 256)])
def test_read_guards(address, size):
    s = device().recovery_session(LOADER)
    with pytest.raises(ValueError):
        s.read(address, size)


@pytest.mark.parametrize('payload', [b'', bytes(255), bytes(257)])
def test_program_page_size_guard(payload):
    s = device().recovery_session(LOADER)
    with pytest.raises(ValueError):
        s.program(APP[0], payload)


@pytest.mark.parametrize('operation,kind,after_bytes', [
    ('program', 'torn', 73), ('erase', 'torn', 613),
    ('program', 'ack_loss', 0), ('erase', 'ack_loss', 0),
    ('program', 'disconnect_before', 0), ('erase', 'disconnect_before', 0),
])
def test_faults_preserve_exact_partial_or_committed_nor_after_reopen(tmp_path, operation, kind, after_bytes):
    initial = BASELINE if operation == 'program' else BASELINE[:APP[0]]+bytes(SECTOR_BYTES)+BASELINE[APP[0]+SECTOR_BYTES:]
    d = device(tmp_path, flash=initial)
    s = d.recovery_session(LOADER)
    d.inject_failure(operation, kind, after_bytes=after_bytes)
    error = {'torn': SimulatedPowerLoss, 'ack_loss': SimulatedAckLoss, 'disconnect_before': SimulatedDisconnect}[kind]
    with pytest.raises(error):
        if operation == 'program':
            s.program(APP[0], b'\xa5'*256)
        else:
            s.erase(APP[0])
    with pytest.raises(SimulatedDisconnect):
        s.online()
    assert not d.failures
    assert [e for e in d.events if e['event'] == 'fault'][-1]['kind'] == kind
    count = 0 if kind == 'disconnect_before' else after_bytes if kind == 'torn' else 256 if operation == 'program' else SECTOR_BYTES
    expected = bytearray(initial)
    expected[APP[0]:APP[0]+count] = (b'\xa5' if operation == 'program' else b'\xff')*count
    reopened = SimulatedDevice(path=tmp_path/'device')
    assert reopened.flash == bytes(expected)
    recovered = reopened.recovery_session(LOADER)
    assert recovered.read(0, FLASH_SIZE) == bytes(expected)
    assert reopened.flash[:APP[0]] == initial[:APP[0]]
    assert reopened.flash[APP[1]:] == initial[APP[1]:]


def test_occurrence_targets_specific_page_without_implicit_retry():
    d = device()
    s = d.recovery_session(LOADER)
    d.inject_failure('program', 'torn', occurrence=3, after_bytes=17)
    for offset in (0, 256):
        s.program(APP[0]+offset, bytes(256))
    with pytest.raises(SimulatedPowerLoss):
        s.program(APP[0]+512, bytes(256))
    assert d.flash[APP[0]:APP[0]+529] == bytes(529)
    assert d.flash[APP[0]+529:APP[1]] == b'\xff'*(APP[1]-APP[0]-529)


def test_reset_power_loss_and_reenumeration_clear_ram_and_stale_handles():
    d = device()
    s = d.recovery_session(LOADER)
    d.reset()
    assert d.mode == 'app' and not d._uploaded and not any(d._ram)
    with pytest.raises(SimulatedDisconnect):
        s.cmd(0xFC0A)
    s = d.recovery_session(LOADER)
    d.power_loss()
    assert d.mode == 'off'
    with pytest.raises(SimulatedDisconnect):
        d.open_session()
    with pytest.raises(SimulatedDisconnect):
        s.identity()
    d.reconnect()
    assert d.mode == 'app' and d.flash == BASELINE


def test_corrupted_app_requires_modeled_external_usb_key(tmp_path):
    d = device(tmp_path)
    s = d.recovery_session(LOADER)
    s.program(APP[0], bytes(256))
    d.reset()
    assert d.mode == 'app_unavailable'
    with pytest.raises(ValueError, match='healthy'):
        d.soft_key()
    unavailable = d.open_session()
    with pytest.raises(ValueError):
        unavailable.cmd(0x12)
    d.usb_key()
    with pytest.raises(SimulatedDisconnect):
        unavailable.identity()
    s = d.open_session()
    s.load(LOADER)
    s.erase(APP[0])
    d.reset()
    assert d.mode == 'app' and d.flash == BASELINE
    assert any(e['event'] == 'external_usb_key' for e in d.events)


def test_registered_bootable_target_hash_persists(tmp_path):
    d = device(tmp_path)
    target = bytearray(BASELINE)
    target[APP[0]:APP[0]+256] = b'\x65'*256
    d.register_bootable_image(target)
    d.recovery_session(LOADER).program(APP[0], b'\x65'*256)
    d.reset()
    assert d.mode == 'app'
    reopened = SimulatedDevice(path=tmp_path/'device')
    assert reopened.mode == 'app' and reopened.flash == bytes(target)
    with pytest.raises(ValueError):
        reopened.register_bootable_image(bytes(256))


def test_read_corruption_does_not_mutate_nor_and_dump_is_exact(tmp_path):
    d = device()
    s = d.recovery_session(LOADER)
    d.inject_failure('read', 'corrupt_read', occurrence=2)
    observed = s.read(APP[0], 512)
    assert observed[:256] == b'\xff'*256
    assert observed[256] == 0xfe and observed[257:] == b'\xff'*255
    assert d.flash == BASELINE
    output = tmp_path/'dump.bin'
    result = s.dump(output)
    assert result == {'file': 'dump.bin', 'bytes': FLASH_SIZE, 'sha256': hashlib.sha256(BASELINE).hexdigest()}
    assert output.read_bytes() == BASELINE and output.stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        s.dump(output)


def test_existing_scratch_cdb_layout_matches_simulated_roundtrip():
    baseline = b'\xff'*FLASH_SIZE
    d = SimulatedDevice(baseline, writable_ranges=[(SECTOR, SECTOR+SECTOR_BYTES)],
                        simulator_loader_sha256=LOADER_HASH)
    s = d.recovery_session(LOADER)
    for op, address, payload in [(0xFB01, SECTOR, b''), (0xFB04, SECTOR, PATTERN[:256])]:
        assert simulated_request(op, 'loader', address=address, payload=payload) == restore_request(op, 'loader', address=address, payload=payload)
    for offset in range(0, SECTOR_BYTES, CHUNK):
        s.program(SECTOR+offset, PATTERN[offset:offset+CHUNK])
    assert s.sector() == PATTERN
    s.erase(SECTOR)
    assert d.flash == baseline


def test_persistent_state_metadata_and_reopen_fail_closed(tmp_path):
    d = device(tmp_path)
    path = tmp_path/'device'
    assert (path/'state.json').stat().st_mode & 0o777 == 0o600
    with pytest.raises(ValueError, match='without an initial'):
        SimulatedDevice(BASELINE, path=path)
    data = json.loads((path/'state.json').read_text())
    data['simulated'] = False
    (path/'state.json').write_text(json.dumps(data))
    with pytest.raises(ValueError, match='supported simulated'):
        SimulatedDevice(path=path)
    assert d.flash == BASELINE


@pytest.mark.parametrize('operation,kind,kwargs', [
    ('bogus', 'torn', {}), ('program', 'bogus', {}), ('read', 'torn', {}),
    ('program', 'corrupt_read', {}), ('program', 'torn', {'after_bytes': 257}),
    ('erase', 'torn', {'after_bytes': 4097}), ('program', 'ack_loss', {'occurrence': 0}),
])
def test_invalid_fault_injections_are_rejected(operation, kind, kwargs):
    with pytest.raises(ValueError):
        device().inject_failure(operation, kind, **kwargs)
