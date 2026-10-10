"""Bounded dump tool cannot issue erase, flash-write, key-write or config commands."""
import importlib.util
from pathlib import Path
import binascii

import pytest

spec=importlib.util.spec_from_file_location('uboot_read', Path(__file__).resolve().parents[1]/'tools/fm1_uboot_read.py')
p=importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


def test_every_opcode_outside_phase_allowlist_is_rejected():
    for phase, allowed in [('rom',{0x12,0xFB06,0xFB08}),('loader',{0xFC14,0xFC0A,0xFD05})]:
        for op in range(65536):
            if op not in allowed:
                with pytest.raises(ValueError):
                    p.request(op,phase)


def test_ram_upload_never_reaches_config_or_flash():
    data=bytes(range(256))*2
    cdb,out,n=p.request(0xFB06,'rom',address=p.RAM,payload=data)
    assert out==data and n==0
    assert cdb[:2]==b'\xfb\x06' and cdb[9:11]==binascii.crc_hqx(data,0).to_bytes(2,'little')
    for address in (0,p.RAM-512,p.RAM+1,p.RAM+p.LOADER_SIZE,0x01C07E00):
        with pytest.raises(ValueError):
            p.request(0xFB06,'rom',address=address,payload=data)
    for size in (0,256,513):
        with pytest.raises(ValueError):
            p.request(0xFB06,'rom',address=p.RAM,payload=bytes(size))


def test_jump_has_only_audited_entry_and_argument():
    cdb,out,n=p.request(0xFB08,'rom',address=p.RAM)
    assert cdb==b'\xfb\x08'+p.RAM.to_bytes(4,'big')+b'\x00\x01'+b'\xff'*8
    for address in (0,p.RAM+4):
        with pytest.raises(ValueError):
            p.request(0xFB08,'rom',address=address)


def test_flash_reads_are_256_byte_aligned_and_bounded():
    for address in (0,p.FLASH_SIZE-256):
        cdb,out,n=p.request(0xFD05,'loader',address=address)
        assert n==256 and not out and cdb[6:8]==b'\x01\x00'
    for address in (-256,1,p.FLASH_SIZE):
        with pytest.raises(ValueError):
            p.request(0xFD05,'loader',address=address)


def test_online_never_appends_configuration_magic():
    for op in (0xFC0A,0xFC14):
        cdb,out,n=p.request(op,'loader')
        assert cdb[2:]==b'\xff'*14 and n==16 and not out
        with pytest.raises(ValueError):
            p.request(op,'loader',payload=b'_0')


def test_loader_hash_rejected_before_first_usb_command():
    reader=p.Reader.__new__(p.Reader)
    reader.cmd=lambda *a,**k: pytest.fail('must not touch device')
    with pytest.raises(ValueError):
        reader.load(bytes(p.LOADER_SIZE))
