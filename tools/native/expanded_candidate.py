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
from audit_link import Elf, audit, collect_sources
from probe_artifact import flatten, artifact_call_payloads, artifact_stub_boundaries

STATUS = 'private-expanded-native-candidate-verified-offline'
HOT_DSP_RAM_PRE_PUSH_READY_BODIES = [
                      'SixOp::Instance::Render', 'SixOp::Instance::RenderBlock', 'plaits::FMVoice::Render',
                      'plaits::fm::Voice<6>::Render(Parameters,float**,size_t)',
                      'Hall::Instance::Render', 'Limiter::HoldStep', 'Limiter::BoxStep',
                      'Limiter::TapOut', 'Limiter::Render', 'fm1_app_render']
# The c0 profiler-off frozen build predates the BoxStep RAM placement. Keep its
# exact ordered receipt shape as a compatibility profile; do not accept an
# arbitrary subset of the current placement list.
HOT_DSP_RAM_LEGACY_BODIES = ['SixOp::Instance::Render', 'SixOp::Instance::RenderBlock',
                             'plaits::FMVoice::Render',
                             'plaits::fm::Voice<6>::Render(Parameters,float**,size_t)',
                             'Hall::Instance::Render', 'Limiter::Render', 'fm1_app_render']
# Preserve the exact eight-body BoxStep experiment as well as the original
# seven-body profile; neither permits an arbitrary partial helper placement.
HOT_DSP_RAM_BOXSTEP_BODIES = [
    'SixOp::Instance::Render', 'SixOp::Instance::RenderBlock', 'plaits::FMVoice::Render',
    'plaits::fm::Voice<6>::Render(Parameters,float**,size_t)',
    'Hall::Instance::Render', 'Limiter::BoxStep', 'Limiter::Render', 'fm1_app_render']
# Exact profile after moving the internal resampler push helper. Retain the
# prior lists above as complete historical profiles; reject partial mixtures.
HOT_DSP_RAM_PUSH_READY_BODIES = HOT_DSP_RAM_PRE_PUSH_READY_BODIES + ['fm1_resampler_push_ready_']
HOT_DSP_RAM_PUSH_READY_DRUMS_BODIES = HOT_DSP_RAM_PUSH_READY_BODIES + ['Drums::Instance::Render']
HOT_DSP_RAM_RENDERBLOCK_BODIES = HOT_DSP_RAM_PUSH_READY_DRUMS_BODIES + ['Drums::Instance::RenderBlock']
HOT_DSP_RAM_BODIES = HOT_DSP_RAM_RENDERBLOCK_BODIES
HOT_DSP_RAM_SUPPORTED_BODY_PROFILES = (
    HOT_DSP_RAM_LEGACY_BODIES, HOT_DSP_RAM_BOXSTEP_BODIES,
    HOT_DSP_RAM_PRE_PUSH_READY_BODIES, HOT_DSP_RAM_PUSH_READY_BODIES,
    HOT_DSP_RAM_PUSH_READY_DRUMS_BODIES, HOT_DSP_RAM_RENDERBLOCK_BODIES)


def validate_hot_dsp_ram_receipts(elf, verification, artifact):
    """Bind the RAM section to exact linked receipts and the bounded runtime."""
    profile = verification.get('hot_dsp_ram') if isinstance(verification, dict) else None
    enabled = profile.get('enabled') if isinstance(profile, dict) else None
    if (type(enabled) is not bool or not isinstance(artifact, dict) or
            artifact.get('hot_dsp_ram') is not enabled):
        raise ValueError('Explicit matching hot DSP RAM build and artifact receipts required')
    if not enabled:
        if profile != dict(enabled=False, selected_bodies=[], all_callees_in_ram=False,
                           flash_write_execution_verified=False, extent=None):
            raise ValueError('Disabled hot DSP RAM receipt is malformed')
        return False
    runtime = verification.get('runtime_configuration')
    save = verification.get('project_save_service')
    if (profile.get('selected_bodies') not in HOT_DSP_RAM_SUPPORTED_BODY_PROFILES or
            profile.get('all_callees_in_ram') is not False or
            profile.get('flash_write_execution_verified') is not False or
            not isinstance(runtime, dict) or runtime.get('runtime_mode') not in
            ('diagnostic', 'song-diagnostic') or runtime.get('return_to_rom_seconds') != 120 or
            not isinstance(save, dict) or save.get('linked') is not True or
            any(save.get(key) is not False for key in (
                'storage_admitted', 'flash_io_bound', 'save_service_armed',
                'runtime_verified', 'hardware_tested'))):
        raise ValueError('Hot DSP RAM requires bounded diagnostic runtime and disarmed SAVE')
    extent = profile.get('extent')
    if not isinstance(extent, dict) or set(extent) != {
            'section', 'start', 'end', 'bytes', 'flash_load'}:
        raise ValueError('Exact hot DSP RAM extent receipt required')
    image = Elf(elf)
    sections = [row for row in image.sections if row['name'] == '.ram_dsp']
    start, end, load = (image.symbol_value(name) for name in ('_rd_start', '_rd_end', '_rd_load'))
    expected = (dict(section='.ram_dsp', start='0x%08x' % start,
                     end='0x%08x' % end, bytes=end - start,
                     flash_load='0x%08x' % load)
                if start is not None and end is not None and load is not None else None)
    if (len(sections) != 1 or expected != extent or start != sections[0]['addr'] or
            end - start != sections[0]['size'] or not 0x01C00000 <= start < end <= 0x01C06000):
        raise ValueError('Hot DSP RAM receipt differs from linked ELF extent')
    return True


