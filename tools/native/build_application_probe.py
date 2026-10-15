#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Link a private timed shared-app probe; never install or access a device.

Consumes sixteen source-bound -Oz/LTO/shared-resampler catalogue outputs.
Explicit --hot-dsp-os and --limiter-os options record the selected -Os units.
Cached object hashes and source manifests are checked against current inputs.
Hardware admission remains a separate operation.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
from module_selection import resolve_modules, wavetable_namespaces
import sys

from build_probe import check_pins
from audit_ram_call_allowlist import audit_ram_call_allowlist
from compile_catalogue import source_manifest, optimization_overrides
from compact_font import compact_header, compact_gfx
from prepare_wavetables import prepare
from embed_image_content import content_source
from companion_selection import builder_content_parent_indices
from verify_image_profile import load_prepared_profile
from flash_layout import FLASH_LAYOUTS, app_budget, linker_script
from stack_watermark import instrument_entry, verify_instrumentation
from runtime_mode import MODES, runtime_configuration
from firmware_identity import identity_configuration, platform_with_identity

ROOT = Path(__file__).resolve().parents[2]
ENGINE_IDS = ('macro', 'shapes', 'macro-heavy', 'sixop', 'dx7', 'sw-sophie',
              'drums', 'acid-bass', 'comet', 'crater', 'drawbar', 'trio',
              'phase-bend', 'test-sine')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def project_save_service_configuration(enabled):
    """Describe the opt-in production service while keeping storage disarmed."""
    if type(enabled) is not bool:
        raise TypeError("project SAVE service option must be a bool")
    return dict(linked=enabled,
                compile_definition="LUNAR_PROJECT_SAVE_SERVICE=1" if enabled else None,
                storage_admitted=False, flash_io_bound=False,
                save_service_armed=False, runtime_verified=False,
                hardware_tested=False)


def project_save_service_flags(enabled):
    """Compile the real app SAVE path only on explicit opt-in."""
    receipt = project_save_service_configuration(enabled)
    if not receipt["compile_definition"]:
        return []
    return ["-D" + receipt["compile_definition"],
            "-DFM1_STATE_BIN_COMPACT_WRITER=1"]


def native_midi_input_configuration(enabled):
    """Describe optional polled TRS input; USB MIDI stays available."""
    if type(enabled) is not bool:
        raise TypeError("native MIDI input option must be a bool")
    return dict(enabled=enabled,
                compile_definition="LUNAR_UART1_MIDI=1" if enabled else None,
                transport="UART1-RX/PH8" if enabled else None,
                ring_bytes=256 if enabled else 0,
                bytes_per_poll=32 if enabled else 0,
                usb_midi_preserved=True,
                diagnostic_counters=["usb_messages_drained", "uart_bytes_processed",
                                     "accepted_note_ons", "rejected_messages"],
                hardware_tested=False)


def native_midi_input_flags(enabled):
    receipt = native_midi_input_configuration(enabled)
    return (["-D" + receipt["compile_definition"]]
            if receipt["compile_definition"] else [])


def trio_diagnostic_pulse_configuration(enabled):
    if type(enabled) is not bool:
        raise TypeError("Trio diagnostic pulse option must be a bool")
    return dict(enabled=enabled, compile_definition=(
        "LUNAR_DIAGNOSTIC_TRIO_PULSE=1" if enabled else None),
        note=60 if enabled else None, velocity=100 if enabled else None,
        start_ms=3000 if enabled else None, end_ms=5000 if enabled else None,
        once=True, hardware_tested=False)


def validate_trio_diagnostic_pulse(enabled, runtime_mode, prepared_content,
                                   startup_project_index, startup_set_index,
                                   trs_midi_enabled, all_production_modules):
    receipt = trio_diagnostic_pulse_configuration(enabled)
    if not enabled:
        return receipt
    if runtime_mode != "song-diagnostic":
        raise ValueError("Trio diagnostic pulse requires song-diagnostic runtime")
    if not prepared_content:
        raise ValueError("Trio diagnostic pulse requires a prepared, content-free profile")
    if startup_project_index is not None or startup_set_index is not None:
        raise ValueError("Trio diagnostic pulse cannot be combined with startup content")
    if not trs_midi_enabled:
        raise ValueError("Trio diagnostic pulse requires explicit TRS MIDI diagnostic mode")
    if not all_production_modules:
        raise ValueError("Trio diagnostic pulse requires all production modules")
    return receipt


def trio_diagnostic_pulse_flags(enabled):
    receipt = trio_diagnostic_pulse_configuration(enabled)
    return (["-D" + receipt["compile_definition"]]
            if receipt["compile_definition"] else [])


def diagnostic_telemetry_configuration(enabled):
    if type(enabled) is not bool:
        raise TypeError("diagnostic telemetry option must be a bool")
    return dict(enabled=enabled,
                compile_definition=("LUNAR_DIAGNOSTIC_TELEMETRY=1" if enabled else None),
                interval_ms=1000 if enabled else None,
                transport="USB-MIDI-SysEx" if enabled else None,
                hardware_tested=False)


def validate_diagnostic_telemetry(enabled, runtime_mode):
    receipt = diagnostic_telemetry_configuration(enabled)
    if enabled and runtime_mode not in ("diagnostic", "song-diagnostic"):
        raise ValueError("diagnostic telemetry requires a bounded diagnostic runtime")
    return receipt


def diagnostic_telemetry_enabled(explicit, trio_pulse):
    """Keep legacy pulse builds instrumented while allowing telemetry alone."""
    diagnostic_telemetry_configuration(explicit)
    trio_diagnostic_pulse_configuration(trio_pulse)
    return explicit or trio_pulse


def diagnostic_telemetry_flags(enabled):
    receipt = diagnostic_telemetry_configuration(enabled)
    return (["-D" + receipt["compile_definition"]]
            if receipt["compile_definition"] else [])


def diagnostic_producer_gaps_configuration(enabled):
    if type(enabled) is not bool:
        raise TypeError("diagnostic producer-gap option must be a bool")
    if not enabled:
        return dict(enabled=False, schema=None, compile_definition=None,
                    frame_bytes=None, packets_per_frame=None, transport=None,
                    hardware_tested=False)
    return dict(enabled=True, schema=5,
                compile_definition="LUNAR_DIAGNOSTIC_PRODUCER_GAPS=1",
                frame_bytes=59, packets_per_frame=20,
                transport="USB-MIDI-SysEx", hardware_tested=False)


def validate_diagnostic_producer_gaps(enabled, runtime_mode, telemetry_explicit,
                                      startup_project_index, song_play):
    receipt = diagnostic_producer_gaps_configuration(enabled)
    if enabled and (runtime_mode != "song-diagnostic" or not telemetry_explicit
                    or startup_project_index is None or not song_play):
        raise ValueError("producer-gap telemetry requires explicit telemetry, prepared song startup, "
                         "one-shot song PLAY and song-diagnostic runtime")
    return receipt


def diagnostic_producer_gaps_flags(enabled):
    receipt = diagnostic_producer_gaps_configuration(enabled)
    return (["-D" + receipt["compile_definition"]]
            if receipt["compile_definition"] else [])


def diagnostic_irq_profile_configuration(enabled):
    if type(enabled) is not bool:
        raise TypeError("diagnostic IRQ profile option must be a bool")
    return dict(enabled=enabled, schema=6 if enabled else None,
                compile_definition="LUNAR_DIAGNOSTIC_IRQ_PROFILE=1" if enabled else None,
                frame_bytes=119 if enabled else None,
                packets_per_frame=40 if enabled else None,
                transport="USB-MIDI-SysEx" if enabled else None,
                hardware_tested=False)


