#!/usr/bin/env python3
"""MIT. One fixed-loader core reset after a verified dev-kit transaction.

Continues the coordinator's existing fixed-loader session, never uploads one.
Re-reads the complete installed image before one FC0C argument-1 request.
No arbitrary command, flash mutation, eFuse operation or automatic retry.
USB disappearance or request completion is not application boot evidence.
Protocol credit: kagaimiq (Andrey Grigoryev), jl-uboot-tool, MIT.
"""
import argparse
import json
import os
from pathlib import Path
import time

import devkit_flash_transaction as tx

RESET_CDB = bytes.fromhex('fc0c00000001ffffffffffffffffffff')


class ResetReader(tx.backup.DevkitReader):
    reset_used = False

    def build_request(self, op, address, payload):
        if op == 0xFC0C:
            if self.phase != 'loader' or address or payload or self.reset_used:
                raise ValueError('One literal reset in the existing loader session only')
            self.reset_used = True  # Consume before syscall, including timeout.
            return RESET_CDB, b'', 16
        if op not in (0xFD05, 0xFC0A):
            raise ValueError('Only verification reads and one reset permitted')
        return tx.backup.request(op, self.phase, address=address, payload=payload)


def verify_transaction(directory, expected):
    if len(expected) != tx.backup.FLASH_SIZE or tx.digest(expected) not in tx.IMAGE_PLANS:
        raise ValueError('Exact reviewed diagnostic required')
    receipt = json.loads((directory/'receipt.json').read_text())
    after = receipt.get('after', {})
    if (receipt.get('mode') != 'install' or receipt.get('full_flash_verified') is not True
            or receipt.get('reset_sent') is not False
            or after.get('sha256') != tx.digest(expected)
            or after.get('bytes') != len(expected)
            or after.get('file') != 'after.bin'
            or (directory/'after.bin').read_bytes() != expected):
        raise ValueError('Complete matching installation receipt/readback required')


def reset_verified(reader, expected, out):
    reader.phase = 'loader'
    if reader.online() != (3, 0x5e4017):
        raise ValueError('Unexpected dev-kit flash identity')
    reader.dump(out/'pre-reset.bin')
    if (out/'pre-reset.bin').read_bytes() != expected:
        raise ValueError('Current full flash differs; no reset')
    reader.log('reset_intent', cdb=RESET_CDB.hex(), retry=False, boot_observed=False)
    try:
        reader.cmd(0xFC0C)
    except (OSError, ValueError) as exc:
        # Reset can interrupt its own USB response. Never infer success or retry.
        result = dict(request_completed=False, error=str(exc), boot_observed=False)
    else:
        result = dict(request_completed=True, boot_observed=False)
    reader.log('reset_result', **result)
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ('device', 'usb-path', 'devnum'):
        ap.add_argument('--'+name, required=True)
    for name in ('target', 'transaction', 'out'):
        ap.add_argument('--'+name, type=Path, required=True)
    a = ap.parse_args()
    expected = a.target.read_bytes()
    verify_transaction(a.transaction, expected)
    # One attempt per installation, even if a new output directory is requested.
    with (a.transaction/'.core-reset-attempted').open('xb') as marker:
        marker.write(b'one attempt; observe UART separately\n')
        marker.flush()
        os.fsync(marker.fileno())
    a.out.mkdir(mode=0o700, parents=True, exist_ok=False)
    with (a.out/'commands.jsonl').open('x') as fp:
        os.chmod(fp.name, 0o600)
        def log(event, **fields):
            fp.write(json.dumps(dict(time=time.time(), event=event, **fields))+'\n')
            fp.flush()
            if event != 'command':
                os.fsync(fp.fileno())
        reader = ResetReader(a.device, log)
        try:
            if reader.usb.name != a.usb_path or (reader.usb/'devnum').read_text().strip() != a.devnum:
                raise ValueError('USB connection changed; no command')
            result = reset_verified(reader, expected, a.out)
            (a.out/'receipt.json').write_text(json.dumps(result, indent=2)+'\n')
            print(json.dumps(result), flush=True)
        finally:
            reader.close()


if __name__ == '__main__':
    main()
