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


def test_cpu1_probe_plan_is_narrow_and_preserves_renderer_restore_bounds():
    assert tx.CPU1_PUBLICATION_TARGET_SHA == '9d3d4f8c46ddf3a0edb3fce6abd5a7482a257f82c3b798ba87ec5460bce9f761'
    allowed = tx.IMAGE_PLANS[tx.CPU1_PUBLICATION_TARGET_SHA]
    assert allowed == tuple(range(0x4000, 0x2d000, 4096))
    assert len(allowed) == 41
    assert tx.CPU1_LONG_TARGET_SHA == '3bbfa865e5c3fd37c8babe9f01c9fe7e6d56f7d41e211488e26b57d71a8a5c23'
    assert tx.IMAGE_PLANS[tx.CPU1_LONG_TARGET_SHA] == allowed
    assert tx.CPU1_RING_TARGET_SHA == '0fd1dcb5ff74bf036f2c785144745bf2fe6254587a73b86bec4d3396fb9dfd09'
    assert tx.IMAGE_PLANS[tx.CPU1_RING_TARGET_SHA] == allowed
    assert tx.CPU1_RING_PHASE_TARGET_SHA == '43b911a84f17e0045e911249c495f967cc42087c33a996f87080c6e4d44b0455'
    assert tx.IMAGE_PLANS[tx.CPU1_RING_PHASE_TARGET_SHA] == allowed
    assert tx.IMAGE_PLANS[tx.RENDERER_FILTER_MONO_TARGET_SHA] == tuple(range(0x4000, 0x8d000, 4096))
    desired = bytes(tx.backup.FLASH_SIZE)
    tx.mutation_request(0xFB01, 0x2c000, b'', desired, allowed)
    tx.mutation_request(0xFB04, 0x2cf00, bytes(256), desired, allowed)
    for address in (0x3000, 0x2d000, 0x8c000, 0x7ff000):
        with pytest.raises(ValueError):
            tx.mutation_request(0xFB01, address, b'', desired, allowed)
        with pytest.raises(ValueError):
            tx.mutation_request(0xFB04, address, bytes(256), desired, allowed)
    changed = bytearray(desired)
    changed[0x2d000] = 1
    assert not tx.protected_equal(changed, desired, allowed)


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
    assert tx.RENDERER_FM6_KIND_RAM_TARGET_SHA == 'd4c443a8bfa97eba564bccd32b782d6c478954bf1fbe170c87e3f1cc72e73a58'
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
    assert tx.RENDERER_FM6_KIND_RAM_TARGET_SHA == 'd4c443a8bfa97eba564bccd32b782d6c478954bf1fbe170c87e3f1cc72e73a58'
    allowed = tx.IMAGE_PLANS[target_sha]
    assert allowed == tuple(range(0x4000, 0x8b000, 4096))
    desired = bytes(tx.backup.FLASH_SIZE)
    tx.mutation_request(0xFB01, 0x8a000, b'', desired, allowed)
    tx.mutation_request(0xFB04, 0x8af00, bytes(256), desired, allowed)
    for sha, other in tx.IMAGE_PLANS.items():
        if sha not in (tx.RENDERER_QUEUE_INSERT_V39_TARGET_SHA, tx.RENDERER_MODULE_MICRO_V38_TARGET_SHA, tx.RENDERER_MOD_MICRO_V37_TARGET_SHA, tx.RENDERER_ENV_FAST_V36_TARGET_SHA, tx.RENDERER_QUEUE_CONTROL_V35_TARGET_SHA, tx.RENDERER_QUEUE_MICRO_V34_TARGET_SHA, tx.RENDERER_DRIVE_SETTLED_V33_TARGET_SHA, tx.RENDERER_QUEUE_DETAIL_V32_TARGET_SHA, tx.RENDERER_QUEUE_REGION_V31_TARGET_SHA, tx.RENDERER_QUEUE_DRUMS_V30_TARGET_SHA, tx.RENDERER_QUEUE_V29_TARGET_SHA, tx.RENDERER_FM6_OUTER_TIMING_TARGET_SHA, tx.RENDERER_FM6_OSCILLATOR_SLOPES_TARGET_SHA, tx.RENDERER_FM6_VCF_PROFILE_TARGET_SHA, tx.RENDERER_FM6_VCF_UNROLL_TARGET_SHA, tx.RENDERER_FM6_ENGINE_PROFILE_TARGET_SHA, tx.RENDERER_FM6_MIXED_PIXELS_TARGET_SHA, tx.RENDERER_FM6_PLAN_RAM_TARGET_SHA, tx.RENDERER_FM6_EVENT_RAM_TARGET_SHA, tx.RENDERER_FM6_KIND_RAM_TARGET_SHA, tx.RENDERER_FM6_MODULE_RAM_TARGET_SHA, tx.RENDERER_FM6_NESTED_TARGET_SHA, tx.RENDERER_FM6_HOOK_RAM_TARGET_SHA, tx.RENDERER_FM6_DISPATCH_PROFILE_TARGET_SHA, tx.RENDERER_FM6_AUTO_TARGET_SHA, tx.RENDERER_FM6_PREP_TARGET_SHA, tx.RENDERER_FM6_UI_TARGET_SHA, tx.RENDERER_FM6_CLOCK_TARGET_SHA, tx.RENDERER_FM6_DETAIL_TARGET_SHA, tx.RENDERER_FM6_PAGE_CACHE_TARGET_SHA, tx.RENDERER_FM6_WORST_TARGET_SHA, tx.RENDERER_FM6_SCHEDULING_TARGET_SHA, tx.RENDERER_FM6_REFUSAL_TARGET_SHA, tx.RENDERER_FM6_POOL_TARGET_SHA, tx.RENDERER_FM6_STATIC_TARGET_SHA, tx.RENDERER_FM6_PAIR_TARGET_SHA, tx.RENDERER_FILTER_MONO_TARGET_SHA, tx.RENDERER_COMP_SETTLED_TARGET_SHA, tx.RENDERER_FM_PURE2_TARGET_SHA, tx.RENDERER_ROUTE_TARGET_SHA, tx.RENDERER_FM_SINE32_TARGET_SHA, tx.RENDERER_FM_NARROW_TARGET_SHA, tx.RENDERER_LED_GUARD_TARGET_SHA, tx.RENDERER_SESSION_TARGET_SHA, tx.RENDERER_DISPATCH_TARGET_SHA, tx.RENDERER_KEYS_TARGET_SHA, tx.RENDERER_SCHEDULE_TARGET_SHA, tx.RENDERER_MIXER_TARGET_SHA, tx.RENDERER_O3_TARGET_SHA, tx.RENDERER_UNROLL_TARGET_SHA, tx.RENDERER_DETAIL_TARGET_SHA, tx.RENDERER_SLOPES_TARGET_SHA, tx.RENDERER_PROFILE_TARGET_SHA, tx.RENDERER_HOT_TARGET_SHA, tx.RENDERER_SINE_TARGET_SHA, tx.RENDERER_RECOVERY_TARGET_SHA, tx.RENDERER_STAGES_TARGET_SHA, tx.RENDERER_VCF_TARGET_SHA, tx.RENDERER_ARITHMETIC_TARGET_SHA, tx.RENDERER_RESAMPLER_TARGET_SHA, tx.RENDERER_CACHE_TARGET_SHA, tx.RENDERER_FX_TARGET_SHA, tx.RENDERER_OUTLINE_TARGET_SHA, tx.RENDERER_FILTER_TARGET_SHA, tx.RENDERER_FILTER_STACK_TARGET_SHA, tx.RENDERER_CONTROL_TARGET_SHA, tx.RENDERER_PLAITS_CACHE_TARGET_SHA):
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
    assert tx.RENDERER_FM6_KIND_RAM_TARGET_SHA == 'd4c443a8bfa97eba564bccd32b782d6c478954bf1fbe170c87e3f1cc72e73a58'
    allowed = tx.IMAGE_PLANS[target_sha]
    assert allowed == tuple(range(0x4000, 0x8c000, 4096))
    desired = bytes(tx.backup.FLASH_SIZE)
    tx.mutation_request(0xFB01, 0x8b000, b'', desired, allowed)
    tx.mutation_request(0xFB04, 0x8bf00, bytes(256), desired, allowed)
    for sha, older in tx.IMAGE_PLANS.items():
        if sha not in (tx.RENDERER_QUEUE_INSERT_V39_TARGET_SHA, tx.RENDERER_MODULE_MICRO_V38_TARGET_SHA, tx.RENDERER_MOD_MICRO_V37_TARGET_SHA, tx.RENDERER_ENV_FAST_V36_TARGET_SHA, tx.RENDERER_QUEUE_CONTROL_V35_TARGET_SHA, tx.RENDERER_QUEUE_MICRO_V34_TARGET_SHA, tx.RENDERER_DRIVE_SETTLED_V33_TARGET_SHA, tx.RENDERER_QUEUE_DETAIL_V32_TARGET_SHA, tx.RENDERER_QUEUE_REGION_V31_TARGET_SHA, tx.RENDERER_QUEUE_DRUMS_V30_TARGET_SHA, tx.RENDERER_QUEUE_V29_TARGET_SHA, tx.RENDERER_FM6_OUTER_TIMING_TARGET_SHA, tx.RENDERER_FM6_OSCILLATOR_SLOPES_TARGET_SHA, tx.RENDERER_FM6_VCF_PROFILE_TARGET_SHA, tx.RENDERER_FM6_VCF_UNROLL_TARGET_SHA, tx.RENDERER_FM6_ENGINE_PROFILE_TARGET_SHA, tx.RENDERER_FM6_MIXED_PIXELS_TARGET_SHA, tx.RENDERER_FM6_PLAN_RAM_TARGET_SHA, tx.RENDERER_FM6_EVENT_RAM_TARGET_SHA, tx.RENDERER_FM6_KIND_RAM_TARGET_SHA, tx.RENDERER_FM6_MODULE_RAM_TARGET_SHA, tx.RENDERER_FM6_NESTED_TARGET_SHA, tx.RENDERER_FM6_HOOK_RAM_TARGET_SHA, tx.RENDERER_FM6_DISPATCH_PROFILE_TARGET_SHA, tx.RENDERER_FM6_AUTO_TARGET_SHA, tx.RENDERER_FM6_PREP_TARGET_SHA, tx.RENDERER_FM6_UI_TARGET_SHA, tx.RENDERER_FM6_CLOCK_TARGET_SHA, tx.RENDERER_FM6_DETAIL_TARGET_SHA, tx.RENDERER_FM6_PAGE_CACHE_TARGET_SHA, tx.RENDERER_FM6_WORST_TARGET_SHA, tx.RENDERER_FM6_SCHEDULING_TARGET_SHA, tx.RENDERER_FM6_REFUSAL_TARGET_SHA, tx.RENDERER_FM6_POOL_TARGET_SHA, tx.RENDERER_FM6_STATIC_TARGET_SHA, tx.RENDERER_FM6_PAIR_TARGET_SHA, tx.RENDERER_FILTER_MONO_TARGET_SHA, tx.RENDERER_COMP_SETTLED_TARGET_SHA, tx.RENDERER_FM_PURE2_TARGET_SHA, tx.RENDERER_ROUTE_TARGET_SHA, tx.RENDERER_FM_SINE32_TARGET_SHA, tx.RENDERER_FM_NARROW_TARGET_SHA, tx.RENDERER_LED_GUARD_TARGET_SHA, tx.RENDERER_SESSION_TARGET_SHA, tx.RENDERER_DISPATCH_TARGET_SHA, tx.RENDERER_KEYS_TARGET_SHA, tx.RENDERER_SCHEDULE_TARGET_SHA, tx.RENDERER_MIXER_TARGET_SHA, tx.RENDERER_O3_TARGET_SHA, tx.RENDERER_SLOPES_TARGET_SHA, tx.RENDERER_DETAIL_TARGET_SHA, tx.RENDERER_UNROLL_TARGET_SHA):
            with pytest.raises(ValueError):
                tx.mutation_request(0xFB01, 0x8b000, b'', desired, older)
    for address in (0x3000, 0x8c000, 0x7ff000):
        with pytest.raises(ValueError):
            tx.mutation_request(0xFB01, address, b'', desired, allowed)
    for address, permitted in ((0x3fff, False), (0x8bfff, True), (0x8c000, False)):
        changed = bytearray(desired)
        changed[address] = 1
        assert tx.protected_equal(changed, desired, allowed) == permitted