def validate_diagnostic_irq_profile(enabled, runtime_mode, telemetry_explicit):
    receipt = diagnostic_irq_profile_configuration(enabled)
    if enabled and (runtime_mode != "song-diagnostic" or not telemetry_explicit):
        raise ValueError("diagnostic IRQ profile requires explicit telemetry and song-diagnostic runtime")
    return receipt


def diagnostic_irq_profile_flags(enabled):
    receipt = diagnostic_irq_profile_configuration(enabled)
    return (["-D" + receipt["compile_definition"]]
            if receipt["compile_definition"] else [])


def diagnostic_cpu_rate_configuration(enabled):
    if type(enabled) is not bool:
        raise TypeError("diagnostic CPU-rate option must be a bool")
    return dict(enabled=enabled, schema=8 if enabled else None,
                compile_definition="LUNAR_DIAGNOSTIC_CPU_RATE=1" if enabled else None,
                frame_bytes=49 if enabled else None,
                packets_per_frame=17 if enabled else None,
                kernel="fixed integer workload in XIP and .ram_text" if enabled else None,
                iterations_per_trial=4096 if enabled else None,
                trials_per_kernel=4 if enabled else None,
                timing="raw TIMER4 ticks; no CPU frequency interpretation" if enabled else None,
                starts="post-recovery, pre-platform flash probe" if enabled else None,
                register_writes=False, hardware_tested=False)


def validate_diagnostic_cpu_rate(enabled, runtime_mode, telemetry_explicit,
                                 song_play, trio_pulse):
    receipt = diagnostic_cpu_rate_configuration(enabled)
    if enabled and (runtime_mode != "song-diagnostic" or not telemetry_explicit
                    or song_play or trio_pulse):
        raise ValueError("CPU-rate calibration requires explicit song-diagnostic telemetry with playback disabled")
    return receipt


def diagnostic_cpu_rate_flags(enabled):
    receipt = diagnostic_cpu_rate_configuration(enabled)
    return (["-D" + receipt["compile_definition"]]
            if receipt["compile_definition"] else [])


def render_stage_profile_configuration(enabled):
    if type(enabled) is not bool:
        raise TypeError("render-stage profile option must be a bool")
    return dict(enabled=enabled,
                compile_definition=("LUNAR_RENDER_STAGE_PROFILE=1" if enabled else None),
                schema=2 if enabled else None,
                stages=["sequence_dispatch", "sound_0", "sound_1", "sound_2",
                        "sound_3", "master_fx_0", "master_fx_1", "postmix",
                        "display_strip"] if enabled else [],
                hardware_tested=False)


def validate_render_stage_profile(enabled, runtime_mode, telemetry_explicit):
    receipt = render_stage_profile_configuration(enabled)
    if enabled and (not telemetry_explicit or
                    runtime_mode not in ("diagnostic", "song-diagnostic")):
        raise ValueError("render-stage profiling requires explicit telemetry and a bounded diagnostic runtime")
    return receipt


def render_stage_profile_flags(enabled):
    receipt = render_stage_profile_configuration(enabled)
    return (["-D" + receipt["compile_definition"]]
            if receipt["compile_definition"] else [])


def engine_render_profile_configuration(enabled):
    if type(enabled) is not bool:
        raise TypeError("engine render profile option must be a bool")
    return dict(enabled=enabled, schema=7 if enabled else None,
                compile_definition="LUNAR_DIAGNOSTIC_ENGINE_RENDER_PROFILE=1" if enabled else None,
                frame_bytes=54 if enabled else None, packets_per_frame=18 if enabled else None,
                counters=("uptime_ms", "drums_render_ticks", "drums_render_calls",
                          "drums_render_block_ticks", "drums_render_block_calls",
                          "sixop_render_ticks", "sixop_render_calls",
                          "sixop_render_block_ticks", "sixop_render_block_calls") if enabled else [],
                counter_semantics="cumulative-uint32-device-timer-ticks" if enabled else None,
                hardware_tested=False)


def validate_engine_render_profile(enabled, runtime_mode, telemetry_explicit,
                                   render_stage_profile, producer_gaps, irq_profile):
    receipt = engine_render_profile_configuration(enabled)
    if enabled and (runtime_mode != "song-diagnostic" or not telemetry_explicit or
                    not render_stage_profile or producer_gaps or irq_profile):
        raise ValueError("engine render profiling requires song-diagnostic telemetry and schema-2 stage profiling, "
                         "and cannot share producer-gap or IRQ cadence")
    return receipt


def engine_render_profile_flags(enabled):
    receipt = engine_render_profile_configuration(enabled)
    return (["-D" + receipt["compile_definition"]]
            if receipt["compile_definition"] else [])


def validate_clock_snapshot(enabled, runtime_mode, telemetry_explicit):
    if type(enabled) is not bool:
        raise TypeError("clock snapshot option must be a bool")
    if enabled and (not telemetry_explicit or
                    runtime_mode not in ("diagnostic", "song-diagnostic")):
        raise ValueError("clock snapshot requires explicit telemetry and a bounded diagnostic runtime")
    return dict(enabled=enabled, schema=3 if enabled else None,
                supplemental_schema=4 if enabled else None,
                supplemental_registers=("pll_osc_selector_raw", "pll_predivider_raw",
                                        "pll_multiplier_raw") if enabled else [],
                supplemental_register_addresses=("0x119a0", "0x119a8", "0x119ac") if enabled else [],
                supplemental_frequency_interpreted=False,
                compile_definition="LUNAR_DIAGNOSTIC_CLOCK_SNAPSHOT=1" if enabled else None,
                sample="post-platform-init" if enabled else None,
                register_writes=False, frequency_interpreted=False, hardware_tested=False)


def validate_diagnostic_song_play(enabled, runtime_mode, startup_project_index,
                                  telemetry, trio_pulse):
    if type(enabled) is not bool:
        raise TypeError("diagnostic song play option must be a bool")
    if enabled and (runtime_mode != "song-diagnostic" or
                    startup_project_index is None or not telemetry or trio_pulse):
        raise ValueError("diagnostic song play requires prepared project startup, "
                         "song-diagnostic telemetry and no Trio pulse")
    return dict(enabled=enabled,
                compile_definition="LUNAR_DIAGNOSTIC_SONG_PLAY=1" if enabled else None,
                start_ms=2000 if enabled else None,
                once=enabled, hardware_tested=False)


def state_bin_object_index(objects):
    """Find the one cached codec object that a SAVE build must replace."""
    matches = [i for i, path in enumerate(objects)
               if Path(path).as_posix().endswith("state/state/state_bin.o")]
    if len(matches) != 1:
        raise SystemExit("Expected exactly one catalogue state_bin.o, found " + str(len(matches)))
    return matches[0]


def compact_state_bin_flags(tc, catalogue, indexed_tft, shapes_voices):
    """Mirror compile_catalogue's C target flags and add the SAVE codec mode."""
    shard = catalogue / "shard-00"
    return ["-target", "pi32v2", "-mcpu=r3", "-mfprev1", "-std=c99", "-Oz",
            "-ffreestanding", "-fno-builtin", "-ffunction-sections", "-fdata-sections",
            "-D_GNU_SOURCE", "-D_XOPEN_SOURCE=700", "-DFM1_FREESTANDING=1",
            "-D_LIBCPP_HAS_NO_THREADS", "-D_LIBCPP_DISABLE_EXTERN_TEMPLATE",
            "-isystem", str(shard / "cxx"), "-isystem", str(tc / "pi32v2/include"),
            "-DFM1_TFT_INDEXED=" + str(int(indexed_tft)),
            "-DFM1_SHAPES_VOICES=" + str(shapes_voices), "-flto",
            "-DFM1_STATE_BIN_COMPACT_WRITER=1",
            "-I", str(ROOT / "engines/include"), "-I", str(ROOT / "engines/mod"),
            "-I", str(shard / "obj/gen"), "-I", str(ROOT / "sim/web/src"),
            "-Wall", "-Wextra"]


