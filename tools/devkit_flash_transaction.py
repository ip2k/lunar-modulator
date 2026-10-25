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
               RENDERER_VCF_TARGET_SHA: RENDERER_PROFILE_ALLOWED}


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
