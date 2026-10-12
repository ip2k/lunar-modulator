"""MIT. Genuine factories with modeled SG, USB capture and owned lifecycle.

This fixture never replaces a source pin, registry or factory. It is restricted
to disposable device-free Linux containers. Bound scripts are exact derivatives
of tracked templates; process lifecycle files are explicitly modeled evidence,
not a claim that the capture supervisor ran or owned a physical USB capture.
"""
import ast
import errno
import importlib
import json
import os
from pathlib import Path
import stat
import struct
from types import SimpleNamespace

from sdk_trace_read_fixture import (canonical_dependencies, digest,
    genuine_trace_read_ready, model_native_reads, private_write)

MODES = ('completed', 'ioctl-exception', 'native-status', 'missing-log', 'empty-log')


def admitted_dependencies():
    """A pending successor must stop before the expensive completed install."""
    a = importlib.import_module('fm1_sdk_trace_return_admission')
    stage = Path(__file__).resolve().parents[1]
    if Path(a.__file__).absolute() != stage/'tools/fm1_sdk_trace_return_admission.py':
        raise ValueError('Exact canonical returned admission required')
    for value in (a.BOOT_SHA, a.READER_SHA, a.NATIVE_SHA, a.WIRE_SHA):
        a.pin(value)
    modules = canonical_dependencies()
    for name, expected in (('fm1_sdk_trace_boot', a.BOOT_SHA),
            ('fm1_sdk_trace_read', a.READER_SHA), ('fm1_sdk_trace_sg', a.NATIVE_SHA),
            ('fm1_sdk_trace_read_wire', a.WIRE_SHA)):
        if digest((stage/'tools'/(name+'.py')).read_bytes()) != expected:
            raise ValueError('Exact accepted admission dependency differs')
    if stat.S_IMODE(stage.stat().st_mode) != 0o700:
        raise ValueError('Disposable canonical stage must be private 700')
    return a, stage, modules


def bind_template(raw, values):
    """Use the same exact AST-only assignments the real admission checks."""
    tree = ast.parse(raw)
    found = set()
    for node in tree.body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name) and node.targets[0].id in values):
            name = node.targets[0].id
            if name in found or not isinstance(node.value, ast.Constant) or node.value.value is not None:
                raise ValueError('Unique closed template assignment required')
            found.add(name)
            value = values[name]
            text = 'Path('+repr(str(value))+')' if isinstance(value, Path) else repr(value)
            node.value = ast.parse(text, mode='eval').body
    if found != set(values):
        raise ValueError('Complete template substitution required')
    return ast.unparse(ast.fix_missing_locations(tree)).encode('utf8')


def modeled_wire(usb, operations, replies, *, failed_status=False):
    """BOT records from the actual modeled ioctl operations and response bytes."""
    rows = []
    tick = 0
    def transfer(direction, raw):
        nonlocal tick
        token = 't'+str(len(rows))
        endpoint = direction+':'+usb['busnum']+':'+usb['devnum'].zfill(3)+':1'
        length = len(raw)
        tick += 1
        rows.append(f'{token} {tick} S {endpoint} -115 {length} '+
                    ('= '+raw.hex() if direction == 'Bo' else '<'))
        tick += 1
        rows.append(f'{token} {tick} C {endpoint} 0 {length} '+
                    ('>' if direction == 'Bo' else '= '+raw[:32].hex()))
    for index, (cdb, out, size) in enumerate(operations):
        assert out == b'' and size == len(replies[index])
        tag = struct.pack('<I', index+1)
        cbw = b'USBC'+tag+struct.pack('<I', size)+bytes((128, 0, len(cdb)))+cdb.ljust(16,b'\0')
        transfer('Bo', cbw)
        transfer('Bi', replies[index])
        status = int(failed_status and index == len(operations)-1)
        transfer('Bi', b'USBS'+tag+bytes(4)+bytes((status,)))
    return ('\n'.join(rows)+ ('\n' if rows else '')).encode('ascii')