def construct(baseline_a, baseline_b, manifest, identity, reference, app, elf,
              baseline_profile, disassembly='', ram_layout='combined',
              flash_layout='expanded-d9000', hot_dsp_ram=False,
              hot_dsp_ram_receipt=None):
    """Recompute each gate; caller receipts cannot substitute for checked bytes."""
    validators = {'recorded-original-loader': raw.profile_dump,
                  'fixed-loader': raw.profile_dump_fixed_loader}
    if baseline_profile not in validators:
        raise ValueError('Explicit supported backup provenance required')
    area_end = expanded.area_end(flash_layout)
    profile = validators[baseline_profile](baseline_a, baseline_b, manifest, identity, reference)
    if type(hot_dsp_ram) is not bool:
        raise TypeError('hot_dsp_ram must be a bool')
    if hot_dsp_ram:
        if not isinstance(hot_dsp_ram_receipt, dict):
            raise ValueError('Hot DSP RAM requires linked build and artifact receipts')
        if not validate_hot_dsp_ram_receipts(
                elf, hot_dsp_ram_receipt.get('verification'),
                hot_dsp_ram_receipt.get('artifact')):
            raise ValueError('Hot DSP RAM profile is not enabled in its receipts')
    elif hot_dsp_ram_receipt is not None and validate_hot_dsp_ram_receipts(
            elf, hot_dsp_ram_receipt.get('verification'),
            hot_dsp_ram_receipt.get('artifact')):
        raise ValueError('Hot DSP RAM ELF requires explicit candidate selection')
    image, reconstructed = flatten(elf, ram_layout, flash_layout, hot_dsp_ram)
    if app != reconstructed:
        raise ValueError('Application differs from independently reconstructed ELF')
    link = audit([('native-probe.elf', image)], [('app.bin', app)], True,
                 sources=collect_sources([Path(__file__).resolve().parents[2] / 'firmware/native']),
                 runtime='sdk-free',
                 call_payloads=artifact_call_payloads(image, app, disassembly),
                 stub_boundaries=artifact_stub_boundaries(image, app, disassembly))
    if not link['passed'] or link['n_pending']:
        raise ValueError('Complete SDK-free link audit required')
    target, receipt = expanded.construct_geometry(baseline_a, baseline_b, reference, app, flash_layout)
    sectors = [offset for offset in range(raw.APP_BASE, area_end, 4096)
               if baseline_a[offset:offset + 4096] != target[offset:offset + 4096]]
    if not sectors:
        raise ValueError('Target has no application changes')
    receipt.update(schema=1, status=STATUS, provenance_verified=True, elf_verified=True,
                   baseline_profile=baseline_profile, backup_profile=profile,
                   baseline_sha256=raw.digest(baseline_a), elf_sha256=raw.digest(elf),
                   disassembly_sha256=raw.digest(disassembly.encode()), link_audit=link,
                   ram_layout=ram_layout, flash_layout=flash_layout,
                   hot_dsp_ram=hot_dsp_ram,
                   target_bytes=len(target), allowed_sectors=sectors,
                   protected_ranges=[[0, raw.APP_BASE], [area_end, raw.FLASH_BYTES]],
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
    parser.add_argument('--flash-layout', choices=tuple(expanded.AREA_ENDS), default='expanded-d9000')
    parser.add_argument('--hot-dsp-ram', action='store_true')
    parser.add_argument('--verification', type=Path)
    parser.add_argument('--artifact', type=Path)
    parser.add_argument('--objdump', required=True, help='vendor pi32v2 objdump executable')
    args = parser.parse_args()
    decoded = subprocess.check_output([args.objdump, '-d', '-mcpu=r3', str(args.elf)], text=True)
    ram_receipt = None
    if args.verification is not None or args.artifact is not None:
        if args.verification is None or args.artifact is None:
            parser.error('--verification and --artifact must be supplied together')
        ram_receipt = dict(verification=json.loads(args.verification.read_bytes()),
                           artifact=json.loads(args.artifact.read_bytes()))
    if args.hot_dsp_ram and ram_receipt is None:
        parser.error('--hot-dsp-ram requires --verification and --artifact')
    target, receipt = construct(args.baseline_a.read_bytes(), args.baseline_b.read_bytes(),
                               json.loads(args.manifest.read_bytes()), json.loads(args.identity.read_bytes()),
                               args.reference, args.app.read_bytes(), args.elf.read_bytes(),
                               args.baseline_profile, decoded, args.ram_layout, args.flash_layout,
                               args.hot_dsp_ram, ram_receipt)
    print(json.dumps(_emit_private(args.out, target, receipt, STATUS), sort_keys=True))


if __name__ == '__main__':
    main()
