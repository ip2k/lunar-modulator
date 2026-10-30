#!/usr/bin/env python3
"""AC79 dev-kit flash-data backup using the reviewed fixed RAM loader.

No flash erase, program, eFuse, reset or arbitrary command is implemented.
The loader does execute in RAM. Require the exact observed USB path/devnum;
never use this adapter for an FM-1. Raw output belongs in private storage.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time

import fm1_uboot_read as base

FLASH_SIZE = 8 * 1024 * 1024
LOADER_SHA = 'fe6d1bd36c8ffe4674e4a05ee748fe87480b5867fac58230b14ff089d411012c'


def validate_loader(loader):
    if len(loader) != base.LOADER_SIZE or hashlib.sha256(loader).hexdigest() != LOADER_SHA:
        raise ValueError('Only the reviewed fixed-configuration loader is permitted; no USB access')


def request(op, phase, *, address=0, payload=b''):
    if op == 0xFD05 and phase == 'loader':
        if payload or address % base.CHUNK or not 0 <= address <= FLASH_SIZE-base.CHUNK:
            raise ValueError('Dev-kit read outside aligned 8 MiB boundary')
        args = address.to_bytes(4, 'big') + base.CHUNK.to_bytes(2, 'big')
        return (b'\xfd\x05' + args).ljust(16, b'\xff'), b'', base.CHUNK
    return base.request(op, phase, address=address, payload=payload)


class DevkitReader(base.Reader):
    def load(self, loader):
        # Preserve the original Reader's historical pin. This adapter admits
        # only the separately reviewed fixed configuration, never the original.
        validate_loader(loader)
        inquiry = self.cmd(0x12)
        vendor, product = inquiry[8:16].decode('ascii').strip(), inquiry[16:32].decode('ascii').strip()
        self.log('inquiry', vendor=vendor, product=product)
        if vendor != 'WL82' or product != 'UBOOT1.00':
            raise ValueError('Unexpected chip/boot mode; no RAM upload')
        self.log('loader_upload', sha256=LOADER_SHA, bytes=len(loader), base=base.RAM)
        for offset in range(0, len(loader), 512):
            self.cmd(0xFB06, address=base.RAM+offset, payload=loader[offset:offset+512])
        self.cmd(0xFB08, address=base.RAM)
        self.phase = 'loader'
        buff = self.cmd(0xFC14)
        size = int.from_bytes(buff[2:6], 'big')
        if not base.CHUNK <= size <= 65535:
            raise ValueError(f'Unexpected loader buffer size {size}')
        self.log('loader_buffer', size=size)
        self.online()

    def build_request(self, op, address, payload):
        return request(op, self.phase, address=address, payload=payload)

    def online(self):
        r = self.cmd(0xFC0A)
        kind, jedec = r[2], int.from_bytes(r[4:8], 'little')
        # JEDEC capacity 0x17 denotes 2**23 bytes. Refuse other devices rather
        # than guessing capacity from the factory filesystem's size message.
        if kind != 3 or jedec & 0xff != 0x17:
            raise ValueError(f'Expected 8 MiB SPI NOR, got kind={kind} JEDEC={jedec:06x}')
        self.log('flash_identity', kind=kind, jedec=f'{jedec:06x}', bytes=FLASH_SIZE)
        return kind, jedec

    def dump(self, path):
        digest = hashlib.sha256()
        last_alive = time.monotonic()
        with path.open('xb') as fp:
            os.chmod(path, 0o600)
            for address in range(0, FLASH_SIZE, base.CHUNK):
                if time.monotonic()-last_alive >= 0.5:
                    self.online()
                    last_alive = time.monotonic()
                data = self.cmd(0xFD05, address=address)
                fp.write(data)
                digest.update(data)
                if address % 0x100000 == 0:
                    print(json.dumps({'progress': address, 'file': path.name}), flush=True)
            fp.flush()
            os.fsync(fp.fileno())
        return {'file': path.name, 'bytes': path.stat().st_size,
                'sha256': digest.hexdigest()}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--device', required=True)
    ap.add_argument('--usb-path', required=True)
    ap.add_argument('--devnum', required=True)
    ap.add_argument('--loader', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    loader = a.loader.read_bytes()
    validate_loader(loader)
    a.out.mkdir(mode=0o700, parents=True, exist_ok=False)
    with (a.out/'commands.jsonl').open('x') as log_file:
        def log(event, **fields):
            log_file.write(json.dumps({'time': time.time(), 'event': event, **fields})+'\n')
            log_file.flush()
        reader = DevkitReader(a.device, log)
        try:
            if reader.usb.name != a.usb_path or (reader.usb/'devnum').read_text().strip() != a.devnum:
                raise ValueError('USB path/devnum differs from observed dev kit')
            reader.load(loader)
            first = reader.dump(a.out/'factory-A.bin')
            second = reader.dump(a.out/'factory-B.bin')
            if first['sha256'] != second['sha256']:
                raise ValueError('Factory reads differ; do not write flash')
            result = {'reads': [first, second], 'matched': True, 'loader_sha256': LOADER_SHA,
                      'flash_erase_program_commands_sent': False,
                      'nor_status_unchanged': None, 'restore_demonstrated': False}
            (a.out/'receipt.json').write_text(json.dumps(result, indent=2)+'\n')
            print(json.dumps(result), flush=True)
        finally:
            reader.close()


if __name__ == '__main__':
    main()
