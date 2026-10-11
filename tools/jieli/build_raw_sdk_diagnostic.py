#!/usr/bin/env python3
"""MIT. Construct a private FM-1_092 SDK diagnostic target offline, without USB."""
import argparse
import json
from pathlib import Path

import build_raw_diagnostic as emitter
import raw_flash_profile as raw
import raw_sdk_diagnostic as sdk

STATUS = 'private-raw-sdk-diagnostic-constructed-offline'


def construct(baseline_a, baseline_b, manifest, identity, reference, app, elf,
              baseline_profile='recorded-original-loader', expected_native_audit=None):
    sdk.profile_dump(baseline_a, baseline_b, manifest, identity, reference, baseline_profile)
    target = emitter._replace_application(baseline_a, reference, app)
    receipt = sdk.validate_target(baseline_a, baseline_b, target, manifest, identity,
                                  reference, app, elf, baseline_profile, expected_native_audit)
    receipt.update(status=STATUS, target_bytes=len(target), binary_emitted=False,
                   directory_sector=raw.APP_BASE,
                   installation_order='application data sectors before directory sector',
                   distribution='private SDK and stock-derived target; never commit or publish',
                   hardware_approval=False)
    return target, receipt


def emit(directory, target, receipt):
    return emitter._emit_private(directory, target, receipt, STATUS)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('baseline-a', 'baseline-b', 'manifest', 'identity', 'reference', 'app', 'elf', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--baseline-profile', choices=('recorded-original-loader', 'fixed-loader'), required=True)
    parser.add_argument('--native-audit', type=Path)
    args = parser.parse_args()
    target, receipt = construct(args.baseline_a.read_bytes(), args.baseline_b.read_bytes(),
        json.loads(args.manifest.read_bytes()), json.loads(args.identity.read_bytes()),
        args.reference, args.app.read_bytes(), args.elf.read_bytes(), args.baseline_profile,
        json.loads(args.native_audit.read_bytes()) if args.native_audit else None)
    print(json.dumps(emit(args.out, target, receipt), sort_keys=True))


if __name__ == '__main__':
    main()
