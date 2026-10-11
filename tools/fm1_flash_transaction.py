"""Durable, transport-independent sector transactions. MIT.

No device opener or arbitrary hardware CLI lives here. A physical adapter must
enforce its own reviewed command/payload allowlist. Simulator adapters can
exercise wider ranges. Journal progress is never trusted instead of readback.
"""
import fcntl
import hashlib
import json
import os
from pathlib import Path

from fm1_uboot_read import FLASH_SIZE, CHUNK

SECTOR_BYTES = 4096


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def sync_directory(directory):
    fd = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def save_new(path, data):
    with path.open('xb') as fp:
        os.chmod(path, 0o600)
        fp.write(data)
        fp.flush()
        os.fsync(fp.fileno())


def save_journal(directory, journal):
    """Publish a complete synced record; an old record remains valid on crash."""
    journal['record_sha256'] = digest(encoded(
        {key: value for key, value in journal.items() if key != 'record_sha256'}))
    temporary = directory / 'journal.next'
    with temporary.open('wb') as fp:
        os.chmod(temporary, 0o600)
        fp.write(encoded(journal))
        fp.flush()
        os.fsync(fp.fileno())
    os.replace(temporary, directory / 'journal.json')
    sync_directory(directory)


def checked_ranges(ranges):
    result = [list(pair) for pair in ranges]
    previous = 0
    if not result:
        raise ValueError('An explicit writable sector range is required')
    for pair in result:
        if (len(pair) != 2 or any(type(x) is not int for x in pair) or
                not previous <= pair[0] < pair[1] <= FLASH_SIZE or
                pair[0] % SECTOR_BYTES or pair[1] % SECTOR_BYTES):
            raise ValueError('Writable ranges must be sorted, disjoint aligned sectors')
        previous = pair[1]
    return result


def check_outside(current, baseline, ranges):
    previous = 0
    for start, end in ranges:
        if current[previous:start] != baseline[previous:start]:
            raise ValueError('Flash outside the authorized ranges changed; no write')
        previous = end
    if current[previous:] != baseline[previous:]:
        raise ValueError('Flash outside the authorized ranges changed; no write')


def checked_identity(identity):
    if (not isinstance(identity, dict) or not identity.get('unit_id') or
            identity.get('flash_size') != FLASH_SIZE or
            identity.get('sector_size') != SECTOR_BYTES or
            identity.get('page_size') != CHUNK or identity.get('jedec') != 0x856014 or
            type(identity.get('simulated')) is not bool):
        raise ValueError('Exact unit binding and reviewed flash geometry required')
    # Reject non-JSON metadata before creating files; detach mutable caller data.
    return json.loads(encoded(identity))


def create_transaction(directory, baseline_a, baseline_b, target, identity,
                       writable_ranges, scope):
    """Prepare immutable artifacts before any destructive device operation."""
    directory = Path(directory)
    if (any(not isinstance(x, bytes) or len(x) != FLASH_SIZE
            for x in (baseline_a, baseline_b, target)) or baseline_a != baseline_b):
        raise ValueError('Two matching complete backups and a complete target required')
    ranges = checked_ranges(writable_ranges)
    check_outside(target, baseline_a, ranges)
    identity = checked_identity(identity)
    if not isinstance(scope, str) or not scope:
        raise ValueError('A concrete experiment scope is required')
    plan = {'schema': 1, 'identity': identity, 'scope': scope,
            'writable_ranges': ranges, 'baseline_sha256': digest(baseline_a),
            'target_sha256': digest(target)}
    directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    for name, data in (('backupA.bin', baseline_a), ('backupB.bin', baseline_b),
                       ('target.bin', target), ('plan.json', encoded(plan))):
        save_new(directory / name, data)
    sync_directory(directory)
    sync_directory(directory.parent)
    save_journal(directory, {'schema': 1, 'plan_sha256': digest(encoded(plan)),
                             'state': 'prepared', 'direction': None, 'intent': None})
    return plan