@pytest.mark.parametrize('target_sha', [tx.RENDERER_O3_TARGET_SHA, tx.RENDERER_MIXER_TARGET_SHA, tx.RENDERER_SCHEDULE_TARGET_SHA, tx.RENDERER_FM6_PAIR_TARGET_SHA, tx.RENDERER_FM6_STATIC_TARGET_SHA, tx.RENDERER_FM6_POOL_TARGET_SHA, tx.RENDERER_FM6_REFUSAL_TARGET_SHA, tx.RENDERER_FM6_SCHEDULING_TARGET_SHA, tx.RENDERER_FM6_WORST_TARGET_SHA, tx.RENDERER_FM6_PAGE_CACHE_TARGET_SHA, tx.RENDERER_FM6_DETAIL_TARGET_SHA, tx.RENDERER_FM6_CLOCK_TARGET_SHA, tx.RENDERER_FM6_UI_TARGET_SHA, tx.RENDERER_FM6_PREP_TARGET_SHA, tx.RENDERER_FM6_HOOK_RAM_TARGET_SHA, tx.RENDERER_FM6_DISPATCH_PROFILE_TARGET_SHA, tx.RENDERER_FM6_AUTO_TARGET_SHA])
def test_renderer_o3_extra_sectors_are_exact_image_only(target_sha):
    assert tx.RENDERER_FM6_CLOCK_TARGET_SHA == '2c0b53f53b8e8c240233b9c9233860b5fe4c68bf784e6e53d86145ac24763686'
    assert tx.RENDERER_FM6_HOOK_RAM_TARGET_SHA == 'b34e5f591b14bade352c60630aa394fba74f7cedbe0d7080f3481f34930cf27a'
    assert tx.RENDERER_FM6_DISPATCH_PROFILE_TARGET_SHA == 'd7b4d18c6b3a8506ab44244e393fe3f2b0640b3f996103aea18c46d19fec0cab'
    assert tx.RENDERER_FM6_AUTO_TARGET_SHA == '7353e97745fae6c2489a85e5ad1a90ab33cdf4b9660bf8561fe63f28e98c1d03'
    assert tx.RENDERER_FM6_PREP_TARGET_SHA == '8f705a96c211e8ec06896e99b4d86552a3fb8047eeebff61160b75e5503ca665'
    assert tx.RENDERER_FM6_UI_TARGET_SHA == '6d977407df3c892278e6d41cd15f4e7c1c4763e886fba36b6c99456e4bf73bc9'
    assert tx.RENDERER_FM6_REFUSAL_TARGET_SHA == 'b2b3ab557b788b6c8e500755e41be47db14986ed5aa6dfd6681c4aefd611f983'
    assert tx.RENDERER_FM6_SCHEDULING_TARGET_SHA == '14dd61780bca60ae1ea772cb925a068d7117539f81f4dd0fbccf5a8f9fc1a061'
    assert tx.RENDERER_FM6_DETAIL_TARGET_SHA == '344330443ae9cb9e11b95525b2d5fa58714df2397cf15656940a7a1de974a49a'
    assert tx.RENDERER_FM6_PAGE_CACHE_TARGET_SHA == 'cc85c192bffa3118f1e4d19b8caec85858d78a43c1790a7bf23abf90ca2fa178'
    assert tx.RENDERER_FM6_WORST_TARGET_SHA == 'fd8a5df8a0d10cf2ab7294c69e5f35b9e1717ba1199131e8c02c34097e891309'
    assert tx.RENDERER_FM6_POOL_TARGET_SHA == '718f09c30e9b4efe8fdf226926a3d0701bcab37609dbc4e2dbec7857f5580d25'
    assert tx.RENDERER_FM6_STATIC_TARGET_SHA == 'afdc2fa73bc27aff9ade73f8e10cb1ecdaa1d9e2c1f6e0e693d423af16fe322a'
    assert tx.RENDERER_FM6_PAIR_TARGET_SHA == '393f497566bf1ee9b709bdbd67adec23ecb0f216809afd632dffc66adfe7534a'
    assert tx.RENDERER_O3_TARGET_SHA == 'fd32ec039217b59762efc09b185dd25871420c47db689ffa626b07d3e183adf3'
    assert tx.RENDERER_MIXER_TARGET_SHA == 'ccee05d465d396d5749b9d70b6cf8387c2bca100040b654af8f6306dc539e416'
    assert tx.RENDERER_SCHEDULE_TARGET_SHA == 'fe4a860bcbebd57bee05ff94c3dffb613f2914163f1d302bdb007ccc14016512'
    assert tx.RENDERER_FM6_KIND_RAM_TARGET_SHA == 'd4c443a8bfa97eba564bccd32b782d6c478954bf1fbe170c87e3f1cc72e73a58'
    allowed = tx.IMAGE_PLANS[target_sha]
    assert allowed == tuple(range(0x4000, 0x8e000, 4096))
    desired = bytes(tx.backup.FLASH_SIZE)
    for address in (0x8c000, 0x8d000):
        tx.mutation_request(0xFB01, address, b'', desired, allowed)
        tx.mutation_request(0xFB04, address + 0xf00, bytes(256), desired, allowed)
        for sha, older in tx.IMAGE_PLANS.items():
            if sha not in (tx.RENDERER_QUEUE_INSERT_V39_TARGET_SHA, tx.RENDERER_MODULE_MICRO_V38_TARGET_SHA, tx.RENDERER_MOD_MICRO_V37_TARGET_SHA, tx.RENDERER_ENV_FAST_V36_TARGET_SHA, tx.RENDERER_QUEUE_CONTROL_V35_TARGET_SHA, tx.RENDERER_QUEUE_MICRO_V34_TARGET_SHA, tx.RENDERER_DRIVE_SETTLED_V33_TARGET_SHA, tx.RENDERER_QUEUE_DETAIL_V32_TARGET_SHA, tx.RENDERER_QUEUE_REGION_V31_TARGET_SHA, tx.RENDERER_QUEUE_DRUMS_V30_TARGET_SHA, tx.RENDERER_QUEUE_V29_TARGET_SHA, tx.RENDERER_FM6_OUTER_TIMING_TARGET_SHA, tx.RENDERER_FM6_OSCILLATOR_SLOPES_TARGET_SHA, tx.RENDERER_FM6_VCF_PROFILE_TARGET_SHA, tx.RENDERER_FM6_VCF_UNROLL_TARGET_SHA, tx.RENDERER_FM6_ENGINE_PROFILE_TARGET_SHA, tx.RENDERER_FM6_MIXED_PIXELS_TARGET_SHA, tx.RENDERER_FM6_PLAN_RAM_TARGET_SHA, tx.RENDERER_FM6_EVENT_RAM_TARGET_SHA, tx.RENDERER_FM6_KIND_RAM_TARGET_SHA, tx.RENDERER_FM6_MODULE_RAM_TARGET_SHA, tx.RENDERER_FM6_NESTED_TARGET_SHA, tx.RENDERER_FM6_HOOK_RAM_TARGET_SHA, tx.RENDERER_FM6_DISPATCH_PROFILE_TARGET_SHA, tx.RENDERER_FM6_AUTO_TARGET_SHA, tx.RENDERER_FM6_PREP_TARGET_SHA, tx.RENDERER_FM6_UI_TARGET_SHA, tx.RENDERER_FM6_CLOCK_TARGET_SHA, tx.RENDERER_FM6_DETAIL_TARGET_SHA, tx.RENDERER_FM6_PAGE_CACHE_TARGET_SHA, tx.RENDERER_FM6_WORST_TARGET_SHA, tx.RENDERER_FM6_SCHEDULING_TARGET_SHA, tx.RENDERER_FM6_REFUSAL_TARGET_SHA, tx.RENDERER_FM6_POOL_TARGET_SHA, tx.RENDERER_FM6_STATIC_TARGET_SHA, tx.RENDERER_FM6_PAIR_TARGET_SHA, tx.RENDERER_O3_TARGET_SHA, tx.RENDERER_MIXER_TARGET_SHA, tx.RENDERER_SCHEDULE_TARGET_SHA) and not (sha in (tx.RENDERER_FILTER_MONO_TARGET_SHA, tx.RENDERER_COMP_SETTLED_TARGET_SHA, tx.RENDERER_FM_PURE2_TARGET_SHA, tx.RENDERER_ROUTE_TARGET_SHA, tx.RENDERER_FM_SINE32_TARGET_SHA, tx.RENDERER_FM_NARROW_TARGET_SHA, tx.RENDERER_LED_GUARD_TARGET_SHA, tx.RENDERER_SESSION_TARGET_SHA, tx.RENDERER_KEYS_TARGET_SHA, tx.RENDERER_DISPATCH_TARGET_SHA) and address == 0x8c000):
                with pytest.raises(ValueError):
                    tx.mutation_request(0xFB01, address, b'', desired, older)
    for address in (0x3000, 0x8e000, 0x7ff000):
        with pytest.raises(ValueError):
            tx.mutation_request(0xFB01, address, b'', desired, allowed)
    for address, permitted in ((0x3fff, False), (0x8dfff, True), (0x8e000, False)):
        changed = bytearray(desired)
        changed[address] = 1
        assert tx.protected_equal(changed, desired, allowed) == permitted


