"""Synthetic fixed-campaign tests; all SG syscalls/topology are mocked."""
import ctypes as C
from dataclasses import replace
import json
import os
from pathlib import Path
import stat
import sys
import time
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import fm1_fixed_loader_backup as b
import fm1_uboot_read as reader
from fm1_softkey_probe import KNOWN_092


USB = {'path': '3-2', 'busnum': '3', 'devnum': '28', 'vid': '4c4a', 'pid': '8057'}


@pytest.fixture
def campaign(monkeypatch, tmp_path):
    tmp_path.chmod(0o700)
    loader = bytes((i * 7) % 256 for i in range(b.LOADER_SIZE))
    monkeypatch.setattr(b, 'LOADER_SHA', b.digest(loader))
    lp = tmp_path / 'candidate.bin'; lp.write_bytes(loader)
    inventory = []
    for index, offset in enumerate(range(0, len(loader), 512)):
        payload = loader[offset:offset + 512]
        cdb, _, size = reader.request(0xFB06, 'rom', address=b.RAM + offset, payload=payload)
        inventory.append(dict(index=index, address=b.RAM + offset, bytes=512,
            cdb_sha256=b.digest(cdb), payload_sha256=b.digest(payload), read_size=size))
    profile = dict(upload_inventory=inventory, patched_encrypted_sha256=b.LOADER_SHA,
                   original_encrypted_sha256=b.ORIGINAL_SHA)
    pp = tmp_path / 'profile.json'; pp.write_text(json.dumps(profile))
    monkeypatch.setattr(b, 'PROFILE_SHA', b.digest(pp.read_bytes()))
    now = time.time()
    entry = [{'time': now - 5, 'event': 'before', 'usb_path': USB['path'],
              'midi': '/dev/snd/midiC4D0', 'usb': [{**USB, 'pid': 'c755', 'devnum': '27', 'product': 'FM-1', 'speed': '12'}]},
             {'time': now - 4, 'event': 'sending_identity', 'hex': 'f0 00 32 45 00 00 00 40 7f f7'},
             {'time': now - 3, 'event': 'identity', 'reply': KNOWN_092.hex(' '), 'decoded': {'identity': 'FM-1_092'}},
             {'time': now - 2, 'event': 'sending_soft_key', 'hex': 'f0 22 24 35 7d f7'},
             {'time': now - 1, 'event': 'uboot_enumerated', 'elapsed': 1,
              'usb': [{**USB, 'product': 'UBOOT1.00', 'speed': '12'}]}]
    ep = tmp_path / 'entry.jsonl'; ep.write_text('\n'.join(json.dumps(x) for x in entry))
    config = dict(schema=1, kind='fm1-fixed-loader-backup-campaign',
        adapter_sha256=b.digest(Path(b.__file__).read_bytes()), loader_path=str(lp),
        profile_path=str(pp), profile_source_path=str(Path(b.__file__).with_name('jieli') / 'loader_config_profile.py'),
        entry_log_path=str(ep), entry_log_sha256=b.digest(ep.read_bytes()),
        usb_binding=USB, receipt_path=str(tmp_path / 'receipt'))
    path = tmp_path / 'campaign.json'; path.write_text(json.dumps(config))
    return path, config, entry


def save_config(path, config):
    path.write_text(json.dumps(config))


