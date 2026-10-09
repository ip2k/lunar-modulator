#!/usr/bin/env python3
"""Linux ALSA raw-MIDI identity + explicitly requested FM-1 soft-key probe.

Only two messages can be sent: the identity request and F0 22 24 35 7D F7.
No flash, loader upload, SCSI, arbitrary SysEx or retry operation is implemented.
The soft key resets the FM-1; power-cycle it to return to its installed app.
MIT licence. See notes/2026-10-07-fm1-softkey-bench.md.
"""
import argparse
import json
import os
from pathlib import Path
import select
import time

from fm1_identify import decode

IDENTITY = bytes.fromhex('F0 00 32 45 00 00 00 40 7F F7')
SOFT_KEY = bytes.fromhex('F0 22 24 35 7D F7')
VETTED = {'FM-1_015', 'FM-1_092'}
# Captured on the owner's unit, 2026-10-07; only this complete frame is excepted.
KNOWN_092 = bytes.fromhex('f0 00 32 45 58 01 00 00 23 4d 5a 44 79 05 26 0e 19 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 20 06 f7')


def frames(data):
    """Extract complete SysEx; MIDI real-time bytes may interrupt a message."""
    frame = bytearray()
    for b in data:
        if b >= 0xF8:
            continue
        if b == 0xF0:
            frame = bytearray([b])
        elif frame:
            if b == 0xF7:
                yield bytes(frame + bytes([b]))
                frame.clear()
            elif b < 0x80:
                frame.append(b)
            else:
                frame.clear()


def checked_identity(data, expected, known_092=False):
    for reply in frames(data):
        info = decode(reply)
        if (not info.get('error') and (info.get('checksum_ok') is True or
                    (known_092 and expected == 'FM-1_092' and reply == KNOWN_092))
                and info.get('identity') == expected):
            return reply, info
    raise ValueError(f'No valid checksummed identity matching {expected}; soft key not sent')


def usb_parent(midi, root=Path('/sys/class/sound')):
    name = Path(midi).name
    if not name.startswith('midiC') or '/' in name:
        raise ValueError('Expected an ALSA /dev/snd/midiC…D… raw-MIDI device')
    link = root / name / 'device'
    if not link.exists():
        raise ValueError(f'No sysfs device for {name}')
    for p in [link.resolve(), *link.resolve().parents]:
        if (p / 'idVendor').exists() and (p / 'idProduct').exists():
            if ((p / 'idVendor').read_text().strip().lower(),
                (p / 'idProduct').read_text().strip().lower()) != ('4c4a', 'c755'):
                raise ValueError('Raw-MIDI device is not USB 4c4a:c755')
            if not p.parent.name.startswith('usb'):
                raise ValueError('Use a direct USB root port, rather than a downstream hub')
            return p
    raise ValueError('No USB ancestor for MIDI device')


def enumerate_usb(root=Path('/sys/bus/usb/devices')):
    out = []
    for p in sorted(root.glob('*')):
        try:
            vid, pid = (p / 'idVendor').read_text().strip(), (p / 'idProduct').read_text().strip()
        except OSError:
            continue
        item = {'path': p.name, 'vid': vid, 'pid': pid}
        for k in ('product', 'busnum', 'devnum', 'speed'):
            try:
                item[k] = (p / k).read_text().strip()
            except OSError:
                pass
        out.append(item)
    return out


def write_message(fd, data):
    if data not in (IDENTITY, SOFT_KEY):
        raise ValueError('Message not in the two-message allowlist')
    n = os.write(fd, data)  # one write, never an automatic retry
    if n != len(data):
        raise OSError(f'Partial MIDI write: {n}/{len(data)}; stop and inspect capture')


def probe(device, expected, send_soft_key, log, timeout=3.0, known_092=False):
    if send_soft_key and expected not in VETTED:
        raise ValueError('Soft-key path statically checked only for FM-1_015 / FM-1_092')
    parent = usb_parent(device)
    log('before', usb=enumerate_usb(), midi=str(device), usb_path=parent.name)
    fd = os.open(device, os.O_RDWR | os.O_NONBLOCK)
    try:
        # Flush stale input before requesting a fresh identity.
        while select.select([fd], [], [], 0)[0]:
            if not os.read(fd, 4096):
                break
        log('sending_identity', hex=IDENTITY.hex(' '))
        write_message(fd, IDENTITY)
        data = bytearray()
        end = time.monotonic() + timeout
        result = None
        while time.monotonic() < end:
            if select.select([fd], [], [], min(0.1, max(0, end-time.monotonic())))[0]:
                chunk = os.read(fd, 4096)
                if not chunk:
                    raise OSError('MIDI device disconnected during identity')
                data.extend(chunk)
                try:
                    result = checked_identity(data, expected, known_092)
                    break
                except ValueError:
                    pass
        if result is None:
            log('identity_failed', received=data.hex(' '))
            raise ValueError('Fresh expected identity not received; soft key not sent')
        reply, info = result
        log('identity', reply=reply.hex(' '), decoded=info)
        if not send_soft_key:
            return info
        # Do not retry. Kernel ALSA packing must be checked in the passive capture.
        log('sending_soft_key', hex=SOFT_KEY.hex(' '), expected_usb_packet='04 f0 22 24 07 35 7d f7')
        write_message(fd, SOFT_KEY)
    finally:
        os.close(fd)
    started = time.monotonic()
    while time.monotonic() - started < 5:
        devices = enumerate_usb()
        if any(d['vid'].lower() == '4c4a' and d['pid'].lower() == '8057' for d in devices):
            log('uboot_enumerated', elapsed=time.monotonic()-started, usb=devices)
            return info
        time.sleep(0.1)
    log('uboot_not_observed', usb=enumerate_usb())
    raise RuntimeError('UBOOT 4c4a:8057 not observed; inspect capture, do not retry automatically')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--device', required=True)
    ap.add_argument('--expect', required=True, help='exact installed identity, e.g. FM-1_092')
    ap.add_argument('--accept-known-092-checksum-bug', action='store_true',
                    help='accept only the exact 41-byte faulty identity captured on the owner unit')
    ap.add_argument('--send-soft-key', action='store_true', help='reset once into UBOOT after matching identity')
    ap.add_argument('--log', type=Path, required=True, help='new private JSONL session log')
    args = ap.parse_args()
    args.log.parent.mkdir(parents=True, exist_ok=True)
    with args.log.open('x') as fp:
        def log(event, **fields):
            item = {'time': time.time(), 'event': event, **fields}
            line = json.dumps(item)
            fp.write(line + '\n'); fp.flush(); os.fsync(fp.fileno())
            print(line, flush=True)
        try:
            probe(args.device, args.expect, args.send_soft_key, log, known_092=args.accept_known_092_checksum_bug)
        except Exception as exc:
            log('stopped', error=str(exc))
            raise SystemExit(1) from exc


if __name__ == '__main__':
    main()
