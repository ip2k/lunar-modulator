#!/usr/bin/env python3
"""Bounded Linux SG_IO flash backup for the owner's soft-key UBOOT session.

Protocol facts and Linux SG_IO layout checked against kagaimiq's jl-uboot-tool
(adb3f188, MIT, Copyright (c) 2023 Andrey Grigoryev) and the local loader audit.
This implementation permits only INQUIRY, pinned-loader RAM upload/jump,
FC14/FC0A and 256-byte FD05 flash reads. It implements no flash writes.
MIT licence, like this repository. Vendor loader and private dumps stay out of Git.
"""
import argparse
import binascii
import ctypes as C
import fcntl
import hashlib
import json
import os
from pathlib import Path
import time

LOADER_SHA = 'd41da6126760c9d66660bcc0cac8d27d221806c5e369a8036921efe68dca5376'
RAM = 0x01C02000
LOADER_SIZE = 24064
FLASH_SIZE = 0x100000
CHUNK = 256  # WL82 buffer limit, including the transporter's reported quirk


class SGHeader(C.Structure):
    _fields_ = [('interface_id', C.c_int), ('direction', C.c_int),
                ('cmd_len', C.c_ubyte), ('sense_max', C.c_ubyte),
                ('iovec_count', C.c_ushort), ('data_len', C.c_uint),
                ('data', C.c_void_p), ('cmd', C.c_void_p), ('sense', C.c_void_p),
                ('timeout', C.c_uint), ('flags', C.c_uint), ('pack_id', C.c_int),
                ('user', C.c_void_p), ('status', C.c_ubyte), ('masked', C.c_ubyte),
                ('msg', C.c_ubyte), ('sense_len', C.c_ubyte),
                ('host', C.c_ushort), ('driver', C.c_ushort), ('resid', C.c_int),
                ('duration', C.c_uint), ('info', C.c_uint)]


def request(op, phase, *, address=0, payload=b''):
    """Construct only reviewed CDBs, with every unused byte FF (not '_0')."""
    if op == 0x12:
        if phase != 'rom' or address or payload:
            raise ValueError('INQUIRY only before loader execution')
        return bytes.fromhex('12 00 00 00 24 00'), b'', 36
    args, length, data = b'', 16, b''
    if phase == 'rom' and op == 0xFB06:
        if (len(payload) != 512 or address % 512 or
                not RAM <= address <= RAM + LOADER_SIZE - 512):
            raise ValueError('RAM upload must stay within the exact loader range')
        args = address.to_bytes(4, 'big') + len(payload).to_bytes(2, 'big') + b'\x00' + binascii.crc_hqx(payload, 0).to_bytes(2, 'little')
        data, length = payload, 0
    elif phase == 'rom' and op == 0xFB08:
        if address != RAM or payload:
            raise ValueError('Only pinned loader entry with argument 1')
        args = RAM.to_bytes(4, 'big') + b'\x00\x01'
    elif phase == 'loader' and op in (0xFC14, 0xFC0A):
        if address or payload:
            raise ValueError('No online-device configuration or extra arguments')
    elif phase == 'loader' and op == 0xFD05:
        if payload or address % CHUNK or not 0 <= address <= FLASH_SIZE-CHUNK:
            raise ValueError('Flash reads are aligned, bounded 256-byte chunks')
        args = address.to_bytes(4, 'big') + CHUNK.to_bytes(2, 'big')
        length = CHUNK
    else:
        raise ValueError(f'Forbidden operation {op:04x} in {phase}')
    cdb = (op.to_bytes(2, 'big') + args).ljust(16, b'\xff')
    return cdb, data, length