@pytest.mark.parametrize("target_sha", [tx.RENDERER_KEYS_TARGET_SHA, tx.RENDERER_SESSION_TARGET_SHA, tx.RENDERER_LED_GUARD_TARGET_SHA, tx.RENDERER_FM_NARROW_TARGET_SHA, tx.RENDERER_FM_SINE32_TARGET_SHA, tx.RENDERER_ROUTE_TARGET_SHA, tx.RENDERER_FM_PURE2_TARGET_SHA, tx.RENDERER_COMP_SETTLED_TARGET_SHA, tx.RENDERER_FILTER_MONO_TARGET_SHA])
def test_named_keys_image_has_its_own_narrower_bounds(target_sha):
    assert tx.RENDERER_KEYS_TARGET_SHA == 'bee9d4bc83cc78e1c1a4a40448dc4211f2d8276cb6a8cad5878c9c5d7ee2aa36'
    assert tx.RENDERER_SESSION_TARGET_SHA == '6619c671eaf054db1e7c3e8873787f7a61a54940fd6a3faceb1971d73cf9c4eb'
    assert tx.RENDERER_FM_SINE32_TARGET_SHA == '4589d46ba8382c86ae7f05c6c60c8b3c8e3c8b0b942c811ffceefa03d1d2a7bf'
    assert tx.RENDERER_ROUTE_TARGET_SHA == 'e2fb418459789350793538d33ed82dfe5a43ade037c31211d65c84da23c40304'
    assert tx.RENDERER_FM_PURE2_TARGET_SHA == 'b8823c2a322aa47e28306ca11d423838438daa1328a393969c554ffedaf4ab98'
    assert tx.RENDERER_COMP_SETTLED_TARGET_SHA == 'f9233d22b81bcd3203e460fa602d2d2d6f00c75387347a5a997c642937f093f3'
    assert tx.RENDERER_FILTER_MONO_TARGET_SHA == '49ef7762bf3276e5e5ec150ca6d777f285b7b83f60b0ca5f1d771d60e2314a8e'
    assert tx.RENDERER_FM_NARROW_TARGET_SHA == '5370ec631766ddee6594a8648a0840c213dd1e37637d3c064cbc4a8a2412a2ab'
    assert tx.RENDERER_LED_GUARD_TARGET_SHA == 'f6c74b7b198dd1ac5e154862e39d09dded5a2cfa6dae4613528aa63b8d545f23'
    assert tx.RENDERER_FM6_KIND_RAM_TARGET_SHA == 'd4c443a8bfa97eba564bccd32b782d6c478954bf1fbe170c87e3f1cc72e73a58'
    allowed = tx.IMAGE_PLANS[target_sha]
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


