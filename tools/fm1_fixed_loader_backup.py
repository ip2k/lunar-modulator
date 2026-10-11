#!/usr/bin/env python3
"""Exact-candidate Linux SG_IO backup campaign; MIT, no automatic recovery.

ROM framing and SG_IO layout are reused from the pinned backup reader, which
credits kagaimiq's jl-uboot-tool (adb3f188, MIT, Andrey Grigoryev). This adapter
accepts only the independently reviewed fixed selector candidate. Successful
transport and matching reads do not establish physical recovery or initializer
safety. The old reader and its original loader pin remain unchanged.
"""
import argparse
import ctypes as C
from dataclasses import dataclass
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import time
import types

LOADER_SHA = 'fe6d1bd36c8ffe4674e4a05ee748fe87480b5867fac58230b14ff089d411012c'
ORIGINAL_SHA = 'd41da6126760c9d66660bcc0cac8d27d221806c5e369a8036921efe68dca5376'
PROFILE_SHA = '3c03e413b9df29d85e4c07d886d9bfb9b3ab2fc66845d5220f82998dd44f4afe'
PROFILE_SOURCE_SHA = '9664e1329d8259362da78c047ce2d6003dfe8df2850f02703f98e8b6bf277cd8'
READER_SHA = '28317ee56a489e0bb38de981fe0d0c4260384be570349795741fdb9a98d6ae57'
RAM, LOADER_SIZE, FLASH_SIZE, PAGE = 0x01C02000, 24064, 0x100000, 256
MAX_ENTRY_AGE = 600
# Exact owner-unit frame excepted by fm1_softkey_probe.KNOWN_092; the decoded
# label alone is not evidence that the probe received that reviewed frame.
ENTRY_REPLY_SHA = '7679e7be907c6cc32b3c1f27c48cc8ce6daa865852e8021e2207cdeae223217d'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def sync_dir(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def bounded_file(path):
    path = Path(path)
    if not path.is_absolute():
        raise ValueError('Pinned path must be absolute')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        fp = os.fdopen(fd, 'rb')
    except BaseException:
        os.close(fd)
        raise
    with fp:
        if not stat.S_ISREG(os.fstat(fp.fileno()).st_mode):
            raise ValueError('Pinned file must be regular')
        data = fp.read(2 * FLASH_SIZE + 1)
    if len(data) > 2 * FLASH_SIZE:
        raise ValueError('File exceeds bounded input size: ' + str(path))
    return data


def pinned_file(path, expected):
    data = bounded_file(path)
    if digest(data) != expected:
        raise ValueError('Pinned file hash differs: ' + str(path))
    return data


def private_file(path, mode='wb'):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                 os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    try:
        return os.fdopen(fd, mode)
    except BaseException:
        os.close(fd)
        raise


def validate_usb(usb):
    if (set(usb) != {'path', 'busnum', 'devnum', 'vid', 'pid'} or
            not all(isinstance(x, str) for x in usb.values()) or
            not re.fullmatch(r'[1-9][0-9]*-[1-9][0-9]*(?:\.[1-9][0-9]*)*', usb['path']) or
            not re.fullmatch(r'[1-9][0-9]*', usb['busnum']) or
            not re.fullmatch(r'[1-9][0-9]*', usb['devnum']) or
            usb['path'].split('-')[0] != usb['busnum'] or
            (usb['vid'], usb['pid']) != ('4c4a', '8057')):
        raise ValueError('Exact ROM USB topology required')


def validate_entry(data, usb, now):
    events = [json.loads(line) for line in data.decode('utf8').splitlines()]
    names = [e.get('event') for e in events]
    ordered = ('before', 'sending_identity', 'identity', 'sending_soft_key', 'uboot_enumerated')
    if (any(names.count(name) != 1 for name in ordered) or
            any(e in names for e in ('identity_failed', 'uboot_not_observed', 'stopped'))):
        raise ValueError('Need one successful fresh soft-key entry')
    indices = [names.index(n) for n in ordered]
    if indices != sorted(indices):
        raise ValueError('Entry events out of order')
    before, requested, identity, soft, entered = [events[i] for i in indices]
    projected = [{key: item.get(key) for key in usb} for item in entered.get('usb', [])]
    normal = [item for item in before.get('usb', []) if
              (item.get('path'), item.get('vid'), item.get('pid')) == (usb['path'], '4c4a', 'c755')]
    if (before.get('usb_path') != usb['path'] or len(normal) != 1 or
            requested.get('hex', '').lower() != 'f0 00 32 45 00 00 00 40 7f f7' or
            identity.get('decoded', {}).get('identity') != 'FM-1_092' or
            digest(bytes.fromhex(identity.get('reply', ''))) != ENTRY_REPLY_SHA or
            soft.get('hex', '').lower() != 'f0 22 24 35 7d f7' or
            projected.count(usb) != 1):
        raise ValueError('Entry identity/key/topology differs')
    timestamps = [e.get('time') for e in (before, requested, identity, soft, entered)]
    if (not all(type(t) in (int, float) for t in timestamps) or
            timestamps != sorted(timestamps) or
            not 0 <= now - timestamps[0] <= MAX_ENTRY_AGE or
            not 0 <= entered.get('elapsed', -1) <= 5):
        raise ValueError('Entry is stale or has invalid timestamps')
    return entered['time']


@dataclass(frozen=True)
class Operation:
    phase: str
    cdb: bytes
    payload: bytes
    read_size: int
    label: str


@dataclass(frozen=True)
class PreparedCampaign:
    config: dict
    manifest_sha256: str
    loader: bytes
    operations: tuple
    header_type: type
    entered_at: float
    request_inventory_sha256: str


def inventory_digest(operations):
    inventory = [{'phase': op.phase, 'cdb': op.cdb.hex(), 'label': op.label,
                  'payload_sha256': digest(op.payload) if op.payload else None,
                  'out_len': len(op.payload), 'in_len': op.read_size}
                 for op in operations]
    return digest(json.dumps(inventory, sort_keys=True, separators=(',', ':')).encode('ascii'))


def prepare_campaign(path, *, now=None):
    """Validate all immutable inputs before discovering/opening an SG device."""
    now = time.time() if now is None else now
    path = Path(path).absolute()
    # Campaign is review input, not a credential. Its source hashes must equal
    # actual staged files; authority to execute remains with the bench owner.
    raw = bounded_file(path)
    config = json.loads(raw)
    required = {'schema', 'kind', 'adapter_sha256', 'loader_path', 'profile_path',
                'profile_source_path', 'entry_log_path', 'entry_log_sha256',
                'usb_binding', 'receipt_path'}
    if (set(config) != required or config['schema'] != 1 or
            config['kind'] != 'fm1-fixed-loader-backup-campaign'):
        raise ValueError('Unexpected campaign schema')
    pinned_file(Path(__file__).absolute(), config['adapter_sha256'])
    loader = pinned_file(config['loader_path'], LOADER_SHA)
    if len(loader) != LOADER_SIZE:
        raise ValueError('Exact 24064-byte loader required')
    profile = json.loads(pinned_file(config['profile_path'], PROFILE_SHA))
    pinned_file(config['profile_source_path'], PROFILE_SOURCE_SHA)
    entry = pinned_file(config['entry_log_path'], config['entry_log_sha256'])
    validate_usb(config['usb_binding'])
    entered_at = validate_entry(entry, config['usb_binding'], now)
    destination = Path(config['receipt_path'])
    if (not destination.is_absolute() or destination.exists() or
            not stat.S_ISDIR(destination.parent.lstat().st_mode) or
            destination.parent.stat().st_mode & 0o777 != 0o700):
        raise ValueError('New receipt under private direct directory required')
    reader_path = Path(__file__).absolute().with_name('fm1_uboot_read.py')
    source = pinned_file(reader_path, READER_SHA)
    reader = types.ModuleType('_fm1_verified_reader')
    # Execute the already read, hashed bytes; never resolve an ambient module.
    exec(compile(source, str(reader_path), 'exec'), reader.__dict__)
    if C.sizeof(reader.SGHeader) != 88:
        raise ValueError('Only reviewed 64-bit Linux SG_IO layout supported')
    operations = []

    def add(op, phase, label, address=0, payload=b''):
        cdb, data, size = reader.request(op, phase, address=address, payload=payload)
        operations.append(Operation(phase, cdb, data, size, label))

    add(0x12, 'rom', 'inquiry')
    for index, offset in enumerate(range(0, LOADER_SIZE, 512)):
        add(0xFB06, 'rom', 'upload', RAM + offset, loader[offset:offset + 512])
        op = operations[-1]
        expected = {'index': index, 'address': RAM + offset, 'bytes': 512,
                    'cdb_sha256': digest(op.cdb), 'payload_sha256': digest(op.payload),
                    'read_size': 0}
        if profile['upload_inventory'][index] != expected:
            raise ValueError('Profile upload inventory differs')
    if (len(profile['upload_inventory']) != 47 or
            profile['patched_encrypted_sha256'] != LOADER_SHA or
            profile['original_encrypted_sha256'] != ORIGINAL_SHA):
        raise ValueError('Profile loader identity differs')
    add(0xFB08, 'rom', 'jump', RAM)
    add(0xFC14, 'loader', 'buffer')
    add(0xFC0A, 'loader', 'online')
    # Fixed cadence: one online check before each 4KiB group and at pass end. No timers
    # or arbitrary caller-selected opcodes/ranges can extend the envelope.
    for name in ('dumpA.bin', 'dumpB.bin'):
        for address in range(0, FLASH_SIZE, PAGE):
            if address % 4096 == 0:
                add(0xFC0A, 'loader', 'online')
            add(0xFD05, 'loader', name, address)
        add(0xFC0A, 'loader', name + '.end')
    return PreparedCampaign(config, digest(raw), loader, tuple(operations),
                            reader.SGHeader, entered_at, inventory_digest(operations))


def usb_snapshot(root):
    return {'path': root.name, **{key: (root / attribute).read_text().strip().lower()
                                for key, attribute in (('busnum', 'busnum'),
                                    ('devnum', 'devnum'), ('vid', 'idVendor'),
                                    ('pid', 'idProduct'))}}


def identity(path):
    value = path.stat()
    return value.st_dev, value.st_ino, value.st_rdev


def discover_sg(usb):
    root = Path('/sys/bus/usb/devices') / usb['path']
    if usb_snapshot(root) != usb:
        raise ValueError('ROM USB topology differs')
    resolved = root.resolve(strict=True)
    candidates = []
    for item in Path('/sys/class/scsi_generic').glob('sg*'):
        device = (item / 'device').resolve(strict=True)
        if resolved in (device, *device.parents):
            candidates.append(item)
    if len(candidates) != 1:
        raise ValueError('Exactly one SG device on pinned topology required')
    item = candidates[0]
    node = Path('/dev') / item.name
    value = node.lstat()
    if not stat.S_ISCHR(value.st_mode):
        raise ValueError('SG node must be a direct character device')
    mapped = Path('/sys/dev/char') / f'{os.major(value.st_rdev)}:{os.minor(value.st_rdev)}'
    if mapped.resolve(strict=True) != item.resolve(strict=True):
        raise ValueError('SG character-device mapping differs')
    return {'node': str(node), 'class': str(item.resolve(strict=True)),
            'device': str((item / 'device').resolve(strict=True)), 'usb': str(resolved),
            'node_identity': identity(node), 'class_identity': identity(item),
            'device_identity': identity(item / 'device'), 'usb_identity': identity(root)}


class FixedSG:
    """One consumed ordered envelope with fail-closed FD and topology binding."""
    def __init__(self, prepared, log):
        if not isinstance(prepared, PreparedCampaign):
            raise ValueError('Prepared campaign required before opening hardware')
        self.prepared, self.log = prepared, log
        self.fd, self.next, self.ioctl_attempts, self.phase = None, 0, 0, 'rom'
        self.failed = False
        try:
            if prepared.request_inventory_sha256 != inventory_digest(prepared.operations):
                raise ValueError('Prepared command inventory differs')
            if not 0 <= time.time() - prepared.entered_at <= MAX_ENTRY_AGE:
                raise ValueError('Entry became stale before device open')
            self.mapping = discover_sg(prepared.config['usb_binding'])
            self.fd = os.open(self.mapping['node'], os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC)
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            opened = os.fstat(self.fd)
            self.fd_identity = opened.st_dev, opened.st_ino, opened.st_rdev
            if not stat.S_ISCHR(opened.st_mode) or self.fd_identity != self.mapping['node_identity']:
                raise ValueError('Opened descriptor differs from discovered SG device')
            self.binding()
        except BaseException:
            self.failed = True
            self.close()
            raise

    def close(self):
        if self.fd is not None:
            fd, self.fd = self.fd, None
            os.close(fd)

    def binding(self):
        if self.fd is None:
            raise ValueError('Closed SG descriptor')
        opened = os.fstat(self.fd)
        if ((opened.st_dev, opened.st_ino, opened.st_rdev) != self.fd_identity or
                not stat.S_ISCHR(opened.st_mode) or
                discover_sg(self.prepared.config['usb_binding']) != self.mapping):
            raise ValueError('Bound SG/sysfs/USB connection replaced')

    def exchange_next(self):
        try:
            if self.failed or self.fd is None or self.next >= len(self.prepared.operations):
                raise ValueError('Closed, failed, or consumed campaign')
            index = self.next
            op = self.prepared.operations[index]
            self.next += 1  # Consume before logging, binding, or syscall.
            if op.phase != self.phase:
                raise ValueError('Campaign phase differs')
            command, sense = C.create_string_buffer(op.cdb), C.create_string_buffer(32)
            data = C.create_string_buffer(op.payload) if op.payload else C.create_string_buffer(op.read_size)
            h = self.prepared.header_type(interface_id=ord('S'), direction=-2 if op.payload else -3,
                cmd_len=len(op.cdb), sense_max=32, data_len=len(op.payload) or op.read_size,
                data=C.addressof(data), cmd=C.addressof(command), sense=C.addressof(sense), timeout=3000)
            self.log('sg_submit_intent', index=index, phase=self.phase, label=op.label,
                     cdb=op.cdb.hex(), payload_sha256=digest(op.payload) if op.payload else None,
                     out_len=len(op.payload), in_len=op.read_size, retry=False)
            self.binding()
            self.ioctl_attempts += 1
            fcntl.ioctl(self.fd, 0x2285, h)
            self.binding()  # Re-enumeration is ambiguous even following a reply.
            self.log('sg_completion', index=index, status=h.status, masked=h.masked, msg=h.msg,
                     host=h.host, driver=h.driver, resid=h.resid, info=h.info,
                     sense_len=h.sense_len, sense_hex=sense.raw[:min(h.sense_len, 32)].hex(), retry=False)
            if (h.status or h.masked or h.msg or h.host or h.driver or h.resid or h.info & 1 or h.sense_len):
                raise OSError('Incomplete or unsuccessful SG_IO completion')
            result = data.raw[:op.read_size]
            if op.read_size == 16 and result[:2] != op.cdb[:2]:
                raise ValueError('Response command echo differs')
            if op.label == 'inquiry' and (result[8:16].strip() != b'WL82' or
                                           result[16:32].strip() != b'UBOOT1.00'):
                raise ValueError('Inquiry chip/boot mode differs')
            if op.label == 'buffer' and not PAGE <= int.from_bytes(result[2:6], 'big') <= 65535:
                raise ValueError('Unexpected loader buffer size')
            if op.cdb[:2] == b'\xfc\x0a' and (result[2] != 3 or int.from_bytes(result[4:8], 'little') != 0x856014):
                raise ValueError('Unexpected flash type/JEDEC')
            if op.label == 'jump':
                self.phase = 'loader'
            return op, result
        except BaseException:
            self.failed = True
            self.phase = 'failed'
            self.close()
            raise


def run_campaign(prepared):
    """Create durable exclusive receipts and read two full images; never retry."""
    receipt = Path(prepared.config['receipt_path'])
    receipt.mkdir(mode=0o700, exist_ok=False)
    sync_dir(receipt.parent)
    # A fresh log can authorize at most one attempt in this receipt parent.
    # Persist consumption before SG open; ambiguous/failed attempts cannot reuse
    # the entry by choosing another receipt name in the same campaign directory.
    marker = receipt.parent / ('.entry-' + prepared.config['entry_log_sha256'] + '.consumed')
    with private_file(marker) as fp:
        fp.write(prepared.manifest_sha256.encode('ascii'))
        fp.flush(); os.fsync(fp.fileno())
    sync_dir(receipt.parent)
    with private_file(receipt / 'commands.jsonl', 'w') as events:
        def log(event, **fields):
            events.write(json.dumps({'time': time.time(), 'event': event, **fields}) + '\n')
            events.flush()
            if event != 'sg_completion' and (event != 'sg_submit_intent' or
                    fields.get('label') not in ('online', 'dumpA.bin', 'dumpB.bin',
                                               'dumpA.bin.end', 'dumpB.bin.end')):
                os.fsync(events.fileno()); sync_dir(receipt)

        transport = None
        try:
            log('campaign_prepared', campaign_sha256=prepared.manifest_sha256,
                adapter_sha256=prepared.config['adapter_sha256'], loader_sha256=LOADER_SHA,
                profile_sha256=PROFILE_SHA, profile_source_sha256=PROFILE_SOURCE_SHA,
                reader_sha256=READER_SHA, entry_log_sha256=prepared.config['entry_log_sha256'],
                usb_binding=prepared.config['usb_binding'], commands=len(prepared.operations),
                request_inventory_sha256=prepared.request_inventory_sha256,
                kernel_exclusivity=False, physical_recovery_verified=False)
            transport = FixedSG(prepared, log)
            dumps = []
            for name in ('dumpA.bin', 'dumpB.bin'):
                hasher, count = hashlib.sha256(), 0
                with private_file(receipt / name) as fp:
                    while transport.next < len(prepared.operations):
                        pending = prepared.operations[transport.next]
                        if pending.label not in ('inquiry', 'upload', 'jump', 'buffer', 'online', name, name + '.end'):
                            break
                        op, data = transport.exchange_next()
                        if op.label == name:
                            fp.write(data); hasher.update(data); count += len(data)
                        if op.label == name + '.end':
                            break
                    fp.flush(); os.fsync(fp.fileno())
                sync_dir(receipt)
                if count != FLASH_SIZE:
                    raise ValueError('Incomplete flash dump')
                dumps.append({'file': name, 'bytes': count, 'sha256': hasher.hexdigest(), 'complete': True})
            transport.binding()
            if (transport.next != len(prepared.operations) or
                    dumps[0]['sha256'] != dumps[1]['sha256']):
                raise ValueError('Incomplete campaign or mismatched backups')
            # Re-read durable files independently before claiming completion.
            for entry in dumps:
                pinned_file(receipt / entry['file'], entry['sha256'])
                if (receipt / entry['file']).stat().st_size != FLASH_SIZE:
                    raise ValueError('Durable dump length differs')
            manifest = {'schema': 1, 'kind': 'fm1-fixed-loader-backup',
                'loader_sha256': LOADER_SHA, 'original_loader_sha256': ORIGINAL_SHA,
                'loader_profile_sha256': PROFILE_SHA, 'profile_source_sha256': PROFILE_SOURCE_SHA,
                'adapter_sha256': prepared.config['adapter_sha256'],
                'dependency_sha256': {'fm1_uboot_read.py': READER_SHA},
                'campaign_sha256': prepared.manifest_sha256,
                'request_inventory_sha256': prepared.request_inventory_sha256,
                'entry_log_sha256': prepared.config['entry_log_sha256'], 'unit_identity': 'FM-1_092',
                'usb_binding': prepared.config['usb_binding'], 'sg_binding': transport.mapping,
                'flash_bytes': FLASH_SIZE, 'dumps': dumps, 'identical': True,
                'command_completions': True, 'commands': transport.next,
                'flash_readback_only': True, 'physical_recovery_verified': False,
                'kernel_exclusivity': False}
            log('campaign_completed', identical=True, bytes_per_dump=FLASH_SIZE,
                physical_recovery_verified=False, retry=False)
            with private_file(receipt / 'manifest.json', 'w') as fp:
                json.dump(manifest, fp, indent=2); fp.write('\n'); fp.flush(); os.fsync(fp.fileno())
            sync_dir(receipt)
            return manifest
        except BaseException as exc:
            if transport is not None:
                transport.failed = True
                transport.close()
            # Failed publication must not leave the success filename. A storage
            # failure may also prevent cleanup/logging; successful process exit,
            # the final manifest and the completed event are all acceptance gates.
            try:
                (receipt / 'manifest.json').unlink(missing_ok=True)
                sync_dir(receipt)
            except OSError:
                pass
            try:
                log('campaign_stopped_ambiguous', error=type(exc).__name__, detail=str(exc), retry=False)
            except OSError:
                pass
            raise
        finally:
            if transport is not None:
                transport.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign', required=True, type=Path)
    args = parser.parse_args()
    if sys.platform != 'linux':
        raise SystemExit('Linux SG_IO only')
    os.umask(0o077)
    prepared = prepare_campaign(args.campaign)
    run_campaign(prepared)


if __name__ == '__main__':
    main()