class Reader:
    def __init__(self, device, log):
        name = Path(device).name
        p = (Path('/sys/class/scsi_generic') / name / 'device').resolve()
        found = None
        for ancestor in [p, *p.parents]:
            if (ancestor / 'idVendor').exists():
                found = ancestor
                break
        if found is None or ((found/'idVendor').read_text().strip().lower(),
                             (found/'idProduct').read_text().strip().lower()) != ('4c4a', '8057'):
            raise ValueError('SG device is not USB 4c4a:8057 UBOOT')
        self.usb = found
        self.fd = os.open(device, os.O_RDWR)
        self.phase, self.log = 'rom', log

    def close(self):
        os.close(self.fd)

    def build_request(self, op, address, payload):
        return request(op, self.phase, address=address, payload=payload)

    def cmd(self, op, *, address=0, payload=b''):
        cdb, data_out, in_size = self.build_request(op, address, payload)
        command = C.create_string_buffer(cdb)
        sense = C.create_string_buffer(32)
        data = C.create_string_buffer(data_out) if data_out else C.create_string_buffer(in_size)
        h = SGHeader(interface_id=ord('S'), direction=-2 if data_out else -3,
                     cmd_len=len(cdb), sense_max=32, data_len=len(data_out) or in_size,
                     data=C.addressof(data), cmd=C.addressof(command), sense=C.addressof(sense), timeout=3000)
        # Dump data is deliberately not logged. CDBs contain ranges, never keys.
        self.log('command', phase=self.phase, cdb=cdb.hex(), out_len=len(data_out), in_len=in_size)
        fcntl.ioctl(self.fd, 0x2285, h)
        if h.status or h.host or h.driver or (h.info & 1) or h.resid:
            raise OSError(f'SG_IO status={h.status} host={h.host} driver={h.driver} resid={h.resid} sense={sense.raw[:h.sense_len].hex()}')
        result = data.raw[:in_size]
        if in_size == 16 and int.from_bytes(result[:2], 'big') != op:
            raise ValueError(f'Response did not echo {op:04x}: {result.hex()}')
        return result

    def load(self, loader):
        if len(loader) != LOADER_SIZE or hashlib.sha256(loader).hexdigest() != LOADER_SHA:
            raise ValueError('Loader does not match the audited 24064-byte blob')
        inquiry = self.cmd(0x12)
        vendor, product = inquiry[8:16].decode('ascii').strip(), inquiry[16:32].decode('ascii').strip()
        self.log('inquiry', vendor=vendor, product=product)
        if vendor != 'WL82' or product != 'UBOOT1.00':
            raise ValueError('Unexpected chip/boot mode; no RAM upload')
        self.log('loader_upload', sha256=LOADER_SHA, bytes=len(loader), base=RAM)
        for i in range(0, len(loader), 512):
            self.cmd(0xFB06, address=RAM+i, payload=loader[i:i+512])
        self.cmd(0xFB08, address=RAM)
        self.phase = 'loader'
        buff = self.cmd(0xFC14)
        size = int.from_bytes(buff[2:6], 'big')
        if not CHUNK <= size <= 65535:
            raise ValueError(f'Unexpected loader buffer size {size}')
        self.log('loader_buffer', size=size)
        self.online()

    def online(self):
        r = self.cmd(0xFC0A)
        kind, jedec = r[2], int.from_bytes(r[4:8], 'little')
        if kind != 3 or jedec != 0x856014:
            raise ValueError(f'Unexpected flash type/JEDEC: {kind} {jedec:06x}')
        return kind, jedec

    def dump(self, file):
        digest = hashlib.sha256()
        last_alive = time.monotonic()
        with file.open('xb') as fp:
            os.chmod(file, 0o600)
            for address in range(0, FLASH_SIZE, CHUNK):
                if time.monotonic()-last_alive >= 0.5:
                    self.online()
                    last_alive = time.monotonic()
                data = self.cmd(0xFD05, address=address)
                fp.write(data)
                digest.update(data)
            fp.flush(); os.fsync(fp.fileno())
        return {'file': file.name, 'bytes': file.stat().st_size, 'sha256': digest.hexdigest()}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--device', required=True)
    ap.add_argument('--loader', required=True, type=Path)
    ap.add_argument('--entry-log', required=True, type=Path)
    ap.add_argument('--out', required=True, type=Path, help='new private backup directory')
    args = ap.parse_args()
    # Validate local inputs before even opening the USB device.
    loader = args.loader.read_bytes()
    if len(loader) != LOADER_SIZE or hashlib.sha256(loader).hexdigest() != LOADER_SHA:
        raise SystemExit('Loader hash/length mismatch')
    events = [json.loads(s) for s in args.entry_log.read_text().splitlines()]
    entered = [e for e in events if e.get('event') == 'uboot_enumerated']
    if not entered or not any(e.get('event') == 'identity' and e['decoded'].get('identity') == 'FM-1_092' for e in events):
        raise SystemExit('Need the successful owner-unit soft-key entry log')
    args.out.mkdir(mode=0o700, parents=True, exist_ok=False)
    with (args.out/'commands.jsonl').open('x') as fp:
        def log(event, **fields):
            fp.write(json.dumps({'time':time.time(), 'event':event, **fields})+'\n')
            fp.flush()  # Avoid fsync per flash chunk; manifests/data are explicitly synced.
        reader = None
        try:
            reader = Reader(args.device, log)
            observed = [d for d in entered[-1]['usb'] if d['vid']=='4c4a' and d['pid']=='8057']
            if not any(d['path']==reader.usb.name and d['devnum']==(reader.usb/'devnum').read_text().strip() for d in observed):
                raise ValueError('SG device differs from recorded UBOOT enumeration')
            reader.load(loader)
            a = reader.dump(args.out/'dumpA.bin')
            reader.online()
            b = reader.dump(args.out/'dumpB.bin')
            if a['sha256'] != b['sha256'] or a['bytes'] != FLASH_SIZE or b['bytes'] != FLASH_SIZE:
                raise ValueError('Backups differ or are incomplete')
            manifest = {'entry_log':str(args.entry_log), 'loader_sha256':LOADER_SHA,
                        'flash_bytes':FLASH_SIZE, 'dumps':[a,b], 'identical':True}
            with (args.out/'manifest.json').open('x') as m:
                json.dump(manifest,m,indent=2); m.flush(); os.fsync(m.fileno())
            print(json.dumps(manifest),flush=True)
        except Exception as exc:
            log('stopped', error=str(exc)); fp.flush(); os.fsync(fp.fileno())
            print(f'Stopped: {exc}',flush=True)
            raise SystemExit(1) from exc
        finally:
            if reader is not None:
                reader.close()


if __name__ == '__main__':
    main()
