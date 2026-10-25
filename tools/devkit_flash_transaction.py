#!/usr/bin/env python3
"""MIT. Exact dev-kit diagnostic sector transaction, not an FM-1 flasher.

No loader upload, reset, chip erase or eFuse operation. Factory and diagnostic
images are private, hash-pinned inputs. Install metadata last; verify every
sector and the complete flash. Interrupted transactions require explicit
restore using the same factory bytes and fixed mutation range.
"""
import argparse
import binascii
import hashlib
import json
import os
from pathlib import Path
import time

import devkit_flash_backup as backup

BASELINE_SHA = '127b2ebbef9da3469f0bf7ea3841a5515d01721ebac9bbdc7fc739032d7b5ec1'
TARGET_SHA = 'e77ee8af309fc57d1a8eddaac95dec253dda031f269021382c9cb1e977baa103'
SECTOR = 4096
ALLOWED = tuple(range(0x4000, 0x2c000, SECTOR))
# Reviewed private internal-DAC reference probe; no arbitrary target/range CLI.
AUDIO_TARGET_SHA = '5cba22f0b0b19bda0847a303eee033f7a2b31a7bef5255ef1d98ca27f796c7b2'
AUDIO_ALLOWED = tuple(range(0x4000, 0x2e000, SECTOR))
# Three-window DAC correction, separately reviewed; retain v2 for recovery.
AUDIO_V3_TARGET_SHA = 'cfa6afbe0b3ff60f11760dff72c2b2b25221a7af555007eca8c188bb9349dd32'
# Opt-in UART1 control image; same DAC probe and fixed application boundary.
AUDIO_CONTROL_TARGET_SHA = 'ba8b03938e0b2a90461a728646a31f7de72975df282e9c1931750400cadaaaa6'
AUDIO_CONTROL_V2_TARGET_SHA = '1bbaf5ae4ddf6a6fc6289c095f0f4b4361913b436b616f6c1f9e43d7da4cad25'
# Actual FM6 timing plus UART control; no DAC output. Separate reviewed bounds.
FM6_CONTROL_TARGET_SHA = '79e0cc9bb394415f544f2e9a33ea8e6cfab2ae70120ca9590b1eb32c1d629789'
FM6_RAM_CONTROL_TARGET_SHA = '80c455edeea61649e21f1c8c625240da3bfcd1d3682aa31914825ee77e72448f'
FM6_ALLOWED = tuple(range(0x4000, 0x37000, SECTOR))
# v1's DAC object compiled the reference branch; retain its exact restore plan.
FM6_AUDIO_TARGET_SHA = 'f9def23ecbd6b5bdaa9861ac2093264cb1c51181f84ffb2ae54a410a4dc96993'
FM6_AUDIO_ALLOWED = tuple(range(0x4000, 0x3a000, SECTOR))
FM6_AUDIO_V2_TARGET_SHA = '80f7491493b45a5408214f792066f0da390bb282cdf9a103bbbc9920058a1422'
FM6_AUDIO_V2_ALLOWED = tuple(range(0x4000, 0x39000, SECTOR))
# Same bounded live workload with completed-case PCM fingerprints.
FM6_AUDIO_V3_TARGET_SHA = 'f7863aad94f993742140161350edd28c0555a348574c9c01f3bdf253a4204ced'
# Full shared-renderer worker preflight, no DAC; audited SDK link and private
# independent cipher/CRC/objcopy checks. UART control and 20 KiB worker stack.
RENDERER_TIMING_TARGET_SHA = 'b8305c69d6ce8ccfe7dabe52f08553369dcaced81b47e7d75d61860d5494bfa3'
RENDERER_TIMING_ALLOWED = tuple(range(0x4000, 0x8a000, SECTOR))
# Corrected division guard and startup UART recovery window; independently
# reviewed packing and interrupted-transaction model, same fixed bounds.
RENDERER_TIMING_V3_TARGET_SHA = '7478c40947fa308a6ffacba32ab1f109632446b0370dafc2183c091421a93b16'
# Call-site profiling of the same worker workload; independent vendor exports,
# cipher/CRC, link/startup review and interrupted NOR restore model checked.
# These profiling comparisons have independently reviewed exact-image bounds.
RENDERER_PROFILE_TARGET_SHA = 'a6ce75351236f19c2d517841b7392e58e2ca94197c7255352b62a8f672810870'
RENDERER_PROFILE_ALLOWED = tuple(range(0x4000, 0x8b000, SECTOR))
# Same workload with selected DSP code in startup-copied SRAM; constants XIP.
# Vendor placement/copy/link review and independent cipher/NOR checks pass.
RENDERER_HOT_TARGET_SHA = 'b4fc59a4eca97df13d8ac1fc324da69e3f89b7bf82a6fb8daa57aad664739181'
# Code placement retained; only 8 KiB sine table moves from XIP to SRAM.
# Independent table bytes, link/copy/recovery, cipher/CRC and NOR checks pass.
RENDERER_SINE_TARGET_SHA = '734b3995171a778e495bfb870e0be695075adf8580a279e944f7da25e743b8a4'
# Recovery reserved before workload; independent exact-image review/model pass.
RENDERER_RECOVERY_TARGET_SHA = 'd1d534f71ed6473046d1f23bedd4c39fe8df8a3ef0874f544c82458766324274'
# Same recovery/placement with six enclosing stage timers; exact export,
# startup/recovery, independent cipher/CRC and interrupted restore checks pass.
RENDERER_STAGES_TARGET_SHA = 'e16931a08a7357b4e2cf97adeee9d4628f89a1de8706b5db3c33e4870e3b54f4'
# Selected VA+Filter code in SRAM; exact export/startup/recovery, table bytes,
# independent cipher/CRC and interrupted NOR restore model reviewed offline.
RENDERER_VCF_TARGET_SHA = '14c60db2f8d0f280c39d308535dc62dd4a78a1cb847b7946f35bb9a5fe620df1'
# Bounded arithmetic kernels before unchanged renderer workload; offline reviewed.
RENDERER_ARITHMETIC_TARGET_SHA = '8d67a77a1f7e7bcf4095c96a18a6b63f614eb0713af007d5b4254395c7f6480c'
# Shared resampler coefficient SRAM copy; exact image and restore reviewed.
RENDERER_RESAMPLER_TARGET_SHA = 'a680a4e8b04d1fd67d5859c6411983fd91fed11ee5ddca3a33fa0d9297ccd746'
# Existing SDK cache data RAM tables; exact copy/recovery/cipher/NOR reviewed.
RENDERER_CACHE_TARGET_SHA = 'ea83cfdb345882c0a0a26265b396a61917fd4850b2dbd58a154d6d68a30c6ba8'
# Same data layout with compressor/drive/echo SRAM code; exact image reviewed.
RENDERER_FX_TARGET_SHA = '3169034433b2a0ce0b338678e591754e59bf77e215e2da8f4f4412445e8250e5'
# Two outlined resampler kernels; exact startup/cipher/NOR review completed.
RENDERER_OUTLINE_TARGET_SHA = 'e988ec53133161065b051f524495c65cfcf7b0c4c0c70ec9bb295bfd4e3ce47b'
RENDERER_FILTER_TARGET_SHA = 'cf5328fc716e97604b415fab49d5ece58b4ef4d05874504e108041de4f6fa9f7'
RENDERER_FILTER_STACK_TARGET_SHA = '842758192917d9eeaf877d1117b1e38426063fd432e6f00fa7fe09c507844bd0'
# Control-path SRAM timing comparison; exact startup/SDK/cipher/NOR reviewed.
RENDERER_CONTROL_TARGET_SHA = 'bb3cc21d3fdc9fa0a0920334920845a6795e7726086a3638dbf1f4e20df3f759'
# Reviewed exact Plaits sine/pitch table cache comparison; same 135 sectors.
RENDERER_PLAITS_CACHE_TARGET_SHA = '1e1068c7a99071d44b1d4400d41e1ab8027feee5b8b6222f7f8adbae74e07dcb'
# Reviewed float32 slope-pair comparison; exact 136-sector image only.
RENDERER_SLOPES_TARGET_SHA = '7f1d2286a353084c681258556294b8309d3121fc66c301f80832c98b455f6d34'
RENDERER_SLOPES_ALLOWED = tuple(range(0x4000, 0x8c000, SECTOR))
# Reviewed nested engine counters; same exact 136-sector bounds.
RENDERER_DETAIL_TARGET_SHA = '57a605672d17ae479e8db05f9bacc12fd84bce49940da7c46a56130b352b3027'
# Reviewed fixed FIR expansion; same exact 136-sector bounds.
RENDERER_UNROLL_TARGET_SHA = '92d1e3f1fdea9e5a73961f0d88d683527012026a2c5302bbbda2a9d8288f457e'
# Reviewed renderer O3 comparison; exact-image bounds cover 138 sectors.
RENDERER_O3_TARGET_SHA = 'fd32ec039217b59762efc09b185dd25871420c47db689ffa626b07d3e183adf3'
RENDERER_O3_ALLOWED = tuple(range(0x4000, 0x8e000, SECTOR))
# Reviewed mixer/dispatch SRAM comparison; same bounds, separate exact image.
RENDERER_MIXER_TARGET_SHA = 'ccee05d465d396d5749b9d70b6cf8387c2bca100040b654af8f6306dc539e416'
# Reviewed FIR scheduling comparison; identical filter and fixed sector bounds.
RENDERER_SCHEDULE_TARGET_SHA = 'fe4a860bcbebd57bee05ff94c3dffb613f2914163f1d302bdb007ccc14016512'
# Named keys arrangement: reviewed exact image, 137 sectors; mixed unchanged.
RENDERER_KEYS_TARGET_SHA = 'bee9d4bc83cc78e1c1a4a40448dc4211f2d8276cb6a8cad5878c9c5d7ee2aa36'
RENDERER_KEYS_ALLOWED = tuple(range(0x4000, 0x8d000, SECTOR))
# Reviewed keys dispatch SRAM comparison; same exact 137-sector boundary.
RENDERER_DISPATCH_TARGET_SHA = '356c0b070d8ac6483fd8034767777b8c5dc13c25d04227c9f63dccaf3b1523e8'
# Compact session metadata; exact vendor/PCM/recovery/cipher/NOR review passed.
RENDERER_SESSION_TARGET_SHA = '6619c671eaf054db1e7c3e8873787f7a61a54940fd6a3faceb1971d73cf9c4eb'
# Reviewed LED early-return guards; unchanged 137-sector layout and recovery.
RENDERER_LED_GUARD_TARGET_SHA = 'f6c74b7b198dd1ac5e154862e39d09dded5a2cfa6dae4613528aa63b8d545f23'
# Reviewed narrow FM additions; exact PCM/oracle/vendor/recovery/cipher/NOR checks.
RENDERER_FM_NARROW_TARGET_SHA = '5370ec631766ddee6594a8648a0840c213dd1e37637d3c064cbc4a8a2412a2ab'
# Reviewed bounded sine product; exact PCM/oracle/vendor/recovery/cipher/NOR checks.
RENDERER_FM_SINE32_TARGET_SHA = '4589d46ba8382c86ae7f05c6c60c8b3c8e3c8b0b942c811ffceefa03d1d2a7bf'
# Compact current-route snapshot; exact reviewed app and unchanged 137-sector plan.
RENDERER_ROUTE_TARGET_SHA = 'e2fb418459789350793538d33ed82dfe5a43ade037c31211d65c84da23c40304'
# Reviewed pure-operator two-way unroll; exact app/recovery/cipher/NOR checks.
RENDERER_FM_PURE2_TARGET_SHA = 'b8823c2a322aa47e28306ca11d423838438daa1328a393969c554ffedaf4ab98'
# Reviewed settled-control compressor; exact recovery/cipher/NOR checks.
RENDERER_COMP_SETTLED_TARGET_SHA = 'f9233d22b81bcd3203e460fa602d2d2d6f00c75387347a5a997c642937f093f3'
# Reviewed bit-identical SVF channel shortcut; exact recovery/cipher/NOR checks.
RENDERER_FILTER_MONO_TARGET_SHA = '49ef7762bf3276e5e5ec150ca6d777f285b7b83f60b0ca5f1d771d60e2314a8e'
# Reviewed short CPU1 publication/pinning probe; no renderer or audio acceptance.
CPU1_PUBLICATION_TARGET_SHA = '9d3d4f8c46ddf3a0edb3fce6abd5a7482a257f82c3b798ba87ec5460bce9f761'
CPU1_PUBLICATION_ALLOWED = tuple(range(0x4000, 0x2d000, SECTOR))
# Reviewed bounded 100-million-exchange comparison; same narrow application span.
CPU1_LONG_TARGET_SHA = '3bbfa865e5c3fd37c8babe9f01c9fe7e6d56f7d41e211488e26b57d71a8a5c23'
# Reviewed finite arithmetic/paced SRAM ring; no DAC or hardware acceptance.
CPU1_RING_TARGET_SHA = '0fd1dcb5ff74bf036f2c785144745bf2fe6254587a73b86bec4d3396fb9dfd09'
# Reviewed phase timing variant; exact export/cipher/CRC/NOR checks, same span.
CPU1_RING_PHASE_TARGET_SHA = '43b911a84f17e0045e911249c495f967cc42087c33a996f87080c6e4d44b0455'
# Finite copied FM6 renderer; exact vendor/PCM/recovery/cipher/NOR review.
RENDERER_FM6_PAIR_TARGET_SHA = '393f497566bf1ee9b709bdbd67adec23ecb0f216809afd632dffc66adfe7534a'
# Same finite renderer with permanently reserved SDK TCB and 4 KiB worker stack.
RENDERER_FM6_STATIC_TARGET_SHA = 'afdc2fa73bc27aff9ade73f8e10cb1ecdaa1d9e2c1f6e0e693d423af16fe322a'
# Same finite keys renderer with a measured-capacity 96 KiB arena; mixed unchanged.
RENDERER_FM6_POOL_TARGET_SHA = '718f09c30e9b4efe8fdf226926a3d0701bcab37609dbc4e2dbec7857f5580d25'
# Same finite keys diagnostic with CPU0-owned first-refusal evidence.
RENDERER_FM6_REFUSAL_TARGET_SHA = 'b2b3ab557b788b6c8e500755e41be47db14986ed5aa6dfd6681c4aefd611f983'
IMAGE_PLANS = {TARGET_SHA: ALLOWED, AUDIO_TARGET_SHA: AUDIO_ALLOWED,
               AUDIO_V3_TARGET_SHA: AUDIO_ALLOWED,
               AUDIO_CONTROL_TARGET_SHA: AUDIO_ALLOWED,
               AUDIO_CONTROL_V2_TARGET_SHA: AUDIO_ALLOWED,
               FM6_CONTROL_TARGET_SHA: FM6_ALLOWED,
               FM6_RAM_CONTROL_TARGET_SHA: FM6_ALLOWED,
               FM6_AUDIO_TARGET_SHA: FM6_AUDIO_ALLOWED,
               FM6_AUDIO_V2_TARGET_SHA: FM6_AUDIO_V2_ALLOWED,
               FM6_AUDIO_V3_TARGET_SHA: FM6_AUDIO_V2_ALLOWED,
               RENDERER_TIMING_TARGET_SHA: RENDERER_TIMING_ALLOWED,
               RENDERER_TIMING_V3_TARGET_SHA: RENDERER_TIMING_ALLOWED,
               RENDERER_PROFILE_TARGET_SHA: RENDERER_PROFILE_ALLOWED,
               RENDERER_HOT_TARGET_SHA: RENDERER_PROFILE_ALLOWED,
               RENDERER_SINE_TARGET_SHA: RENDERER_PROFILE_ALLOWED,
               RENDERER_RECOVERY_TARGET_SHA: RENDERER_PROFILE_ALLOWED,
               RENDERER_STAGES_TARGET_SHA: RENDERER_PROFILE_ALLOWED,
               RENDERER_VCF_TARGET_SHA: RENDERER_PROFILE_ALLOWED,
               RENDERER_ARITHMETIC_TARGET_SHA: RENDERER_PROFILE_ALLOWED,
               RENDERER_RESAMPLER_TARGET_SHA: RENDERER_PROFILE_ALLOWED,
               RENDERER_CACHE_TARGET_SHA: RENDERER_PROFILE_ALLOWED,
               RENDERER_FX_TARGET_SHA: RENDERER_PROFILE_ALLOWED,
               RENDERER_OUTLINE_TARGET_SHA: RENDERER_PROFILE_ALLOWED,
               RENDERER_FILTER_TARGET_SHA: RENDERER_PROFILE_ALLOWED,
               RENDERER_FILTER_STACK_TARGET_SHA: RENDERER_PROFILE_ALLOWED,
               RENDERER_CONTROL_TARGET_SHA: RENDERER_PROFILE_ALLOWED,
               RENDERER_PLAITS_CACHE_TARGET_SHA: RENDERER_PROFILE_ALLOWED,
               RENDERER_SLOPES_TARGET_SHA: RENDERER_SLOPES_ALLOWED,
               RENDERER_DETAIL_TARGET_SHA: RENDERER_SLOPES_ALLOWED,
               RENDERER_UNROLL_TARGET_SHA: RENDERER_SLOPES_ALLOWED,
               RENDERER_O3_TARGET_SHA: RENDERER_O3_ALLOWED,
               RENDERER_MIXER_TARGET_SHA: RENDERER_O3_ALLOWED,
               RENDERER_SCHEDULE_TARGET_SHA: RENDERER_O3_ALLOWED,
               RENDERER_KEYS_TARGET_SHA: RENDERER_KEYS_ALLOWED,
               RENDERER_DISPATCH_TARGET_SHA: RENDERER_KEYS_ALLOWED,
               RENDERER_SESSION_TARGET_SHA: RENDERER_KEYS_ALLOWED,
               RENDERER_LED_GUARD_TARGET_SHA: RENDERER_KEYS_ALLOWED,
               RENDERER_FM_NARROW_TARGET_SHA: RENDERER_KEYS_ALLOWED,
               RENDERER_FM_SINE32_TARGET_SHA: RENDERER_KEYS_ALLOWED,
               RENDERER_ROUTE_TARGET_SHA: RENDERER_KEYS_ALLOWED,
               RENDERER_FM_PURE2_TARGET_SHA: RENDERER_KEYS_ALLOWED,
               RENDERER_COMP_SETTLED_TARGET_SHA: RENDERER_KEYS_ALLOWED,
               RENDERER_FILTER_MONO_TARGET_SHA: RENDERER_KEYS_ALLOWED,
               CPU1_PUBLICATION_TARGET_SHA: CPU1_PUBLICATION_ALLOWED,
               CPU1_LONG_TARGET_SHA: CPU1_PUBLICATION_ALLOWED,
               CPU1_RING_TARGET_SHA: CPU1_PUBLICATION_ALLOWED,
               CPU1_RING_PHASE_TARGET_SHA: CPU1_PUBLICATION_ALLOWED,
               RENDERER_FM6_PAIR_TARGET_SHA: RENDERER_O3_ALLOWED,
               RENDERER_FM6_STATIC_TARGET_SHA: RENDERER_O3_ALLOWED,
               RENDERER_FM6_POOL_TARGET_SHA: RENDERER_O3_ALLOWED,
               RENDERER_FM6_REFUSAL_TARGET_SHA: RENDERER_O3_ALLOWED}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def validate_images(factory, target):
    allowed = IMAGE_PLANS.get(digest(target))
    if (len(factory) != backup.FLASH_SIZE or len(target) != backup.FLASH_SIZE
            or digest(factory) != BASELINE_SHA or allowed is None):
        raise ValueError('Exact private factory and reviewed diagnostic images required')
    dirty = tuple(a for a in range(0, len(factory), SECTOR)
                  if factory[a:a+SECTOR] != target[a:a+SECTOR])
    if dirty != allowed:
        raise ValueError('Diagnostic mutation range changed')
    return allowed


