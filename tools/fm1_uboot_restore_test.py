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

SECTOR = 0xD8000
SECTOR_BYTES = 4096
PATTERN = bytes((i*73+19) & 255 for i in range(SECTOR_BYTES))


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


def test_sector(reader, baseline):
    if len(baseline)!=FLASH_SIZE or baseline[SECTOR:SECTOR+SECTOR_BYTES] != b'\xff'*SECTOR_BYTES:
        raise ValueError('Baseline does not prove the entire scratch sector is FF')
    if reader.sector() != b'\xff'*SECTOR_BYTES:
        raise ValueError('Scratch sector changed since the full baseline; no write')
    reader.online()
    started=False
    try:
        # Initial sector is FF, so no erase is needed before this known pattern.
        started=True
        for offset in range(0,SECTOR_BYTES,CHUNK):
            reader.cmd(0xFB04,address=SECTOR+offset,payload=PATTERN[offset:offset+CHUNK])
        if reader.sector()!=PATTERN:
            raise ValueError('Pattern readback mismatch')
        reader.log('pattern_verified',sector=SECTOR,bytes=SECTOR_BYTES,sha256=hashlib.sha256(PATTERN).hexdigest())
    finally:
        if started:
            # Even a partial program or a mismatched readback needs restoration.
            reader.online()
            reader.cmd(0xFB01,address=SECTOR)
            if reader.sector()!=b'\xff'*SECTOR_BYTES:
                raise ValueError('Scratch-sector restore failed; retain backups and stop')
            reader.log('sector_restored',sector=SECTOR,bytes=SECTOR_BYTES)


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
    ap.add_argument('--test-unused-sector',action='store_true',help='explicitly enable the fixed program/restore proof')
    args=ap.parse_args()
    if not args.test_unused_sector:
        raise SystemExit('Explicit --test-unused-sector required')
    old=checked_backup(args.backup)
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
            if a['sha256']!=b['sha256'] or before[:0xD9000]!=old[:0xD9000]:
                raise ValueError('Fresh backups differ, or code/scratch differs from previous 092 backup')
            test_sector(reader,before)
            reader.online()
            after=reader.dump(args.out/'after.bin')
            if after['sha256']!=a['sha256']:
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
