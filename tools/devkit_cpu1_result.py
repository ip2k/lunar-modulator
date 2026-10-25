#!/usr/bin/env python3
"""Validate a short CPU1 probe receipt, not audio or long-soak acceptance."""
import argparse
import json
from pathlib import Path
import re


def parse(data):
    text = data.decode('ascii', errors='replace')
    if 'LUNAR_CPU1 error=' in text:
        raise ValueError('CPU1 diagnostic reported an error')
    def row(prefix):
        lines = [line for line in text.splitlines() if line.startswith(prefix)]
        if len(lines) != 1:
            raise ValueError('Require exactly one ' + prefix + ' receipt')
        pairs = re.findall(r'(\w+)=(\d+)(?=\s|$)', lines[0])
        result = dict(pairs)
        if len(result) != len(pairs):
            raise ValueError('Duplicate receipt field')
        return {key: int(value) for key, value in result.items()}
    timer = row('LUNAR_CPU1 timer_check_ticks=')
    result = row('LUNAR_CPU1 complete=')
    if not 2000000 <= timer.get('timer_check_ticks', 0) <= 3000000:
        raise ValueError('Timer rate outside 24 MHz check range')
    if timer.get('delay_os_ticks') != 10 or timer.get('rounds') != 4096 or timer.get('words') != 64:
        raise ValueError('Unexpected probe dimensions')
    expected = dict(complete=4096, errors=0, abort=0, exited=1, parent0=4096,
                    parent1=0, parent_other=0, worker0=0, worker1=4096, worker_other=0)
    for key, value in expected.items():
        if result.get(key) != value:
            raise ValueError('Short probe failed: ' + key)
    for field, allocated in [('worker_stack_unused_words', 1024), ('stack_unused_words', 2048)]:
        if not 0 < result.get(field, 0) < allocated:
            raise ValueError('Missing or invalid stack high-water receipt: ' + field)
    if not 0 < result.get('ticks', 0) < 24000000 * 60:
        raise ValueError('Missing or excessive short-probe duration')
    return dict(short_publication_and_pinning_pass=True, timer=timer, result=result,
                acceptance='4096 exchanges only; long coherence, FPU, renderer, DAC and soak gates remain')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('capture', type=Path)
    args = parser.parse_args()
    print(json.dumps(parse(args.capture.read_bytes()), indent=2))
