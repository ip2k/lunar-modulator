#!/usr/bin/env python3
"""Read-only-flash AC79 dev-kit backup using the existing pinned RAM loader.

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


def request(op, phase, *, address=0, payload=b''):
    if op == 0xFD05 and phase == 'loader':
        if payload or address % base.CHUNK or not 0 <= address <= FLASH_SIZE-base.CHUNK:
            raise ValueError('Dev-kit read outside aligned 8 MiB boundary')
        args = address.to_bytes(4, 'big') + base.CHUNK.to_bytes(2, 'big')
        return (b'\xfd\x05' + args).ljust(16, b'\xff'), b'', base.CHUNK
    return base.request(op, phase, address=address, payload=payload)


class DevkitReader(base.Reader):
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
    if len(loader) != base.LOADER_SIZE or hashlib.sha256(loader).hexdigest() != base.LOADER_SHA:
        raise SystemExit('Pinned loader hash/size mismatch; no USB access')
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
            result = {'reads': [first, second], 'matched': True,
                      'flash_written': False, 'restore_demonstrated': False}
            (a.out/'receipt.json').write_text(json.dumps(result, indent=2)+'\n')
            print(json.dumps(result), flush=True)
        finally:
            reader.close()


if __name__ == '__main__':
    main()