def mock_sg(monkeypatch, *, fault=None, binding_fault=None):
    mapping = dict(node='/dev/sgMOCK', node_identity=(1, 2, 3), usb_identity=(4, 5, 6))
    state = SimpleNamespace(calls=[], closed=[], discoveries=0)
    real_open, real_fstat, real_close, real_flock = os.open, os.fstat, os.close, b.fcntl.flock

    def discover(usb):
        assert usb == USB
        state.discoveries += 1
        if binding_fault:
            binding_fault(state)
        return dict(mapping)

    monkeypatch.setattr(b, 'discover_sg', discover)
    monkeypatch.setattr(b.os, 'open', lambda path, flags, *a: 888 if str(path) == '/dev/sgMOCK' else real_open(path, flags, *a))
    monkeypatch.setattr(b.os, 'fstat', lambda fd: SimpleNamespace(st_mode=stat.S_IFCHR,
        st_dev=1, st_ino=2, st_rdev=3) if fd == 888 else real_fstat(fd))

    def close(fd):
        if fd == 888:
            state.closed.append(fd)
        else:
            real_close(fd)

    monkeypatch.setattr(b.os, 'close', close)
    monkeypatch.setattr(b.fcntl, 'flock', lambda fd, flags: None if fd == 888 else real_flock(fd, flags))

    def ioctl(fd, number, h):
        assert fd == 888 and number == 0x2285
        cdb = C.string_at(h.cmd, h.cmd_len)
        state.calls.append(cdb)
        op = int.from_bytes(cdb[:2], 'big') if len(cdb) == 16 else 0x12
        data = bytearray(h.data_len)
        if op == 0x12:
            data[8:16] = b'WL82    '; data[16:32] = b'UBOOT1.00       '
        elif op != 0xFB06:
            if op == 0xFD05:
                data[:] = bytes([int.from_bytes(cdb[2:6], 'big') // 256 % 256]) * len(data)
            else:
                data[:2] = cdb[:2]
                if op == 0xFC14:
                    data[2:6] = (256).to_bytes(4, 'big')
                if op == 0xFC0A:
                    data[2] = 3; data[4:8] = (0x856014).to_bytes(4, 'little')
        if fault:
            fault(h, data, op, state)
        if op != 0xFB06:
            C.memmove(h.data, bytes(data), len(data))

    monkeypatch.setattr(b.fcntl, 'ioctl', ioctl)
    return state


def test_exact_inventory_and_no_destructive_commands(campaign):
    prepared = b.prepare_campaign(campaign[0])
    ops = prepared.operations
    assert len(ops) == 8757
    assert prepared.request_inventory_sha256 == b.inventory_digest(ops)
    assert len(prepared.request_inventory_sha256) == 64
    assert [x.label for x in ops[:2]] == ['inquiry', 'upload']
    uploads = [x for x in ops if x.label == 'upload']
    assert len(uploads) == 47
    assert [int.from_bytes(x.cdb[2:6], 'big') for x in uploads] == list(range(b.RAM, b.RAM + 24064, 512))
    assert [x for x in ops if x.label == 'jump'][0].cdb == reader.request(0xFB08, 'rom', address=b.RAM)[0]
    assert {x.cdb[:2] for x in ops if len(x.cdb) == 16} == {b'\xfb\x06', b'\xfb\x08', b'\xfc\x14', b'\xfc\x0a', b'\xfd\x05'}
    for name in ('dumpA.bin', 'dumpB.bin'):
        reads = [x for x in ops if x.label == name]
        assert [int.from_bytes(x.cdb[2:6], 'big') for x in reads] == list(range(0, 0x100000, 256))
        first = next(i for i, op in enumerate(ops) if op.label == name)
        assert ops[first - 1].label == 'online'
        assert ops[first + 16].label == 'online'
        assert next(x for x in ops if x.label == name + '.end').cdb[:2] == b'\xfc\x0a'


@pytest.mark.parametrize('field', ['adapter_sha256', 'entry_log_sha256', 'loader_path', 'profile_path', 'profile_source_path'])
def test_unpinned_factory_inputs_do_not_open_sg(campaign, monkeypatch, field):
    path, config, _ = campaign
    if field.endswith('sha256'):
        config[field] = '0' * 64
    else:
        config[field] = str(path)
    save_config(path, config)
    monkeypatch.setattr(b, 'discover_sg', lambda _: pytest.fail('hardware discovered'))
    with pytest.raises(ValueError):
        b.prepare_campaign(path)


@pytest.mark.parametrize('mutation', ['stale', 'wrong_unit', 'wrong_port', 'key_twice', 'wrong_key',
    'out_of_order', 'failed', 'stopped', 'normal_other_port', 'no_normal', 'malformed_reply', 'duplicate_rom'])
def test_entry_freshness_identity_topology_and_single_key(campaign, mutation):
    path, config, entry = campaign
    if mutation == 'stale':
        for e in entry:
            e['time'] -= 601
    elif mutation == 'wrong_unit':
        entry[2]['decoded']['identity'] = 'FM-1_015'
    elif mutation == 'wrong_port':
        entry[-1]['usb'] = [{**USB, 'devnum': '29'}]
    elif mutation == 'key_twice':
        entry.append(entry[3])
    elif mutation == 'wrong_key':
        entry[3]['hex'] = 'f0 22 24 35 7f f7'
    elif mutation == 'out_of_order':
        entry.reverse()
    elif mutation == 'failed':
        entry.append({'event': 'uboot_not_observed'})
    elif mutation == 'stopped':
        entry.append({'event': 'stopped'})
    elif mutation == 'normal_other_port':
        entry[0]['usb_path'] = '3-1'
    elif mutation == 'no_normal':
        entry[0]['usb'][0]['pid'] = '8057'
    elif mutation == 'malformed_reply':
        entry[2]['reply'] = 'f0 00 f7'
    elif mutation == 'duplicate_rom':
        entry[-1]['usb'].append(dict(entry[-1]['usb'][0]))
    ep = Path(config['entry_log_path']); ep.write_text('\n'.join(json.dumps(e) for e in entry))
    config['entry_log_sha256'] = b.digest(ep.read_bytes()); save_config(path, config)
    with pytest.raises(ValueError):
        b.prepare_campaign(path)


@pytest.mark.parametrize('field,value', [('status', 2), ('host', 1), ('driver', 1),
    ('resid', 1), ('resid', -1), ('info', 1), ('sense_len', 1), ('sense_len', 33),
    ('masked', 1), ('msg', 1)])
def test_bad_completion_latches_and_never_retries(campaign, monkeypatch, field, value):
    prepared = b.prepare_campaign(campaign[0])
    state = mock_sg(monkeypatch, fault=lambda h, *_: setattr(h, field, value))
    transport = b.FixedSG(prepared, lambda *_a, **_k: None)
    with pytest.raises(OSError):
        transport.exchange_next()
    assert transport.phase == 'failed' and transport.next == 1
    with pytest.raises(ValueError):
        transport.exchange_next()
    assert len(state.calls) == 1 and state.closed == [888]


@pytest.mark.parametrize('fault_name', ['inquiry', 'echo', 'buffer', 'online_kind', 'online_jedec', 'ioctl'])
def test_semantic_reply_and_syscall_failures_latch(campaign, monkeypatch, fault_name):
    prepared = b.prepare_campaign(campaign[0])

    def fault(h, data, op, _state):
        if fault_name == 'inquiry' and op == 0x12:
            data[8:16] = b'OTHER   '
        elif fault_name == 'echo' and op == 0xFB08:
            data[:2] = b'\x00\x00'
        elif fault_name == 'buffer' and op == 0xFC14:
            data[2:6] = (128).to_bytes(4, 'big')
        elif fault_name == 'online_kind' and op == 0xFC0A:
            data[2] = 1
        elif fault_name == 'online_jedec' and op == 0xFC0A:
            data[4:8] = bytes(4)
        elif fault_name == 'ioctl':
            raise TimeoutError('mock timeout')

    state = mock_sg(monkeypatch, fault=fault)
    transport = b.FixedSG(prepared, lambda *_a, **_k: None)
    with pytest.raises((ValueError, TimeoutError)):
        for _ in range(51):
            transport.exchange_next()
    before = len(state.calls)
    with pytest.raises(ValueError):
        transport.exchange_next()
    assert len(state.calls) == before and state.closed == [888]
    if fault_name == 'echo':
        assert transport.next == 49  # Ambiguous jump never enters loader phase.


@pytest.mark.parametrize('when,submissions', [(3, 0), (4, 1)])
def test_binding_replacement_before_and_after_submission(campaign, monkeypatch, when, submissions):
    prepared = b.prepare_campaign(campaign[0])

    def replace_binding(state):
        if state.discoveries >= when:
            raise ValueError('mock re-enumeration')

    state = mock_sg(monkeypatch, binding_fault=replace_binding)
    transport = b.FixedSG(prepared, lambda *_a, **_k: None)
    with pytest.raises(ValueError):
        transport.exchange_next()
    assert len(state.calls) == submissions and transport.next == 1
    assert transport.failed and state.closed == [888]


def test_intent_failure_consumes_without_syscall(campaign, monkeypatch):
    prepared = b.prepare_campaign(campaign[0]); state = mock_sg(monkeypatch)

    def log(*_a, **_kw):
        raise OSError('mock fsync failure')

    transport = b.FixedSG(prepared, log)
    with pytest.raises(OSError):
        transport.exchange_next()
    assert transport.next == 1 and not state.calls and transport.failed


def test_complete_two_full_dumps_manifest_and_private_receipts(campaign, monkeypatch):
    prepared = b.prepare_campaign(campaign[0]); state = mock_sg(monkeypatch)
    manifest = b.run_campaign(prepared)
    root = Path(prepared.config['receipt_path'])
    assert manifest['kind'] == 'fm1-fixed-loader-backup'
    assert manifest['loader_sha256'] == b.LOADER_SHA != b.ORIGINAL_SHA
    assert manifest['original_loader_sha256'] == b.ORIGINAL_SHA
    assert manifest['commands'] == 8757 == len(state.calls)
    assert manifest['request_inventory_sha256'] == prepared.request_inventory_sha256
    assert manifest['identical'] and not manifest['physical_recovery_verified']
    assert [d['bytes'] for d in manifest['dumps']] == [0x100000, 0x100000]
    assert (root / 'dumpA.bin').read_bytes() == (root / 'dumpB.bin').read_bytes()
    assert root.stat().st_mode & 0o777 == 0o700
    for p in root.iterdir():
        assert p.stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        b.run_campaign(prepared)
    # Changing the receipt name cannot reuse this entry in the same parent.
    other = replace(prepared, config={**prepared.config, 'receipt_path': str(root.with_name('another'))})
    with pytest.raises(FileExistsError):
        b.run_campaign(other)
    assert len(state.calls) == 8757 and state.closed == [888]


def test_mismatched_dump_has_no_completion_manifest(campaign, monkeypatch):
    prepared = b.prepare_campaign(campaign[0])
    reads = 0

    def fault(_h, data, op, _state):
        nonlocal reads
        if op == 0xFD05:
            reads += 1
            if reads == 4097:
                data[0] ^= 1

    state = mock_sg(monkeypatch, fault=fault)
    with pytest.raises(ValueError, match='mismatched'):
        b.run_campaign(prepared)
    root = Path(prepared.config['receipt_path'])
    assert not (root / 'manifest.json').exists()
    assert state.closed == [888]
    assert json.loads((root / 'commands.jsonl').read_text().splitlines()[-1])['event'] == 'campaign_stopped_ambiguous'


def test_altered_inventory_rejected_before_discovery(campaign, monkeypatch):
    prepared = b.prepare_campaign(campaign[0])
    altered = replace(prepared, operations=prepared.operations[::-1])
    monkeypatch.setattr(b, 'discover_sg', lambda _: pytest.fail('hardware discovered'))
    with pytest.raises(ValueError, match='inventory'):
        b.FixedSG(altered, lambda *_a, **_kw: None)


@pytest.mark.parametrize('fault', ['symlink', 'oversized', 'directory'])
def test_campaign_bounded_regular_nofollow_input(campaign, tmp_path, monkeypatch, fault):
    path = campaign[0]
    invalid = tmp_path / 'invalid'
    if fault == 'symlink':
        invalid.symlink_to(path)
    elif fault == 'oversized':
        invalid.write_bytes(b' ' * (2 * b.FLASH_SIZE + 1))
    else:
        invalid.mkdir()
    monkeypatch.setattr(b, 'discover_sg', lambda _: pytest.fail('hardware discovered'))
    with pytest.raises((OSError, ValueError)):
        b.prepare_campaign(invalid)


def test_private_file_fdopen_failure_closes_descriptor(tmp_path, monkeypatch):
    real_close = b.os.close
    closed = []

    def close(fd):
        closed.append(fd); real_close(fd)

    monkeypatch.setattr(b.os, 'close', close)

    def fail(*_a, **_kw):
        raise OSError('mock fdopen failed')

    monkeypatch.setattr(b.os, 'fdopen', fail)
    with pytest.raises(OSError):
        b.private_file(tmp_path / 'private')
    assert len(closed) == 1
    with pytest.raises(OSError):
        b.os.fstat(closed[0])


@pytest.mark.parametrize('phase', ['completed_log', 'manifest_directory'])
def test_final_receipt_failure_removes_success_manifest(campaign, monkeypatch, phase):
    prepared = b.prepare_campaign(campaign[0]); state = mock_sg(monkeypatch)
    receipt = Path(prepared.config['receipt_path'])
    real_sync, real_fsync = b.sync_dir, b.os.fsync
    tripped = False

    def sync(path):
        nonlocal tripped
        if phase == 'manifest_directory' and (receipt / 'manifest.json').exists() and not tripped:
            tripped = True
            raise OSError('mock final directory sync failure')
        real_sync(path)

    def fsync(fd):
        nonlocal tripped
        log = receipt / 'commands.jsonl'
        if (phase == 'completed_log' and log.exists() and not tripped and
                'campaign_completed' in log.read_text()):
            tripped = True
            raise OSError('mock completed log sync failure')
        real_fsync(fd)

    monkeypatch.setattr(b, 'sync_dir', sync)
    monkeypatch.setattr(b.os, 'fsync', fsync)
    with pytest.raises(OSError):
        b.run_campaign(prepared)
    assert tripped and state.closed == [888]
    assert not (receipt / 'manifest.json').exists()
    assert json.loads((receipt / 'commands.jsonl').read_text().splitlines()[-1])['event'] == 'campaign_stopped_ambiguous'


@pytest.fixture
def sysfs(monkeypatch, tmp_path):
    """Actual discover_sg path logic, with a synthetic char node and sysfs tree."""
    usb = tmp_path / 'sys/devices/usb3/3-2'; usb.mkdir(parents=True)
    for key, value in {'busnum': '3', 'devnum': '28', 'idVendor': '4c4a', 'idProduct': '8057'}.items():
        (usb / key).write_text(value + '\n')
    bus = tmp_path / 'sys/bus/usb/devices'; bus.mkdir(parents=True)
    (bus / '3-2').symlink_to(usb)
    device = usb / '3-2:1.0/host0/target0:0:0/0:0:0:0'; device.mkdir(parents=True)
    sg = device / 'scsi_generic/sg0'; sg.mkdir(parents=True)
    (sg / 'device').symlink_to(device)
    classes = tmp_path / 'sys/class/scsi_generic'; classes.mkdir(parents=True)
    (classes / 'sg0').symlink_to(sg)
    chars = tmp_path / 'sys/dev/char'; chars.mkdir(parents=True)
    (chars / '21:0').symlink_to(sg)
    dev = tmp_path / 'dev'; dev.mkdir()
    node = dev / 'sg0'; node.touch()
    state = SimpleNamespace(usb=usb, classes=classes, chars=chars, node=node, sg=sg,
                            mode=stat.S_IFCHR, inode=10)
    real_path, real_stat, real_lstat = Path, Path.stat, Path.lstat
    monkeypatch.setattr(b, 'Path', lambda value: tmp_path / str(value).lstrip('/')
                        if str(value).startswith(('/sys/', '/dev')) else real_path(value))

    def node_stat(path, *args, **kwargs):
        if path == node:
            return SimpleNamespace(st_mode=state.mode, st_dev=1, st_ino=state.inode, st_rdev=os.makedev(21, 0))
        return real_stat(path, *args, **kwargs)

    def node_lstat(path, *args, **kwargs):
        if path == node:
            return node_stat(path)
        return real_lstat(path, *args, **kwargs)

    monkeypatch.setattr(Path, 'stat', node_stat)
    monkeypatch.setattr(Path, 'lstat', node_lstat)
    return state


def test_discover_sg_actual_sysfs_ancestry_mapping_and_identity(sysfs):
    first = b.discover_sg(USB)
    assert first['node'] == str(sysfs.node)
    assert first['usb'] == str(sysfs.usb)
    assert first['class'] == str(sysfs.sg)
    sysfs.inode += 1
    assert b.discover_sg(USB) != first


@pytest.mark.parametrize('fault', ['devnum', 'unrelated_usb', 'duplicate_sg', 'symlink_node', 'char_mapping'])
def test_discover_sg_actual_negative_sysfs_bindings(sysfs, fault):
    if fault == 'devnum':
        (sysfs.usb / 'devnum').write_text('29')
    elif fault == 'unrelated_usb':
        link = sysfs.sg / 'device'; link.unlink(); link.symlink_to(sysfs.chars)
    elif fault == 'duplicate_sg':
        (sysfs.classes / 'sg1').symlink_to(sysfs.sg)
    elif fault == 'symlink_node':
        sysfs.mode = stat.S_IFLNK
    else:
        link = sysfs.chars / '21:0'; link.unlink(); link.symlink_to(sysfs.usb)
    with pytest.raises(ValueError):
        b.discover_sg(USB)


def test_bounded_file_fdopen_failure_closes_descriptor(tmp_path, monkeypatch):
    path = tmp_path / 'input'; path.write_bytes(b'bounded')
    real_close = b.os.close
    closed = []

    def close(fd):
        closed.append(fd); real_close(fd)

    monkeypatch.setattr(b.os, 'close', close)
    monkeypatch.setattr(b.os, 'fdopen', lambda *_a, **_kw: (_ for _ in ()).throw(OSError('mock fdopen failure')))
    with pytest.raises(OSError):
        b.bounded_file(path)
    assert len(closed) == 1
    with pytest.raises(OSError):
        b.os.fstat(closed[0])