@pytest.mark.parametrize('target_sha', [tx.RENDERER_FM6_NESTED_TARGET_SHA, tx.RENDERER_FM6_MODULE_RAM_TARGET_SHA, tx.RENDERER_FM6_KIND_RAM_TARGET_SHA])
def test_nested_dispatch_139th_sector_requires_its_exact_image(target_sha):
    assert tx.RENDERER_FM6_NESTED_TARGET_SHA == 'f68182d2e673abf012b5571c2e45cbfc3fc5d4cdb213e4bd70679461c35b2dfc'
    assert tx.RENDERER_FM6_MODULE_RAM_TARGET_SHA == '06f2087f64dd15dc882b247b15b90ca59f516c21502d1f964af760d095f06e22'
    assert tx.RENDERER_FM6_KIND_RAM_TARGET_SHA == 'd4c443a8bfa97eba564bccd32b782d6c478954bf1fbe170c87e3f1cc72e73a58'
    allowed = tx.IMAGE_PLANS[target_sha]
    assert allowed == tuple(range(0x4000, 0x8f000, 4096))
    desired = bytes(tx.backup.FLASH_SIZE)
    tx.mutation_request(0xFB01, 0x8e000, b'', desired, allowed)
    tx.mutation_request(0xFB04, 0x8ef00, bytes(256), desired, allowed)
    for sha, older in tx.IMAGE_PLANS.items():
        if sha not in (tx.RENDERER_QUEUE_INSERT_V39_TARGET_SHA, tx.RENDERER_MODULE_MICRO_V38_TARGET_SHA, tx.RENDERER_MOD_MICRO_V37_TARGET_SHA, tx.RENDERER_ENV_FAST_V36_TARGET_SHA, tx.RENDERER_QUEUE_CONTROL_V35_TARGET_SHA, tx.RENDERER_QUEUE_MICRO_V34_TARGET_SHA, tx.RENDERER_DRIVE_SETTLED_V33_TARGET_SHA, tx.RENDERER_QUEUE_DETAIL_V32_TARGET_SHA, tx.RENDERER_QUEUE_REGION_V31_TARGET_SHA, tx.RENDERER_QUEUE_DRUMS_V30_TARGET_SHA, tx.RENDERER_QUEUE_V29_TARGET_SHA, tx.RENDERER_FM6_OUTER_TIMING_TARGET_SHA, tx.RENDERER_FM6_OSCILLATOR_SLOPES_TARGET_SHA, tx.RENDERER_FM6_VCF_PROFILE_TARGET_SHA, tx.RENDERER_FM6_VCF_UNROLL_TARGET_SHA, tx.RENDERER_FM6_PLAN_RAM_TARGET_SHA, tx.RENDERER_FM6_NESTED_TARGET_SHA, tx.RENDERER_FM6_MODULE_RAM_TARGET_SHA, tx.RENDERER_FM6_KIND_RAM_TARGET_SHA):
            with pytest.raises(ValueError):
                tx.mutation_request(0xFB01, 0x8e000, b'', desired, older)
            with pytest.raises(ValueError):
                tx.mutation_request(0xFB04, 0x8ef00, bytes(256), desired, older)
    for address in (0x3000, 0x8f000, 0x7ff000):
        with pytest.raises(ValueError):
            tx.mutation_request(0xFB01, address, b'', desired, allowed)
    for address, permitted in ((0x3fff, False), (0x8efff, True), (0x8f000, False)):
        changed = bytearray(desired)
        changed[address] = 1
        assert tx.protected_equal(changed, desired, allowed) == permitted
    assert tx.IMAGE_PLANS[tx.RENDERER_FM6_HOOK_RAM_TARGET_SHA] == tuple(range(0x4000, 0x8e000, 4096))


