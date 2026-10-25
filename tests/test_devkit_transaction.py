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
    assert tx.IMAGE_PLANS[tx.FM6_AUDIO_TARGET_SHA] == tuple(range(0x4000, 0x3a000, 4096))
    assert tx.IMAGE_PLANS[tx.FM6_AUDIO_V2_TARGET_SHA] == tuple(range(0x4000, 0x39000, 4096))
    assert tx.IMAGE_PLANS[tx.FM6_AUDIO_V3_TARGET_SHA] == tuple(range(0x4000, 0x39000, 4096))
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


@pytest.mark.parametrize('target_sha', [
    tx.RENDERER_TIMING_TARGET_SHA,
    tx.RENDERER_TIMING_V3_TARGET_SHA,
])
def test_renderer_plan_preserves_boot_tail_and_older_bounds(target_sha):
    allowed = tx.IMAGE_PLANS[target_sha]
    assert allowed == tuple(range(0x4000, 0x8a000, 4096))
    desired = bytes(tx.backup.FLASH_SIZE)
    tx.mutation_request(0xFB01, 0x89000, b'', desired, allowed)
    tx.mutation_request(0xFB04, 0x89f00, bytes(256), desired, allowed)
    for address in (0x3000, 0x8a000, 0x7ff000):
        with pytest.raises(ValueError):
            tx.mutation_request(0xFB01, address, b'', desired, allowed)
    for old in (tx.ALLOWED, tx.AUDIO_ALLOWED, tx.FM6_ALLOWED, tx.FM6_AUDIO_V2_ALLOWED):
        with pytest.raises(ValueError):
            tx.mutation_request(0xFB01, 0x89000, b'', desired, old)
    for address, permitted in ((0x3fff, False), (0x89fff, True), (0x8a000, False)):
        changed = bytearray(desired)
        changed[address] = 1
        assert tx.protected_equal(changed, desired, allowed) == permitted


@pytest.mark.parametrize("target_sha", [tx.RENDERER_PROFILE_TARGET_SHA, tx.RENDERER_HOT_TARGET_SHA, tx.RENDERER_SINE_TARGET_SHA, tx.RENDERER_RECOVERY_TARGET_SHA, tx.RENDERER_STAGES_TARGET_SHA, tx.RENDERER_VCF_TARGET_SHA, tx.RENDERER_ARITHMETIC_TARGET_SHA, tx.RENDERER_RESAMPLER_TARGET_SHA, tx.RENDERER_CACHE_TARGET_SHA, tx.RENDERER_FX_TARGET_SHA, tx.RENDERER_OUTLINE_TARGET_SHA, tx.RENDERER_FILTER_TARGET_SHA, tx.RENDERER_FILTER_STACK_TARGET_SHA, tx.RENDERER_CONTROL_TARGET_SHA, tx.RENDERER_PLAITS_CACHE_TARGET_SHA])
def test_renderer_profile_extra_sector_is_image_specific(target_sha):
    allowed = tx.IMAGE_PLANS[target_sha]
    assert allowed == tuple(range(0x4000, 0x8b000, 4096))
    desired = bytes(tx.backup.FLASH_SIZE)
    tx.mutation_request(0xFB01, 0x8a000, b'', desired, allowed)
    tx.mutation_request(0xFB04, 0x8af00, bytes(256), desired, allowed)
    for sha, other in tx.IMAGE_PLANS.items():
        if sha not in (tx.RENDERER_DISPATCH_TARGET_SHA, tx.RENDERER_KEYS_TARGET_SHA, tx.RENDERER_SCHEDULE_TARGET_SHA, tx.RENDERER_MIXER_TARGET_SHA, tx.RENDERER_O3_TARGET_SHA, tx.RENDERER_UNROLL_TARGET_SHA, tx.RENDERER_DETAIL_TARGET_SHA, tx.RENDERER_SLOPES_TARGET_SHA, tx.RENDERER_PROFILE_TARGET_SHA, tx.RENDERER_HOT_TARGET_SHA, tx.RENDERER_SINE_TARGET_SHA, tx.RENDERER_RECOVERY_TARGET_SHA, tx.RENDERER_STAGES_TARGET_SHA, tx.RENDERER_VCF_TARGET_SHA, tx.RENDERER_ARITHMETIC_TARGET_SHA, tx.RENDERER_RESAMPLER_TARGET_SHA, tx.RENDERER_CACHE_TARGET_SHA, tx.RENDERER_FX_TARGET_SHA, tx.RENDERER_OUTLINE_TARGET_SHA, tx.RENDERER_FILTER_TARGET_SHA, tx.RENDERER_FILTER_STACK_TARGET_SHA, tx.RENDERER_CONTROL_TARGET_SHA, tx.RENDERER_PLAITS_CACHE_TARGET_SHA):
            with pytest.raises(ValueError):
                tx.mutation_request(0xFB01, 0x8a000, b'', desired, other)
    for address in (0x3000, 0x8b000, 0x7ff000):
        with pytest.raises(ValueError):
            tx.mutation_request(0xFB01, address, b'', desired, allowed)
    for address, permitted in ((0x3fff, False), (0x8afff, True), (0x8b000, False)):
        changed = bytearray(desired)
        changed[address] = 1
        assert tx.protected_equal(changed, desired, allowed) == permitted


@pytest.mark.parametrize('target_sha', [tx.RENDERER_SLOPES_TARGET_SHA,
                                      tx.RENDERER_DETAIL_TARGET_SHA,
                                      tx.RENDERER_UNROLL_TARGET_SHA])
