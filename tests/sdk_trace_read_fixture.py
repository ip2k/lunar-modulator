"""MIT. Genuine canonical install→boot→reader→native composition fixture.

Only for disposable device-free Hera containers. Production factories, pins,
registries and executable sources remain intact; clocks, device syscalls and
passive USB evidence are modeled. Source activation is a caller prerequisite.
"""
from copy import deepcopy
import ctypes as C
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import stat
import struct
import sys
from types import SimpleNamespace


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical_dependencies():
    """Reject closed or stale canonical sources before an expensive install."""
    root = Path(__file__).resolve().parents[1] / 'tools'
    modules = {}
    for name in ('fm1_sdk_trace_install', 'fm1_sdk_trace_boot',
                 'fm1_sdk_trace_read', 'fm1_sdk_trace_sg'):
        module = importlib.import_module(name)
        path = root / (name + '.py')
        if Path(module.__file__).absolute() != path or sys.modules[name] is not module:
            raise ValueError('Exact canonical top-level source required')
        modules[name] = module
    install, boot, reader, native = modules.values()
    boot_sha = digest(Path(boot.__file__).read_bytes())
    reader_sha = digest(Path(reader.__file__).read_bytes())
    if (reader.BOOT_POLICY_SHA != boot_sha or native.READ_POLICY_SHA != reader_sha
            or getattr(boot, 'IMPORTED_SOURCE_SHA256', None) != boot_sha
            or boot.INSTALL_SHA != digest(Path(install.__file__).read_bytes())):
        raise ValueError('Accepted literal canonical install/boot/read/native chain required')
    for value in (reader.BOOT_POLICY_SHA, native.READ_POLICY_SHA):
        if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{64}', value):
            raise ValueError('Source activation remains closed')
    return SimpleNamespace(install=install, boot=boot, reader=reader, native=native,
                           modules=modules)


def private_write(path, raw):
    """Test evidence is original, exclusive and private, never source replacement."""
    path = Path(path)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        fp = os.fdopen(fd, 'wb')
    except BaseException:
        os.close(fd)
        raise
    with fp:
        fp.write(raw)
    return path


