#!/usr/bin/python3
"""MIT. CLOSED owned capture around one exact trace reader; root activates.

Distinct file-only preparation-stop authority; no reset/upload/NOR/soft key/retry. A later reviewed bound derivative
must pin every source and actual private packet before any runtime activity.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
import time
import types

STAGE = None
RUN = None
PACKET_SHA = None
PACKET_MEMBERS = None
NATIVE_SHA = None
READER_SHA = None
PROOF_SHA = None
CHILD_SHA = None
CAMPAIGN_SHA = None
STOP_SHA = None
ARTIFACTS = ('wrapper-attempt.json', 'capture-open.json', 'capture-stop.json',
    'execution.stdout', 'execution-exit.json', 'usbmon.txt', 'usbmon.stderr',
    'wrapper-stopped-ambiguous.json', 'wrapper-cleanup-ambiguous.json', 'owned-capture.json')
OWNED_FILES = ('execute-once.py', 'execute-child.py', 'preflight.json',
    'wrapper-attempt.json', 'capture-open.json', 'capture-stop.json',
    'execution.stdout', 'execution-exit.json', 'usbmon.txt', 'usbmon.stderr')


def require_frozen():
    pins = (PACKET_SHA, NATIVE_SHA, READER_SHA, PROOF_SHA, CHILD_SHA, CAMPAIGN_SHA, STOP_SHA)
    if (any(type(p) is not str or re.fullmatch('[0-9a-f]{64}', p) is None for p in pins)
            or type(PACKET_MEMBERS) is not int or PACKET_MEMBERS < 8
            or not isinstance(STAGE, Path) or not isinstance(RUN, Path)
            or not STAGE.is_absolute() or not RUN.is_absolute() or RUN.parent != STAGE):
        raise ValueError('Closed template: exact stop/reader/native/capture packet unaccepted')


def read(path, limit=2 * 1048576):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    try:
        fp = os.fdopen(fd, 'rb')
    except BaseException:
        os.close(fd); raise
    with fp:
        if not stat.S_ISREG(os.fstat(fp.fileno()).st_mode):
            raise ValueError('Direct regular evidence required')
        raw = fp.read(limit + 1)
    if len(raw) > limit:
        raise ValueError('Evidence exceeds bound')
    return raw


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def sync(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def save(path, value):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    try:
        fp = os.fdopen(fd, 'w')
    except BaseException:
        os.close(fd); raise
    with fp:
        json.dump(value, fp, sort_keys=True, allow_nan=False)
        fp.write('\n'); fp.flush(); os.fsync(fp.fileno())
    sync(path.parent)


def load(path, expected, name):
    raw = read(path)
    if digest(raw) != expected:
        raise ValueError('Reviewed source differs')
    module = types.ModuleType(name); module.__file__ = str(path)
    sys.modules[name] = module
    exec(compile(raw, str(path), 'exec'), module.__dict__)
    if read(path) != raw:
        raise ValueError('Source drift during import')
    return module


def packet_check():
    raw = read(RUN / 'packet-pins.json', 65536)
    if digest(raw) != PACKET_SHA:
        raise ValueError('Actual packet inventory differs')
    pins = json.loads(raw)
    if type(pins) is not dict or len(pins) != PACKET_MEMBERS:
        raise ValueError('Exact packet inventory required')
    required = {str((RUN / name).relative_to(STAGE)) for name in
                ('execute-child.py', 'campaign.json', 'preparation-stop.json', 'preflight.json')}
    required.update('tools/' + name for name in
                    ('fm1_sdk_prepare_stop_trace_read.py', 'fm1_sdk_trace_read.py', 'fm1_sdk_trace_prepare_stop.py'))
    if not required <= set(pins):
        raise ValueError('All exact wrapper and source members required')
    for name, pin in pins.items():
        path = Path(name)
        if (type(name) is not str or path.is_absolute() or '..' in path.parts
                or type(pin) is not str or not re.fullmatch('[0-9a-f]{64}', pin)
                or digest(read(STAGE / path, 32 * 1048576)) != pin):
            raise ValueError('Direct exact stage-relative packet member required')
    checks = ((RUN / 'campaign.json', CAMPAIGN_SHA), (RUN / 'preparation-stop.json', STOP_SHA),
        (RUN / 'execute-child.py', CHILD_SHA), (STAGE / 'tools/fm1_sdk_prepare_stop_trace_read.py', NATIVE_SHA),
        (STAGE / 'tools/fm1_sdk_trace_read.py', READER_SHA), (STAGE / 'tools/fm1_sdk_trace_prepare_stop.py', PROOF_SHA))
    if any(digest(read(path)) != pin for path, pin in checks):
        raise ValueError('Actual input/source pin differs')


def capture_alive(process, bus):
    if process.poll() is not None or os.getpgid(process.pid) != process.pid:
        raise RuntimeError('Owned capture exited or PGID differs')
    target = '/sys/kernel/debug/usb/usbmon/' + bus + 'u'
    proc = Path('/proc') / str(process.pid)
    if read(proc / 'cmdline', 65536).rstrip(b'\0').split(b'\0') != [b'/usr/bin/timeout', b'60', b'/bin/cat', target.encode()]:
        raise ValueError('Owned capture command differs')
    children = read(proc / 'task' / str(process.pid) / 'children', 65536).split()
    if len(children) != 1:
        raise ValueError('Exactly one owned cat required')
    child = int(children[0]); childproc = Path('/proc') / str(child)
    if (os.getpgid(child) != process.pid or
            read(childproc / 'cmdline', 65536).rstrip(b'\0').split(b'\0') != [b'/bin/cat', target.encode()]):
        raise ValueError('Owned cat differs')
    links = []
    for fd in (childproc / 'fd').iterdir():
        try:
            links.append(os.readlink(fd))
        except FileNotFoundError:
            pass
    if target not in links:
        raise ValueError('Owned capture FD not open')
    return dict(timeout_pid=process.pid, cat_pid=child, process_group=process.pid, open_capture_fd=True)


def publish_capture():
    if (os.path.lexists(RUN / 'wrapper-cleanup-ambiguous.json') or
            os.path.lexists(RUN / 'wrapper-stopped-ambiguous.json') or read(RUN / 'usbmon.stderr', 65536)):
        raise ValueError('Owned capture lifecycle ambiguous')
    save(RUN / 'owned-capture.json', dict(schema=1, kind='fm1-owned-preparation-stop-trace-read-capture',
        native_campaign_path=str(RUN / 'campaign.json'), native_campaign_sha256=CAMPAIGN_SHA,
        preparation_stop_path=str(RUN / 'preparation-stop.json'), preparation_stop_sha256=STOP_SHA,
        wrapper_files_sha256={name: digest(read(RUN / name, 16 * 1048576 if name == 'usbmon.txt' else 2 * 1048576))
                              for name in OWNED_FILES}))


def main():
    require_frozen()  # First, before any file, process or device operation.
    if sys.platform != 'linux' or os.geteuid() != 0 or sys.flags.optimize != 0:
        raise ValueError('Reviewed nonoptimized Linux root interpreter required')
    os.umask(0o077)
    for path in (STAGE, RUN):
        if not stat.S_ISDIR(path.lstat().st_mode) or stat.S_IMODE(path.stat().st_mode) != 0o700:
            raise ValueError('Direct private stage/run required')
    if any(os.path.lexists(RUN / name) for name in ARTIFACTS):
        raise ValueError('Wrapper already attempted; no retry')
    packet_check()
    sys.path.insert(0, str(STAGE / 'tools'))
    native = load(STAGE / 'tools/fm1_sdk_prepare_stop_trace_read.py', NATIVE_SHA,
                  'fm1_sdk_prepare_stop_trace_read')
    if native.READ_SOURCE_SHA != READER_SHA or native.PROOF_SOURCE_SHA != PROOF_SHA:
        raise ValueError('Exact distinct reader/proof activation required')
    prepared = native.prepare_campaign(RUN / 'campaign.json')
    if (prepared.stop_sha256 != STOP_SHA or
            json.loads(prepared.seal)['preparation_stop_path'] != str(RUN / 'preparation-stop.json')):
        raise ValueError('Captured stop envelope must match canonical reader evidence')
    snapshot = json.loads(prepared.read.snapshot)
    bus = snapshot['usb_binding']['busnum']
    if type(bus) is not str or not re.fullmatch('[1-9][0-9]{0,2}', bus):
        raise ValueError('Exact capture bus required')
    save(RUN / 'wrapper-attempt.json', dict(time=time.time(), campaign_sha256=CAMPAIGN_SHA,
        preparation_stop_sha256=STOP_SHA, native_sha256=NATIVE_SHA, reader_sha256=READER_SHA,
        proof_sha256=PROOF_SHA, usb_binding=snapshot['usb_binding'], retry=False, commands=5,
        upload_operations=0, reset_operations=0, flash_operations=0))
    capture = None; status = 1; child_finished = False; cleanup_good = False
    try:
        with open(RUN / 'usbmon.txt', 'xb', buffering=0) as output, open(RUN / 'usbmon.stderr', 'xb', buffering=0) as error:
            capture = subprocess.Popen(['/usr/bin/timeout', '60', '/bin/cat',
                '/sys/kernel/debug/usb/usbmon/' + bus + 'u'], stdout=output, stderr=error, start_new_session=True)
            opened = None
            for attempt in range(50):
                try:
                    opened = capture_alive(capture, bus); break
                except (ValueError, FileNotFoundError):
                    time.sleep(.02)
            if opened is None:
                raise RuntimeError('Owned capture did not open')
            save(RUN / 'capture-open.json', dict(time=time.time(), **opened))
            packet_check(); prepared.check(); capture_alive(capture, bus)
            with open(RUN / 'execution.stdout', 'xb', buffering=0) as log:
                child = subprocess.run(['/usr/bin/python3', '-B', '-E', '-s', '-S', str(RUN / 'execute-child.py')],
                    cwd=STAGE, env={'PATH': '/usr/bin:/bin', 'LC_ALL': 'C.UTF-8'},
                    stdout=log, stderr=subprocess.STDOUT, timeout=40)
                os.fsync(log.fileno())
            status = child.returncode; child_finished = True
            capture_alive(capture, bus); os.fsync(output.fileno())
            save(RUN / 'execution-exit.json', dict(time=time.time(), exit_status=status,
                campaign_sha256=CAMPAIGN_SHA, capture_alive_after_child=True, retry=False,
                read_completion_attested=False, recovery_proven=False, boot_cause_proven=False))
    except BaseException as exc:
        save(RUN / 'wrapper-stopped-ambiguous.json', dict(time=time.time(), error=type(exc).__name__, retry=False))
        raise
    finally:
        if capture is not None:
            try:
                capture_alive(capture, bus); os.killpg(capture.pid, signal.SIGTERM)
                capture.wait(timeout=5)
                if capture.returncode != -15:
                    raise ValueError('Owned capture terminal status differs')
                for name in ('usbmon.txt', 'usbmon.stderr'):
                    fd = os.open(RUN / name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
                    try:
                        os.fsync(fd)
                    finally:
                        os.close(fd)
                save(RUN / 'capture-stop.json', dict(time=time.time(), process_group=capture.pid,
                    returncode=capture.returncode, owned_processes_only=True))
                cleanup_good = True
            except BaseException as exc:
                save(RUN / 'wrapper-cleanup-ambiguous.json', dict(time=time.time(), error=type(exc).__name__, retry=False))
                raise
    if child_finished and cleanup_good:
        publish_capture()
    return status  # Nonzero child remains nonzero, even if capture cleanup succeeded.


if __name__ == '__main__':
    raise SystemExit(main())