def test_reviewed_136_sector_images_preserve_older_bounds(target_sha):
    assert tx.RENDERER_SLOPES_TARGET_SHA == '7f1d2286a353084c681258556294b8309d3121fc66c301f80832c98b455f6d34'
    assert tx.RENDERER_DETAIL_TARGET_SHA == '57a605672d17ae479e8db05f9bacc12fd84bce49940da7c46a56130b352b3027'
    assert tx.RENDERER_UNROLL_TARGET_SHA == '92d1e3f1fdea9e5a73961f0d88d683527012026a2c5302bbbda2a9d8288f457e'
    allowed = tx.IMAGE_PLANS[target_sha]
    assert allowed == tuple(range(0x4000, 0x8c000, 4096))
    desired = bytes(tx.backup.FLASH_SIZE)
    tx.mutation_request(0xFB01, 0x8b000, b'', desired, allowed)
    tx.mutation_request(0xFB04, 0x8bf00, bytes(256), desired, allowed)
    for sha, older in tx.IMAGE_PLANS.items():
        if sha not in (tx.RENDERER_DISPATCH_TARGET_SHA, tx.RENDERER_KEYS_TARGET_SHA, tx.RENDERER_SCHEDULE_TARGET_SHA, tx.RENDERER_MIXER_TARGET_SHA, tx.RENDERER_O3_TARGET_SHA, tx.RENDERER_SLOPES_TARGET_SHA, tx.RENDERER_DETAIL_TARGET_SHA, tx.RENDERER_UNROLL_TARGET_SHA):
            with pytest.raises(ValueError):
                tx.mutation_request(0xFB01, 0x8b000, b'', desired, older)
    for address in (0x3000, 0x8c000, 0x7ff000):
        with pytest.raises(ValueError):
            tx.mutation_request(0xFB01, address, b'', desired, allowed)
    for address, permitted in ((0x3fff, False), (0x8bfff, True), (0x8c000, False)):
        changed = bytearray(desired)
        changed[address] = 1
        assert tx.protected_equal(changed, desired, allowed) == permitted


@pytest.mark.parametrize('target_sha', [tx.RENDERER_O3_TARGET_SHA, tx.RENDERER_MIXER_TARGET_SHA, tx.RENDERER_SCHEDULE_TARGET_SHA])
def test_renderer_o3_extra_sectors_are_exact_image_only(target_sha):
    assert tx.RENDERER_O3_TARGET_SHA == 'fd32ec039217b59762efc09b185dd25871420c47db689ffa626b07d3e183adf3'
    assert tx.RENDERER_MIXER_TARGET_SHA == 'ccee05d465d396d5749b9d70b6cf8387c2bca100040b654af8f6306dc539e416'
    assert tx.RENDERER_SCHEDULE_TARGET_SHA == 'fe4a860bcbebd57bee05ff94c3dffb613f2914163f1d302bdb007ccc14016512'
    allowed = tx.IMAGE_PLANS[target_sha]
    assert allowed == tuple(range(0x4000, 0x8e000, 4096))
    desired = bytes(tx.backup.FLASH_SIZE)
    for address in (0x8c000, 0x8d000):
        tx.mutation_request(0xFB01, address, b'', desired, allowed)
        tx.mutation_request(0xFB04, address + 0xf00, bytes(256), desired, allowed)
        for sha, older in tx.IMAGE_PLANS.items():
            if sha not in (tx.RENDERER_O3_TARGET_SHA, tx.RENDERER_MIXER_TARGET_SHA, tx.RENDERER_SCHEDULE_TARGET_SHA) and not (sha in (tx.RENDERER_KEYS_TARGET_SHA, tx.RENDERER_DISPATCH_TARGET_SHA) and address == 0x8c000):
                with pytest.raises(ValueError):
                    tx.mutation_request(0xFB01, address, b'', desired, older)
    for address in (0x3000, 0x8e000, 0x7ff000):
        with pytest.raises(ValueError):
            tx.mutation_request(0xFB01, address, b'', desired, allowed)
    for address, permitted in ((0x3fff, False), (0x8dfff, True), (0x8e000, False)):
        changed = bytearray(desired)
        changed[address] = 1
        assert tx.protected_equal(changed, desired, allowed) == permitted


def test_named_keys_image_has_its_own_narrower_bounds():
    assert tx.RENDERER_KEYS_TARGET_SHA == 'bee9d4bc83cc78e1c1a4a40448dc4211f2d8276cb6a8cad5878c9c5d7ee2aa36'
    allowed = tx.IMAGE_PLANS[tx.RENDERER_KEYS_TARGET_SHA]
    assert allowed == tuple(range(0x4000, 0x8d000, 4096))
    desired = bytes(tx.backup.FLASH_SIZE)
    tx.mutation_request(0xFB01, 0x8c000, b'', desired, allowed)
    tx.mutation_request(0xFB04, 0x8cf00, bytes(256), desired, allowed)
    for address in (0x3000, 0x8d000, 0x7ff000):
        with pytest.raises(ValueError):
            tx.mutation_request(0xFB01, address, b'', desired, allowed)
    for address, permitted in ((0x3fff, False), (0x8cfff, True), (0x8d000, False)):
        changed = bytearray(desired)
        changed[address] = 1
        assert tx.protected_equal(changed, desired, allowed) == permitted


def test_dispatch_image_keeps_keys_boundary_and_separate_hash():
    assert tx.RENDERER_DISPATCH_TARGET_SHA == '356c0b070d8ac6483fd8034767777b8c5dc13c25d04227c9f63dccaf3b1523e8'
    assert tx.RENDERER_DISPATCH_TARGET_SHA != tx.RENDERER_KEYS_TARGET_SHA
    assert tx.IMAGE_PLANS[tx.RENDERER_DISPATCH_TARGET_SHA] == tuple(range(0x4000, 0x8d000, tx.SECTOR))