def replace_with_compact_state_bin(objects, catalogue, tc, out, indexed_tft, shapes_voices):
    """Replace the freshness-checked default codec rather than linking both."""
    index = state_bin_object_index(objects)
    cached = objects[index]
    fresh = out / "state-bin-compact" / "state_bin.o"
    fresh.parent.mkdir(parents=True, exist_ok=False)
    source = ROOT / "engines/state/state_bin.c"
    flags = compact_state_bin_flags(tc, catalogue, indexed_tft, shapes_voices)
    compiler = str(tc / "common/bin/clang")
    subprocess.run([compiler, *flags, "-c", str(source), "-o", str(fresh)],
                   check=True, capture_output=True, text=True)
    objects[index] = fresh
    return dict(mode="compact-writer", source=str(source), source_sha256=digest(source),
                cached_object=str(cached), cached_object_sha256=digest(cached),
                fresh_object=str(fresh), fresh_object_sha256=digest(fresh),
                compile_flags=flags, compile_definition="FM1_STATE_BIN_COMPACT_WRITER=1",
                replaced_exactly_one=True)


def embedded_content_receipt(prepared_sha256, source, descriptors, payloads):
    """Build a receipt whose ordered identities describe the linked payloads."""
    if len(descriptors) != len(payloads):
        raise ValueError('Content descriptors and payloads differ in count')
    assets = []
    for descriptor, payload in zip(descriptors, payloads):
        if not isinstance(descriptor, dict):
            raise ValueError('Content descriptor is invalid')
        kind = descriptor.get('kind')
        if kind not in ('project', 'set'):
            raise ValueError('Content descriptor has an invalid kind')
        payload_sha256 = hashlib.sha256(payload).hexdigest()
        if descriptor.get('bytes') != len(payload):
            raise ValueError('Prepared content length differs from payload')
        if descriptor.get('packed_sha256') != payload_sha256:
            raise ValueError('Prepared content digest differs from payload')
        assets.append(dict(kind=kind, bytes=len(payload), packed_sha256=payload_sha256))
    return dict(prepared_sha256=prepared_sha256,
                source_sha256=hashlib.sha256(source).hexdigest(),
                asset_count=len(payloads), packed_content_bytes=sum(map(len, payloads)),
                packed_sha256=[asset['packed_sha256'] for asset in assets], assets=assets,
                sequence_semantics_verified=False, native_playback_verified=False)


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise SystemExit('Pinned adaptation no longer matches: ' + old)
    return text.replace(old, new)


def hot_dsp_ram_linker_script(source, enabled):
    """Keep the default generated linker script byte-for-byte unchanged."""
    if type(enabled) is not bool:
        raise TypeError('hot DSP RAM option must be a bool')
    templates = (
        ('/* HOT_DSP_RAM_PHDR_BEGIN\n',
         '    ramdsp PT_LOAD FLAGS(5);\n',
         '    HOT_DSP_RAM_PHDR_END */'),
        ('    /* HOT_DSP_RAM_SECTION_BEGIN\n',
         '    .ram_dsp : { _rd_start = .; KEEP(*(.ram_dsp*)) . = ALIGN(4); _rd_end = .; } > RAMTEXT AT > XIP :ramdsp\n'
         '    _rd_load = LOADADDR(.ram_dsp);\n',
         '    HOT_DSP_RAM_SECTION_END */'),
        ('/* HOT_DSP_RAM_ASSERT_BEGIN\n',
         'ASSERT(_rd_start >= _rt_end && _rd_end <= 0x01C06000,\n'
         '       "Lunar hot DSP RAM overlaps flash-writer code or reserved debug region")\n',
         'HOT_DSP_RAM_ASSERT_END */'),
    )
    for begin, body, end in templates:
        marker = begin + body + end
        if source.count(marker) != 1:
            raise ValueError('Pinned hot DSP RAM linker markers changed')
        marker_start = source.index(marker)
        line_start = source.rfind('\n', 0, marker_start) + 1
        marker_end = marker_start + len(marker)
        line_end = source.find('\n', marker_end)
        if line_end < 0:
            line_end = len(source)
        else:
            line_end += 1
        source = source[:line_start] + (body if enabled else '') + source[line_end:]
    return source


HOT_DSP_RAM_BODIES = ['SixOp::Instance::Render', 'SixOp::Instance::RenderBlock', 'plaits::FMVoice::Render',
                      'plaits::fm::Voice<6>::Render(Parameters,float**,size_t)',
                      'Hall::Instance::Render', 'Limiter::BoxStep', 'Limiter::Render', 'fm1_app_render']


def hot_dsp_ram_configuration(enabled, runtime_mode):
    if type(enabled) is not bool:
        raise TypeError('hot DSP RAM option must be a bool')
    if enabled and runtime_mode not in ('diagnostic', 'song-diagnostic'):
        raise ValueError('--hot-dsp-ram requires a bounded diagnostic or song-diagnostic runtime')
    return dict(enabled=enabled, selected_bodies=HOT_DSP_RAM_BODIES if enabled else [],
                all_callees_in_ram=False, flash_write_execution_verified=False)


def hot_dsp_ram_platform(source, enabled):
    if not enabled:
        return source
    source = replace_once(
        source,
        '    extern uint32_t _pool_start[], _pool_end[], _rt_start[], _rt_end[], _rt_load[];\n',
        '    extern uint32_t _pool_start[], _pool_end[], _rt_start[], _rt_end[], _rt_load[];\n'
        '    extern uint32_t _rd_start[], _rd_end[], _rd_load[];\n')
    source = replace_once(
        source,
        '    for (s = _rt_load, d = _rt_start; d < _rt_end; s++, d++) *d = *s;\n',
        '    for (s = _rt_load, d = _rt_start; d < _rt_end; s++, d++) *d = *s;\n'
        '    for (s = _rd_load, d = _rd_start; d < _rd_end; s++, d++) *d = *s;\n')
    # The HAL's second PC window admits only .ram_text by default. Extend its
    # upper bound through the separately copied DSP section; the linker bounds
    # both sections within RAMTEXT and keeps the flash-writer closure separate.
    guard = '    fm1_guard_enable(FM1_GUARD_STACK | FM1_GUARD_WRITE | FM1_GUARD_BUS | FM1_GUARD_PC);\n'
    return replace_once(source, guard, guard +
        '    fm1__dbg_unlock();\n'
        '    FM1_PC_LIMIT1_H = (uint32_t)(uintptr_t)_rd_end - 1u;\n'
        '    fm1__dbg_lock();\n')


def hot_dsp_ram_extent(elf_path):
    sys.path.insert(0, str(ROOT / 'tools/jieli'))
    from audit_link import Elf
    image = Elf(elf_path.read_bytes())
    sections = [section for section in image.sections if section['name'] == '.ram_dsp']
    start, end, load = (image.symbol_value(name) for name in ('_rd_start', '_rd_end', '_rd_load'))
    if (len(sections) != 1 or start is None or end is None or load is None or
            start != sections[0]['addr'] or end - start != sections[0]['size'] or
            not start < end <= 0x01C06000 or start < 0x01C00000):
        raise SystemExit('Invalid linked hot DSP RAM extent')
    return dict(section='.ram_dsp', start='0x%08x' % start,
                end='0x%08x' % end, bytes=end - start,
                flash_load='0x%08x' % load)


