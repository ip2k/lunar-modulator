"""Recovery decisions use fresh flash bytes, never a journal page cursor."""
import fcntl
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from fm1_flash_transaction import create_transaction, run_transaction, FLASH_SIZE
from fm1_uboot_restore_test import (checked_scratch_transaction, RestoreReader,
                                   SECTOR, SECTOR_BYTES, PATTERN, SCOPE)

IDENTITY = {'unit_id': 'fixture', 'flash_size': FLASH_SIZE, 'sector_size': 4096,
            'page_size': 256, 'jedec': 0x856014, 'simulated': True}


class Session:
    def __init__(self, flash, identity=None):
        self.flash = flash
        self.unit = identity or IDENTITY
        self.writes = []
        self.fail = False

    def identity(self):
        return self.unit

    def online(self):
        return 3, 0x856014

    def read(self, address, size):
        return bytes(self.flash[address:address+size])

    def erase(self, address):
        self.writes.append(('erase', address))
        self.flash[address:address+4096] = b'\xff' * 4096

    def program(self, address, data):
        self.writes.append(('program', address))
        if self.fail:
            self.flash[address:address+13] = data[:13]
            raise OSError('partial write, disconnected')
        self.flash[address:address+len(data)] = data


def prepare(tmp_path):
    before = b'\xff' * FLASH_SIZE
    target = before[:4096] + b'\x42' * 256 + before[4352:]
    directory = tmp_path / 'transaction'
    create_transaction(directory, before, before, target, IDENTITY,
                       ((4096, 8192),), 'fixture')
    return directory, before, target, Session(bytearray(before))


def test_partial_write_is_durable_and_restores_on_fresh_session(tmp_path):
    directory, before, _, session = prepare(tmp_path)
    session.fail = True
    with pytest.raises(OSError):
        run_transaction(directory, session)
    assert session.writes == [('program', 4096)]  # no cleanup on stale handle
    journal = json.loads((directory / 'journal.json').read_bytes())
    assert journal['state'] == 'recovery_required'
    assert journal['intent'] == {'operation': 'program', 'address': 4096}
    fresh = Session(session.flash)
    result = run_transaction(directory, fresh, direction='restore')
    assert fresh.writes == [('erase', 4096)]
    assert bytes(fresh.flash) == before and result['direction'] == 'restore'


def test_intent_is_persisted_before_command_and_resume_rereads(tmp_path):
    directory, _, target, session = prepare(tmp_path)
    def crash(event, **fields):
        if event == 'durable_intent':
            assert json.loads((directory / 'journal.json').read_bytes())['intent'] == fields
            raise KeyboardInterrupt()
    with pytest.raises(KeyboardInterrupt):
        run_transaction(directory, session, checkpoint=crash)
    assert not session.writes
    run_transaction(directory, Session(session.flash))
    assert bytes(session.flash) == target


def test_preflight_failure_never_grants_resume_permission(tmp_path):
    directory, _, _, session = prepare(tmp_path)
    session.flash[4096] = 0  # authorized sector changed before our first write
    for _ in range(2):
        with pytest.raises(ValueError, match='Fresh flash differs'):
            run_transaction(directory, session)
        assert json.loads((directory / 'journal.json').read_bytes())['state'] == 'prepared'
    assert not session.writes


def test_completed_journal_still_verifies_full_flash(tmp_path):
    directory, _, _, session = prepare(tmp_path)
    run_transaction(directory, session)
    session.writes.clear()
    session.flash[0] = 0
    with pytest.raises(ValueError, match='outside'):
        run_transaction(directory, session)
    assert not session.writes


@pytest.mark.parametrize('file', ['backupA.bin', 'backupB.bin', 'target.bin', 'plan.json', 'journal.json'])
def test_corrupted_artifacts_prevent_device_operations(tmp_path, file):
    directory, _, _, session = prepare(tmp_path)
    (directory / file).write_bytes(b'bad')
    session.identity = lambda: pytest.fail('must validate disk first')
    with pytest.raises((ValueError, KeyError)):
        run_transaction(directory, session)


def test_wrong_unit_and_competing_process_prevent_writes(tmp_path):
    directory, _, _, session = prepare(tmp_path)
    session.unit = {**IDENTITY, 'unit_id': 'different'}
    with pytest.raises(ValueError, match='unit differs'):
        run_transaction(directory, session)
    with (directory / '.transaction.lock').open('a+b') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(BlockingIOError):
            run_transaction(directory, session)
    assert not session.writes


@pytest.mark.parametrize('ranges', [(), ((0, 1),), ((4096, 8192), (0, 4096)),
                                   ((0, 8192), (4096, 12288))])
def test_invalid_ranges_never_create_transaction(tmp_path, ranges):
    before = b'\xff' * FLASH_SIZE
    with pytest.raises(ValueError):
        create_transaction(tmp_path/'bad', before, before, before, IDENTITY, ranges, 'fixture')
    assert not (tmp_path/'bad').exists()


def test_physical_scratch_adapter_cannot_use_simulator_transaction(tmp_path):
    directory, _, _, _ = prepare(tmp_path)
    with pytest.raises(ValueError, match='fixed physical'):
        checked_scratch_transaction(directory)
    reader = RestoreReader.__new__(RestoreReader)
    reader.phase = 'loader'
    # Same low-level guard as the historical proof, before any SG_IO call.
    for op, address, payload in ((0xFB01, 0, b''), (0xFB04, SECTOR, b'\0'*256),
                                  (0xFC12, 0, b'')):
        with pytest.raises(ValueError):
            reader.build_request(op, address, payload)


def test_exact_physical_scratch_plan_is_accepted(tmp_path):
    baseline = b'\xff' * FLASH_SIZE
    target = baseline[:SECTOR] + PATTERN + baseline[SECTOR+SECTOR_BYTES:]
    identity = {**IDENTITY, 'unit_id': 'FM-1_092@3-2', 'simulated': False}
    directory = tmp_path/'scratch'
    create_transaction(directory, baseline, baseline, target, identity,
                       ((SECTOR, SECTOR+SECTOR_BYTES),), SCOPE)
    assert checked_scratch_transaction(directory)[2] == baseline