def test_event_ram_image_keeps_its_own_smaller_bounds():
    assert tx.RENDERER_FM6_EVENT_RAM_TARGET_SHA == 'bb769d4dcc6798b372156cccc4f9ec5b6f3508044e72b2af65837c3d9e3100df'
    allowed = tx.IMAGE_PLANS[tx.RENDERER_FM6_EVENT_RAM_TARGET_SHA]
    assert allowed == tuple(range(0x4000, 0x8e000, 4096))
    assert tx.IMAGE_PLANS[tx.RENDERER_FM6_KIND_RAM_TARGET_SHA] == tuple(range(0x4000, 0x8f000, 4096))
    desired = bytes(tx.backup.FLASH_SIZE)
    tx.mutation_request(0xFB01, 0x8d000, b'', desired, allowed)
    tx.mutation_request(0xFB04, 0x8df00, bytes(256), desired, allowed)
    for address in (0x3000, 0x8e000, 0x7ff000):
        with pytest.raises(ValueError):
            tx.mutation_request(0xFB01, address, b'', desired, allowed)


def test_plan_ram_image_keeps_exact_bounds_and_prior_event_image_smaller():
    assert tx.RENDERER_FM6_PLAN_RAM_TARGET_SHA == '5f893effee2c5482c613d8d4805a1e5f9fb461411563bd3275159307a1234588'
    allowed = tx.IMAGE_PLANS[tx.RENDERER_FM6_PLAN_RAM_TARGET_SHA]
    assert allowed == tuple(range(0x4000, 0x8f000, 4096))
    previous = tx.IMAGE_PLANS[tx.RENDERER_FM6_EVENT_RAM_TARGET_SHA]
    assert previous == tuple(range(0x4000, 0x8e000, 4096))
    desired = bytes(tx.backup.FLASH_SIZE)
    tx.mutation_request(0xFB01, 0x8e000, b'', desired, allowed)
    tx.mutation_request(0xFB04, 0x8ef00, bytes(256), desired, allowed)
    for address in (0x3000, 0x8f000, 0x7ff000):
        with pytest.raises(ValueError):
            tx.mutation_request(0xFB01, address, b'', desired, allowed)
    with pytest.raises(ValueError):
        tx.mutation_request(0xFB01, 0x8e000, b'', desired, previous)


def test_mixed_pixels_image_preserves_exact_prior_bounds():
    assert tx.RENDERER_FM6_MIXED_PIXELS_TARGET_SHA == 'b8f8e24bd6e8ff05ba4609a3593acc2370bfaf18daa4c4fdbd598cd8f3a79d10'
    allowed = tx.IMAGE_PLANS[tx.RENDERER_FM6_MIXED_PIXELS_TARGET_SHA]
    assert allowed == tuple(range(0x4000, 0x8e000, tx.SECTOR))
    assert tx.IMAGE_PLANS[tx.RENDERER_FM6_PLAN_RAM_TARGET_SHA] == tuple(range(0x4000, 0x8f000, tx.SECTOR))
    assert tx.IMAGE_PLANS[tx.RENDERER_FM6_EVENT_RAM_TARGET_SHA] == allowed
    desired = bytes(tx.backup.FLASH_SIZE)
    tx.mutation_request(0xFB01, 0x8d000, b'', desired, allowed)
    tx.mutation_request(0xFB04, 0x8df00, bytes(256), desired, allowed)
    for address in (0x3000, 0x8e000, 0x7ff000):
        with pytest.raises(ValueError):
            tx.mutation_request(0xFB01, address, b'', desired, allowed)


