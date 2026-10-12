#!/usr/bin/env python3
"""MIT. One fixed-loader FC0C arg1 after the genuine returned-ROM stock restore.

WIP: RESTORE_SOURCE_SHA remains None until the completed-restore evidence helper
freezes and passes independent review. No upload, flash operation, read probe,
retry or assertion that a transmitted request caused a hardware reset.
Python instance registries are not a hostile-code security boundary.
"""
import argparse
import ctypes as C
from dataclasses import dataclass
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import time
import types
from weakref import WeakSet

RESTORE_SOURCE_SHA = None
RESET_SOURCE_SHA = 'dbbe363104aa339b63430ff0a99f817aba27afa233a266d449f45e048cd09116'
BRIDGE_SOURCE_SHA = '79bbe99ce923daaf8af2c701a65ec39a015191313de79676e36622cb8db00afb'
READER_SOURCE_SHA = '28317ee56a489e0bb38de981fe0d0c4260384be570349795741fdb9a98d6ae57'
BASELINE_SHA = '96006a51917750743d7adc68461f1289e82adc004a75bd2bbd5da40ecc44c4e4'
TARGET_SHA = 'df6c963ecd37b334f393c5bc92c2780b6094181308822a03c8190b016a4e97db'
_AUTHORIZED = WeakSet()
_OPENING = WeakSet()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('ascii')


def read_file(path, limit=2 * 1048576):
    path = Path(path)
    if not path.is_absolute():
        raise ValueError('Absolute direct evidence required')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
    try:
        fp = os.fdopen(fd, 'rb')
    except BaseException:
        os.close(fd)
        raise
    with fp:
        if not stat.S_ISREG(os.fstat(fp.fileno()).st_mode):
            raise ValueError('Direct regular evidence required')
        data = fp.read(limit + 1)
    if len(data) > limit:
        raise ValueError('Evidence exceeds bound')
    return data


def load_source(path, expected, name):
    data = read_file(path)
    if not isinstance(expected, str) or digest(data) != expected:
        raise ValueError('Reviewed dependency has not frozen or differs')
    module = types.ModuleType(name)
    module.__file__ = str(path)
    sys.modules[name] = module
    exec(compile(data, str(path), 'exec'), module.__dict__)
    if read_file(path) != data:
        raise ValueError('Source changed during import')
    return module


@dataclass(frozen=True, eq=False)
class Prepared:
    campaign: bytes
    campaign_sha256: str
    backup_manifest_sha256: str
    usb_binding: bytes
    expected_mapping: bytes
    bridge: object
    header_type: type
    reset: object
    evidence: tuple
    absent_paths: tuple

    def check(self):
        require_prepared(self, check=False)
        for path, data, limit in self.evidence:
            if read_file(path, limit) != data:
                raise ValueError('Frozen returned-stock reset evidence changed')
        for path in self.absent_paths:
            if os.path.lexists(path):
                raise ValueError('Required absent returned-stock reset evidence appeared')


def require_prepared(prepared, *, check=True):
    if not isinstance(prepared, Prepared) or prepared not in _AUTHORIZED:
        raise ValueError('Exact returned-stock reset authority required')
    if check:
        prepared.check()


def prepare_campaign(path):
    """Evidence-only admission; never call an old opener or fabricate its log."""
    evidence = []

    def freeze(path, expected=None, limit=2 * 1048576):
        path = Path(path)
        data = read_file(path, limit)
        if expected is not None and digest(data) != expected:
            raise ValueError('Pinned returned-stock reset evidence differs')
        evidence.append((path, data, limit))
        return data

    raw = freeze(Path(path).absolute(), limit=65536)
    c = json.loads(raw)
    keys = {'schema', 'kind', 'adapter_sha256', 'restore_campaign_path',
        'restore_campaign_sha256', 'restore_commands_sha256', 'restore_result_sha256',
        'restore_exit_status', 'restore_journal_sha256', 'active_session_state', 'receipt_path'}
    if (set(c) != keys or type(c['schema']) is not int or c['schema'] != 1 or
            c['kind'] != 'fm1-returned-fixed-loader-stock-reset' or
            type(c['restore_exit_status']) is not int or c['restore_exit_status'] != 0 or
            c['active_session_state'] != 'returned-fixed-loader-stock-restored-no-later-commands'):
        raise ValueError('Exact completed returned stock-restore campaign required')
    root = Path(__file__).absolute().parent
    freeze(Path(__file__).absolute(), c['adapter_sha256'])
    dependencies = (
        ('fm1_returned_rom_stock_restore.py', RESTORE_SOURCE_SHA, '_returned_stock_reset_restore'),
        ('fm1_fixed_loader_reset.py', RESET_SOURCE_SHA, '_returned_stock_reset_mechanics'),
        ('fm1_fixed_loader_backup.py', BRIDGE_SOURCE_SHA, '_returned_stock_reset_bridge'),
        ('fm1_uboot_read.py', READER_SOURCE_SHA, '_returned_stock_reset_reader'))
    modules = []
    for name, sha, module_name in dependencies:
        if not isinstance(sha, str):
            raise ValueError('Completed-restore dependency has not frozen')
        freeze(root / name, sha)
        modules.append(load_source(root / name, sha, module_name))
    restore, reset, bridge, reader = modules
    proof = restore.validate_completed_restore(c['restore_campaign_path'],
        campaign_sha256=c['restore_campaign_sha256'],
        commands_sha256=c['restore_commands_sha256'], result_sha256=c['restore_result_sha256'],
        journal_sha256=c['restore_journal_sha256'], freeze=freeze)
    absent_paths = proof['_absent_paths']
    if (type(absent_paths) is not tuple or
            any(not isinstance(p, Path) or not p.is_absolute() for p in absent_paths)):
        raise ValueError('Exact absolute absent evidence paths required')
    if (proof['baseline_sha256'] != BASELINE_SHA or proof['target_sha256'] != TARGET_SHA or
            type(proof['sectors_written']) is not int or proof['sectors_written'] != 30 or
            proof['sector_order'] != list(range(0x5000, 0x22000, 4096)) + [0x4000]):
        raise ValueError('Exact full stock restoration and directory-last plan required')
    bridge.validate_usb(proof['usb_binding'])
    sg_class = Path(proof['sg_binding']['class'])
    if (not sg_class.is_absolute() or not sg_class.name.startswith('sg') or
            proof['sg_binding']['node'] != '/dev/' + sg_class.name or
            C.sizeof(reader.SGHeader) != 88 or C.sizeof(C.c_void_p) != 8):
        raise ValueError('Reviewed new SG binding and 64-bit layout required')
    parent = Path(proof['returned_backup_receipt_path'])
    receipt = Path(c['receipt_path'])
    if (not parent.is_absolute() or not receipt.is_absolute() or receipt.parent != parent or
            receipt.exists() or not stat.S_ISDIR(parent.lstat().st_mode) or
            parent.stat().st_mode & 0o777 != 0o700 or
            (parent / '.returned-stock-core-reset.consumed').exists()):
        raise ValueError('New private receipt and unused returned-stock origin required')
    obj = Prepared(canonical(c), digest(raw), proof['returned_backup_manifest_sha256'],
        canonical(proof['usb_binding']), canonical(proof['sg_binding']), bridge,
        reader.SGHeader, reset, tuple(evidence), absent_paths)
    _AUTHORIZED.add(obj)
    obj.check()
    return obj


