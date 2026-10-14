# SPDX-License-Identifier: MIT
"""Offline Event Horizon installation transcript replay; never opens a device.

The pure replay below checks recorded operations against supplied immutable
images. Its result is evidence verification, not transport/boot authorization.
"""
import json
import math
import time

from fm1_fixed_target_reset import Replay, canonical, digest
from native.expanded_sg import COMMAND_LIMIT, LIVE_SECONDS


def unique_object(pairs):
    # Keep the file-only verifier independent of CLI modules' import setup.
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate transcript JSON key')
        result[key] = value
    return result


def replay(raw, result, *, campaign_sha256, sources, adapter_sha256,
           backup_manifest_sha256, sg_binding, baseline, target, sector_order,
           observed_at):
    """Require every complete SG command, final page and terminal event."""
    if (not isinstance(raw, bytes) or len(raw) > 32 * 1048576 or
            any(not isinstance(image, bytes) or len(image) != 1048576
                for image in (baseline, target))):
        raise ValueError('Bounded transcript and complete immutable images required')
    changed = [address for address in range(0x4000, 0xD9000, 4096)
               if baseline[address:address + 4096] != target[address:address + 4096]]
    expected_order = [address for address in changed if address != 0x4000] + [0x4000]
    if (baseline[:0x4000] != target[:0x4000] or
            baseline[0xD9000:] != target[0xD9000:] or
            0x4000 not in changed or list(sector_order) != expected_order):
        raise ValueError('Exact changed application sectors with directory last required')
    events = [json.loads(line, object_pairs_hook=unique_object)
              for line in raw.decode('utf8').splitlines()]
    if not events or len(events) > 100000:
        raise ValueError('Bounded complete transcript required')
    times = [event.get('time') for event in events]
    if (type(observed_at) not in (int, float) or not math.isfinite(observed_at) or
            not all(type(t) in (int, float) and math.isfinite(t) for t in times) or
            times != sorted(times) or times[-1] > time.time() or
            not 0 <= times[0] - observed_at <= 120 or
            not 0 <= times[-1] - times[0] <= LIVE_SECONDS):
        raise ValueError('Invalid installation chronology')
    cursor = Replay(events)
    cursor.event('native_transaction_prepared', campaign_sha256=campaign_sha256,
        source_sha256=sources, adapter_sha256=adapter_sha256,
        backup_manifest_sha256=backup_manifest_sha256, sg_binding=sg_binding,
        variant='native', direction='install', retry=False)
    cursor.direction = 'install'
    cursor.command(0xFC0A)
    cursor.read(baseline, 0, 1048576)
    current, written = baseline, 0
    for address in sector_order:
        sector = target[address:address + 4096]
        actual = current[address:address + 4096]
        cursor.read(current, address, 4096)
        if actual != b'\xff' * 4096:
            cursor.event('durable_intent', operation='erase', address=address)
            cursor.command(0xFC0A)
            cursor.command(0xFB01, address)
            cursor.event('operation_returned', operation='erase', address=address)
        blank = current[:address] + b'\xff' * 4096 + current[address + 4096:]
        cursor.read(blank, address, 4096)
        for page in range(address, address + 4096, 256):
            payload = target[page:page + 256]
            if payload != b'\xff' * 256:
                cursor.event('durable_intent', operation='program', address=page)
                cursor.command(0xFC0A)
                cursor.command(0xFB04, page, payload)
                cursor.event('operation_returned', operation='program', address=page)
        current = current[:address] + sector + current[address + 4096:]
        cursor.read(current, address, 4096)
        cursor.event('sector_verified', address=address)
        written += 1
    cursor.read(target, 0, 1048576)
    accepted = dict(campaign_sha256=campaign_sha256, direction='install', variant='native',
        verified_sha256=digest(target), sectors_written=written,
        full_flash_readback_verified=True, boot_observed=False,
        physical_recovery_verified=False, kernel_exclusivity=False,
        hardware_admitted=False, installable=False)
    cursor.event('native_transaction_completed', **accepted)
    if (cursor.position != len(events) or cursor.index > COMMAND_LIMIT or
            canonical(result) != canonical(accepted)):
        raise ValueError('Exact terminal result and no trailing events required')
    return dict(verified=True, hardware_operations=0, commands=cursor.index,
        events=len(events), sectors=written, seconds=times[-1] - times[0],
        target_sha256=digest(target), transcript_sha256=digest(raw),
        boot_observed=False, physical_recovery_verified=False)
