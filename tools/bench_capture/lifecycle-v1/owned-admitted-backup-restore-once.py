#!/usr/bin/python3
"""One-use owned usbmon capture for the frozen admitted backup or restore CLI.

This wrapper has only two fixed modes, each pinned to a reviewed canonical
factory and its source inventory. It prepares with that factory before opening
capture, starts the one documented child CLI once, then records a passive
same-port USB/SG snapshot while capture is still owned and running. It does not
discover, alter, synthesize, or replace campaign authority.
"""
import argparse
import hashlib
import importlib
import json
import os
import signal
import stat
import subprocess
import sys
import time
from pathlib import Path

USBMON = '/sys/kernel/debug/usb/usbmon/1u'
MAX_PACKET = 65536
MAX_SOURCE = 32 * 1048576
CAPTURE_SECONDS = 1800
CHILD_TIMEOUT = 1750

REHEARSAL = {
    'tools/fm1_bound_sdk_diagnostic.py': '4718825ab07c05364d3141f9281554b22d3eb2c902af759f4bc68a83ca648847',
    'tools/fm1_bound_diagnostic.py': '25e57ffda466c898df88370069cf4d7fce02134e141ba95516347c30953d1a36',
    'tools/fm1_flash_transaction.py': 'd0527efbe74314b30a2cd76897c022a1c7857db888ef6e8f8610dbb329956908',
    'tools/fm1_uboot_read.py': '28317ee56a489e0bb38de981fe0d0c4260384be570349795741fdb9a98d6ae57',
    'tools/fm1_fixed_loader_backup.py': '79bbe99ce923daaf8af2c701a65ec39a015191313de79676e36622cb8db00afb',
    'tools/fm1_fixed_loader_reset.py': 'dbbe363104aa339b63430ff0a99f817aba27afa233a266d449f45e048cd09116',
    'tools/jieli/raw_flash_profile.py': '43e4d23f665fac1a73dee2b5ae6e05bc5c3d0ab9bee04b886abad34c6289ae8f',
    'tools/jieli/raw_sdk_diagnostic.py': '8c59b67da2c5b66d48dacadf4d90e48bd80272d1868fab21b2a3a80eb1496f07',
    'tools/jieli/audit_sdk_diagnostic.py': 'e8ce7a43e43ef127ecaf87db55578b7cad7bb1a926f2be3ce92b8688ae7dff8b',
    'tools/jieli/audit_link.py': '673daa193891462147e1aab1082e62f339508e801e14de80a4cfabcca9828252',
    'tools/jieli/diagnostic_report.py': 'd85f2ca1dd70adc015b724b46d3c332c307509ad91fa6faa86adc5fc45e755cf',
    'tools/jieli/inspect_fwsc.py': '2c7a3b61d41366755d457b03d6029c7d9b331b07961335e67e1892fe6168b820',
    'tools/jieli/inspect_stock_flash.py': 'de68a7d862e18adcce066bc6309364830ecfeb9dac6147fe9178384aae98e34b',
    'tools/jieli/package_guard.py': '78643b8a13114293afc1b3b0880e56858371669cf42a4cadbb31a7bb7557dc51',
    'tools/jieli/loader_config_profile.py': '9664e1329d8259362da78c047ce2d6003dfe8df2850f02703f98e8b6bf277cd8',
}

BACKUP_PINS = {
    **REHEARSAL,
    'tools/fm1_sdk_trace_admitted_backup.py': '7e9dbf156c92e7cdcc2dcd01fbbdd19ad8e06eef9fcd8772f72870afaebf738f',
    'tools/fm1_returned_rom_backup.py': 'afeefe7bd7e9044cb34106081766d6104cda7ab0196d0de903c35a5c1a52b4be',
    'tools/fm1_sdk_trace_return_admission.py': '5ca132fc2f2595400bc9ccb231c3e5cd44ecc9886cd830e201272b33a677b34a',
    'tools/fm1_sdk_rehearsal.py': 'f696484511754b91d4faf449aa2e4cab3ca910daf05a9acd66daa966bae7d6c4',
}
RESTORE_PINS = {
    **BACKUP_PINS,
    'tools/fm1_sdk_trace_admitted_stock_restore.py': '683275d73a846dd4c3d5edbb6695fe853832c4c7e4f7921ac9504293a8531e4e',
    'tools/fm1_returned_rom_stock_restore.py': 'f583523740bb709dde0cf8bc2e07677e2ab26063d511dcb3ba84a6b232e9af33',
    'tools/fm1_bound_sdk_trace.py': '54bd9a2990d0055b1d102bc8481a71d883d586649aa2d79d62a185a415296835',
    'tools/fm1_fixed_target_reset.py': 'b846b574fe1e5b7597001f6f833044a07143540f2c0b3676e93bac807869833a',
}
MODES = {
    'backup': ('fm1_sdk_trace_admitted_backup', 'fm1-sdk-trace-admitted-backup-one-shot', BACKUP_PINS),
    'restore': ('fm1_sdk_trace_admitted_stock_restore', 'fm1-sdk-trace-restore-one-shot', RESTORE_PINS),
}


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def read_regular(path, limit):
    p = Path(path)
    if not p.is_absolute():
        raise ValueError('absolute direct file required')
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError('direct regular file required')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            data = stream.read(limit + 1)
    finally:
        os.close(fd)
    if len(data) > limit:
        raise ValueError('file exceeds bound')
    return data