@dataclass(frozen=True, eq=False)
class _OpenPermit:
    prepared: object


def transport_type(prepared):
    require_prepared(prepared)

    class ResetSG(prepared.reset.ResetSG):
        """Pinned one-request mechanics behind this separate durable authority."""
        def __init__(self, candidate, log, permit=None):
            require_prepared(candidate)
            if candidate is not prepared or permit not in _OPENING or permit.prepared is not candidate:
                raise ValueError('Open only after the durable returned-stock marker')
            _OPENING.discard(permit)
            if sys.platform != 'linux':
                raise ValueError('Linux SG_IO only')
            self.prepared, self.log = candidate, log
            self.fd, self.consumed, self.failed, self.ioctl_attempts = None, False, False, 0
            self.phase, self.started = 'returned-stock-fixed-loader', time.monotonic()
            self.usb = json.loads(candidate.usb_binding)
            try:
                self.mapping = candidate.bridge.discover_sg(self.usb)
                if canonical(self.mapping) != candidate.expected_mapping:
                    raise ValueError('Returned stock SG connection replaced')
                self.fd = os.open(self.mapping['node'], os.O_RDWR | os.O_NOFOLLOW |
                    os.O_CLOEXEC | os.O_NONBLOCK)
                fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                self.binding()
            except BaseException:
                self.failed = True
                self.close()
                raise

        def binding(self):
            self.prepared.check()
            return super().binding()

    return ResetSG


def run_campaign(prepared):
    require_prepared(prepared)
    c, bridge = json.loads(prepared.campaign), prepared.bridge
    receipt = Path(c['receipt_path'])
    receipt.mkdir(mode=0o700, exist_ok=False)
    bridge.sync_dir(receipt.parent)
    with bridge.private_file(receipt.parent / '.returned-stock-core-reset.consumed') as fp:
        fp.write(prepared.campaign_sha256.encode('ascii'))
        fp.flush()
        os.fsync(fp.fileno())
    bridge.sync_dir(receipt.parent)
    with bridge.private_file(receipt / 'commands.jsonl', 'w') as events:
        def log(event, **fields):
            events.write(json.dumps(dict(time=time.time(), event=event, **fields)) + '\n')
            events.flush()
            os.fsync(events.fileno())
            bridge.sync_dir(receipt)

        transport = None
        permit = None
        try:
            log('returned_stock_reset_prepared', campaign_sha256=prepared.campaign_sha256,
                restore_campaign_sha256=c['restore_campaign_sha256'],
                restore_commands_sha256=c['restore_commands_sha256'],
                backup_manifest_sha256=prepared.backup_manifest_sha256,
                adapter_sha256=c['adapter_sha256'], commands=1, flash_operations=0,
                upload_operations=0, kernel_exclusivity=False, boot_observed=False)
            prepared.check()
            permit = _OpenPermit(prepared)
            _OPENING.add(permit)
            transport = transport_type(prepared)(prepared, log, permit)
            result = transport.request_reset()
            log('reset_request_completed', **result, retry=False)
            return result
        except BaseException as exc:
            try:
                log('reset_stopped_ambiguous', error=type(exc).__name__, detail=str(exc),
                    retry=False, core_reset_observed=False, boot_observed=False)
            except OSError:
                pass
            raise
        finally:
            if permit is not None:
                _OPENING.discard(permit)
            if transport is not None:
                transport.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign', type=Path, required=True)
    args = parser.parse_args()
    if sys.platform != 'linux':
        raise SystemExit('Linux SG_IO only')
    os.umask(0o077)
    run_campaign(prepare_campaign(args.campaign))


if __name__ == '__main__':
    main()