def checked_catalogue(root, compressed=False, indexed_tft=False, shapes_voices=12,
                      hot_dsp_os=False, hot_dsp_ram=False,
                      engine_render_profile=False, limiter_os=False):
    objects, receipts, indices = [], [], set()
    inputs = source_manifest(ROOT)
    overrides = optimization_overrides('z', hot_dsp_os, limiter_os)
    expected = json.loads((root / 'shard-00/objects.json').read_text())
    for shard in range(16):
        directory = root / ('shard-%02d' % shard)
        report = json.loads((directory / 'report.json').read_text())
        required = dict(shard=shard, chunks=16, catalogue_objects=len(expected),
                        gpl_mods=1, modules='all', optimization='-Oz', lto=True,
                        shared_resampler=True, indexed_tft=indexed_tft, shapes_voices=shapes_voices,
                        closed_sdk_archives=[], hot_dsp_ram=hot_dsp_ram,
                        engine_render_profile=engine_render_profile,
                        device_sdk_headers=[])
        if any(report.get(k) != v for k, v in required.items()):
            raise SystemExit('Incompatible catalogue report: ' + str(directory))
        if report.get('optimization_overrides', {}) != overrides:
            raise SystemExit('Incompatible catalogue optimization overrides')
        recorded_limiter_os = report.get('limiter_os', False)
        if type(recorded_limiter_os) is not bool or recorded_limiter_os is not limiter_os:
            raise SystemExit('Incompatible catalogue limiter optimization selection')
        if report.get('source_manifest') != inputs:
            raise SystemExit('Catalogue source manifest is stale or absent')
        if json.loads((directory / 'objects.json').read_text()) != expected:
            raise SystemExit('Catalogue object lists differ')
        if digest(directory / 'cxx/__config') != report['configured_sha256']:
            raise SystemExit('Catalogue C++ configuration hash mismatch')
        for item in report['results']:
            index = item['index']
            if (index in indices or index % 16 != shard or
                    not 0 <= index < len(expected) or
                    item['object'] != expected[index] or item['exit']):
                raise SystemExit('Invalid catalogue result')
            indices.add(index)
            relative = Path(item['object'])
            if relative.is_absolute() or '..' in relative.parts:
                raise SystemExit('Invalid catalogue object path')
            object_opt = overrides.get(item['object'], '-Oz')
            # Legacy uniform -Oz receipts lack per-object settings. Mixed
            # receipts must explicitly identify every unit's actual setting.
            required_opt = None if (hot_dsp_os or limiter_os) else '-Oz'
            if item.get('optimization', required_opt) != object_opt:
                raise SystemExit('Catalogue object optimization mismatch')
            obj = directory / 'obj' / relative
            if digest(obj) != item['sha256']:
                raise SystemExit('Catalogue object hash mismatch: ' + str(obj))
            receipts.append(dict(path=str(obj), sha256=item['sha256'],
                                 optimization=object_opt))
            if item['object'] not in ('sim/src/fm1_web.o', 'sim/src/fm1_app.o',
                                       'our/src/registry.o') and not (compressed and
                                       item['object'] in tuple('tp/' + n + '/resources.o' for n in compressed)):
                objects.append(obj)
    if indices != set(range(len(expected))):
        raise SystemExit('Incomplete catalogue')
    return objects, receipts