def mutation_request(op, address, payload, desired, allowed=ALLOWED):
    if op == 0xFB01:
        if address not in allowed or payload:
            raise ValueError('Only exact application-sector erases permitted')
        return (b'\xfb\x01'+address.to_bytes(4, 'big')).ljust(16, b'\xff'), b'', 16
    if op == 0xFB04:
        if (address % backup.base.CHUNK or address // SECTOR * SECTOR not in allowed
                or len(payload) != backup.base.CHUNK
                or payload != desired[address:address+backup.base.CHUNK]):
            raise ValueError('Only exact desired application pages permitted')
        cdb = (b'\xfb\x04'+address.to_bytes(4, 'big')
               +backup.base.CHUNK.to_bytes(2, 'big')+b'\0'
               +binascii.crc_hqx(payload, 0).to_bytes(2, 'little'))
        return cdb.ljust(16, b'\xff'), payload, 0
    # Deliberately no fallback to ROM operations, even if a caller changes phase.
    if op not in (0xFD05, 0xFC0A, 0xFC14):
        raise ValueError('Transaction operation forbidden')
    return backup.request(op, 'loader', address=address, payload=payload)


class Writer(backup.DevkitReader):
    allowed = ALLOWED
    def build_request(self, op, address, payload):
        return mutation_request(op, address, payload, self.desired, self.allowed)


