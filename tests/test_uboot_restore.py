"""The restore proof cannot become an arbitrary flash writer."""
import importlib.util
from pathlib import Path
import sys
from unittest.mock import Mock

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from fm1_uboot_restore_test import restore_request, test_sector as exercise_sector, PATTERN, SECTOR, SECTOR_BYTES, FLASH_SIZE


def test_erase_is_one_fixed_sector_only():
    cdb,data,n=restore_request(0xFB01,'loader',address=SECTOR)
    assert cdb[2:6]==SECTOR.to_bytes(4,'big') and n==16 and not data
    for a in (0,0x4000,SECTOR-4096,SECTOR+4096,0xff000):
        with pytest.raises(ValueError): restore_request(0xFB01,'loader',address=a)
    with pytest.raises(ValueError): restore_request(0xFB01,'rom',address=SECTOR)


def test_program_cannot_change_other_ranges_or_payloads():
    for off in range(0,SECTOR_BYTES,256):
        _,data,n=restore_request(0xFB04,'loader',address=SECTOR+off,payload=PATTERN[off:off+256])
        assert len(data)==256 and n==0
    for a,data in [(SECTOR-256,PATTERN[:256]),(SECTOR+4096,PATTERN[:256]),(SECTOR+1,PATTERN[:256]),(SECTOR,b'\x00'*256)]:
        with pytest.raises(ValueError): restore_request(0xFB04,'loader',address=a,payload=data)


def test_chip_key_chip_erase_and_other_writes_rejected():
    for op in (0xFC12,0xFB02,0xFB00,0xFC0C,0xFC0D,0xA1,0x2a):
        with pytest.raises(ValueError): restore_request(op,'loader')


def test_nonblank_baseline_prevents_all_writes():
    r=Mock()
    with pytest.raises(ValueError): exercise_sector(r,b'\x00'*FLASH_SIZE)
    r.cmd.assert_not_called()


def test_changed_sector_prevents_all_writes(tmp_path):
    r=Mock(); r.sector.return_value=b'\x00'*SECTOR_BYTES
    baseline=b'\xff'*FLASH_SIZE
    transaction=tmp_path/'transaction'
    with pytest.raises(ValueError, match='Scratch sector changed'):
        exercise_sector(r,baseline,transaction,baseline)
    r.sector.assert_called_once()
    assert not transaction.exists()
    r.cmd.assert_not_called()


def test_missing_durable_backup_prevents_program_or_cleanup():
    r=Mock()
    with pytest.raises(ValueError, match='Durable transaction'):
        exercise_sector(r,b'\xff'*FLASH_SIZE)
    r.cmd.assert_not_called()


def test_transaction_reads_keep_loader_alive(monkeypatch):
    import fm1_uboot_restore_test as module
    reader=module.RestoreReader.__new__(module.RestoreReader)
    clock=[0.0]
    events=[]
    monkeypatch.setattr(module.time,'monotonic',lambda:clock[0])
    def command(op, *, address=0):
        events.append((op,address,clock[0]))
        clock[0]+=0.3
        return b'\x42'*256
    reader.cmd=command
    reader.online=lambda:events.append(('online',clock[0]))
    assert reader.read(0,256*6)==b'\x42'*(256*6)
    assert [e[0] for e in events]==[0xFD05,0xFD05,'online',0xFD05,
                                   0xFD05,'online',0xFD05,0xFD05]
    for address,size in ((1,256),(0,1),(0,0),(FLASH_SIZE,256)):
        with pytest.raises(ValueError):
            reader.read(address,size)
