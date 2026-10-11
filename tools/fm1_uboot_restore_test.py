#!/usr/bin/env python3
"""Bounded restore proof: test pattern in ONE unused 4 KiB sector, then restore FF.

Fixed FM-1_092 scratch range [D8000,D9000), verified FF in two full backups.
No boot/app/VM/USR/key sector, other write range, arbitrary payload, chip erase
or eFuse operation is permitted. Requires an explicitly requested test and
an active, previously audited loader session. MIT licence.
"""
import argparse
import binascii
import hashlib
import json
import os
from pathlib import Path
import time

from fm1_uboot_read import Reader, request, CHUNK, FLASH_SIZE, LOADER_SHA
from fm1_flash_transaction import create_transaction, load_transaction, run_transaction

SECTOR = 0xD8000
SECTOR_BYTES = 4096
PATTERN = bytes((i*73+19) & 255 for i in range(SECTOR_BYTES))
SCOPE = 'FM-1_092 fixed unused-sector proof'


def restore_request(op, phase, *, address=0, payload=b''):
    if op == 0xFB01:
        if phase != 'loader' or address != SECTOR or payload:
            raise ValueError('Erase only the fixed scratch sector, without parameters')
        return (op.to_bytes(2,'big')+address.to_bytes(4,'big')).ljust(16,b'\xff'), b'', 16
    if op == 0xFB04:
        offset=address-SECTOR
        if (phase != 'loader' or offset % CHUNK or not 0 <= offset <= SECTOR_BYTES-CHUNK
                or payload != PATTERN[offset:offset+CHUNK]):
            raise ValueError('Program only the fixed scratch pattern within its sector')
        cdb=(op.to_bytes(2,'big')+address.to_bytes(4,'big')+CHUNK.to_bytes(2,'big')
             +b'\x00'+binascii.crc_hqx(payload,0).to_bytes(2,'little')).ljust(16,b'\xff')
        return cdb,payload,0
    return request(op,phase,address=address,payload=payload)


class RestoreReader(Reader):
    def build_request(self,op,address,payload):
        return restore_request(op,self.phase,address=address,payload=payload)

    def sector(self):
        return b''.join(self.cmd(0xFD05,address=a) for a in range(SECTOR,SECTOR+SECTOR_BYTES,CHUNK))

    def identity(self):
        # The USB port is a session binding, not a silicon serial number. Full
        # immutable flash comparison additionally binds this owner backup.
        return {'unit_id': 'FM-1_092@' + self.usb.name, 'flash_size': FLASH_SIZE,
                'sector_size': SECTOR_BYTES, 'page_size': CHUNK,
                'jedec': 0x856014, 'simulated': False}

    def read(self, address, size):
        if (address % CHUNK or size % CHUNK or size <= 0 or
                not 0 <= address <= FLASH_SIZE-size):
            raise ValueError('Aligned bounded flash reads only')
        return b''.join(self.cmd(0xFD05, address=a)
                        for a in range(address, address+size, CHUNK))

    def erase(self, address):
        self.cmd(0xFB01, address=address)

    def program(self, address, data):
        self.cmd(0xFB04, address=address, payload=data)


def checked_scratch_transaction(directory):
    plan, journal, baseline, target = load_transaction(directory)
    expected = baseline[:SECTOR] + PATTERN + baseline[SECTOR+SECTOR_BYTES:]
    if (plan['scope'] != SCOPE or plan['identity']['simulated'] is not False or
            plan['writable_ranges'] != [[SECTOR, SECTOR+SECTOR_BYTES]] or
            baseline[SECTOR:SECTOR+SECTOR_BYTES] != b'\xff'*SECTOR_BYTES or
            target != expected):
        raise ValueError('Only the fixed physical scratch transaction is permitted')
    return plan, journal, baseline, target


def test_sector(reader, baseline, transaction=None, baseline_b=None):
    if len(baseline)!=FLASH_SIZE or baseline[SECTOR:SECTOR+SECTOR_BYTES] != b'\xff'*SECTOR_BYTES:
        raise ValueError('Baseline does not prove the entire scratch sector is FF')
    if transaction is None or baseline_b != baseline:
        raise ValueError('Durable transaction and two matching fresh backups required')
    if reader.sector() != b'\xff'*SECTOR_BYTES:
        raise ValueError('Scratch sector changed since the full baseline; no write')
    target = baseline[:SECTOR] + PATTERN + baseline[SECTOR+SECTOR_BYTES:]
    create_transaction(transaction, baseline, baseline_b, target, reader.identity(),
                       ((SECTOR, SECTOR+SECTOR_BYTES),), SCOPE)
    checked_scratch_transaction(transaction)
    run_transaction(transaction, reader)
    reader.log('pattern_verified', sector=SECTOR, bytes=SECTOR_BYTES,
               sha256=hashlib.sha256(PATTERN).hexdigest())
    # An error above exits with durable recovery intent. Do not issue an erase
    # on the potentially stale handle inside finally, masking the first error.
    run_transaction(transaction, reader, direction='restore')
    reader.log('sector_restored', sector=SECTOR, bytes=SECTOR_BYTES)


