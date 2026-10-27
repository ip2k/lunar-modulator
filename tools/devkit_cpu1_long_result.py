#!/usr/bin/env python3
"""Validate long CPU1 publication receipts; never audio acceptance."""
import argparse
import json
from pathlib import Path
import re


def parse(data):
    text = data.decode('ascii', errors='replace')
    if 'LUNAR_CPU1_LONG error=' in text:
        raise ValueError('Long publication diagnostic reported an error')
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
    timer = row('LUNAR_CPU1_LONG timer_check_ticks=')
    if (not 2000000 <= timer.get('timer_check_ticks', 0) <= 3000000
            or timer.get('delay_os_ticks') != 10 or timer.get('rounds') != 100000000
            or timer.get('budget_ticks') != 3840000000):
        raise ValueError('Unexpected timer, dimensions or bound')
    phases = [row('LUNAR_CPU1_LONG phase=' + str(n) + ' ') for n in (0, 1)]
    result = row('LUNAR_CPU1_LONG complete_unfenced=')
    expected = dict(complete_unfenced=100000000, complete_fenced=100000000,
                    parent_errors_fenced=0, worker_errors_fenced=0, abort=0, exited=1,
                    parent0=200000000, parent1=0, parent_other=0,
                    worker0=0, worker1=200000000, worker_other=0)
    if any(result.get(key) != value for key, value in expected.items()):
        raise ValueError('Incomplete, corrupted, timed-out or migrated run')
    for n, phase in enumerate(phases):
        key = 'parent_errors_fenced' if n else 'parent_errors_unfenced'
        if (phase.get('complete') != 100000000 or phase.get('errors') != result.get(key)
                or not 0 <= phase.get('errors', -1) <= 100000000):
            raise ValueError('Phase and completion receipts disagree')
    if not 0 <= result.get('worker_errors_unfenced', -1) <= 100000000:
        raise ValueError('Missing unfenced worker comparison')
    for key, size in [('worker_stack_unused_words', 1024), ('stack_unused_words', 2048)]:
        if not 0 < result.get(key, 0) < size:
            raise ValueError('Invalid stack high-water receipt')
    if not 0 < result.get('ticks', 0) < 3840000000:
        raise ValueError('Missing or excessive duration')
    return dict(long_publication_pass=True, timer=timer, phases=phases, result=result,
                acceptance='Publication only; FPU, ring, renderer, DAC and analog soak gates remain')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('capture', type=Path)
    args = parser.parse_args()
    print(json.dumps(parse(args.capture.read_bytes()), indent=2))