def test_mixed_engine_profile_image_preserves_exact_prior_bounds():
    assert tx.RENDERER_FM6_ENGINE_PROFILE_TARGET_SHA == 'a64d6e17162d96367f8ba9fb49c9c07a8839585be63c5aef5553bc0b8b086a0d'
    allowed = tx.IMAGE_PLANS[tx.RENDERER_FM6_ENGINE_PROFILE_TARGET_SHA]
    assert allowed == tx.IMAGE_PLANS[tx.RENDERER_FM6_MIXED_PIXELS_TARGET_SHA]
    assert allowed == tuple(range(0x4000, 0x8e000, tx.SECTOR))
    desired = bytes(tx.backup.FLASH_SIZE)
    tx.mutation_request(0xFB01, 0x8d000, b'', desired, allowed)
    tx.mutation_request(0xFB04, 0x8df00, bytes(256), desired, allowed)
    for address in (0x3000, 0x8e000, 0x7ff000):
        with pytest.raises(ValueError):
            tx.mutation_request(0xFB01, address, b'', desired, allowed)


def test_vcf_unroll_image_has_its_own_additional_sector():
    assert tx.RENDERER_FM6_VCF_UNROLL_TARGET_SHA == '5c57aab671f77465c8024fa94f04e0a2b5c677ad8a67aaeaf68a5762104ad22a'
    allowed = tx.IMAGE_PLANS[tx.RENDERER_FM6_VCF_UNROLL_TARGET_SHA]
    previous = tx.IMAGE_PLANS[tx.RENDERER_FM6_ENGINE_PROFILE_TARGET_SHA]
    assert allowed == tuple(range(0x4000, 0x8f000, tx.SECTOR))
    assert previous == tuple(range(0x4000, 0x8e000, tx.SECTOR))
    desired = bytes(tx.backup.FLASH_SIZE)
    tx.mutation_request(0xFB01, 0x8e000, b'', desired, allowed)
    tx.mutation_request(0xFB04, 0x8ef00, bytes(256), desired, allowed)
    with pytest.raises(ValueError):
        tx.mutation_request(0xFB01, 0x8e000, b'', desired, previous)
    for address in (0x3000, 0x8f000, 0x7ff000):
        with pytest.raises(ValueError):
            tx.mutation_request(0xFB01, address, b'', desired, allowed)


def test_vcf_profile_exact_plan_retains_prior_bounds():
    assert tx.RENDERER_FM6_VCF_PROFILE_TARGET_SHA == '836f2967e245dd4848704ec3bc282c9b1364f121db855f6fb8db54acd9e27797'
    allowed = tx.IMAGE_PLANS[tx.RENDERER_FM6_VCF_PROFILE_TARGET_SHA]
    assert allowed == tuple(range(0x4000, 0x8f000, tx.SECTOR))
    assert len(allowed) == 139
    assert tx.IMAGE_PLANS[tx.RENDERER_FM6_VCF_UNROLL_TARGET_SHA] == allowed
    assert tx.IMAGE_PLANS[tx.RENDERER_FM6_ENGINE_PROFILE_TARGET_SHA] == tuple(range(0x4000, 0x8e000, tx.SECTOR))


def test_oscillator_slopes_additional_sector_requires_exact_image():
    assert tx.RENDERER_FM6_OSCILLATOR_SLOPES_TARGET_SHA == '23ce7c2d55059beae51625efd849c15b71a180fc33b7301e55d8b310228625ec'
    allowed = tx.IMAGE_PLANS[tx.RENDERER_FM6_OSCILLATOR_SLOPES_TARGET_SHA]
    assert allowed == tuple(range(0x4000, 0x90000, tx.SECTOR))
    assert len(allowed) == 140
    desired = bytes(tx.backup.FLASH_SIZE)
    tx.mutation_request(0xFB01, 0x8f000, b'', desired, allowed)
    tx.mutation_request(0xFB04, 0x8ff00, bytes(256), desired, allowed)
    for sha, older in tx.IMAGE_PLANS.items():
        if sha not in (tx.RENDERER_QUEUE_INSERT_V39_TARGET_SHA, tx.RENDERER_FM6_OSCILLATOR_SLOPES_TARGET_SHA, tx.RENDERER_QUEUE_DETAIL_V32_TARGET_SHA, tx.RENDERER_DRIVE_SETTLED_V33_TARGET_SHA, tx.RENDERER_QUEUE_MICRO_V34_TARGET_SHA, tx.RENDERER_QUEUE_CONTROL_V35_TARGET_SHA, tx.RENDERER_ENV_FAST_V36_TARGET_SHA, tx.RENDERER_MODULE_MICRO_V38_TARGET_SHA, tx.RENDERER_MOD_MICRO_V37_TARGET_SHA):
            with pytest.raises(ValueError):
                tx.mutation_request(0xFB01, 0x8f000, b'', desired, older)
    for address in (0x3000, 0x90000, 0x7ff000):
        with pytest.raises(ValueError):
            tx.mutation_request(0xFB01, address, b'', desired, allowed)
    assert tx.IMAGE_PLANS[tx.RENDERER_FM6_VCF_PROFILE_TARGET_SHA] == tuple(range(0x4000, 0x8f000, tx.SECTOR))


def test_outer_timing_exact_plan_keeps_current_restore_independent():
    assert tx.RENDERER_FM6_OUTER_TIMING_TARGET_SHA == '389b6fa96d0b2036ded3685f8a93f7f85f8e2e4189e8b306dafcaa4416589c53'
    allowed = tx.IMAGE_PLANS[tx.RENDERER_FM6_OUTER_TIMING_TARGET_SHA]
    assert allowed == tuple(range(0x4000, 0x8f000, tx.SECTOR))
    assert len(allowed) == 139
    current = tx.IMAGE_PLANS[tx.RENDERER_FM6_OSCILLATOR_SLOPES_TARGET_SHA]
    assert len(current) == 140
    desired = bytes(tx.backup.FLASH_SIZE)
    tx.mutation_request(0xFB01, 0x8e000, b'', desired, allowed)
    tx.mutation_request(0xFB01, 0x8f000, b'', desired, current)
    for address in (0x3000, 0x8f000, 0x7ff000):
        with pytest.raises(ValueError):
            tx.mutation_request(0xFB01, address, b'', desired, allowed)


