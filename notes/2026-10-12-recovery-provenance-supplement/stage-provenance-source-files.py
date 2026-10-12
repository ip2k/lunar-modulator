#!/usr/bin/env python3
"""Closed file-only addition of exact native provenance; no hardware or factory."""
import argparse, hashlib, io, json, os, stat, sys, tarfile, time
from pathlib import Path, PurePosixPath
LIMIT = 16 * 1048576
ROOTS = {'acquire': Path('/home/claude/fm1-sdk-trace-partial-acquire-20261012-v5'),
         'restore': Path('/home/claude/fm1-sdk-trace-partial-restore-20261012-v5')}
MAIN_STAGE = Path('/home/claude/fm1-sdk-trace-campaign-20261012-v5')
ARCHIVE_SHA = 'f0ffe4884eed0ed34b32106c05b519fc82abc9d7c8e07f0193f09009a0895349'
INVENTORY_SHA = '6fc8eeb4e0e18c29db0a972d6b3a4c4bc455f4a71c3199e115aa9ffbcb67d3fc'
def digest(raw):
    return hashlib.sha256(raw).hexdigest()

def directory_fd(path, *, private=False):
    """Traverse every directory component without following symbolic links."""
    path = Path(path)
    if not path.is_absolute() or '..' in path.parts:
        raise ValueError('direct absolute directory required')
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        for component in path.parts[1:]:
            child = os.open(component, os.O_RDONLY | os.O_DIRECTORY |
                            os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
            os.close(fd)
            fd = child
        s = os.fstat(fd)
        if private and (s.st_uid != 0 or stat.S_IMODE(s.st_mode) != 0o700):
            raise ValueError('root-owned private0700 directory required')
        return fd
    except BaseException:
        os.close(fd)
        raise

def read(path, limit=LIMIT, *, private=False):
    path = Path(path)
    pfd = directory_fd(path.parent, private=private)
    fd = None
    try:
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW |
                     os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=pfd)
        s = os.fstat(fd)
        if (not stat.S_ISREG(s.st_mode) or s.st_size > limit or
                private and (s.st_uid != 0 or stat.S_IMODE(s.st_mode) != 0o600)):
            raise ValueError('bounded direct regular private input required')
        with os.fdopen(fd, 'rb') as f:
            fd = None
            raw = f.read(limit + 1)
        if len(raw) > limit or len(raw) != s.st_size:
            raise ValueError('input size changed or exceeded limit')
        return raw
    finally:
        if fd is not None:
            os.close(fd)
        os.close(pfd)

def relative(name):
    p = PurePosixPath(name)
    if p.is_absolute() or not p.parts or any(x in ('', '.', '..') for x in p.parts) or str(p) != name:
        raise ValueError('canonical relative file path required')
    return p

def write_exclusive(path, raw):
    pfd = directory_fd(path.parent, private=True)
    fd = None
    try:
        fd = os.open(path.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                     os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=pfd)
        with os.fdopen(fd, 'wb') as f:
            fd = None
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
        os.fsync(pfd)
    finally:
        if fd is not None:
            os.close(fd)
        os.close(pfd)

def mkdir_exclusive(path):
    pfd = directory_fd(path.parent)
    try:
        os.mkdir(path.name, 0o700, dir_fd=pfd)
        fd = os.open(path.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW |
                     os.O_CLOEXEC, dir_fd=pfd)
        try:
            s = os.fstat(fd)
            if s.st_uid != 0 or stat.S_IMODE(s.st_mode) != 0o700:
                raise ValueError('new stage directory permissions differ')
            os.fsync(fd)
        finally:
            os.close(fd)
        os.fsync(pfd)
    finally:
        os.close(pfd)

def save(path, obj):
    write_exclusive(path, (json.dumps(obj, indent=2, sort_keys=True) + '\n').encode())