def load_transaction(directory):
    directory = Path(directory)
    plan = json.loads((directory / 'plan.json').read_bytes())
    journal = json.loads((directory / 'journal.json').read_bytes())
    if (not isinstance(plan, dict) or not isinstance(journal, dict) or
            journal.get('record_sha256') != digest(encoded(
                {key: value for key, value in journal.items()
                 if key != 'record_sha256'})) or
            plan.get('schema') != 1 or journal.get('schema') != 1 or
            journal.get('plan_sha256') != digest(encoded(plan)) or
            journal.get('state') not in
            ('prepared', 'running', 'recovery_required', 'complete') or
            journal.get('direction') not in (None, 'install', 'restore')):
        raise ValueError('Invalid or mismatched transaction journal/plan')
    checked_identity(plan['identity'])
    checked_ranges(plan['writable_ranges'])
    a = (directory / 'backupA.bin').read_bytes()
    b = (directory / 'backupB.bin').read_bytes()
    target = (directory / 'target.bin').read_bytes()
    if (len(a) != FLASH_SIZE or a != b or digest(a) != plan['baseline_sha256'] or
            len(target) != FLASH_SIZE or digest(target) != plan['target_sha256']):
        raise ValueError('Transaction backup or target hash mismatch; no device operation')
    check_outside(target, a, plan['writable_ranges'])
    return plan, journal, a, target


def run_transaction(directory, session, direction='install', checkpoint=None):
    """Run or resume once on a freshly acquired loader session.

    A failed command is ambiguous: record recovery_required and exit. Never
    retry on a stale handle. Caller must reconnect/re-enter ROM and load the
    audited loader explicitly. On resume read the entire device again, check
    immutable regions, and rebuild any differing authorized sector from its
    durable image. A completed journal also requires complete fresh readback.
    """
    if direction not in ('install', 'restore'):
        raise ValueError('Direction must be install or restore')
    directory = Path(directory)
    with (directory / '.transaction.lock').open('a+b') as lock:
        os.chmod(directory / '.transaction.lock', 0o600)
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        plan, journal, baseline, target = load_transaction(directory)
        desired = target if direction == 'install' else baseline
        if checked_identity(session.identity()) != plan['identity']:
            raise ValueError('Connected unit differs from transaction; no write')
        if session.online() != (3, 0x856014):
            raise ValueError('Unexpected flash query; no write')

        def read(address, size):
            data = session.read(address, size)
            if not isinstance(data, bytes) or len(data) != size:
                raise ValueError('Incomplete flash read; no inferred padding')
            return data

        def checkpoint_event(event, **fields):
            if checkpoint is not None:
                checkpoint(event, **fields)

        def mutate(operation, address, data=None):
            journal.update(state='running', direction=direction,
                           intent={'operation': operation, 'address': address})
            save_journal(directory, journal)
            checkpoint_event('durable_intent', operation=operation, address=address)
            if session.online() != (3, 0x856014):
                raise ValueError('Flash query changed before mutation; no write')
            if operation == 'erase':
                session.erase(address)
            else:
                session.program(address, data)
            checkpoint_event('operation_returned', operation=operation, address=address)

        try:
            current = read(0, FLASH_SIZE)
            check_outside(current, baseline, plan['writable_ranges'])
            if journal['state'] == 'prepared' and current != baseline:
                raise ValueError('Fresh flash differs from the two backups; no write')
            sectors_written = 0
            for start, end in plan['writable_ranges']:
                for address in range(start, end, SECTOR_BYTES):
                    sector = desired[address:address + SECTOR_BYTES]
                    actual = read(address, SECTOR_BYTES)
                    if actual == sector:
                        continue
                    # A verified blank sector needs no erase. Otherwise rebuild
                    # the whole sector; never interpret a torn page as a cursor.
                    if actual != b'\xff' * SECTOR_BYTES:
                        mutate('erase', address)
                    if read(address, SECTOR_BYTES) != b'\xff' * SECTOR_BYTES:
                        raise ValueError('Erase readback mismatch')
                    for offset in range(0, SECTOR_BYTES, CHUNK):
                        page = sector[offset:offset + CHUNK]
                        if page != b'\xff' * CHUNK:
                            mutate('program', address + offset, page)
                    if read(address, SECTOR_BYTES) != sector:
                        raise ValueError('Program readback mismatch')
                    sectors_written += 1
                    journal.update(intent=None)
                    save_journal(directory, journal)
                    checkpoint_event('sector_verified', address=address)
            final = read(0, FLASH_SIZE)
            if final != desired:
                raise ValueError('Full-flash final verification mismatch')
            journal.update(state='complete', direction=direction, intent=None,
                           verified_sha256=digest(final))
            save_journal(directory, journal)
            return {'scope': plan['scope'], 'direction': direction,
                    'verified_sha256': digest(final), 'sectors_written': sectors_written,
                    'simulated': plan['identity']['simulated']}
        except BaseException as exc:
            # A failed preflight does not grant permission to treat unrelated
            # pre-existing changes as our interrupted write on the next run.
            state = ('prepared' if journal['state'] == 'prepared'
                     else 'recovery_required')
            journal.update(state=state, direction=direction,
                           error=type(exc).__name__)
            save_journal(directory, journal)
            raise
