#!/usr/bin/env python3
"""Validate finite per-task arithmetic and paced SRAM transfer, never audio."""
import argparse
import json
from pathlib import Path
import re


def parse(data):
    text = data.decode('ascii', errors='replace')
    if 'LUNAR_CPU1_RING error=' in text:
        raise ValueError('Ring diagnostic reported an error')
    lines = [re.sub(r'^\[\d{2}:\d{2}:\d{2}\.\d{3}\]', '', line)
             for line in text.splitlines()]
    def row(prefix):
        matches = [line for line in lines if line.startswith(prefix)]
        if len(matches) != 1:
            raise ValueError('Require exactly one ' + prefix + ' receipt')
        pairs = re.findall(r'(\w+)=(\d+)(?=\s|$)', matches[0])
        values = dict(pairs)
        if len(values) != len(pairs):
            raise ValueError('Duplicate receipt field')
        return {key: int(value) for key, value in values.items()}
    timer = row('LUNAR_CPU1_RING timer_check_ticks=')
    if (not 2000000 <= timer.get('timer_check_ticks', 0) <= 3000000 or
            any(timer.get(k) != v for k, v in dict(delay_os_ticks=10, blocks=413607,
                frames=64, rate=44118, capacity=16, budget_ms=625000).items())):
        raise ValueError('Unexpected timer or workload dimensions')
    arithmetic = [row('LUNAR_CPU1_RING fpu_op=' + str(op) + ' ') for op in range(4)]
    for op, r in enumerate(arithmetic):
        bits = r.get('parent_bits', -1)
        if (not 0 <= bits <= 0xffffffff or r.get('worker_bits') != bits or
                r.get('iterations') != 1024 or r.get('parent_batches') != 8 or
                r.get('worker_batches') != 8 or
                not 0 < r.get('parent_ticks', 0) < 24000000 or
                not 0 < r.get('worker_ticks', 0) < 24000000 or
                (op == 0 and bits != 1025) or (op == 1 and bits != 0x40000000) or
                (op > 0 and bits & 0x7f800000 == 0x7f800000)):
            raise ValueError('Missing or mismatched finite arithmetic')
    result = row('LUNAR_CPU1_RING complete=')
    expected = dict(complete=413607, consumed=413607, bad_crc=0, bad_data=0,
                    bad_sequence=0, abort=0, exited=1, parent0=413607, parent1=0,
                    parent_other=0, worker0=0, worker1=413607, worker_other=0, late_blocks=0)
    if any(result.get(k) != v for k, v in expected.items()):
        raise ValueError('Incomplete, corrupted, late, aborted or migrated ring')
    if (not 599990 <= result.get('elapsed_ms', 0) <= 600050 or
            not 0 <= result.get('max_late_ticks', -1) < 34815 or
            not 0 <= result.get('peak_depth', -1) <= 16):
        raise ValueError('Invalid pacing, duration or queue depth')
    for key, size in [('worker_stack_unused_words', 1024), ('stack_unused_words', 2048)]:
        if not 0 < result.get(key, 0) < size:
            raise ValueError('Invalid stack high-water receipt')
    return dict(paced_ring_pass=True, timer=timer, arithmetic=arithmetic, result=result,
                acceptance='Finite task arithmetic/SRAM ring only; FPU IRQ, renderer, DAC and analog soak gates remain')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('capture', type=Path)
    args = ap.parse_args()
    print(json.dumps(parse(args.capture.read_bytes()), indent=2))