def test_whole_engine_queue_v29_exact_plan_and_current_restore():
    assert tx.RENDERER_QUEUE_V29_TARGET_SHA == '91f34e30db7ed5008628c98a6104a4269cd1746a2280b5e9b6d2167f05772768'
    allowed = tx.IMAGE_PLANS[tx.RENDERER_QUEUE_V29_TARGET_SHA]
    assert allowed == tuple(range(0x4000, 0x8f000, tx.SECTOR))
    assert len(allowed) == 139
    assert tx.IMAGE_PLANS[tx.RENDERER_FM6_OUTER_TIMING_TARGET_SHA] == allowed
    desired = bytes(tx.backup.FLASH_SIZE)
    tx.mutation_request(0xFB01, 0x8e000, b'', desired, allowed)
    tx.mutation_request(0xFB04, 0x8ef00, bytes(256), desired, allowed)
    for address in (0x3000, 0x8f000, 0x7ff000):
        with pytest.raises(ValueError):
            tx.mutation_request(0xFB01, address, b'', desired, allowed)


def test_macro_drums_queue_v30_exact_plan_and_current_restore():
    assert tx.RENDERER_QUEUE_DRUMS_V30_TARGET_SHA == '14e39d30b7e01be23d5ecc9e9ab2bcb5cb5e5f4f86f6af57bf4402af34d786c2'
    allowed = tx.IMAGE_PLANS[tx.RENDERER_QUEUE_DRUMS_V30_TARGET_SHA]
    assert allowed == tuple(range(0x4000, 0x8f000, tx.SECTOR))
    assert len(allowed) == 139
    assert tx.IMAGE_PLANS[tx.RENDERER_QUEUE_V29_TARGET_SHA] == allowed
    desired = bytes(tx.backup.FLASH_SIZE)
    tx.mutation_request(0xFB01, 0x8e000, b'', desired, allowed)
    tx.mutation_request(0xFB04, 0x8ef00, bytes(256), desired, allowed)
    for address in (0x3000, 0x8f000, 0x7ff000):
        with pytest.raises(ValueError):
            tx.mutation_request(0xFB01, address, b'', desired, allowed)


def test_profiled_queue_v31_exact_plan_and_current_restore():
    assert tx.RENDERER_QUEUE_REGION_V31_TARGET_SHA == 'f9aa8f87f9895b46d71f59d267a8b16515f0a1d4b80c7296f8c2b2fdc4178612'
    allowed = tx.IMAGE_PLANS[tx.RENDERER_QUEUE_REGION_V31_TARGET_SHA]
    assert allowed == tuple(range(0x4000, 0x8f000, tx.SECTOR))
    assert len(allowed) == 139
    assert tx.IMAGE_PLANS[tx.RENDERER_QUEUE_DRUMS_V30_TARGET_SHA] == allowed
    desired = bytes(tx.backup.FLASH_SIZE)
    tx.mutation_request(0xFB01, 0x8e000, b'', desired, allowed)
    tx.mutation_request(0xFB04, 0x8ef00, bytes(256), desired, allowed)
    for address in (0x3000, 0x8f000, 0x7ff000):
        with pytest.raises(ValueError):
            tx.mutation_request(0xFB01, address, b'', desired, allowed)


def test_detail_queue_v32_extra_sector_does_not_expand_current_restore():
    allowed = tx.IMAGE_PLANS[tx.RENDERER_QUEUE_DETAIL_V32_TARGET_SHA]
    current = tx.IMAGE_PLANS[tx.RENDERER_QUEUE_REGION_V31_TARGET_SHA]
    assert len(allowed) == 140 and len(current) == 139
    assert allowed == tuple(range(0x4000, 0x90000, tx.SECTOR))
    assert current == tuple(range(0x4000, 0x8f000, tx.SECTOR))
    desired = bytes(tx.backup.FLASH_SIZE)
    tx.mutation_request(0xFB01, 0x8f000, b'', desired, allowed)
    tx.mutation_request(0xFB04, 0x8ff00, bytes(256), desired, allowed)
    with pytest.raises(ValueError):
        tx.mutation_request(0xFB01, 0x8f000, b'', desired, current)
    for address in (0x3000, 0x90000, 0x7ff000):
        with pytest.raises(ValueError):
            tx.mutation_request(0xFB01, address, b'', desired, allowed)
    changed = bytearray(desired)
    changed[0x8ffff] = 1
    assert tx.protected_equal(changed, desired, allowed)
    assert not tx.protected_equal(changed, desired, current)
    changed[0x90000] = 1
    assert not tx.protected_equal(changed, desired, allowed)


def test_micro_v34_exact_plan_preserves_prior_restore_bounds():
    assert tx.RENDERER_QUEUE_MICRO_V34_TARGET_SHA == 'c70fddedc7f029bb04dccbc56d80d992b6557ab6b435ecc90260e2bd2ce52974'
    allowed = tx.IMAGE_PLANS[tx.RENDERER_QUEUE_MICRO_V34_TARGET_SHA]
    assert allowed == tuple(range(0x4000, 0x90000, tx.SECTOR))
    assert allowed == tx.IMAGE_PLANS[tx.RENDERER_DRIVE_SETTLED_V33_TARGET_SHA]
    desired = bytes(tx.backup.FLASH_SIZE)
    tx.mutation_request(0xFB01, 0x8f000, b'', desired, allowed)
    tx.mutation_request(0xFB04, 0x8ff00, bytes(256), desired, allowed)
    for address in (0x3000, 0x90000, 0x7ff000):
        with pytest.raises(ValueError):
            tx.mutation_request(0xFB01, address, b'', desired, allowed)
    current_v31 = tx.IMAGE_PLANS[tx.RENDERER_QUEUE_REGION_V31_TARGET_SHA]
    with pytest.raises(ValueError):
        tx.mutation_request(0xFB01, 0x8f000, b'', desired, current_v31)


