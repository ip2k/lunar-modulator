#!/usr/bin/env python3
"""MIT. Compare completed diagnostic PCM cases with an independent host replay.

Accepts UART prefixes and repeated worker snapshots. The reference bounds the
comparison; later target cases are counted but not certified. FNV fingerprints
are diagnostic checks, not cryptographic identity or analog audio acceptance.
This tool reads files only and sends no device commands.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

RECORD = re.compile(r'LUNAR_PCM completed=(\d+) case=(\d+) fnv1a=([0-9a-fA-F]{8})\s*$')


def records(text):
    rows, errors, last = {}, [], 0
    for number, line in enumerate(text.splitlines(), 1):
        if 'LUNAR_PCM' not in line:
            continue
        match = RECORD.search(line)
        if not match:
            errors.append(f'malformed PCM record at line {number}')
            continue
        completed, case = map(int, match.group(1, 2))
        if completed == 0:  # Startup snapshot, no completed case yet.
            continue
        value = (case, match.group(3).lower())
        if case >= 12 or case != (completed - 1) % 12:
            errors.append(f'invalid case order at completed {completed}')
        if completed < last:
            errors.append(f'completion counter regressed at line {number}')
        if completed in rows and rows[completed] != value:
            errors.append(f'conflicting snapshots at completed {completed}')
        rows[completed] = value
        last = completed
    return rows, errors


def compare(reference, target):
    expected, errors = records(reference)
    actual, target_errors = records(target)
    errors += target_errors
    if not expected:
        errors.append('reference contains no completed cases')
    if len(expected) < 24:
        errors.append('reference must cover at least two complete 12-case cycles')
    end = max(expected, default=0)
    if set(expected) != set(range(1, end + 1)):
        errors.append('reference completion sequence is incomplete')
    missing = sorted(set(expected) - set(actual))
    mismatches = [n for n in sorted(expected.keys() & actual.keys())
                  if expected[n] != actual[n]]
    return dict(completed_pcm_comparison_passed=not (errors or missing or mismatches),
                expected_cases=len(expected), matched_cases=sum(expected[n] == actual.get(n)
                                                              for n in expected),
                missing_completed=missing, mismatched_completed=mismatches,
                later_target_cases_not_compared=sum(n > end for n in actual), errors=errors,
                certifies_analog_audio=False, certifies_full_workload=False)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--reference', type=Path, required=True)
    ap.add_argument('--uart', type=Path, required=True)
    args = ap.parse_args()
    reference, target = args.reference.read_bytes(), args.uart.read_bytes()
    result = compare(reference.decode('utf-8', errors='replace'),
                     target.decode('utf-8', errors='replace'))
    result.update(reference_sha256=hashlib.sha256(reference).hexdigest(),
                  uart_sha256=hashlib.sha256(target).hexdigest())
    print(json.dumps(result, indent=2))
    return 0 if result['completed_pcm_comparison_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
