#!/usr/bin/python3
"""Proposed parent for one unchanged entry script plus one fixed-loader backup.

This is an ignored, review-only proposal. It is deliberately bound to the
existing private entry root and exact reviewed child sources. It performs no
work unless explicitly invoked with the reviewed candidate SHA.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import sys
import time

ROOT = Path('/home/claude/fm1-sdk-trace-entry-20261012-v3-2')
ENTRY_SOURCE = ROOT / 'entry-once/enter-once-v3.py'
PREPARE_SOURCE = ROOT / 'prepare-backup-v3.py'
BACKUP_SOURCE = ROOT / 'tools/fm1_fixed_loader_backup.py'
READER_SOURCE = ROOT / 'tools/fm1_uboot_read.py'
RUN = ROOT / 'initial-entry-backup-v3-2'
USBMON = '/sys/kernel/debug/usb/usbmon/1u'
PINS_SHA = '29ff2afe7f6148151241891bc05ec95e30420df414e0f0ee142a4db12e6236cc'
ENTRY_SHA = '412177d5b1f795427e98195d4cef630c4f7d8be8f2c2096d866330a9c760b904'
PREPARE_SHA = '069040d12b0bda7e1f1f9ddebc01f37e955cc903a87634b71df05f65efed9168'
BACKUP_SHA = '79bbe99ce923daaf8af2c701a65ec39a015191313de79676e36622cb8db00afb'
READER_SHA = '28317ee56a489e0bb38de981fe0d0c4260384be570349795741fdb9a98d6ae57'
STOCK_SHA = '96006a51917750743d7adc68461f1289e82adc004a75bd2bbd5da40ecc44c4e4'
MAX_SOURCE = 64 * 1048576


def read_regular(path, limit=MAX_SOURCE):
    path = Path(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError('direct regular input required: ' + path.name)
        with os.fdopen(fd, 'rb', closefd=False) as fp:
            data = fp.read(limit + 1)
    finally:
        os.close(fd)
    if len(data) > limit:
        raise ValueError('bounded input exceeded: ' + path.name)
    return data


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def save(path, obj):
    path = Path(path)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                 os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', closefd=False) as fp:
            json.dump(obj, fp, sort_keys=True, allow_nan=False)
            fp.write('\n')
            fp.flush()
            os.fsync(fp.fileno())
    finally:
        os.close(fd)
    dfd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        os.fsync(dfd)
    finally:
        os.close(dfd)


def same_private_root():
    st = ROOT.lstat()
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != 0 or stat.S_IMODE(st.st_mode) != 0o700:
        raise ValueError('existing root-owned private entry root required')
    if RUN.exists() or RUN.is_symlink():
        raise ValueError('one-shot run directory already exists')
    os.mkdir(RUN, 0o700)
    dfd = os.open(ROOT, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        os.fsync(dfd)
    finally:
        os.close(dfd)


def verify_stage(expected_self_sha):
    if os.geteuid() != 0 or sys.platform != 'linux' or sys.flags.optimize != 0:
        raise ValueError('nonoptimized Linux root required')
    own = read_regular(__file__, 2 * 1048576)
    if sha_bytes(own) != expected_self_sha:
        raise ValueError('candidate wrapper SHA differs from reviewed invocation pin')
    expected = {ENTRY_SOURCE: ENTRY_SHA, PREPARE_SOURCE: PREPARE_SHA,
                BACKUP_SOURCE: BACKUP_SHA, READER_SOURCE: READER_SHA,
                ROOT / 'pins.json': PINS_SHA}
    for path, pin in expected.items():
        if sha_bytes(read_regular(path)) != pin:
            raise ValueError('reviewed source differs: ' + path.name)
    pins = json.loads(read_regular(ROOT / 'pins.json', 65536))
    if not isinstance(pins, dict) or not pins:
        raise ValueError('invalid staged source pin map')
    for relative, pin in pins.items():
        path = ROOT / relative
        if path.is_symlink() or sha_bytes(read_regular(path)) != pin:
            raise ValueError('staged source pin mismatch: ' + relative)
    if RUN.exists() or os.path.lexists(ROOT / 'backup-campaign.json') or os.path.lexists(ROOT / 'backup-prepared.json'):
        raise ValueError('prior campaign output prevents one-shot preparation')
    if os.path.lexists(ROOT / 'stock-backup-001'):
        raise ValueError('initial stock backup receipt already exists')
    normal = json.loads(read_regular(ROOT / 'inputs/normal-binding.json', 65536))
    if (normal.get('kind') != 'fm1-passive-normal-binding' or normal.get('schema') != 1 or
            normal.get('speed') != '12' or not isinstance(normal.get('midi_path'), str)):
        raise ValueError('fresh passive normal USB/MIDI binding required')
    if not 0 <= time.time() - normal.get('observed_at', 0) <= 120:
        raise ValueError('passive normal binding receipt must be no older than 120 seconds')
    entry_run = ROOT / 'entry-once'
    if any(os.path.lexists(entry_run / name) for name in (
            'entry-attempt.json', 'capture-pid.json', 'capture-open.json', 'entry.jsonl',
            'entry-exit.json', 'usbmon1.txt', 'usbmon1.stderr')):
        raise ValueError('entry one-shot already attempted')


def proc_status(pid):
    raw = read_regular(Path('/proc') / str(pid) / 'status', 65536).decode('ascii', 'strict')
    values = {}
    for line in raw.splitlines():
        if ':' in line:
            k, v = line.split(':', 1)
            values[k] = v.strip()
    return values


def process_group_members(pgid):
    members = []
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit():
            continue
        try:
            if os.getpgid(int(entry.name)) == pgid:
                members.append(int(entry.name))
        except (ProcessLookupError, PermissionError, FileNotFoundError):
            continue
    return sorted(members)


def capture_identity(capture, stdout_path, stderr_path):
    if capture.poll() is not None:
        raise RuntimeError('owned capture leader exited before stop')
    pid = capture.pid
    if os.getpgid(pid) != pid or int(proc_status(pid)['PPid']) != os.getpid():
        raise RuntimeError('capture parent/process-group identity differs')
    leader = read_regular(Path('/proc') / str(pid) / 'cmdline', 65536).split(b'\0')
    if leader[:4] != [b'/usr/bin/timeout', b'1800s', b'/usr/bin/cat', USBMON.encode()]:
        raise RuntimeError('capture timeout argv differs')
    children = read_regular(Path('/proc') / str(pid) / 'task' / str(pid) / 'children', 65536).split()
    if len(children) != 1:
        raise RuntimeError('capture must own exactly one reader')
    reader = int(children[0])
    rstatus = proc_status(reader)
    rcmd = read_regular(Path('/proc') / str(reader) / 'cmdline', 65536).split(b'\0')
    if (int(rstatus['PPid']) != pid or os.getpgid(reader) != pid or
            rcmd[:2] != [b'/usr/bin/cat', USBMON.encode()]):
        raise RuntimeError('usbmon reader identity differs')
    fds = Path('/proc') / str(reader) / 'fd'
    links = {}
    for fd in fds.iterdir():
        try:
            links[fd.name] = os.readlink(fd)
        except FileNotFoundError:
            continue
    if USBMON not in links.values():
        raise RuntimeError('reader has not opened the exact usbmon endpoint')
    leader_fds = Path('/proc') / str(pid) / 'fd'
    leader_links = {}
    for fd in leader_fds.iterdir():
        try:
            leader_links[fd.name] = os.readlink(fd)
        except FileNotFoundError:
            continue
    if leader_links.get('1') != str(stdout_path) or leader_links.get('2') != str(stderr_path):
        raise RuntimeError('capture output descriptors differ')
    members = process_group_members(pid)
    if members != sorted((pid, reader)):
        raise RuntimeError('capture group contains an unexpected process')
    return {'timeout_pid': pid, 'timeout_ppid': os.getpid(), 'reader_pid': reader,
            'process_group': pid, 'endpoint': USBMON, 'open_capture_fd': True,
            'group_members': members}


def stop_capture(capture, stdout_path, stderr_path, expected_opened=None):
    ident = capture_identity(capture, stdout_path, stderr_path)
    if expected_opened is not None and any(
            ident[key] != expected_opened[key]
            for key in ('timeout_pid', 'timeout_ppid', 'reader_pid', 'process_group')):
        raise RuntimeError('capture identity changed since owned-open receipt')
    os.killpg(ident['process_group'], signal.SIGTERM)
    returncode = capture.wait(timeout=8)
    if returncode != -signal.SIGTERM:
        raise RuntimeError('capture did not exit from owned SIGTERM')
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if (not process_group_members(ident['process_group'])
                and not (Path('/proc') / str(ident['timeout_pid'])).exists()
                and not (Path('/proc') / str(ident['reader_pid'])).exists()):
            break
        time.sleep(0.05)
    if (process_group_members(ident['process_group'])
            or (Path('/proc') / str(ident['timeout_pid'])).exists()
            or (Path('/proc') / str(ident['reader_pid'])).exists()):
        raise RuntimeError('capture leader, reader, or group remains after owned stop')
    for path in (stdout_path, stderr_path):
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise RuntimeError('capture transcript is not a direct regular file')
            os.fsync(fd)
        finally:
            os.close(fd)
    return {'schema': 1, 'time': time.time(), 'process_group': ident['process_group'],
            'timeout_pid': ident['timeout_pid'], 'reader_pid': ident['reader_pid'],
            'signal': 'SIGTERM', 'returncode': returncode, 'owned_processes_only': True,
            'leader_and_reader_absent': True, 'retry': False}



def wait_for_entry_rom_sg(entry_log, timeout=20.0):
    """Passive sysfs wait for the exact ROM topology recorded by this entry."""
    bridge_raw = read_regular(BACKUP_SOURCE)
    module = type(sys)('_fresh_entry_backup_policy')
    module.__file__ = str(BACKUP_SOURCE)
    sys.modules[module.__name__] = module
    exec(compile(bridge_raw, module.__file__, 'exec'), module.__dict__)
    events = [json.loads(line) for line in entry_log.decode('utf8').splitlines()]
    entered = [event for event in events if event.get('event') == 'uboot_enumerated']
    if len(entered) != 1:
        raise ValueError('one actual entry ROM event required before SG wait')
    rom = [{key: item.get(key) for key in ('path', 'busnum', 'devnum', 'vid', 'pid')}
           for item in entered[0].get('usb', [])
           if (item.get('vid'), item.get('pid')) == ('4c4a', '8057')]
    if len(rom) != 1:
        raise ValueError('entry log must identify exactly one ROM USB topology')
    usb = rom[0]
    module.validate_usb(usb)
    root = Path('/sys/bus/usb/devices') / usb['path']
    deadline = time.monotonic() + timeout
    while True:
        current = module.usb_snapshot(root)
        if current != usb:
            raise ValueError('live ROM USB topology drifted during SG readiness wait')
        resolved = root.resolve(strict=True)
        matches = []
        for item in Path('/sys/class/scsi_generic').glob('sg*'):
            device = (item / 'device').resolve(strict=True)
            if resolved in (device, *device.parents):
                matches.append(item)
        if len(matches) > 1:
            raise ValueError('multiple SG nodes on pinned ROM topology')
        if len(matches) == 1:
            mapping = module.discover_sg(usb)
            return {'usb_binding': usb, 'sg_binding': mapping,
                    'wait_seconds_max': timeout, 'passive_sysfs_only': True}
        if time.monotonic() >= deadline:
            raise TimeoutError('ROM SG node did not appear within 20 seconds')
        time.sleep(0.25)

def execute(expected_self_sha):
    os.umask(0o077)
    verify_stage(expected_self_sha)
    same_private_root()
    entry_log = ROOT / 'entry-once/entry.jsonl'
    cap_out = ROOT / 'entry-once/usbmon1.txt'
    cap_err = ROOT / 'entry-once/usbmon1.stderr'
    save(RUN / 'wrapper-attempt.json', {'schema': 1,
         'kind': 'fm1-entry-plus-fixed-loader-backup-one-shot-v3.2', 'time': time.time(),
         'entry_source_sha256': ENTRY_SHA, 'prepare_source_sha256': PREPARE_SHA,
         'backup_source_sha256': BACKUP_SHA, 'reader_source_sha256': READER_SHA,
         'source_pins_sha256': PINS_SHA, 'stock_baseline_sha256': STOCK_SHA,
         'invoked_self_sha256': expected_self_sha,
         'retry': False})
    capture = None
    opened = None
    child_exit = None
    child_started = None
    child_finished = None
    backup_exit = None
    error = None
    try:
        # Execute the frozen original entry source byte-for-byte in this process.
        # Its Popen object remains in this namespace, making this process the
        # real parent able to wait for the owned timeout after the backup.
        entry_raw = read_regular(ENTRY_SOURCE, 2 * 1048576)
        if sha_bytes(entry_raw) != ENTRY_SHA:
            raise ValueError('entry source changed after preflight')
        entry_ns = {'__name__': '__main__', '__file__': str(ENTRY_SOURCE),
                    '__package__': None, '__cached__': None}
        try:
            try:
                exec(compile(entry_raw, str(ENTRY_SOURCE), 'exec'), entry_ns, entry_ns)
                raise RuntimeError('entry script unexpectedly returned')
            except SystemExit as exc:
                if type(exc.code) is int:
                    child_exit = exc.code
                elif exc.code is None:
                    child_exit = 0
                else:
                    raise RuntimeError('entry returned a noninteger exit status')
        finally:
            # Adopt the original Popen handle even if entry execution raises;
            # the outer finally can then conservatively stop/wait this exact child.
            capture = entry_ns.get('proc')
        if not isinstance(capture, subprocess.Popen):
            raise RuntimeError('frozen entry did not leave its owned capture handle')
        # The source writes entry-exit.json before raising SystemExit.
        entry_receipt = json.loads(read_regular(ROOT / 'entry-once/entry-exit.json', 65536))
        if child_exit != 0 or entry_receipt.get('exit_code') != 0 or entry_receipt.get('capture_running') is not True:
            raise RuntimeError('fresh entry did not complete successfully; backup not started')
        pid_receipt = json.loads(read_regular(ROOT / 'entry-once/capture-pid.json', 65536))
        open_receipt = json.loads(read_regular(ROOT / 'entry-once/capture-open.json', 65536))
        opened = capture_identity(capture, cap_out, cap_err)
        if (pid_receipt.get('pid') != opened['timeout_pid'] or
                pid_receipt.get('argv') != ['/usr/bin/timeout', '1800s', '/usr/bin/cat', USBMON] or
                type(pid_receipt.get('stop_deadline')) not in (int, float) or
                open_receipt.get('process_group') != opened['process_group'] or
                open_receipt.get('reader_pid') != opened['reader_pid'] or
                open_receipt.get('endpoint') != USBMON):
            raise RuntimeError('entry capture receipts do not bind the live owned capture')
        stop_deadline = pid_receipt['stop_deadline']
        if stop_deadline - time.time() < 1600:
            raise RuntimeError('capture deadline leaves insufficient time for preparation, backup, stop, and records')
        opened['stop_deadline'] = stop_deadline
        save(RUN / 'capture-open.json', {'schema': 1, 'time': time.time(), **opened,
             'entry_receipt_sha256': sha_bytes(read_regular(ROOT / 'entry-once/entry-exit.json', 65536)),
             'lifecycle_parent_retained': True})
        save(RUN / 'entry-status.json', {'schema': 1, 'entry_exit_status': child_exit,
             'entry_receipt_sha256': sha_bytes(read_regular(ROOT / 'entry-once/entry-exit.json', 65536)),
             'time': time.time(), 'retry': False})
        # Wait passively for SG on the unique ROM topology emitted by this actual entry.
        # This never sends USB/MIDI commands and never retries entry.
        ready = wait_for_entry_rom_sg(read_regular(entry_log), 20.0)
        save(RUN / 'rom-sg-ready.json', {'schema': 1, 'time': time.time(), **ready})
        # The frozen preparer is file/sysfs-only and revalidates the same mapping.
        child_started = time.time()
        with open(RUN / 'backup-preparation.stdout', 'xb', buffering=0) as log:
            try:
                prep = subprocess.run(['/usr/bin/python3', '-B', '-E', '-s', '-S', str(PREPARE_SOURCE)],
                    cwd=ROOT, env={'PATH': '/usr/bin:/bin', 'LC_ALL': 'C.UTF-8'},
                    stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                    timeout=60, check=False)
            finally:
                log.flush(); os.fsync(log.fileno())
        if prep.returncode != 0:
            raise RuntimeError('file/sysfs backup preparation failed')
        capture_identity(capture, cap_out, cap_err)
        if stop_deadline - time.time() < 1530:
            raise RuntimeError('capture deadline no longer leaves backup and owned-stop reserve')
        child_started = time.time()
        with open(RUN / 'backup-execution.stdout', 'xb', buffering=0) as log:
            try:
                backup = subprocess.run(['/usr/bin/python3', '-B', '-E', '-s', '-S', str(BACKUP_SOURCE),
                     '--campaign', str(ROOT / 'backup-campaign.json')],
                    cwd=ROOT, env={'PATH': '/usr/bin:/bin', 'LC_ALL': 'C.UTF-8'},
                    stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                    timeout=1500, check=False)
                child_finished = time.time()
            finally:
                log.flush(); os.fsync(log.fileno())
        backup_exit = backup.returncode
        capture_identity(capture, cap_out, cap_err)
        if backup_exit != 0:
            raise RuntimeError('canonical fixed-loader backup exited nonzero')
        manifest_path = ROOT / 'stock-backup-001/manifest.json'
        manifest = json.loads(read_regular(manifest_path, 65536))
        if (manifest.get('kind') != 'fm1-fixed-loader-backup' or
                manifest.get('identical') is not True or
                manifest.get('physical_recovery_verified') is not False or
                manifest.get('command_completions') is not True or
                manifest.get('flash_bytes') != 1048576 or
                [d.get('file') for d in manifest.get('dumps', [])] != ['dumpA.bin', 'dumpB.bin'] or
                len(manifest.get('dumps', [])) != 2):
            raise RuntimeError('canonical backup success manifest differs')
        for item in manifest['dumps']:
            data = read_regular(ROOT / 'stock-backup-001' / item['file'], 1048576)
            if (len(data) != 1048576 or sha_bytes(data) != item.get('sha256') or
                    item.get('complete') is not True or item.get('sha256') != STOCK_SHA):
                raise RuntimeError('durable full-flash backup differs from pinned stock baseline')
        if manifest['dumps'][0]['sha256'] != manifest['dumps'][1]['sha256']:
            raise RuntimeError('durable full-flash backups differ')
        stop = stop_capture(capture, cap_out, cap_err, opened)
        save(RUN / 'execution-exit.json', {'schema': 1, 'time': time.time(),
             'entry_exit_status': child_exit, 'preparation_exit_status': prep.returncode,
             'backup_exit_status': backup_exit, 'backup_started_at': child_started,
             'backup_finished_at': child_finished, 'capture_alive_after_backup': True,
             'capture_returncode': stop['returncode'], 'retry': False})
        save(RUN / 'capture-stop.json', stop)
        save(RUN / 'result.json', {'schema': 1, 'kind': 'fm1-entry-plus-fixed-loader-backup-v3.2',
             'entry_receipt': str(ROOT / 'entry-once/entry-exit.json'),
             'campaign': str(ROOT / 'backup-campaign.json'),
             'backup_receipt': str(ROOT / 'stock-backup-001'),
             'capture_stopped_and_waited': True, 'retry': False})
        return 0
    except BaseException as exc:
        error = exc
        raise
    finally:
        if capture is not None:
            if capture.poll() is None:
                try:
                    stop = stop_capture(capture, cap_out, cap_err, opened)
                    if not (RUN / 'capture-stop.json').exists():
                        save(RUN / 'capture-stop.json', stop)
                except BaseException as stop_exc:
                    if not (RUN / 'capture-cleanup-ambiguous.json').exists():
                        save(RUN / 'capture-cleanup-ambiguous.json', {'schema': 1,
                             'time': time.time(), 'error': type(stop_exc).__name__,
                             'detail': str(stop_exc), 'retry': False})
            elif not (RUN / 'capture-stop.json').exists():
                save(RUN / 'capture-cleanup-ambiguous.json', {'schema': 1,
                     'time': time.time(), 'error': 'capture-not-running-before-owned-stop',
                     'returncode': capture.returncode, 'retry': False})
        if error is not None and not (RUN / 'wrapper-stopped-ambiguous.json').exists():
            save(RUN / 'wrapper-stopped-ambiguous.json', {'schema': 1,
                 'time': time.time(), 'error': type(error).__name__,
                 'detail': str(error), 'entry_exit_status': child_exit,
                 'backup_exit_status': backup_exit, 'retry': False})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reviewed-self-sha256', required=True)
    args = parser.parse_args()
    return execute(args.reviewed_self_sha256)


if __name__ == '__main__':
    sys.exit(main())