def measure_app_storage(compiler, flags, out):
    """Use target ABI constants, not host sizeof, for framebuffer pool credit."""
    source = out / 'measure_app_storage.c'
    source.write_text('#include "fm1_app.h"\n'
                      'unsigned lunar_app_storage(void) { return sizeof(fm1_app_t); }\n')
    sizes = []
    common = [flag for flag in flags if not flag.startswith('-DFM1_TFT_INDEXED=')]
    for indexed in (0, 1):
        ir = out / ('app-storage-%d.ll' % indexed)
        subprocess.run([compiler, *common, '-DFM1_TFT_INDEXED=' + str(indexed),
                        '-std=c99', '-S', '-emit-llvm', str(source), '-o', str(ir)],
                       check=True, capture_output=True, text=True)
        match = re.search(r'define[^\n]*@lunar_app_storage\([^}]*?ret i32 (\d+)',
                          ir.read_text(), re.S)
        if not match:
            raise SystemExit('Target application sizeof did not reduce to one constant')
        sizes.append(int(match.group(1)))
    if sizes[1] > sizes[0]:
        raise SystemExit('Indexed application unexpectedly exceeds RGB565 storage')
    return dict(rgb565_bytes=sizes[0], indexed_bytes=sizes[1],
                pool_credit_bytes=(sizes[0] - sizes[1]) // 16 * 16)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--toolchain', type=Path, required=True)
    parser.add_argument('--catalogue', type=Path, required=True)
    parser.add_argument('--hot-dsp-os', action='store_true',
                        help='Require explicit sixop/Hall -Os catalogue receipts; '
                        'all other units remain -Oz unless another per-object option is selected')
    parser.add_argument('--limiter-os', action='store_true',
                        help='Require explicit fx_limit.o -Os catalogue receipt; '
                        'independent of --hot-dsp-os')
    parser.add_argument('--hot-dsp-ram', action='store_true',
                        help='Opt in to selected render bodies in RAM; bounded diagnostic runtime only')
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--firmware-identity',
                        help='Explicit Lunar FM-1_5xx handshake identity; omitted keeps historical FM-1_990 probes')
    parser.add_argument('--runtime-mode', choices=MODES, default='diagnostic',
                        help='Song diagnostic returns after 120 seconds; default diagnostic after 20. '
                        'Continuous removes only timed ROM return; remains a private '
                        'unadmitted build with no NOR writes or OTA cleanup')
    parser.add_argument('--stack-watermark', action='store_true',
                        help='Paint both reserved stacks before C entry and sample observed margins; '
                        'diagnostic evidence only, not stack admission')
    parser.add_argument('--flash-layout', choices=FLASH_LAYOUTS, default='protected',
                        help='Explicit link budget only; does not admit packaging or installation')
    parser.add_argument('--exclude', choices=ENGINE_IDS, action='append', default=[])
    parser.add_argument('--modules', help='Literal comma-separated engine/effect/MIDI/mod IDs; '
                        'timed probe must retain trio; incompatible with --exclude')
    parser.add_argument('--prepared-profile', type=Path,
                        help='Checked builder input directory; replaces --modules/--exclude')
    parser.add_argument('--expected-profile-sha256',
                        help='Controller-retained prepared manifest digest')
    parser.add_argument('--link-set-loader', action='store_true',
                        help='Retain the standalone streaming set loader; does not activate content')
    parser.add_argument('--link-project-loader', action='store_true',
                        help='Retain disposable project modulation/sequence staging; does not activate a project')
    parser.add_argument('--link-project-save-service', action='store_true',
                        help='Opt in to the real production SAVE scheduler; storage stays unadmitted and unbound')
    parser.add_argument('--startup-set-index', type=int,
                        help='Opt-in timed probe: stage this embedded SET before Trio allocation; '
                        'requires --link-set-loader and a prepared profile')
    parser.add_argument('--startup-project-index', type=int,
                        help='Opt-in timed probe: restore this embedded PROJECT; '
                        'requires --link-project-loader and a prepared profile')
    parser.add_argument('--shapes-voices', type=int, choices=range(1, 13), default=12,
                        help='Require the selected Shapes polyphony in the catalogue')
    parser.add_argument('--indexed-tft', action='store_true',
                        help='Require a uniformly indexed catalogue and application')
    parser.add_argument('--compressed-wavetables', action='store_true',
                        help='Startup decode fixed RAM tables; reduce instance pool accordingly')
    parser.add_argument('--enable-trs-midi', action='store_true',
                        help='Opt in to polled UART1/PH8 MIDI input alongside USB MIDI')
    parser.add_argument('--diagnostic-trio-pulse', action='store_true',
                        help='Opt in to one C4 pulse at 3-5s for a content-free Trio diagnostic')
    parser.add_argument('--diagnostic-song-play', action='store_true',
                        help='Start the prepared diagnostic song once after 2s of readiness')
    parser.add_argument('--diagnostic-telemetry', action='store_true',
                        help='Opt in to bounded one-second USB-MIDI diagnostic reports; content may be prepared')
    parser.add_argument('--diagnostic-producer-gaps', action='store_true',
                        help='Opt in to schema-5 producer/display timing reports for prepared song playback')
    parser.add_argument('--diagnostic-irq-profile', action='store_true',
                        help='Opt in to schema-6 IRQ timing reports in song-diagnostic mode; requires telemetry')
    parser.add_argument('--diagnostic-cpu-rate', action='store_true',
                        help='Opt in to schema-8 fixed-work XIP/SRAM raw-tick comparison; no CPU-frequency claim')
    parser.add_argument('--diagnostic-clock-snapshot', action='store_true',
                        help='Report raw post-platform clock registers; no clock changes or MHz claim')
    parser.add_argument('--render-stage-profile', action='store_true',
                        help='Opt in to schema-2 render-stage reports; requires --diagnostic-telemetry')
    parser.add_argument('--diagnostic-engine-render-profile', action='store_true',
                        help='Opt in to schema-7 Drums/SixOp Render versus RenderBlock timing; requires schema 2')
    parser.add_argument('--flash-plaits-wavetables', action='store_true',
                        help='With compressed tables, retain original Plaits wave bank in flash '
                        'to recover RAM; decode Braids only when Shapes is selected')
    args = parser.parse_args()
    try:
        identity_receipt = identity_configuration(args.firmware_identity)
    except ValueError as error:
        parser.error(str(error))
    runtime_policy = runtime_configuration(args.runtime_mode)
    save_service_receipt = project_save_service_configuration(args.link_project_save_service)
    native_midi_receipt = native_midi_input_configuration(args.enable_trs_midi)
    if bool(args.prepared_profile) != bool(args.expected_profile_sha256):
        parser.error('--prepared-profile and --expected-profile-sha256 require each other')
    if args.prepared_profile and (args.modules is not None or args.exclude):
        parser.error('--prepared-profile cannot be combined with --modules or --exclude')
    try:
        hot_dsp_ram_receipt = hot_dsp_ram_configuration(args.hot_dsp_ram, args.runtime_mode)
    except ValueError as error:
        parser.error(str(error))
    content_inputs, generated_content = None, None
    content_parent_indices, selection_receipt_sha256 = None, None
    if args.prepared_profile:
        try:
            content_inputs = load_prepared_profile(args.prepared_profile,
                                                  args.expected_profile_sha256)
            content_parent_indices, selection_receipt_sha256 = builder_content_parent_indices(
                args.prepared_profile, args.expected_profile_sha256,
                content_inputs.report, args.startup_project_index, args.startup_set_index)
            generated_content = content_source(
                content_inputs, content_parent_indices,
                require_set_parents=args.startup_project_index is not None)
            args.modules = ','.join(content_inputs.report['module_selection']['selected'])
        except (ValueError, OSError, KeyError, TypeError) as error:
            parser.error(str(error))
    if args.startup_set_index is not None and args.startup_project_index is not None:
        parser.error('Standalone SET and PROJECT startup modes are mutually exclusive')
    if args.startup_set_index is not None:
        if not args.link_set_loader or not content_inputs:
            parser.error('--startup-set-index requires --link-set-loader and --prepared-profile')
        assets = content_inputs.report['content']
        if not 0 <= args.startup_set_index < len(assets):
            parser.error('--startup-set-index is outside the embedded catalogue')
        if assets[args.startup_set_index]['kind'] != 'set':
            parser.error('--startup-set-index must identify a SET, not a project')
    if args.startup_project_index is not None:
        if not args.link_project_loader or not content_inputs:
            parser.error('--startup-project-index requires --link-project-loader and --prepared-profile')
        assets = content_inputs.report['content']
        if not 0 <= args.startup_project_index < len(assets):
            parser.error('--startup-project-index is outside the embedded catalogue')
        if assets[args.startup_project_index]['kind'] != 'project':
            parser.error('--startup-project-index must identify a PROJECT')
        if content_parent_indices is not None and any(parent >= 0 for parent in content_parent_indices):
            if args.startup_project_index >= len(assets):
                parser.error('Companion SET parent startup index is outside the catalogue')
            if any(parent != args.startup_project_index for parent in content_parent_indices if parent >= 0):
                parser.error('Every companion SET must name the selected startup project')
    try:
        trio_pulse_receipt = validate_trio_diagnostic_pulse(
            args.diagnostic_trio_pulse, args.runtime_mode,
            bool(content_inputs) and not content_inputs.report['content'],
            args.startup_project_index, args.startup_set_index,
            args.enable_trs_midi,
            bool(content_inputs) and all(
                module in content_inputs.report['module_selection']['selected']
                for module in ENGINE_IDS if module != 'test-sine'))
    except ValueError as error:
        parser.error(str(error))
    telemetry_enabled = diagnostic_telemetry_enabled(
        args.diagnostic_telemetry, args.diagnostic_trio_pulse)
    try:
        telemetry_receipt = validate_diagnostic_telemetry(
            telemetry_enabled, args.runtime_mode)
        render_profile_receipt = validate_render_stage_profile(
            args.render_stage_profile, args.runtime_mode, args.diagnostic_telemetry)
        clock_snapshot_receipt = validate_clock_snapshot(
            args.diagnostic_clock_snapshot, args.runtime_mode, args.diagnostic_telemetry)
        song_play_receipt = validate_diagnostic_song_play(
            args.diagnostic_song_play, args.runtime_mode, args.startup_project_index,
            telemetry_enabled, args.diagnostic_trio_pulse)
        producer_gap_receipt = validate_diagnostic_producer_gaps(
            args.diagnostic_producer_gaps, args.runtime_mode,
            args.diagnostic_telemetry, args.startup_project_index,
            args.diagnostic_song_play)
        irq_profile_receipt = validate_diagnostic_irq_profile(
            args.diagnostic_irq_profile, args.runtime_mode, args.diagnostic_telemetry)
        cpu_rate_receipt = validate_diagnostic_cpu_rate(
            args.diagnostic_cpu_rate, args.runtime_mode, args.diagnostic_telemetry,
            args.diagnostic_song_play, args.diagnostic_trio_pulse)
        engine_render_profile_receipt = validate_engine_render_profile(
            args.diagnostic_engine_render_profile, args.runtime_mode,
            args.diagnostic_telemetry, args.render_stage_profile,
            args.diagnostic_producer_gaps, args.diagnostic_irq_profile)
    except ValueError as error:
        parser.error(str(error))
    if args.flash_plaits_wavetables and not args.compressed_wavetables:
        parser.error('--flash-plaits-wavetables requires --compressed-wavetables')
    tc, catalogue, out = (p.resolve() for p in
                           (args.toolchain, args.catalogue, args.build))
    if len(set(args.exclude)) != len(args.exclude) or 'trio' in args.exclude:
        parser.error('Exclusions must be unique and retain the initial Trio engine')
    if args.modules is not None and args.exclude:
        parser.error('--modules and --exclude cannot be combined')
    out.mkdir(parents=True, exist_ok=False)
    # Generate both registry flags and omitted-module metadata together.
    # Reuse the canonical catalogue rather than editing engine flags alone.
    try:
        _, all_modules = resolve_modules(ROOT, out / 'module-all', 'all')
        specification = (args.modules if args.modules is not None else
                         ','.join(x for x in all_modules['selected'] if x not in args.exclude)
                         if args.exclude else 'all')
        module_header, module_selection = resolve_modules(ROOT, out / 'module-selection', specification)
    except ValueError as error:
        parser.error(str(error))
    if 'trio' not in module_selection['selected']:
        parser.error('Timed probe must retain the initial Trio engine')
    if content_inputs and module_header != content_inputs.module_header:
        parser.error('Prepared module header differs from current module selection')
    args.exclude = [x for x in ENGINE_IDS if x not in module_selection['selected']]
    platform = ROOT / 'firmware/third_party/dinghy'
    for name in ('dinghy', 'compiler-rt', 'musl', 'printf', 'tlsf'):
        check_pins(ROOT / 'firmware/third_party' / name)
    wave_namespaces = (wavetable_namespaces(module_selection['selected'], args.flash_plaits_wavetables)
                       if args.compressed_wavetables else [])
    objects, catalogue_receipts = checked_catalogue(
        catalogue, wave_namespaces, args.indexed_tft, args.shapes_voices,
        args.hot_dsp_os, args.hot_dsp_ram, args.diagnostic_engine_render_profile,
        args.limiter_os)
    state_bin_codec = None
    if args.link_project_save_service:
        state_bin_codec = replace_with_compact_state_bin(
            objects, catalogue, tc, out, args.indexed_tft, args.shapes_voices)
    wave_records = []
    if args.compressed_wavetables:
        check_pins(ROOT / 'firmware/third_party/tinf')
        wave_records = prepare(out, wave_namespaces)
    # Keep crash/recovery text while eliminating redundant four-bit storage
    # for the pinned small face, whose alpha is strictly binary.
    (out / 'lunar_font.h').write_text(compact_header(
        (platform / 'gen/lunar_font.h').read_text()))
    (out / 'gfx.c').write_text(compact_gfx((platform / 'src/gfx.c').read_text()))
    source = platform_with_identity((platform / 'src/platform.c').read_text(),
                                    args.firmware_identity)
    source = hot_dsp_ram_platform(source, args.hot_dsp_ram)
    companion_set_count = sum(1 for asset in content_inputs.report['content']
                              if asset['kind'] == 'set') if content_inputs else 0
    if companion_set_count and args.startup_project_index is not None:
        if not args.link_set_loader or not args.link_project_loader:
            parser.error('Companion SET selection requires both project and SET loaders')
        if not any(asset['kind'] == 'project' for asset in content_inputs.report['content']):
            parser.error('Companion SET selection requires an embedded parent project')
    if args.startup_project_index is not None:
        project_count = sum(1 for asset in content_inputs.report['content']
                            if asset['kind'] == 'project')
        if project_count > 1 or companion_set_count:
            source = replace_once(source, '#include "usb.c"',
                                  '#include "usb.c"\n#include "preload_selector_platform.h"')
            chooser = ''
            if project_count > 1:
                chooser += ('    lunar_selected_startup_project_index =\n'
                            '        lunar_preload_choose(lunar_selected_startup_project_index);\n')
            if companion_set_count:
                chooser += ('    lunar_selected_companion_set_index =\n'
                            '        lunar_preload_choose_set(lunar_selected_startup_project_index);\n')
            source = replace_once(source,
                '    fm1_audio_init(abuf, HALF_WORDS, isr_alnk0, 3);',
                chooser + '    fm1_audio_init(abuf, HALF_WORDS, isr_alnk0, 3);')
    replacements = {
        '    ota_boot_cleanup();': '    /* Timed probe: retain OTA staging bytes. */',
        '#define FL_RANGE_OK(off, n) (FL_IN(off, n, FL_OTA_LO, FL_OTA_HI) || FL_IN(off, n, SETTINGS_AT, SETTINGS_AT + 0x1000u))':
            '#define FL_RANGE_OK(off, n) (0) /* Timed probe: no NOR writes. */',
        '#define CV_MAX (240u * 64u)': '#define CV_MAX (240u * 16u)',
        'static volatile int32_t master_q12 = 2048;':
            'static volatile int32_t master_q12 = 4096;',
        'master_q12 = (int32_t)((k10 * k10) >> 8);':
            'master_q12 = 4096; lunar_master_raw = (int32_t)k10; lunar_master_adc_raw = (uint32_t)a;',
    }
    for old, new in replacements.items():
        source = replace_once(source, old, new)
    (out / 'platform.c').write_text(source)
    source = (platform / 'src/libc.c').read_text()
    for name in ('memset', 'memcpy', 'memcmp'):
        # Keep private HAL definitions; common calls use the pinned C runtime.
        source = replace_once(source, name + '(', 'dinghy_' + name + '(')
    (out / 'libc.c').write_text(source)
    source = replace_once((platform / 'crt0.S').read_text(), '1:\tr1 = icfg',
                         '1:\tcli\n\tr3 = cnum\n\tif (r3 != 0) goto lunar_entry_rejected\n'
                         '\tr3 = 0x01C7FE08\n\tif (r0 != r3) goto lunar_entry_rejected\n\tr1 = icfg')
    source += '\nlunar_entry_rejected:\n\tgoto lunar_entry_rejected\n'
    if args.stack_watermark:
        source = instrument_entry(source)
    (out / 'crt0.S').write_text(source)
    gen = out / 'gen'
    shutil.copytree(catalogue / 'shard-00/obj/gen', gen)
    header = gen / 'fm1_modules.h'
    header.write_bytes(module_header)
    compiler = str(tc / 'common/bin/clang')
    flags = ['-target', 'pi32v2', '-mcpu=r3', '-mfprev1', '-Oz', '-flto',
             '-ffreestanding', '-fno-builtin', '-ffunction-sections', '-fdata-sections',
             '-DFM1_APP_EXTERNAL_ARENAS=1', '-DLUNAR_APP_PROBE=1', '-DNDEBUG',
             '-DFM1_TFT_INDEXED=' + str(int(args.indexed_tft)), runtime_policy['define']]
    if args.hot_dsp_ram:
        flags += ['-DFM1_HOT_DSP_RAM=1']
    flags += project_save_service_flags(args.link_project_save_service)
    flags += native_midi_input_flags(args.enable_trs_midi)
    if args.diagnostic_song_play:
        flags += ['-DLUNAR_DIAGNOSTIC_SONG_PLAY=1']
    flags += diagnostic_telemetry_flags(telemetry_enabled)
    flags += diagnostic_producer_gaps_flags(args.diagnostic_producer_gaps)
    flags += diagnostic_irq_profile_flags(args.diagnostic_irq_profile)
    flags += diagnostic_cpu_rate_flags(args.diagnostic_cpu_rate)
    flags += render_stage_profile_flags(args.render_stage_profile)
    flags += engine_render_profile_flags(args.diagnostic_engine_render_profile)
    if args.diagnostic_clock_snapshot:
        flags += ["-DLUNAR_DIAGNOSTIC_CLOCK_SNAPSHOT=1"]
    flags += trio_diagnostic_pulse_flags(args.diagnostic_trio_pulse)
    if args.startup_set_index is not None:
        flags += ['-DLUNAR_STARTUP_SET_INDEX=' + str(args.startup_set_index)]
    if args.stack_watermark:
        flags += ['-DLUNAR_STACK_WATERMARK=1']
    if args.startup_project_index is not None:
        flags += ['-DLUNAR_STARTUP_PROJECT_INDEX=' + str(args.startup_project_index)]
    if companion_set_count:
        flags += ['-DLUNAR_COMPANION_SET_CHOOSER=1']
    if args.compressed_wavetables:
        flags += ['-DLUNAR_COMPRESSED_WAVETABLES=1']
    for directory in (gen, ROOT / 'engines/include', ROOT / 'engines/mod',
                      ROOT / 'firmware/native', ROOT / 'firmware/third_party/tlsf',
                      ROOT / 'firmware/third_party/tinf', ROOT / 'engines/third_party/mutable', ROOT / 'engines/host',
                      ROOT / 'engines/state', ROOT / 'sim/web/src', out,
                      platform / 'hal', platform / 'src', platform / 'gen'):
        flags += ['-I', str(directory)]
    flags += ['-isystem', str(tc / 'pi32v2/include')]
    app_storage = measure_app_storage(compiler, flags, out)
    instance_pool_bytes = (192000 +
                           (app_storage['pool_credit_bytes'] if args.indexed_tft else 0) -
                           sum(r['raw_bytes'] for r in wave_records))
    flags += ['-DLUNAR_INSTANCE_MEMORY_BYTES=' + str(instance_pool_bytes)]
    for path in (out / 'crt0.S', platform / 'hal/fm1_vec.S', platform / 'hal/fm1_isr.S'):
        obj = out / (path.stem + '.o')
        subprocess.run([compiler, *[f for f in flags if f != '-flto'], '-c', str(path),
                        '-o', str(obj)], check=True)
        objects.append(obj)
    extra_sources = ([out / ('resources_' + n + '.cc') for n in wave_namespaces] + [
                      ROOT / 'firmware/native/wave_tables.c',
                      ROOT / 'firmware/third_party/tinf/tinflate.c']
                     if args.compressed_wavetables else [])
    if args.enable_trs_midi:
        extra_sources += [ROOT / 'firmware/native/midi_uart_stream.c',
                          ROOT / 'firmware/native/midi_stream.cpp']
    if content_inputs:
        content_path = out / 'content_catalogue.c'
        content_path.write_bytes(generated_content)
        extra_sources.append(content_path)
    if args.link_set_loader:
        # The freshness-checked catalogue already contains the state codecs.
        extra_sources.append(ROOT / 'firmware/native/content_set.c')
    if args.link_project_loader:
        # Shared state codecs/applier are already in the checked catalogue.
        extra_sources += [ROOT / 'firmware/native/project_units.c',
                          ROOT / 'firmware/native/project_mod.c',
                          ROOT / 'firmware/native/project_seq.c',
                          ROOT / 'firmware/native/project_engines.c',
                          ROOT / 'firmware/native/project_start.c',
                          ROOT / 'firmware/native/project_boot.c']
    for path in [ROOT / 'sim/web/src/fm1_app.c', ROOT / 'engines/host/mod_script.c',
                 ROOT / 'firmware/native/app_probe.c', ROOT / 'firmware/native/instance_pool.c',
                 ROOT / 'firmware/native/tlsf_runtime.c', ROOT / 'engines/src/registry.cc', *extra_sources]:
        obj = out / (path.stem + '.o')
        cxx = (['-std=c++11', '-fno-exceptions', '-fno-rtti', '-DTEST',
                '-I', str(ROOT / 'engines/src'), '-isystem', str(catalogue / 'shard-00/cxx'),
                '-D_LIBCPP_HAS_NO_THREADS', '-D_LIBCPP_DISABLE_EXTERN_TEMPLATE']
               if path.suffix in ('.cc', '.cpp') else [])
        if args.enable_trs_midi and path.name == 'midi_stream.cpp':
            cxx += ['-I', str(ROOT / 'firmware/third_party/arduino-midi/src')]
        subprocess.run([compiler, *flags, *cxx, '-c', str(path), '-o', str(obj)], check=True)
        objects.append(obj)
    # Rebuild the small runtimes from checked sources instead of trusting globbed objects.
    runtime = out / 'runtime'
    subprocess.run([sys.executable, str(ROOT / 'tools/native/build_libc.py'),
                    '--toolchain', str(tc), '--build', str(runtime / 'musl')],
                   check=True, stdout=(out / 'libc-build.json').open('w'))
    objects += sorted((runtime / 'musl').glob('*.o'))
    subprocess.run(['make', '-s', '-C', str(ROOT / 'tools/native'), '-j16',
                    'BUILD=' + str(runtime / 'arithmetic'), 'JIELI_TOOLCHAIN=' + str(tc)], check=True)
    objects += [p for p in sorted((runtime / 'arithmetic').glob('*.o'))
                if p.name not in ('arithmetic-probe.o', 'arithmetic-linked.o')]
    printf = runtime / 'printf.o'
    subprocess.run([compiler, *[f for f in flags if f != '-flto'],
                    '-DPRINTF_ALIAS_STANDARD_FUNCTION_NAMES_HARD=1',
                    '-DPRINTF_SUPPORT_WRITEBACK_SPECIFIER=0',
                    '-I', str(ROOT / 'firmware/third_party/printf'), '-c',
                    str(ROOT / 'firmware/third_party/printf/printf/printf.c'),
                    '-o', str(printf)], check=True)
    objects.append(printf)
    roots = ('_start', 'fm1_app_key', 'fm1_app_button', 'fm1_app_encoder',
             'fm1_app_master', 'fm1_app_note_on', 'fm1_app_note_off',
             'fm1_app_pitch_bend', 'fm1_app_all_notes_off')
    if content_inputs:
        roots += ('lunar_content_count', 'lunar_content_catalogue')
    if args.link_set_loader:
        roots += ('lunar_content_load_set', 'lunar_content_activate_set')
    if args.link_project_loader:
        roots += ('lunar_project_mod_stage', 'lunar_project_seq_stage',
                  'lunar_project_engines_stage', 'lunar_project_engines_release',
                  'lunar_project_engines_apply', 'lunar_project_adopt_audio_units',
                  'lunar_project_restore_midi_units', 'lunar_project_restore_scalars',
                  'lunar_project_restore_dx7', 'lunar_project_restore_mod', 'fm1_app_mod_prepare_cold',
                  'fm1_app_mod_adopt_cold', 'lunar_project_start',
                  'lunar_project_restore_view')
    if companion_set_count:
        roots += ('lunar_project_start_with_set',)
    elf = out / 'lunar-app-probe.elf'
    script = out / 'app.ld'
    script.write_text(hot_dsp_ram_linker_script(
        linker_script((ROOT / 'firmware/native/app.ld').read_text(), args.flash_layout),
        args.hot_dsp_ram))
    command = [str(tc / 'pi32v2/bin/ld'), '--plugin', str(tc / 'common/bin/LLVMgold.so'),
               '--plugin-opt=mcpu=r3', '--plugin-opt=-mattr=+fprev1',
               '--plugin-opt=-pi32v2-large-program=true', '--gc-sections',
               '-T', str(script)]
    for symbol in roots:
        command += ['-u', symbol]
    command += [*map(str, objects), '-Map', str(out / 'lunar-app-probe.map'), '-o', str(elf)]
    result = subprocess.run(command, capture_output=True, text=True)
    (out / 'link.log').write_text(result.stdout + result.stderr)
    if result.returncode:
        raise SystemExit(result.stdout + result.stderr)
    objdump = str(tc / 'common/bin/objdump')
    stack_receipt = None
    if args.stack_watermark:
        sys.path.insert(0, str(ROOT / 'tools/jieli'))
        from audit_link import Elf
        full_disassembly = subprocess.check_output([objdump, '-d', '-mcpu=r3', str(elf)], text=True)
        (out / 'stack-watermark-disassembly.txt').write_text(full_disassembly)
        stack_receipt = verify_instrumentation(Elf(elf.read_bytes()), full_disassembly)
    symbols = subprocess.check_output([objdump, '-t', str(elf)], text=True)
    (out / 'symbols.txt').write_text(symbols)
    missing = re.findall(r'^.*\*UND\*[ \t]+00000000[ \t]+(\S+)[ \t]*$', symbols, re.M)
    if missing:
        raise SystemExit('Undefined symbols: ' + repr(missing))
    receipt = out / 'key-audit.json'
    subprocess.run([sys.executable, str(ROOT / 'tools/jieli/audit_link.py'),
                    '--elf', str(elf), '--runtime', 'sdk-free',
                    '--objdump', objdump,
                    '--sources', str(ROOT / 'firmware/native'), '--json', str(receipt)], check=True)
    audit = json.loads(receipt.read_text())
    if not audit['passed'] or audit['n_pending']:
        raise SystemExit('SDK-free audit has failed or pending checks')
    disassembly = subprocess.check_output([objdump, '-d', '-mcpu=r3', '-j', '.ram_text', str(elf)], text=True)
    (out / 'ram-text.txt').write_text(disassembly)
    if args.hot_dsp_ram:
        (out / 'ram-dsp.txt').write_text(subprocess.check_output(
            [objdump, '-d', '-mcpu=r3', '-j', '.ram_dsp', str(elf)], text=True))
    try:
        ram_call_audit = audit_ram_call_allowlist(disassembly, symbols)
    except ValueError as exc:
        raise SystemExit('RAM call audit failed: ' + str(exc)) from exc
    (out / 'ram-call-audit.json').write_text(json.dumps(ram_call_audit, indent=2) + '\n')
    (out / 'sections.txt').write_text(subprocess.check_output([objdump, '-h', str(elf)], text=True))
    report = dict(excluded_engines=args.exclude, module_selection=module_selection, sdk_archives=[],
                  flash_layout=args.flash_layout, app_budget_bytes=app_budget(args.flash_layout),
                  linker_script_sha256=digest(script),
                  compressed_wave_tables=wave_records, indexed_tft=args.indexed_tft,
                  flash_plaits_wavetables=args.flash_plaits_wavetables,
                  shapes_voices=args.shapes_voices,
                  printf_writeback_specifier=False,
                  stack_watermark=args.stack_watermark,
                  stack_watermark_verification=stack_receipt,
                  instance_pool_bytes=instance_pool_bytes, target_app_storage=app_storage,
                  catalogue_objects=catalogue_receipts,
                  catalogue_optimization_overrides=optimization_overrides(
                      'z', args.hot_dsp_os, args.limiter_os),
                  catalogue_limiter_os=args.limiter_os,
                  hot_dsp_ram=dict(hot_dsp_ram_receipt,
                                   extent=hot_dsp_ram_extent(elf) if args.hot_dsp_ram else None),
                  linked_objects=[dict(path=str(p), sha256=digest(p)) for p in objects],
                  key_audit=audit, undefined_symbols=missing, flash_write_range='empty',
                  boot_ota_cleanup=False, entry_core=0, entry_boot_pointer='0x01c7fe08',
                  runtime_configuration=runtime_policy,
                  firmware_identity=identity_receipt,
                  runtime_policy_sha256=digest(ROOT / 'firmware/native/runtime_mode.h'),
                  project_save_service=save_service_receipt,
                  native_midi_input=native_midi_receipt,
                  diagnostic_telemetry=telemetry_receipt,
                  diagnostic_song_play=song_play_receipt,
                  diagnostic_trio_pulse=trio_pulse_receipt,
                  state_bin_codec=state_bin_codec,
                  probe_return_to_rom_seconds=runtime_policy['return_to_rom_seconds'], hardware_candidate=False,
                  catalogue_source_freshness_verified=True,
                  installable=False, hardware_tested=False, elf_sha256=digest(elf))
    if args.diagnostic_producer_gaps:
        report["diagnostic_producer_gaps"] = producer_gap_receipt
    if args.diagnostic_irq_profile:
        report["diagnostic_irq_profile"] = irq_profile_receipt
    if args.diagnostic_cpu_rate:
        report["diagnostic_cpu_rate"] = cpu_rate_receipt
    if args.diagnostic_clock_snapshot:
        report["diagnostic_clock_snapshot"] = clock_snapshot_receipt
    if args.render_stage_profile:
        report["render_stage_profile"] = render_profile_receipt
    if args.diagnostic_engine_render_profile:
        report["diagnostic_engine_render_profile"] = engine_render_profile_receipt
    if content_inputs:
        try:
            report['embedded_content'] = embedded_content_receipt(
                args.expected_profile_sha256, generated_content,
                content_inputs.report['content'], content_inputs.packed_content)
        except (ValueError, KeyError, TypeError) as error:
            raise SystemExit('Prepared content receipt refused: ' + str(error))
    if args.link_set_loader:
        report['set_loader'] = dict(native_link_verified=True, activation_api_link_verified=True, activated=False,
                                   stack_margin_verified=False, hardware_tested=False,
                                   sequence_semantics_verified=False)
    if args.link_project_loader:
        report['project_loader'] = dict(modulation_staging_link_verified=True,
                                       sequence_staging_link_verified=True,
                                       engine_staging_link_verified=True, engine_parameter_link_verified=True, audio_adoption_link_verified=True,
                                       midi_restore_link_verified=True, scalar_restore_link_verified=True, dx7_restore_link_verified=True,
                                       modulation_adoption_link_verified=True, modulation_restore_link_verified=True,
                                       startup_composition_link_verified=True, view_restore_link_verified=True,
                                       activated=False, stack_margin_verified=False,
                                       timing_verified=False, hardware_tested=False,
                                       sequence_semantics_verified=False)
    if args.startup_set_index is not None:
        report['startup_set'] = dict(index=args.startup_set_index, runtime_hook_linked=True,
                                    staging_reclaimed_before_engine_allocation=True,
                                    runtime_verified=False, stack_margin_verified=False,
                                    hardware_tested=False)
    if companion_set_count:
        report['companion_set_selection'] = dict(
            enabled=True, selection_receipt_sha256=selection_receipt_sha256,
            parent_project_index=args.startup_project_index,
            set_indices=[i for i, row in enumerate(content_inputs.report['content'])
                         if row['kind'] == 'set'],
            before_audio_init=True, timeout_keeps_project_sequence=True,
            runtime_verified=False, sequence_semantics_verified=False,
            hardware_tested=False)
    if args.startup_project_index is not None:
        report['startup_project'] = dict(index=args.startup_project_index,
                                        runtime_hook_linked=sum(1 for asset in content_inputs.report['content']
                                                                if asset['kind'] == 'project') > 1,
                                        staging_reclaimed_before_engine_allocation=True,
                                        failure_returns_to_recovery=True, runtime_verified=False,
                                        stack_margin_verified=False, hardware_tested=False)
    (out / 'verification.json').write_text(json.dumps(report, indent=2) + '\n')
    subprocess.run([sys.executable, str(ROOT / 'tools/native/probe_artifact.py'),
                    '--elf', str(elf), '--layout', 'combined',
                    '--flash-layout', args.flash_layout,
                    *(('--hot-dsp-ram',) if args.hot_dsp_ram else ()),
                    '--objdump', objdump,
                    '--out', str(out / 'artifact')], check=True)
    print('Audited private probe:', elf, report['elf_sha256'])


if __name__ == '__main__':
    main()
