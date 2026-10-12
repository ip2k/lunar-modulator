#!/usr/bin/python3
"""One-use captured runner for the exact accepted trace install or boot factory.

The staged packet must be reviewed and pinned before invocation. This program
does not discover devices or construct campaigns; it only validates the frozen
campaign through its canonical factory, captures bus 1 usbmon, and runs that
factory's single documented CLI once.
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
MODES = {
    'install': ('fm1_sdk_trace_install', 'fm1_sdk_trace_install.py', 900, 850),
    'boot': ('fm1_sdk_trace_boot', 'fm1_sdk_trace_boot.py', 120, 45),
}

def sha(path):
    return hashlib.sha256(read_regular(path, 32 * 1048576)).hexdigest()

def read_regular(path, limit):
    p = Path(path)
    if not p.is_absolute(): raise ValueError(f'absolute file required: {p.name}')
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode): raise ValueError(f'not a regular file: {p.name}')
        with os.fdopen(fd, 'rb', closefd=False) as f: data = f.read(limit + 1)
    finally: os.close(fd)
    if len(data) > limit: raise ValueError(f'file exceeds bound: {p.name}')
    return data

def save(path, obj):
    p = Path(path)
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        json.dump(obj, f, sort_keys=True); f.write('\n'); f.flush(); os.fsync(f.fileno())
    dfd = os.open(p.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try: os.fsync(dfd)
    finally: os.close(dfd)

def capture_identity(proc, seconds):
    if proc.poll() is not None: raise RuntimeError('capture process exited')
    pid = proc.pid
    if os.getpgid(pid) != pid: raise RuntimeError('capture is not its own process group')
    cmd = (Path('/proc') / str(pid) / 'cmdline').read_bytes().split(b'\0')
    if cmd[:4] != [b'/usr/bin/timeout', str(seconds).encode(), b'/bin/cat', USBMON.encode()]:
        raise RuntimeError('capture command identity differs')
    children = (Path('/proc') / str(pid) / 'task' / str(pid) / 'children').read_text().split()
    if len(children) != 1: raise RuntimeError('capture child count differs')
    child = int(children[0])
    if os.getpgid(child) != pid: raise RuntimeError('capture child escaped owned group')
    ccmd = (Path('/proc') / str(child) / 'cmdline').read_bytes().split(b'\0')
    if ccmd[:2] != [b'/bin/cat', USBMON.encode()]: raise RuntimeError('capture reader differs')
    links = []
    for fd in (Path('/proc') / str(child) / 'fd').iterdir():
        try: links.append(os.readlink(fd))
        except FileNotFoundError: pass
    if USBMON not in links: raise RuntimeError('capture reader has not opened usbmon1u')
    return {'timeout_pid': pid, 'cat_pid': child, 'process_group': pid, 'open_capture_fd': True}


def process_group_members(pgid):
    members = []
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit(): continue
        try:
            if os.getpgid(int(entry.name)) == pgid: members.append(int(entry.name))
        except (ProcessLookupError, FileNotFoundError):
            continue
    return sorted(members)

def same_capture(observed, current):
    if observed is not None and any(current[k] != observed[k]
            for k in ('timeout_pid', 'cat_pid', 'process_group')):
        raise RuntimeError('capture identity changed since owned open')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('mode', choices=tuple(MODES))
    ap.add_argument('--stage', required=True, type=Path)
    ap.add_argument('--run', required=True, type=Path)
    ap.add_argument('--packet', required=True, type=Path)
    ap.add_argument('--packet-sha256', required=True)
    a = ap.parse_args()
    if os.geteuid() != 0 or sys.platform != 'linux' or sys.flags.optimize != 0:
        raise SystemExit('requires non-optimized Linux root')
    os.umask(0o077)
    stage, run, packet = a.stage.absolute(), a.run.absolute(), a.packet.absolute()
    if (not stat.S_ISDIR(stage.lstat().st_mode) or stat.S_IMODE(stage.stat().st_mode) != 0o700
            or not stat.S_ISDIR(run.lstat().st_mode) or stat.S_IMODE(run.stat().st_mode) != 0o700):
        raise ValueError('private stage and run directories required')
    if sha(packet) != a.packet_sha256: raise ValueError('packet hash mismatch')
    cfg = json.loads(read_regular(packet, 65536))
    expected_keys = {'schema', 'kind', 'campaign_path', 'campaign_sha256', 'adapter_path',
                     'adapter_sha256', 'source_pins', 'usb_binding'}
    module_name, script_name, cap_seconds, timeout = MODES[a.mode]
    if (set(cfg) != expected_keys or cfg['schema'] != 1
            or cfg['kind'] != f'fm1-sdk-trace-{a.mode}-one-shot'
            or Path(cfg['campaign_path']).resolve() != (stage / (Path(cfg['campaign_path']).name)).resolve()
            or Path(cfg['adapter_path']).resolve() != (stage / 'tools' / (module_name + '.py')).resolve()
            or cfg['campaign_sha256'] != sha(cfg['campaign_path'])
            or cfg['adapter_sha256'] != sha(cfg['adapter_path'])):
        raise ValueError('exact frozen one-shot packet required')
    for rel, expected in cfg['source_pins'].items():
        if Path(rel).is_absolute() or sha(stage / rel) != expected: raise ValueError(f'source pin mismatch: {rel}')
    if str(stage / 'tools') not in sys.path: sys.path.insert(0, str(stage / 'tools'))
    factory = importlib.import_module(module_name)
    if (Path(factory.__file__).resolve() != Path(cfg['adapter_path']).resolve()
            or sha(factory.__file__) != cfg['adapter_sha256']):
        raise ValueError('canonical pinned factory identity required')
    prepared = factory.prepare_campaign(cfg['campaign_path'])
    if prepared.campaign_sha256 != cfg['campaign_sha256']:
        raise ValueError('factory prepared different campaign')
    if a.mode == 'install':
        # Install uses a policy config plus a separately frozen SG mapping.
        # Tie the current USB identity to the exact reviewed manifest input.
        campaign_config = json.loads(prepared.config)
        manifest_path = campaign_config['policy_inputs']['manifest_path']
        manifest = json.loads(read_regular(manifest_path, 65536))
        usb_binding = manifest['usb_binding']
    else:
        usb_binding = json.loads(prepared.campaign).get('usb_binding')
    if usb_binding != cfg['usb_binding']:
        raise ValueError('campaign USB binding differs from frozen packet')
    # Marker precedes capture setup: a setup failure consumes this packet.
    save(run / 'wrapper-attempt.json', {'schema': 1, 'kind': cfg['kind'], 'time': time.time(),
         'campaign_sha256': cfg['campaign_sha256'], 'adapter_sha256': cfg['adapter_sha256'], 'retry': False})
    capture = None
    observed = None
    try:
        with open(run / 'usbmon1.txt', 'xb', buffering=0) as out, open(run / 'usbmon1.stderr', 'xb', buffering=0) as err:
            capture = subprocess.Popen(['/usr/bin/timeout', str(cap_seconds), '/bin/cat', USBMON],
                stdout=out, stderr=err, start_new_session=True, close_fds=True)
            observed = None
            for _ in range(100):
                try: observed = capture_identity(capture, cap_seconds); break
                except (FileNotFoundError, RuntimeError): time.sleep(.02)
            if observed is None: raise RuntimeError('owned usbmon1u open was not confirmed')
            opened = {'time': time.time(), **observed}
            if a.mode != 'boot': opened['schema'] = 1
            save(run / 'capture-open.json', opened)
            with open(run / 'execution.stdout', 'xb', buffering=0) as log:
                child_started_at = time.time()
                try:
                    result = subprocess.run(['/usr/bin/python3', '-B', '-E', '-s', '-S',
                        str(stage / 'tools' / script_name), '--campaign', str(cfg['campaign_path'])],
                        cwd=stage, env={'PATH': '/usr/bin:/bin', 'LC_ALL': 'C.UTF-8'},
                        stdout=log, stderr=subprocess.STDOUT, timeout=timeout, check=False)
                    child_finished_at = time.time()
                finally:
                    log.flush(); os.fsync(log.fileno())
            same_capture(observed, capture_identity(capture, cap_seconds))
            out.flush(); os.fsync(out.fileno())
            exited = {'schema': 1, 'time': time.time(),
                 'child_started_at': child_started_at, 'child_finished_at': child_finished_at,
                 'exit_status': result.returncode, 'campaign_sha256': cfg['campaign_sha256'],
                 'adapter_sha256': cfg['adapter_sha256'], 'capture_alive_after_child': True, 'retry': False}
            if a.mode == 'boot':
                exited = {k: exited[k] for k in ('time', 'campaign_sha256', 'exit_status',
                          'capture_alive_after_child', 'retry')}
                exited.update(reset_completed_attested=False, boot_cause_proven=False)
            save(run / 'execution-exit.json', exited)
        if a.mode == 'boot': observe_rom(factory, prepared, run, capture, cap_seconds, cfg['campaign_sha256'])
        return result.returncode
    except BaseException as exc:
        save(run / 'wrapper-stopped-ambiguous.json', {'schema': 1, 'time': time.time(),
             'error': type(exc).__name__, 'detail': str(exc), 'retry': False})
        raise
    finally:
        if capture is not None:
            try:
                if capture.poll() is not None:
                    raise RuntimeError('capture exited before owned stop')
                ident = capture_identity(capture, cap_seconds)
                same_capture(observed, ident)
                if process_group_members(ident['process_group']) != sorted((ident['timeout_pid'], ident['cat_pid'])):
                    raise RuntimeError('capture group contains unexpected processes')
                os.killpg(ident['process_group'], signal.SIGTERM)
                rc = capture.wait(timeout=5)
                if rc != -signal.SIGTERM:
                    raise RuntimeError('capture did not exit from owned SIGTERM')
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    if (not process_group_members(ident['process_group'])
                            and not (Path('/proc') / str(ident['timeout_pid'])).exists()
                            and not (Path('/proc') / str(ident['cat_pid'])).exists()):
                        break
                    time.sleep(.05)
                if (process_group_members(ident['process_group'])
                        or (Path('/proc') / str(ident['timeout_pid'])).exists()
                        or (Path('/proc') / str(ident['cat_pid'])).exists()):
                    raise RuntimeError('capture leader, reader, or group remains after owned stop')
                for p in (run / 'usbmon1.txt', run / 'usbmon1.stderr'):
                    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW)
                    try: os.fsync(fd)
                    finally: os.close(fd)
                stopped = {'time': time.time(), 'process_group': ident['process_group'],
                           'returncode': rc, 'owned_processes_only': True}
                if a.mode != 'boot': stopped['schema'] = 1
                save(run / 'capture-stop.json', stopped)
            except BaseException as exc:
                save(run / 'wrapper-cleanup-ambiguous.json', {'schema': 1, 'time': time.time(),
                     'error': type(exc).__name__, 'detail': str(exc), 'retry': False})
                raise

def observe_rom(factory, prepared, run, capture, cap_seconds, campaign_sha):
    old = json.loads(prepared.campaign)['usb_binding']
    observations, previous, found = [], None, False
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        capture_identity(capture, cap_seconds)
        try:
            usb = prepared.bridge.usb_snapshot(Path('/sys/bus/usb/devices') / old['path'])
            if usb != previous:
                observations.append({'time': time.time(), 'usb_binding': usb}); previous = usb
            prepared.bridge.validate_usb(usb)
            if (any(usb[k] != old[k] for k in ('path', 'busnum', 'vid', 'pid'))
                    or usb['devnum'] == old['devnum'] or usb['vid'] != '4c4a' or usb['pid'] != '8057'):
                time.sleep(.1); continue
            mapping = prepared.bridge.discover_sg(usb)
            save(run / 'rom-snapshot.json', {'schema': 1, 'kind': 'fm1-passive-post-trace-boot-rom',
                 'observed_at': time.time(), 'usb_binding': usb, 'sg_binding': mapping,
                 'target_boot_campaign_sha256': campaign_sha,
                 'quiet_state': 'initial-rom-no-later-commands-no-loader-upload'})
            found = True; break
        except (FileNotFoundError, ValueError): time.sleep(.1)
    save(run / 'rom-observations.json', {'schema': 1, 'time': time.time(), 'found': found,
         'observations': observations, 'passive_sysfs_only': True, 'no_later_device_commands': True})
    if not found: raise RuntimeError('same-port changed ROM/full SG mapping not observed')

if __name__ == '__main__': sys.exit(main())