def genuine_trace_read_ready(actual, tmp_path, monkeypatch):
    """Real completed install, real reset worker and canonical read lineage."""
    if os.environ.get('LUNAR_REHEARSAL_DISPOSABLE') != '1' or sys.platform != 'linux':
        raise ValueError('Explicit disposable Linux device-free fixture required')
    modules = canonical_dependencies()
    boot, native = modules.boot, modules.native
    from sdk_trace_fixture import genuine_completed_trace_install
    from test_reset_wire import capture

    g = genuine_completed_trace_install(actual, tmp_path, monkeypatch)
    assert g.install is modules.install
    installed = boot.validate_completed_install(g.campaign, **g.pins)
    old, mapping = json.loads(installed.usb), json.loads(installed.mapping)
    clock = SimpleNamespace(value=installed.completed_at + 1)
    monkeypatch.setattr(boot.time, 'time', lambda: clock.value)
    config = dict(schema=1, kind='fm1-fixed-loader-sdk-trace-target-reset',
        adapter_sha256=boot.IMPORTED_SOURCE_SHA256,
        install_campaign_path=str(g.campaign),
        install_campaign_sha256=g.pins['campaign_sha256'],
        install_commands_sha256=g.pins['commands_sha256'],
        install_result_sha256=g.pins['result_sha256'],
        install_exit_status=0, journal_sha256=g.pins['journal_sha256'],
        active_session_state='same-fixed-loader-installed-trace-target-no-later-commands',
        usb_binding=old, sg_binding=mapping,
        receipt_path=str(installed.parent / 'composed-target-reset'),
        target_sha256=boot.TARGET_SHA,
        target_boot_authorization='exact-sdk-recovery-trace-diagnostic')
    campaign = private_write(tmp_path / 'composed-boot.json', boot.canonical(config))
    reset = boot.prepare_campaign(campaign)
    monkeypatch.setattr(reset.bridge, 'discover_sg', g.model.discover)
    reset_calls = []

    def reset_ioctl(fd, number, h):
        assert fd == g.model.FD and number == 0x2285
        assert h.interface_id == ord('S') and h.cmd_len == h.data_len == 16
        assert h.sense_max == 32 and h.direction == -3 and h.timeout == 3000
        assert h.iovec_count == h.flags == h.pack_id == 0
        cdb = C.string_at(h.cmd, h.cmd_len)
        assert cdb == boot.legacy.reset.RESET_CDB
        reset_calls.append(cdb)
        C.memmove(h.data, cdb, 16)
        return 0

    monkeypatch.setattr(boot.fcntl, 'ioctl', reset_ioctl)
    outcome = boot.run_campaign(reset)
    assert outcome == dict(request_completion=True, core_reset_observed=False, boot_observed=False)
    assert len(reset_calls) == 1 and len(g.model.opened) == len(g.model.closed) == 2
    fresh = dict(old, devnum=str(int(old['devnum']) + 1))
    fresh_mapping = deepcopy(mapping)
    for key in ('node_identity', 'class_identity', 'device_identity', 'usb_identity'):
        fresh_mapping[key][1] += 100
    snapshot = dict(schema=1, kind='fm1-passive-post-trace-boot-rom',
        observed_at=clock.value + .2, usb_binding=fresh, sg_binding=fresh_mapping,
        target_boot_campaign_sha256=reset.campaign_sha256,
        quiet_state='initial-rom-no-later-commands-no-loader-upload')
    opened = dict(time=clock.value-.1, timeout_pid=100, cat_pid=101,
                  process_group=100, open_capture_fd=True)
    stopped = dict(time=clock.value+.3, process_group=100, returncode=-15,
                   owned_processes_only=True)
    exited = dict(time=clock.value+.1, campaign_sha256=reset.campaign_sha256,
        exit_status=0, capture_alive_after_child=True, retry=False,
        reset_completed_attested=False, boot_cause_proven=False)
    rows = [row.replace(':3:025:', ':'+old['busnum']+':'+old['devnum'].zfill(3)+':')
            for row in capture('reply')]
    originals = dict(capture=('\n'.join(rows)+'\n').encode(),
        capture_open=boot.canonical(opened), capture_stop=boot.canonical(stopped),
        boot_exit=boot.canonical(exited), rom_snapshot=boot.canonical(snapshot))
    config = dict(schema=1, kind='fm1-exact-sdk-trace-boot-read-lineage',
        adapter_sha256=boot.IMPORTED_SOURCE_SHA256,
        boot_campaign_path=str(campaign), boot_campaign_sha256=reset.campaign_sha256,
        boot_commands_sha256=digest((reset.receipt/'commands.jsonl').read_bytes()),
        wire_verifier_sha256=boot.WIRE_VERIFIER_SHA)
    for name, raw in originals.items():
        path = private_write(installed.parent / ('composed-'+name+'.bin'), raw)
        config[name+'_path'], config[name+'_sha256'] = str(path), digest(raw)
    lineage_path = private_write(installed.parent/'composed-lineage.json', boot.canonical(config))
    clock.value += 1
    lineage = boot.prepare_read_lineage(lineage_path)
    boot.require_read_lineage(lineage)
    native_config = dict(schema=1, kind='fm1-exact-native-sdk-trace-read',
        adapter_sha256=digest(Path(native.__file__).read_bytes()),
        inputs=dict(elf_path=str(g.inputs['elf_path']), app_path=str(g.inputs['app_path']),
            manifest_path=str(g.inputs['build_manifest_path']),
            snapshot_path=config['rom_snapshot_path']),
        receipt_path=str(installed.parent/'composed-five-read'))
    native_campaign = private_write(tmp_path/'composed-native.json', native.canonical(native_config))
    prepared = native.prepare_campaign(native_campaign, lineage)
    assert prepared.read.lineage is lineage
    assert sys.modules['fm1_sdk_trace_boot'] is boot
    assert type(lineage).__module__ == 'fm1_sdk_trace_boot'
    # Native's exact-byte private reader/Elf module is part of production design;
    # it must obtain the same canonical boot authority rather than a clone.
    assert prepared.module is not modules.reader
    assert prepared.module.BOOT_POLICY_SHA == modules.reader.BOOT_POLICY_SHA
    return SimpleNamespace(g=g, modules=modules, clock=clock, installed=installed,
        reset=reset, reset_calls=reset_calls, lineage=lineage, lineage_path=lineage_path,
        snapshot=snapshot, native_campaign=native_campaign, prepared=prepared)


