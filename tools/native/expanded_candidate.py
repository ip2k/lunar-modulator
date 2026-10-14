#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Bind a private expanded candidate to backup evidence and audited ELF bytes.

Offline only: does not admit physical writes, migrate settings or emit OTA.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'jieli'))
import raw_flash_profile as raw
import expanded_flash_profile as expanded
from build_raw_diagnostic import _emit_private
from audit_link import audit, collect_sources
from probe_artifact import flatten, artifact_call_payloads, artifact_stub_boundaries

STATUS = 'private-expanded-native-candidate-verified-offline'


def construct(baseline_a, baseline_b, manifest, identity, reference, app, elf,
              baseline_profile, disassembly='', ram_layout='combined'):
    """Recompute each gate; caller receipts cannot substitute for checked bytes."""
    validators = {'recorded-original-loader': raw.profile_dump,
                  'fixed-loader': raw.profile_dump_fixed_loader}
    if baseline_profile not in validators:
        raise ValueError('Explicit supported backup provenance required')
    profile = validators[baseline_profile](baseline_a, baseline_b, manifest, identity, reference)
    image, reconstructed = flatten(elf, ram_layout, 'expanded-d9000')
    if app != reconstructed:
        raise ValueError('Application differs from independently reconstructed ELF')
    link = audit([('native-probe.elf', image)], [('app.bin', app)], True,
                 sources=collect_sources([Path(__file__).resolve().parents[2] / 'firmware/native']),
                 runtime='sdk-free',
                 call_payloads=artifact_call_payloads(image, app, disassembly),
                 stub_boundaries=artifact_stub_boundaries(image, app, disassembly))
    if not link['passed'] or link['n_pending']:
        raise ValueError('Complete SDK-free link audit required')
    target, receipt = expanded.construct_geometry(baseline_a, baseline_b, reference, app)
    sectors = [offset for offset in range(raw.APP_BASE, expanded.AREA_END, 4096)
               if baseline_a[offset:offset + 4096] != target[offset:offset + 4096]]
    if not sectors:
        raise ValueError('Target has no application changes')
    receipt.update(schema=1, status=STATUS, provenance_verified=True, elf_verified=True,
                   baseline_profile=baseline_profile, backup_profile=profile,
                   baseline_sha256=raw.digest(baseline_a), elf_sha256=raw.digest(elf),
                   disassembly_sha256=raw.digest(disassembly.encode()), link_audit=link,
                   ram_layout=ram_layout, flash_layout='expanded-d9000',
                   target_bytes=len(target), allowed_sectors=sectors,
                   protected_ranges=[[0, raw.APP_BASE], [expanded.AREA_END, raw.FLASH_BYTES]],
                   writable_ranges=[[offset, offset + 4096] for offset in sectors],
                   directory_sector=raw.APP_BASE,
                   installation_order='application data sectors before directory sector',
                   physical_writer_ready=False, hardware_approval=False, binary_emitted=False,
                   distribution='private stock-derived candidate; never commit or publish',
                   next_gate='Settings migration, OTA/recovery review and fresh physical admission')
    return target, receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('baseline-a', 'baseline-b', 'manifest', 'identity', 'reference', 'app', 'elf', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--baseline-profile', choices=('recorded-original-loader', 'fixed-loader'), required=True)
    parser.add_argument('--ram-layout', choices=('legacy', 'combined'), default='combined')
    parser.add_argument('--objdump', required=True, help='vendor pi32v2 objdump executable')
    args = parser.parse_args()
    decoded = subprocess.check_output([args.objdump, '-d', str(args.elf)], text=True)
    target, receipt = construct(args.baseline_a.read_bytes(), args.baseline_b.read_bytes(),
                               json.loads(args.manifest.read_bytes()), json.loads(args.identity.read_bytes()),
                               args.reference, args.app.read_bytes(), args.elf.read_bytes(),
                               args.baseline_profile, decoded, args.ram_layout)
    print(json.dumps(_emit_private(args.out, target, receipt, STATUS), sort_keys=True))


if __name__ == '__main__':
    main()