def main():
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument('--archive', required=True, type=Path)
    a.add_argument('--inventory', required=True, type=Path)
    a.add_argument('--expected-self-sha256', required=True)
    a.add_argument('--check-only', action='store_true')
    args = a.parse_args()
    if sys.platform != 'linux' or os.geteuid() != 0 or sys.flags.optimize:
        raise ValueError('nonoptimized Linux root required')
    os.umask(0o077)
    self_sha = digest(read(Path(__file__).absolute()))
    if self_sha != args.expected_self_sha256:
        raise ValueError('reviewed stager differs')
    archive, inv_raw = read(args.archive), read(args.inventory)
    if digest(archive) != ARCHIVE_SHA or digest(inv_raw) != INVENTORY_SHA:
        raise ValueError('sealed supplement differs')
    inv = json.loads(inv_raw)
    manifest = read(MAIN_STAGE/'assets/native/build-manifest.json', private=True)
    if digest(manifest) != inv['manifest_sha256']:
        raise ValueError('native manifest differs')
    required = {n.removeprefix('/source/'): pin for n, pin in
                json.loads(manifest)['source_sha256'].items() if n.startswith('/source/')}
    if len(required) != 11 or any(not n.startswith('firmware/') for n in required):
        raise ValueError('exact eleven firmware provenance inputs required')
    expected = {side+'/'+n for side in ROOTS for n in required}
    if set(inv['files']) != expected:
        raise ValueError('exact supplement set required')
    payload = {}
    with tarfile.open(fileobj=io.BytesIO(archive), mode='r:') as tf:
        members = tf.getmembers()
        if [m.name for m in members] != sorted(expected):
            raise ValueError('archive set/order differs')
        for m in members:
            relative(m.name)
            if not m.isfile() or m.pax_headers or m.mode != 0o600 or m.uid or m.gid or m.mtime:
                raise ValueError('direct normalized regular source file required')
            raw = tf.extractfile(m).read()
            side, rel = m.name.split('/', 1)
            if len(raw) != inv['files'][m.name]['size'] or digest(raw) != required[rel]:
                raise ValueError('manifest-pinned source differs')
            if read(MAIN_STAGE/rel, private=True) != raw:
                raise ValueError('main staged source differs')
            payload[m.name] = raw
    for root in ROOTS.values():
        os.close(directory_fd(root, private=True))
        inventory = json.loads(read(root/'source-inventory.json', private=True))
        for rel, pin in inventory['source_pins'].items():
            relative(rel)
            if digest(read(root/rel, private=True)) != pin:
                raise ValueError('existing tool changed')
        for name in ('firmware', 'provenance-stage-receipt.json', 'preparation-intent.json',
                     'request.json', 'witness.json', 'campaign.json', 'packet.json'):
            if os.path.lexists(root/name):
                raise ValueError('new provenance tree and unattempted recovery required')
    result = dict(schema=1, kind='fm1-v5-native-provenance-source-supplement',
                  helper_sha256=self_sha, inventory_sha256=INVENTORY_SHA,
                  archive_sha256=ARCHIVE_SHA, manifest_sha256=inv['manifest_sha256'],
                  check_only=args.check_only, hardware_opened=False, factory_invoked=False,
                  source_execution=False, retry=False, file_count=22)
    if not args.check_only:
        dirs = set()
        for name in payload:
            side, rel = name.split('/', 1)
            dest = ROOTS[side]/rel
            dirs.update(p for p in dest.parents if p != ROOTS[side] and p.is_relative_to(ROOTS[side]))
        for d in sorted(dirs, key=lambda p: (len(p.parts), str(p))):
            mkdir_exclusive(d)
        for name, raw in payload.items():
            side, rel = name.split('/', 1)
            write_exclusive(ROOTS[side]/rel, raw)
        for name, raw in payload.items():
            side, rel = name.split('/', 1)
            if read(ROOTS[side]/rel, private=True) != raw:
                raise ValueError('staged source differs; preserve partial state without retry')
        for root in ROOTS.values():
            save(root/'provenance-stage-receipt.json', result)
    print(json.dumps(result, sort_keys=True))

if __name__ == '__main__':
    main()