def sha_file(path, limit=MAX_SOURCE):
    return sha_bytes(read_regular(path, limit))


def write_exclusive(path, data):
    p = Path(path)
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    try:
        with os.fdopen(fd, 'wb', closefd=False) as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        os.close(fd)
    dfd = os.open(p.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        os.fsync(dfd)
    finally:
        os.close(dfd)


def write_json(path, value):
    raw = (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode('ascii')
    write_exclusive(path, raw)


def private_dir(path, label):
    p = Path(path)
    info = p.lstat()
    if (not p.is_absolute() or not stat.S_ISDIR(info.st_mode)
            or stat.S_IMODE(info.st_mode) != 0o700 or info.st_uid != os.geteuid()):
        raise ValueError(label + ' must be a direct private directory')
    return p


def staged_file(stage, relative, limit=MAX_SOURCE):
    rel = Path(relative)
    if rel.is_absolute() or not rel.parts or any(part in ('.', '..') for part in rel.parts) or '\\' in str(relative):
        raise ValueError('contained stage-relative source required')
    cursor = stage
    for part in rel.parts[:-1]:
        cursor = cursor / part
        if not stat.S_ISDIR(cursor.lstat().st_mode):
            raise ValueError('staged path crosses a non-directory')
    return read_regular(stage / rel, limit)


def capture_identity(proc):
    if proc.poll() is not None:
        raise RuntimeError('owned capture process exited')
    pid = proc.pid
    if os.getpgid(pid) != pid:
        raise RuntimeError('capture is not its own process group')
    cmd = (Path('/proc') / str(pid) / 'cmdline').read_bytes().split(b'\0')
    if cmd != [b'/usr/bin/timeout', str(CAPTURE_SECONDS).encode(), b'/bin/cat', USBMON.encode(), b'']:
        raise RuntimeError('capture timeout/cat argv differs')
    if Path(os.readlink(Path('/proc') / str(pid) / 'exe')).resolve() != Path('/usr/bin/timeout').resolve():
        raise RuntimeError('capture timeout executable differs')
    children = (Path('/proc') / str(pid) / 'task' / str(pid) / 'children').read_text().split()
    if len(children) != 1:
        raise RuntimeError('capture must own exactly one reader')
    child = int(children[0])
    if os.getpgid(child) != pid:
        raise RuntimeError('capture reader escaped process group')
    ccmd = (Path('/proc') / str(child) / 'cmdline').read_bytes().split(b'\0')
    if ccmd != [b'/bin/cat', USBMON.encode(), b'']:
        raise RuntimeError('usbmon reader argv differs')
    if Path(os.readlink(Path('/proc') / str(child) / 'exe')).resolve() != Path('/bin/cat').resolve():
        raise RuntimeError('usbmon reader executable differs')
    links = []
    for fd in (Path('/proc') / str(child) / 'fd').iterdir():
        try:
            links.append(os.readlink(fd))
        except FileNotFoundError:
            pass
    if USBMON not in links:
        raise RuntimeError('capture reader has not opened bus 1 usbmon')
    return {'timeout_pid': pid, 'cat_pid': child, 'process_group': pid, 'open_capture_fd': True}


def get_usb_binding(prepared, mode):
    if mode == 'backup':
        return json.loads(prepared.snapshot)['usb_binding']
    # Restore Prepared delegates to the actual kernel Prepared; its validated
    # Policy.binding_bytes contains the admitted backup's exact USB binding.
    if len(prepared.policies) != 1:
        raise ValueError('exact single admitted restore policy required')
    return json.loads(prepared.policies[0].binding_bytes)['usb_binding']


def passive_snapshot(prepared, mode, expected_usb, campaign_sha):
    bridge = prepared.bridge
    device_path = expected_usb.get('path') if isinstance(expected_usb, dict) else None
    if (not isinstance(device_path, str) or not device_path or device_path in ('.', '..')
            or Path(device_path).is_absolute() or '/' in device_path or '\\' in device_path):
        raise ValueError('single passive USB sysfs device component required')
    path = Path('/sys/bus/usb/devices') / device_path
    observed_usb = bridge.usb_snapshot(path)
    bridge.validate_usb(observed_usb)
    if observed_usb != expected_usb:
        raise ValueError('passive USB identity changed during campaign')
    observed_sg = bridge.discover_sg(observed_usb)
    if mode == 'backup':
        expected_sg = json.loads(prepared.snapshot)['sg_binding']
    else:
        expected_sg = json.loads(prepared.mapping)
    # discover_sg returns stat identities as tuples; the retained JSON binding
    # represents the same identities as lists. Compare their wire encoding,
    # preserving numeric types and every field rather than coercing values.
    if json.dumps(observed_sg, sort_keys=True, allow_nan=False) != json.dumps(expected_sg, sort_keys=True, allow_nan=False):
        raise ValueError('passive SG mapping changed during campaign')
    return {'schema': 1, 'kind': 'fm1-passive-admitted-' + mode + '-post-command',
        'observed_at': time.time(), 'usb_binding': observed_usb, 'sg_binding': observed_sg,
        'campaign_sha256': campaign_sha, 'quiet_state': 'same-loader-no-later-commands'}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('mode', choices=tuple(MODES))
    ap.add_argument('--stage', required=True, type=Path)
    ap.add_argument('--run', required=True, type=Path)
    ap.add_argument('--packet', required=True, type=Path)
    ap.add_argument('--packet-sha256', required=True)
    args = ap.parse_args()
    if os.geteuid() != 0 or sys.platform != 'linux' or sys.flags.optimize != 0:
        raise SystemExit('requires non-optimized Linux root')
    os.umask(0o077)

    stage = private_dir(args.stage.absolute(), 'staged source root')
    run = private_dir(args.run.absolute(), 'one-use run directory')
    tools = private_dir(stage / 'tools', 'staged tools directory')
    packet_path = args.packet.absolute()
    if packet_path.parent != stage:
        raise ValueError('packet must be a direct stage file')
    packet_raw = read_regular(packet_path, MAX_PACKET)
    if sha_bytes(packet_raw) != args.packet_sha256:
        raise ValueError('packet hash mismatch')
    packet = json.loads(packet_raw)
    module_name, kind, pins = MODES[args.mode]
    adapter_rel = 'tools/' + module_name + '.py'
    expected_keys = {'schema', 'kind', 'campaign_path', 'campaign_sha256', 'adapter_path',
        'adapter_sha256', 'source_pins', 'usb_binding'}
    campaign = Path(packet.get('campaign_path', ''))
    adapter = Path(packet.get('adapter_path', ''))
    if (set(packet) != expected_keys or type(packet['schema']) is not int or packet['schema'] != 1
            or packet['kind'] != kind or campaign.parent != stage or not campaign.is_absolute()
            or adapter != tools / (module_name + '.py') or not adapter.is_absolute()
            or sha_file(campaign, MAX_PACKET) != packet['campaign_sha256']
            or sha_file(adapter) != packet['adapter_sha256']
            or packet['adapter_sha256'] != pins[adapter_rel]
            or set(packet['source_pins']) != set(pins)
            or packet['source_pins'] != pins):
        raise ValueError('exact one-shot packet, factory and literal source inventory required')
    for relative, expected in pins.items():
        if sha_bytes(staged_file(stage, relative)) != expected:
            raise ValueError('staged source differs from reviewed literal: ' + relative)

    sys.path.insert(0, str(tools))
    factory = importlib.import_module(module_name)
    if Path(factory.__file__).absolute() != adapter or sha_file(adapter) != packet['adapter_sha256']:
        raise ValueError('normal canonical factory module identity required')
    prepared = factory.prepare_campaign(campaign)
    if (type(prepared) is not factory.Prepared or prepared.campaign_sha256 != packet['campaign_sha256']):
        raise ValueError('factory-prepared exact campaign required')
    prepared.check()
    usb = get_usb_binding(prepared, args.mode)
    if usb != packet['usb_binding']:
        raise ValueError('prepared factory USB binding differs from reviewed packet')
    write_json(run / 'wrapper-attempt.json', {'schema': 1, 'kind': kind, 'time': time.time(),
        'campaign_sha256': packet['campaign_sha256'], 'adapter_sha256': packet['adapter_sha256'],
        'usb_binding': usb, 'retry': False})
    capture = None
    try:
        out_fd = os.open(run / 'usbmon1.txt', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
        try:
            err_fd = os.open(run / 'usbmon1.stderr', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
            try:
                capture = subprocess.Popen(['/usr/bin/timeout', str(CAPTURE_SECONDS), '/bin/cat', USBMON],
                    stdout=out_fd, stderr=err_fd, start_new_session=True, close_fds=True)
            finally:
                os.close(err_fd)
        finally:
            os.close(out_fd)
        identity = None
        for _ in range(100):
            try:
                identity = capture_identity(capture)
                break
            except (FileNotFoundError, RuntimeError):
                time.sleep(.02)
        if identity is None:
            raise RuntimeError('owned usbmon1u open was not confirmed')
        write_json(run / 'capture-open.json', {'schema': 1, 'time': time.time(), **identity})
        stdout_fd = os.open(run / 'execution.stdout', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
        try:
            child_started = time.time()
            with os.fdopen(stdout_fd, 'wb', closefd=False) as log:
                result = subprocess.run(['/usr/bin/python3', '-B', '-E', '-s', '-S', str(adapter),
                    '--campaign', str(campaign)], cwd=stage, env={'PATH': '/usr/bin:/bin', 'LC_ALL': 'C.UTF-8'},
                    stdout=log, stderr=subprocess.STDOUT, timeout=CHILD_TIMEOUT, check=False)
                child_finished = time.time()
                log.flush()
                os.fsync(log.fileno())
        finally:
            os.close(stdout_fd)
        capture_identity(capture)
        write_json(run / 'execution-exit.json', {'schema': 1, 'time': time.time(),
            'child_started_at': child_started, 'child_finished_at': child_finished,
            'exit_status': result.returncode, 'campaign_sha256': packet['campaign_sha256'],
            'adapter_sha256': packet['adapter_sha256'], 'capture_alive_after_child': True, 'retry': False})
        passive = passive_snapshot(prepared, args.mode, usb, packet['campaign_sha256'])
        write_json(run / 'passive-snapshot.json', passive)
        return result.returncode
    except BaseException as exc:
        write_json(run / 'wrapper-stopped-ambiguous.json', {'schema': 1, 'time': time.time(),
            'error': type(exc).__name__, 'detail': str(exc), 'retry': False})
        raise
    finally:
        if capture is not None:
            try:
                if capture.poll() is not None:
                    raise RuntimeError('owned capture ended before explicit stop')
                # Full argv, direct child, process group and open usbmon FD are
                # rechecked immediately before signaling the exact owned group.
                identity = capture_identity(capture)
                group = identity['process_group']
                os.killpg(group, signal.SIGTERM)
                code = capture.wait(timeout=5)
                fd = os.open(run / 'usbmon1.txt', os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
                try:
                    os.fsync(fd)
                finally:
                    os.close(fd)
                fd = os.open(run / 'usbmon1.stderr', os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
                try:
                    os.fsync(fd)
                finally:
                    os.close(fd)
                write_json(run / 'capture-stop.json', {'schema': 1, 'time': time.time(),
                    'process_group': group, 'returncode': code, 'owned_processes_only': True})
            except BaseException as exc:
                try:
                    if capture.poll() is None:
                        # Never signal a process group from its PID alone. If
                        # ownership cannot be re-established, retain the
                        # ambiguity for operator handling instead of guessing.
                        identity = capture_identity(capture)
                        os.killpg(identity['process_group'], signal.SIGTERM)
                        capture.wait(timeout=5)
                except BaseException:
                    pass
                write_json(run / 'wrapper-cleanup-ambiguous.json', {'schema': 1, 'time': time.time(),
                    'error': type(exc).__name__, 'detail': str(exc), 'retry': False})
                raise


if __name__ == '__main__':
    raise SystemExit(main())