def model_native_reads(fixture, monkeypatch):
    """Replace only device syscalls/discovery and monotonic clock, keep real logs."""
    n, prepared = fixture.modules.native, fixture.prepared
    mapping, usb = fixture.snapshot['sg_binding'], fixture.snapshot['usb_binding']
    state = SimpleNamespace(fd=88888, calls=[], opens=[], closes=[], locks=[])
    real_open, real_close, real_fstat = n.os.open, n.os.close, n.os.fstat
    monkeypatch.setattr(prepared.bridge, 'discover_sg',
                        lambda actual: deepcopy(mapping) if actual == usb else None)

    def opened(path, flags, *args, **kwargs):
        if str(path) != mapping['node']:
            return real_open(path, flags, *args, **kwargs)
        assert prepared.read.marker.exists()
        assert (prepared.read.receipt/'commands.jsonl').exists()
        assert flags == os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK
        state.opens.append(flags)
        return state.fd

    def fstat(fd):
        if fd != state.fd:
            return real_fstat(fd)
        a, b, c = mapping['node_identity']
        return SimpleNamespace(st_mode=stat.S_IFCHR, st_dev=a, st_ino=b, st_rdev=c)

    def close(fd):
        if fd != state.fd:
            return real_close(fd)
        state.closes.append(fd)

    def flock(fd, flags):
        assert fd == state.fd and flags == n.fcntl.LOCK_EX | n.fcntl.LOCK_NB
        state.locks.append(flags)

    decoded_trace = struct.pack('<IHH16sIIIiIIIIII', 0x4c525431, 1, 64,
        prepared.module.NONCE, 5, 5 ^ 0xffffffff, 1, 0, 20000, 1976,
        0xffffffff, 360000000, 60000000, 10)
    raw_trace = prepared.module.decode_transfer(decoded_trace, 64)
    raw_stage = prepared.module.decode_transfer(struct.pack('<I', 6), 4)
    state.replies = [b'\0'*8+b'WL82'.ljust(8)+b'UBOOT1.00'.ljust(16)+b'1.00',
                     raw_trace, raw_stage, raw_trace, raw_stage]

    def ioctl(fd, number, h):
        assert fd == state.fd and number == 0x2285
        assert h.interface_id == ord('S') and h.direction == -3 and h.timeout == 3000
        assert h.sense_max == 32 and h.flags == h.iovec_count == h.pack_id == 0
        assert h.user is None
        cdb = C.string_at(h.cmd, h.cmd_len)
        op = cdb, b'', h.data_len
        assert op == n.OPERATIONS[len(state.calls)]
        outer = [json.loads(row) for row in (prepared.read.receipt/'commands.jsonl').read_bytes().splitlines()]
        journal = [json.loads(row) for row in (prepared.read.receipt/'native.jsonl').read_bytes().splitlines()]
        assert outer[-1]['event'] == 'submit_intent' and outer[-1]['cdb'] == cdb.hex()
        assert journal[-1]['event'] == 'native_ioctl_intent'
        assert journal[-1]['index'] == len(state.calls)
        reply = state.replies[len(state.calls)]
        state.calls.append(op)
        C.memmove(h.data, reply, len(reply))
        return 0

    monkeypatch.setattr(n.os, 'open', opened)
    monkeypatch.setattr(n.os, 'fstat', fstat)
    monkeypatch.setattr(n.os, 'close', close)
    monkeypatch.setattr(n.fcntl, 'flock', flock)
    monkeypatch.setattr(n.fcntl, 'ioctl', ioctl)
    monkeypatch.setattr(n.time, 'monotonic', lambda: 100.)
    return state
