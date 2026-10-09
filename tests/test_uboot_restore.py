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


def test_changed_sector_prevents_all_writes():
    r=Mock(); r.sector.return_value=b'\x00'*SECTOR_BYTES
    with pytest.raises(ValueError): exercise_sector(r,b'\xff'*FLASH_SIZE)
    r.cmd.assert_not_called()


def test_partial_program_still_attempts_original_sector_restore():
    r=Mock()
    r.sector.side_effect=[b'\xff'*SECTOR_BYTES,b'\xff'*SECTOR_BYTES]
    def command(op,**kwargs):
        if op==0xFB04: raise OSError('simulated partial program')
    r.cmd.side_effect=command
    with pytest.raises(OSError): exercise_sector(r,b'\xff'*FLASH_SIZE)
    assert [c.args[0] for c in r.cmd.call_args_list]==[0xFB04,0xFB01]