def genuine_return_ready(actual, tmp_path, monkeypatch, mode):
    if mode not in MODES:
        raise ValueError('Bounded model branch required')
    a, stage, modules = admitted_dependencies()
    f = genuine_trace_read_ready(actual, tmp_path, monkeypatch)
    assert f.modules.boot is modules.boot
    run = stage/('return-model-'+tmp_path.name)
    run.mkdir(mode=0o700)
    lineage_path = private_write(run/'lineage.json', f.lineage_path.read_bytes())
    lineage = modules.boot.prepare_read_lineage(lineage_path)
    campaign = json.loads(f.native_campaign.read_bytes())
    campaign['receipt_path'] = str(f.installed.parent/('return-five-read-'+tmp_path.name))
    campaign_path = private_write(run/'campaign.json', modules.native.canonical(campaign))
    f.prepared = modules.native.prepare_campaign(campaign_path, lineage)
    f.lineage, f.lineage_path, f.native_campaign = lineage, lineage_path, campaign_path
    journal = private_write(run/'original-install-journal.json', f.g.journal.read_bytes())
    values = dict(STAGE=stage, RUN=run, NATIVE_SHA=a.NATIVE_SHA, READER_SHA=a.READER_SHA,
        BOOT_SHA=a.BOOT_SHA, CAMPAIGN_SHA=digest(campaign_path.read_bytes()),
        LINEAGE_SHA=digest(lineage_path.read_bytes()))
    child = bind_template((stage/'tools/fm1_sdk_trace_capture_child.py').read_bytes(), values)
    private_write(run/'execute-child.py', child)
    private_write(run/'preflight.json', a.canonical(dict(schema=1,
        modeled_fixture=True, time=f.clock.value, original_snapshot_sha256=digest(
            Path(campaign['inputs']['snapshot_path']).read_bytes()))))
    paths = [stage/'tools'/name for name in ('fm1_sdk_trace_boot.py',
        'fm1_sdk_trace_read.py', 'fm1_sdk_trace_sg.py')]
    paths += [run/name for name in ('execute-child.py','campaign.json','lineage.json','preflight.json')]
    packet = {str(p.relative_to(stage)):digest(p.read_bytes()) for p in paths}
    packet_raw = a.canonical(packet)
    private_write(run/'packet-pins.json', packet_raw)
    wrapper_values = dict(values, PACKET_SHA=digest(packet_raw), PACKET_MEMBERS=len(packet),
        CHILD_SHA=digest(child))
    wrapper = bind_template((stage/'tools/fm1_sdk_trace_capture.py').read_bytes(), wrapper_values)
    private_write(run/'execute-once.py', wrapper)
    a.verify_derivative((stage/'tools/fm1_sdk_trace_capture.py').read_bytes(), wrapper, wrapper_values)
    a.verify_derivative((stage/'tools/fm1_sdk_trace_capture_child.py').read_bytes(), child, values)
    return SimpleNamespace(a=a, stage=stage, run=run, f=f, journal=journal, mode=mode)