def checked_backup(directory):
    m=json.loads((directory/'manifest.json').read_text())
    if m.get('loader_sha256')!=LOADER_SHA or m.get('identical') is not True:
        raise ValueError('Need the audited-loader matching full-backup manifest')
    copies=[]
    for name in ('dumpA.bin','dumpB.bin'):
        data=(directory/name).read_bytes()
        records=[r for r in m['dumps'] if r['file']==name]
        if len(data)!=FLASH_SIZE or len(records)!=1 or hashlib.sha256(data).hexdigest()!=records[0]['sha256']:
            raise ValueError('Private backup is incomplete or hash mismatch')
        copies.append(data)
    if copies[0]!=copies[1] or copies[0][SECTOR:SECTOR+SECTOR_BYTES]!=b'\xff'*SECTOR_BYTES:
        raise ValueError('Two matching backups must show scratch sector unused/FF')
    return copies[0]


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--device',required=True)
    ap.add_argument('--backup',required=True,type=Path)
    ap.add_argument('--out',required=True,type=Path)
    mode=ap.add_mutually_exclusive_group(required=True)
    mode.add_argument('--test-unused-sector',action='store_true',help='enable the fixed program/restore proof')
    mode.add_argument('--recover-unused-sector',action='store_true',help='restore only the prior fixed scratch transaction to FF')
    ap.add_argument('--transaction',type=Path,help='existing durable transaction, required only for recovery')
    args=ap.parse_args()
    if args.recover_unused_sector != (args.transaction is not None):
        raise SystemExit('--transaction is required only with --recover-unused-sector')
    old=checked_backup(args.backup)
    if args.recover_unused_sector:
        _, _, saved, _ = checked_scratch_transaction(args.transaction)
        if saved[:SECTOR+SECTOR_BYTES] != old[:SECTOR+SECTOR_BYTES]:
            raise SystemExit('Transaction differs from the checked owner backup')
    args.out.mkdir(mode=0o700,parents=True,exist_ok=False)
    with (args.out/'commands.jsonl').open('x') as fp:
        def log(event,**fields):
            fp.write(json.dumps({'time':time.time(),'event':event,**fields})+'\n'); fp.flush(); os.fsync(fp.fileno())
        reader=None
        try:
            reader=RestoreReader(args.device,log)
            # No loader reupload; only a live session that answers the flash query.
            reader.phase='loader'
            reader.online()
            a=reader.dump(args.out/'beforeA.bin')
            reader.online()
            b=reader.dump(args.out/'beforeB.bin')
            before=(args.out/'beforeA.bin').read_bytes()
            if a['sha256']!=b['sha256']:
                raise ValueError('Fresh backups differ; no write')
            if args.recover_unused_sector:
                result=run_transaction(args.transaction,reader,direction='restore')
                log('resumed_scratch_restore', receipt=result)
            elif before[:0xD9000]!=old[:0xD9000]:
                raise ValueError('Fresh backups differ, or code/scratch differs from previous 092 backup')
            else:
                test_sector(reader,before,args.out/'transaction',
                            (args.out/'beforeB.bin').read_bytes())
            reader.online()
            after=reader.dump(args.out/'after.bin')
            expected=(hashlib.sha256(saved).hexdigest() if args.recover_unused_sector
                      else a['sha256'])
            if after['sha256']!=expected:
                raise ValueError('Full-flash hash changed after restore; keep all backups')
            m={'scope':'one unused 4 KiB sector, not full flash rewrite','sector':SECTOR,
               'bytes':SECTOR_BYTES,'before':[a,b],'after':after,'full_flash_identical':True}
            with (args.out/'manifest.json').open('x') as f:
                json.dump(m,f,indent=2); f.flush(); os.fsync(f.fileno())
            log('restore_complete',manifest=m); fp.flush(); os.fsync(fp.fileno())
            print(json.dumps(m),flush=True)
        except Exception as exc:
            log('stopped',error=str(exc)); fp.flush(); os.fsync(fp.fileno())
            print(f'Stopped: {exc}',flush=True)
            raise SystemExit(1) from exc
        finally:
            if reader is not None: reader.close()


if __name__=='__main__':
    main()
