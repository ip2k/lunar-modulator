"""Recovery decisions use fresh flash bytes, never a journal page cursor."""
import fcntl
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from fm1_flash_transaction import (create_transaction, run_transaction, load_transaction,
                                   save_journal, encoded, digest, FLASH_SIZE)
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


def test_new_backup_ancestors_are_synced_before_transaction(tmp_path, monkeypatch):
    import fm1_flash_transaction as module
    synced=[]
    original=module.sync_directory
    def sync(path):
        synced.append(Path(path))
        original(path)
    monkeypatch.setattr(module,'sync_directory',sync)
    before=b'\xff'*FLASH_SIZE
    directory=tmp_path/'new-session'/'private'/'transaction'
    create_transaction(directory,before,before,before,IDENTITY,((4096,8192),),'fixture')
    for path in (tmp_path,directory.parent.parent,directory.parent,directory):
        assert path in synced
    assert all(path.stat().st_mode & 0o777 == 0o700
               for path in (directory.parent.parent,directory.parent,directory))


def two_sector_images():
    baseline = bytearray(b'\xff' * FLASH_SIZE)
    target = bytearray(baseline)
    for address, old, new in ((4096, b'D', b'd'), (8192, b'A', b'a')):
        baseline[address:address+256] = old * 256
        target[address:address+256] = new * 256
    return bytes(baseline), bytes(target)


def two_sector_transaction(tmp_path, commit_sector=4096):
    baseline, target = two_sector_images()
    directory = tmp_path / 'ordered'
    plan = create_transaction(directory, baseline, baseline, target, IDENTITY,
                              ((4096, 12288),), 'fixture', commit_sector=commit_sector)
    return directory, baseline, target, plan


@pytest.mark.parametrize('bad', [True, '4096', 4096.0, -4096, 0, 4097, 12288])
def test_invalid_commit_sector_rejected_before_files(tmp_path, bad):
    baseline, target = two_sector_images()
    with pytest.raises(ValueError, match='Commit sector'):
        create_transaction(tmp_path/'bad', baseline, baseline, target, IDENTITY,
                           ((4096, 12288),), 'fixture', commit_sector=bad)
    assert not (tmp_path/'bad').exists()


def test_commit_order_sealed_and_last_for_install_and_restore(tmp_path):
    directory, baseline, target, plan = two_sector_transaction(tmp_path)
    assert plan['commit_sector'] == 4096 and plan['sector_order'] == [8192, 4096]
    journal = json.loads((directory/'journal.json').read_bytes())
    assert journal['sector_order'] == plan['sector_order']
    assert journal['plan_sha256'] == digest(encoded(plan))
    session = Session(bytearray(baseline))
    for direction, desired in (('install', target), ('restore', baseline)):
        session.writes.clear()
        receipt = run_transaction(directory, session, direction)
        order = list(dict.fromkeys(address//4096*4096 for _, address in session.writes))
        assert order == [8192, 4096]
        assert receipt['sector_order'] == order and receipt['commit_sector'] == 4096
        assert bytes(session.flash) == desired


@pytest.mark.parametrize('direction', ['install', 'restore'])
@pytest.mark.parametrize('event,address', [('durable_intent', 8192),
                                          ('sector_verified', 8192),
                                          ('durable_intent', 4096),
                                          ('operation_returned', 4096)])
def test_interruption_before_or_at_commit_resumes_from_actual_flash(tmp_path, direction, event, address):
    directory, baseline, target, _ = two_sector_transaction(tmp_path)
    if direction == 'restore':
        run_transaction(directory, Session(bytearray(baseline)))
    initial = baseline if direction == 'install' else target
    desired = target if direction == 'install' else baseline
    session = Session(bytearray(initial))
    def crash(actual_event, **fields):
        if actual_event == event and fields['address'] == address:
            # At the commit boundary all data is already verified; before the
            # first directory mutation, the old directory remains untouched.
            if address == 4096 or event == 'sector_verified':
                assert bytes(session.flash[8192:12288]) == desired[8192:12288]
            if event != 'operation_returned':
                assert bytes(session.flash[4096:8192]) == initial[4096:8192]
            raise KeyboardInterrupt()
    with pytest.raises(KeyboardInterrupt):
        run_transaction(directory, session, direction, checkpoint=crash)
    assert json.loads((directory/'journal.json').read_bytes())['state'] == 'recovery_required'
    # Even a journal-verified earlier sector must be freshly read/repaired.
    session.flash[8192] = 0
    fresh = Session(session.flash)
    reads = []
    original_read = fresh.read
    def read(address, size):
        reads.append((address, size))
        return original_read(address, size)
    fresh.read = read
    receipt = run_transaction(directory, fresh, direction)
    assert reads[0] == reads[-1] == (0, FLASH_SIZE)
    assert bytes(fresh.flash) == desired and receipt['verified_sha256'] == digest(desired)
    written = list(dict.fromkeys(a//4096*4096 for _, a in fresh.writes))
    assert written[0] == 8192
    assert written in ([8192], [8192, 4096])


def test_order_or_commit_change_with_resealed_plan_rejected_before_device(tmp_path):
    directory, _, _, plan = two_sector_transaction(tmp_path)
    plan['commit_sector'] = 8192
    (directory/'plan.json').write_bytes(encoded(plan))
    journal = json.loads((directory/'journal.json').read_bytes())
    journal['plan_sha256'] = digest(encoded(plan))
    save_journal(directory, journal)
    with pytest.raises(ValueError, match='sector order'):
        load_transaction(directory)


def test_legacy_and_default_transactions_keep_ascending_order(tmp_path):
    directory, baseline, target, plan = two_sector_transaction(tmp_path, None)
    assert plan['sector_order'] == [4096, 8192] and plan['commit_sector'] is None
    session = Session(bytearray(baseline))
    run_transaction(directory, session)
    assert list(dict.fromkeys(a//4096*4096 for _, a in session.writes)) == [4096, 8192]
    # Historical schema-1 plans/journals had no order fields. Their hashes are
    # still checked, and their command order remains the original ascending one.
    del plan['commit_sector'], plan['sector_order']
    (directory/'plan.json').write_bytes(encoded(plan))
    journal = json.loads((directory/'journal.json').read_bytes())
    del journal['sector_order']
    journal['plan_sha256'] = digest(encoded(plan))
    save_journal(directory, journal)
    legacy = Session(bytearray(target))
    run_transaction(directory, legacy, 'restore')
    assert list(dict.fromkeys(a//4096*4096 for _, a in legacy.writes)) == [4096, 8192]
    assert bytes(legacy.flash) == baseline
