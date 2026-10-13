#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Construct a private native probe NOR candidate offline; no USB or admission."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'jieli'))
import build_raw_diagnostic as emitter
import raw_flash_profile as raw
from audit_link import audit
from probe_artifact import flatten

STATUS = 'private-native-probe-constructed-offline'


def construct(baseline_a, baseline_b, manifest, identity, reference, app, elf,
              baseline_profile='recorded-original-loader'):
    if baseline_profile == 'recorded-original-loader':
        profile = raw.profile_dump(baseline_a, baseline_b, manifest, identity, reference)
    elif baseline_profile == 'fixed-loader':
        profile = raw.profile_dump_fixed_loader(baseline_a, baseline_b, manifest, identity, reference)
    else:
        raise ValueError('Explicit supported backup provenance required')
    image, reconstructed = flatten(elf)
    if app != reconstructed:
        raise ValueError('Application differs from independently reconstructed ELF')
    link = audit([('native-probe.elf', image)], [('app.bin', app)], True, runtime='sdk-free')
    if not link['passed'] or link['n_pending']:
        raise ValueError('Complete SDK-free link audit required')
    target = emitter._replace_application(baseline_a, reference, app)
    receipt = raw._validate_target_geometry(profile, baseline_a, target, reference, app)
    receipt.update(status=STATUS, diagnostic_profile='native-trio-private',
                   baseline_profile=baseline_profile, app_sha256=raw.digest(app),
                   elf_sha256=raw.digest(elf), link_audit=link, layout_passed=True,
                   target_bytes=len(target), hardware_approval=False,
                   hardware_admitted=False, installable=False, binary_emitted=False,
                   distribution='private stock-derived candidate; never commit or publish',
                   directory_sector=raw.APP_BASE,
                   installation_order='application data sectors before directory sector',
                   next_gate='Startup/recovery review and fresh bound backup admission')
    return target, receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('baseline-a', 'baseline-b', 'manifest', 'identity', 'reference', 'app', 'elf', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--baseline-profile', choices=('recorded-original-loader', 'fixed-loader'), required=True)
    args = parser.parse_args()
    target, receipt = construct(args.baseline_a.read_bytes(), args.baseline_b.read_bytes(),
                               json.loads(args.manifest.read_bytes()), json.loads(args.identity.read_bytes()),
                               args.reference, args.app.read_bytes(), args.elf.read_bytes(), args.baseline_profile)
    print(json.dumps(emitter._emit_private(args.out, target, receipt, STATUS), sort_keys=True))


if __name__ == '__main__':
    main()
