"""Public tests contain no private factory or diagnostic firmware bytes."""
import binascii
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import devkit_flash_transaction as tx


def test_unpinned_images_rejected():
    with pytest.raises(ValueError, match='Exact private'):
        tx.validate_images(bytes(tx.backup.FLASH_SIZE), bytes(tx.backup.FLASH_SIZE))


def test_all_other_opcodes_denied():
    desired = bytes(tx.backup.FLASH_SIZE)
    for op in range(65536):
        if op in (0xFB01, 0xFB04, 0xFD05, 0xFC0A, 0xFC14):
            continue
        with pytest.raises(ValueError, match='forbidden'):
            tx.mutation_request(op, 0x4000, b'', desired)


@pytest.mark.parametrize('address', [0, 0x3000, 0x4001, 0x2c000, 0x7ff000, 0x800000])
def test_erase_outside_exact_sectors_denied(address):
    with pytest.raises(ValueError):
        tx.mutation_request(0xFB01, address, b'', bytes(tx.backup.FLASH_SIZE))


def test_erase_and_program_framing():
    desired = bytes(range(256))*32768
    for a in (0x4000, 0x2b000):
        cdb, payload, count = tx.mutation_request(0xFB01, a, b'', desired)
        assert cdb == (b'\xfb\x01'+a.to_bytes(4, 'big')).ljust(16, b'\xff')
        assert payload == b'' and count == 16
    a = 0x2bf00
    page = desired[a:a+256]
    cdb, payload, count = tx.mutation_request(0xFB04, a, page, desired)
    assert cdb[:9] == b'\xfb\x04\x00\x02\xbf\x00\x01\x00\x00'
    assert cdb[9:11] == binascii.crc_hqx(page, 0).to_bytes(2, 'little')
    assert payload == page and count == 0


@pytest.mark.parametrize('address,size', [(0x4001,256),(0x3f00,256),(0x2c000,256),(0x4000,255)])
def test_bad_program_ranges_denied(address, size):
    with pytest.raises(ValueError):
        tx.mutation_request(0xFB04, address, bytes(size), bytes(tx.backup.FLASH_SIZE))


def test_wrong_program_bytes_denied():
    with pytest.raises(ValueError):
        tx.mutation_request(0xFB04, 0x4000, b'\xff'*256, bytes(tx.backup.FLASH_SIZE))


def test_protected_bytes_include_entire_tail_and_boot():
    original = bytes(tx.backup.FLASH_SIZE)
    for address, allowed in ((0,False),(0x3fff,False),(0x4000,True),
                             (0x2bfff,True),(0x2c000,False),(0x7fffff,False)):
        changed = bytearray(original)
        changed[address] = 1
        assert tx.protected_equal(changed, original) == allowed


def test_reviewed_audio_plan_has_its_own_fixed_bounds():
    assert tx.IMAGE_PLANS[tx.TARGET_SHA] == tx.ALLOWED
    assert tx.IMAGE_PLANS[tx.AUDIO_TARGET_SHA] == tx.AUDIO_ALLOWED
    assert tx.IMAGE_PLANS[tx.AUDIO_V3_TARGET_SHA] == tx.AUDIO_ALLOWED
    assert tx.IMAGE_PLANS[tx.AUDIO_CONTROL_TARGET_SHA] == tx.AUDIO_ALLOWED
    assert tx.IMAGE_PLANS[tx.FM6_RAM_CONTROL_TARGET_SHA] == tx.FM6_ALLOWED
    assert tx.AUDIO_CONTROL_TARGET_SHA == 'ba8b03938e0b2a90461a728646a31f7de72975df282e9c1931750400cadaaaa6'
    assert tx.IMAGE_PLANS[tx.AUDIO_CONTROL_V2_TARGET_SHA] == tx.AUDIO_ALLOWED
    assert tx.AUDIO_CONTROL_V2_TARGET_SHA == '1bbaf5ae4ddf6a6fc6289c095f0f4b4361913b436b616f6c1f9e43d7da4cad25'
    assert tx.AUDIO_V3_TARGET_SHA != tx.AUDIO_TARGET_SHA
    desired = bytes(tx.backup.FLASH_SIZE)
    # The newer image's two additional sectors are not opened for v6.
    for address in (0x2c000, 0x2d000):
        with pytest.raises(ValueError):
            tx.mutation_request(0xFB01, address, b'', desired)
        tx.mutation_request(0xFB01, address, b'', desired, tx.AUDIO_ALLOWED)
    for address in (0x3000, 0x2e000, 0x7ff000):
        with pytest.raises(ValueError):
            tx.mutation_request(0xFB01, address, b'', desired, tx.AUDIO_ALLOWED)
    changed = bytearray(desired)
    changed[0x2dfff] = 1
    assert tx.protected_equal(changed, desired, tx.AUDIO_ALLOWED)
    changed[0x2e000] = 1
    assert not tx.protected_equal(changed, desired, tx.AUDIO_ALLOWED)


def test_fm6_plan_cannot_expand_other_images():
    assert tx.FM6_CONTROL_TARGET_SHA == '79e0cc9bb394415f544f2e9a33ea8e6cfab2ae70120ca9590b1eb32c1d629789'
    assert tx.IMAGE_PLANS[tx.FM6_CONTROL_TARGET_SHA] == tx.FM6_ALLOWED
    assert len(tx.FM6_ALLOWED) == 51
    desired = bytes(tx.backup.FLASH_SIZE)
    for address in (0x2e000, 0x36000):
        for allowed in (tx.ALLOWED, tx.AUDIO_ALLOWED):
            with pytest.raises(ValueError):
                tx.mutation_request(0xFB01, address, b'', desired, allowed)
        tx.mutation_request(0xFB01, address, b'', desired, tx.FM6_ALLOWED)
    for address in (0x3000, 0x37000, 0x7ff000):
        with pytest.raises(ValueError):
            tx.mutation_request(0xFB01, address, b'', desired, tx.FM6_ALLOWED)
    changed = bytearray(desired)
    changed[0x36fff] = 1
    assert tx.protected_equal(changed, desired, tx.FM6_ALLOWED)
    changed[0x37000] = 1
    assert not tx.protected_equal(changed, desired, tx.FM6_ALLOWED)