def protected_equal(current, factory, allowed=ALLOWED):
    return (len(current) == len(factory) == backup.FLASH_SIZE
            and current[:0x4000] == factory[:0x4000]
            and current[allowed[-1]+SECTOR:] == factory[allowed[-1]+SECTOR:])


def transact(reader, current, factory, target, mode):
    allowed = validate_images(factory, target)
    if mode not in ('install', 'restore'):
        raise ValueError('Unknown transaction mode')
    if not protected_equal(current, factory, allowed):
        raise ValueError('Protected factory sectors differ; no write')
    if mode == 'install' and current != factory:
        raise ValueError('Install requires complete exact factory preimage')
    reader.allowed = allowed
    reader.desired = target if mode == 'install' else factory
    dirty = [a for a in allowed if current[a:a+SECTOR] != reader.desired[a:a+SECTOR]]
    order = [a for a in dirty if a != 0x4000] + ([0x4000] if 0x4000 in dirty else [])
    for address in order:
        reader.online()
        reader.log('sector_begin', address=address, mode=mode)
        reader.cmd(0xFB01, address=address)
        for a in range(address, address+SECTOR, backup.base.CHUNK):
            reader.cmd(0xFB04, address=a, payload=reader.desired[a:a+backup.base.CHUNK])
        actual = b''.join(reader.cmd(0xFD05, address=a)
                          for a in range(address, address+SECTOR, backup.base.CHUNK))
        if actual != reader.desired[address:address+SECTOR]:
            raise ValueError(f'Sector verification failed at {address:#x}; stop, retain evidence')
        reader.log('sector_verified', address=address, mode=mode)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for flag in ('device', 'usb-path', 'devnum', 'mode'):
        ap.add_argument('--'+flag, required=True)
    for flag in ('factory', 'target', 'fixed-backup', 'out'):
        ap.add_argument('--'+flag, required=True, type=Path)
    ap.add_argument('--apply-exact-devkit-image', action='store_true')
    a = ap.parse_args()
    if not a.apply_exact_devkit_image or a.mode not in ('install', 'restore'):
        raise ValueError('Explicit exact dev-kit transaction required')
    factory, target = a.factory.read_bytes(), a.target.read_bytes()
    validate_images(factory, target)
    receipt = json.loads((a.fixed_backup/'receipt.json').read_text())
    if receipt.get('matched') is not True or receipt.get('loader_sha256') != backup.LOADER_SHA:
        raise ValueError('Reviewed fixed-loader backup receipt required')
    for name in ('factory-A.bin', 'factory-B.bin'):
        if (a.fixed_backup/name).read_bytes() != factory:
            raise ValueError('Fixed-loader backup differs from pinned factory bytes')
    a.out.mkdir(mode=0o700, parents=True, exist_ok=False)
    with (a.out/'commands.jsonl').open('x') as fp:
        os.chmod(fp.name, 0o600)
        def log(event, **fields):
            fp.write(json.dumps(dict(time=time.time(), event=event, **fields))+'\n')
            fp.flush()
            if event != 'command':
                os.fsync(fp.fileno())
        r = Writer(a.device, log)
        try:
            r.desired = target if a.mode == 'install' else factory
            if r.usb.name != a.usb_path or (r.usb/'devnum').read_text().strip() != a.devnum:
                raise ValueError('Device connection changed; no command')
            r.phase = 'loader'  # continuing the recorded fixed-loader session
            if r.online() != (3, 0x5e4017):
                raise ValueError('Unexpected dev-kit flash identity')
            r.dump(a.out/'before.bin')
            current = (a.out/'before.bin').read_bytes()
            transact(r, current, factory, target, a.mode)
            after = r.dump(a.out/'after.bin')
            if after['sha256'] != digest(r.desired):
                raise ValueError('Full flash verification failed; no reset')
            result = dict(mode=a.mode, full_flash_verified=True, after=after,
                          booted=False, reset_sent=False)
            (a.out/'receipt.json').write_text(json.dumps(result, indent=2)+'\n')
            log('complete', **result)
            print(json.dumps(result), flush=True)
        finally:
            r.close()


if __name__ == '__main__':
    main()