def test_control_v35_exact_plan_keeps_current_restore_bounds():
    assert tx.RENDERER_QUEUE_CONTROL_V35_TARGET_SHA == '86f02a974ad0a41c13ce09396a4657289dd7f8943aeb416870cd063e595f3d83'
    allowed = tx.IMAGE_PLANS[tx.RENDERER_QUEUE_CONTROL_V35_TARGET_SHA]
    assert allowed == tuple(range(0x4000, 0x90000, tx.SECTOR))
    assert allowed == tx.IMAGE_PLANS[tx.RENDERER_QUEUE_MICRO_V34_TARGET_SHA]
    desired = bytes(tx.backup.FLASH_SIZE)
    tx.mutation_request(0xFB01, 0x8f000, b'', desired, allowed)
    tx.mutation_request(0xFB04, 0x8ff00, bytes(256), desired, allowed)
    for address in (0x3000, 0x90000, 0x7ff000):
        with pytest.raises(ValueError):
            tx.mutation_request(0xFB01, address, b'', desired, allowed)
    older = tx.IMAGE_PLANS[tx.RENDERER_QUEUE_REGION_V31_TARGET_SHA]
    assert older == tuple(range(0x4000, 0x8f000, tx.SECTOR))
    with pytest.raises(ValueError):
        tx.mutation_request(0xFB01, 0x8f000, b'', desired, older)


def test_env_fast_v36_exact_plan_keeps_current_restore_bounds():
    assert tx.RENDERER_ENV_FAST_V36_TARGET_SHA == '3d00c962b8df3eca3a9ff1122b796cc7328980186498aec97f78a38ee74a8a62'
    allowed = tx.IMAGE_PLANS[tx.RENDERER_ENV_FAST_V36_TARGET_SHA]
    assert allowed == tuple(range(0x4000, 0x90000, tx.SECTOR))
    assert allowed == tx.IMAGE_PLANS[tx.RENDERER_QUEUE_CONTROL_V35_TARGET_SHA]
    desired = bytes(tx.backup.FLASH_SIZE)
    tx.mutation_request(0xFB01, 0x8f000, b'', desired, allowed)
    tx.mutation_request(0xFB04, 0x8ff00, bytes(256), desired, allowed)
    for address in (0x3000, 0x90000, 0x7ff000):
        with pytest.raises(ValueError):
            tx.mutation_request(0xFB01, address, b'', desired, allowed)
    older = tx.IMAGE_PLANS[tx.RENDERER_QUEUE_REGION_V31_TARGET_SHA]
    assert older == tuple(range(0x4000, 0x8f000, tx.SECTOR))
    with pytest.raises(ValueError):
        tx.mutation_request(0xFB01, 0x8f000, b'', desired, older)


def test_mod_micro_v37_exact_plan_keeps_current_restore_bounds():
    assert tx.RENDERER_MOD_MICRO_V37_TARGET_SHA == '5704ca9e632fde350cd10b4a5f2a0a7f54f92857e839a28c778fa55d8cc7e05e'
    allowed = tx.IMAGE_PLANS[tx.RENDERER_MOD_MICRO_V37_TARGET_SHA]
    assert allowed == tuple(range(0x4000, 0x90000, tx.SECTOR))
    assert allowed == tx.IMAGE_PLANS[tx.RENDERER_ENV_FAST_V36_TARGET_SHA]
    desired = bytes(tx.backup.FLASH_SIZE)
    tx.mutation_request(0xFB01, 0x8f000, b'', desired, allowed)
    tx.mutation_request(0xFB04, 0x8ff00, bytes(256), desired, allowed)
    for address in (0x3000, 0x90000, 0x7ff000):
        with pytest.raises(ValueError):
            tx.mutation_request(0xFB01, address, b'', desired, allowed)
    older = tx.IMAGE_PLANS[tx.RENDERER_QUEUE_REGION_V31_TARGET_SHA]
    assert older == tuple(range(0x4000, 0x8f000, tx.SECTOR))
    with pytest.raises(ValueError):
        tx.mutation_request(0xFB01, 0x8f000, b'', desired, older)


def test_module_micro_v38_exact_plan_keeps_current_restore_bounds():
    assert tx.RENDERER_MODULE_MICRO_V38_TARGET_SHA == '2483bb7c1fcba0d3a3099f826981dd15bac6ca23804bfebe6a99de43ff5f8bd6'
    allowed = tx.IMAGE_PLANS[tx.RENDERER_MODULE_MICRO_V38_TARGET_SHA]
    assert allowed == tuple(range(0x4000, 0x90000, tx.SECTOR))
    assert allowed == tx.IMAGE_PLANS[tx.RENDERER_ENV_FAST_V36_TARGET_SHA]
    desired = bytes(tx.backup.FLASH_SIZE)
    tx.mutation_request(0xFB01, 0x8f000, b'', desired, allowed)
    tx.mutation_request(0xFB04, 0x8ff00, bytes(256), desired, allowed)
    for address in (0x3000, 0x90000, 0x7ff000):
        with pytest.raises(ValueError):
            tx.mutation_request(0xFB01, address, b'', desired, allowed)
    older = tx.IMAGE_PLANS[tx.RENDERER_QUEUE_REGION_V31_TARGET_SHA]
    assert older == tuple(range(0x4000, 0x8f000, tx.SECTOR))
    with pytest.raises(ValueError):
        tx.mutation_request(0xFB01, 0x8f000, b'', desired, older)


def test_queue_insert_v39_keeps_installed_v38_restore_plan():
    allowed = tx.IMAGE_PLANS[tx.RENDERER_QUEUE_INSERT_V39_TARGET_SHA]
    assert tx.RENDERER_QUEUE_INSERT_V39_TARGET_SHA == 'de0fa4e5c54bc3e27763e60cce6732160a72dba143348916c190e7efa9ed31a8'
    assert allowed == tuple(range(0x4000, 0x90000, tx.SECTOR))
    assert allowed == tx.IMAGE_PLANS[tx.RENDERER_MODULE_MICRO_V38_TARGET_SHA]
    desired = bytes(tx.backup.FLASH_SIZE)
    tx.mutation_request(0xFB01, 0x8f000, b'', desired, allowed)
    tx.mutation_request(0xFB04, 0x8ff00, bytes(256), desired, allowed)
    for address in (0x3000, 0x90000, 0x7ff000):
        with pytest.raises(ValueError):
            tx.mutation_request(0xFB01, address, b'', desired, allowed)
    older = tx.IMAGE_PLANS[tx.RENDERER_QUEUE_REGION_V31_TARGET_SHA]
    with pytest.raises(ValueError):
        tx.mutation_request(0xFB01, 0x8f000, b'', desired, older)