def run_genuine_read(q, monkeypatch):
    """Run unchanged native worker; inject only bounded syscall failures."""
    f, mode = q.f, q.mode
    state = model_native_reads(f, monkeypatch)
    native, reader = f.modules.native, f.prepared.module
    result, caught = None, None
    # Source-owned read marker/plan/log lifetime, with no fabricated terminal.
    with monkeypatch.context() as faults:
        if mode == 'ioctl-exception':
            original = native.fcntl.ioctl
            def ioctl(*args):
                if len(state.calls) == 1:
                    raise OSError(errno.EIO, 'modeled native input failure')
                return original(*args)
            faults.setattr(native.fcntl, 'ioctl', ioctl)
        elif mode == 'native-status':
            original = native.fcntl.ioctl
            def ioctl(fd, number, header):
                value = original(fd, number, header)
                if len(state.calls) == 2:
                    header.status = 2
                return value
            faults.setattr(native.fcntl, 'ioctl', ioctl)
        elif mode == 'missing-log':
            original = reader.os.open
            def opened(path, *args, **kwargs):
                if Path(path) == f.prepared.read.receipt/'commands.jsonl':
                    raise OSError(errno.EIO, 'modeled command log open failure')
                return original(path, *args, **kwargs)
            faults.setattr(reader.os, 'open', opened)
        elif mode == 'empty-log':
            original = reader.os.fdopen
            class EnterFailure:
                def __init__(self, fp): self.fp = fp
                def __enter__(self):
                    self.fp.close()
                    raise OSError(errno.EIO, 'modeled command log context failure')
                def __exit__(self, *args): self.fp.close()
            def fdopen(fd, *args, **kwargs):
                name = os.readlink('/proc/self/fd/'+str(fd))
                fp = original(fd, *args, **kwargs)
                return EnterFailure(fp) if name == str(f.prepared.read.receipt/'commands.jsonl') else fp
            faults.setattr(reader.os, 'fdopen', fdopen)
        try:
            result = native.run_campaign(f.prepared)
        except (OSError, ValueError) as exc:
            caught = type(exc).__name__
    assert (caught is None) == (mode == 'completed')
    if mode != 'completed':
        assert caught == ('ValueError' if mode == 'native-status' else 'OSError')
    assert len(state.opens) == len(state.closes) == (0 if mode.endswith('-log') else 1)
    if mode.endswith('-log'):
        assert not state.calls
    if mode == 'ioctl-exception':
        assert len(state.calls) == 1
    if mode == 'native-status':
        assert len(state.calls) == 2
    return state, result, caught


def publish_modeled_capture(q, state, result):
    """Explicit modeled owned process receipts, linked to real worker logs."""
    a, f, run = q.a, q.f, q.run
    now = f.clock.value
    pins = dict(campaign_sha256=digest(f.native_campaign.read_bytes()),
        lineage_sha256=digest(f.lineage_path.read_bytes()), native_sha256=a.NATIVE_SHA,
        reader_sha256=a.READER_SHA, boot_sha256=a.BOOT_SHA)
    files = {'wrapper-attempt.json': a.canonical(dict(time=now-.2, **pins,
        usb_binding=f.snapshot['usb_binding'], retry=False, commands=5,
        upload_operations=0, reset_operations=0, flash_operations=0)),
        'capture-open.json': a.canonical(dict(time=now-.1, timeout_pid=200, cat_pid=201,
            process_group=200, open_capture_fd=True)),
        'capture-stop.json': a.canonical(dict(time=now+.2, process_group=200,
            returncode=-15, owned_processes_only=True)),
        'execution-exit.json': a.canonical(dict(time=now+.1,
            exit_status=0 if result is not None else 1,
            campaign_sha256=pins['campaign_sha256'], capture_alive_after_child=True,
            retry=False, read_completion_attested=False, recovery_proven=False, boot_cause_proven=False)),
        'execution.stdout': b'', 'usbmon.stderr': b'',
        'usbmon.txt': modeled_wire(f.snapshot['usb_binding'], state.calls, state.replies,
            failed_status=q.mode == 'native-status')}
    for name, raw in files.items(): private_write(run/name, raw)
    names = ('execute-once.py','execute-child.py','preflight.json', *files)
    assert len(names) == 10
    envelope = dict(schema=1, kind='fm1-owned-sdk-trace-read-capture',
        native_campaign_path=str(f.native_campaign), native_campaign_sha256=pins['campaign_sha256'],
        boot_lineage_path=str(f.lineage_path), boot_lineage_sha256=pins['lineage_sha256'],
        wrapper_files_sha256={n:digest((run/n).read_bytes()) for n in names})
    capture = private_write(run/'owned-capture.json', a.canonical(envelope))
    campaign = dict(schema=1, kind='fm1-exact-owned-sdk-trace-returned-state',
        adapter_sha256=digest(Path(a.__file__).read_bytes()),
        boot_lineage_path=str(f.lineage_path), boot_lineage_sha256=pins['lineage_sha256'],
        native_campaign_path=str(f.native_campaign), native_campaign_sha256=pins['campaign_sha256'],
        owned_capture_path=str(capture), owned_capture_sha256=digest(capture.read_bytes()))
    return private_write(run/'return-admission.json', a.canonical(campaign))
