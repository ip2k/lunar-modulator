#!/usr/bin/env python3
"""Prepare the tracked continuous dev-board DAC pipeline, offline only.

Private AC79 e30b1ee SDK and reviewed scheduler archive are explicit inputs.
No downloading, flashing, backups or device operations. Preserve the small input
receipt and final evidence; remove this lane's reproducible SDK after its run.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil

SYSTEM = Path('cpu/wl82/liba/system.a')
ORIGINAL_SYSTEM_SHA256 = 'a71bdc75e5afbcffaf7d79bc2b27f2b65fec63d94d2261b584744d3e9b9098ea'
PIPELINE_SYSTEM_SHA256 = '792c7599e76e52a2cac9cd3a69d1d99bf301912ba941840d1dc819300484c7ee'
SELECTOR_CORRECTION = 'ac79-e30b1ee-affinity-early-selected-tail-v132'

# Exact-PCM transformations/placement used by the successful private pipeline.
# Internal timing-only setup suppresses the old DAC demo and all observers;
# adapt_pipeline below replaces that worker mode with the tracked DAC driver.
PRESET = dict(timing_only=True, profile=True, hot_ram=True, sine_ram=True,
              resampler_ram=True, cache_tables=True, fx_ram=True,
              filter_process_ram=True, control_ram=True, plaits_cache=True,
              resampler_slopes=True, resampler_unroll=True, renderer_o3=True,
              mixer_ram=True, dispatch_ram=True, msfa_narrow_adds=True,
              msfa_sine32=True, msfa_pure_unroll=True, ui_ram=True,
              prep_profile=True, hook_ram=True, module_ram=True, kind_ram=True,
              event_ram=True, external_pixels=True, vcf_unroll=True,
              oscillator_slopes=True, outer_timing_only=True, metadata_ram=True,
              msfa_sine_pair=True, drums_ready_convert=True)

PIPELINE_APP_HOT = (
    b'static int pipeline_record', b'static void pipeline_validate_stream',
    b'static void pipeline_execute', b'static void post_capture',
    b'static void post_fx_run', b'static void post_amp_run', b'static void post_run',
    b'static void pipeline_preflight', b'static void pipeline_capture_drive',
    b'static void pipeline_level_apply', b'static void pipeline_finish_sound_slot',
    b'static void pipeline_render_sounds', b'static const float *pipeline_consume_block',
    b'static void pipeline_retire_block', b'static void pipeline_produce_block',
    b'int fm1_app_pipeline_produce', b'const float *fm1_app_pipeline_consume',
    b'int fm1_app_pipeline_retire',
)


# Match the retained successful pipeline's exact placement, not intermediate
# cold-constructor experiments. Keep DX7 initialization/allocation/budget paths
# in XIP while the actual synthesis loops remain startup-copied SRAM code.
PIPELINE_XIP = (
    '  void Init(const fm1_host_t *host)',
    '  void NoteOn(uint8_t key, uint8_t velocity)',
    '  Voice *Allocate(uint8_t key)',
    '  unsigned SetVoiceLimit(unsigned limit)',
    '  void BudgetStats(fm1_dx7_budget_stats_t &out) const',
    '  void EnforceVoiceLimit()',
    'extern "C" int fm1_dx7_set_voice_limit(void *self, unsigned limit)',
    'extern "C" int fm1_dx7_get_budget_stats(const void *self, fm1_dx7_budget_stats_t *out)',
)


def place_pipeline_xip(staging):
    path = staging / 'engines/src/msfa_dx7.cc'
    text = path.read_text()
    attribute = '__attribute__((noinline, section(".text"))) '
    for anchor in PIPELINE_XIP:
        if anchor.startswith('extern "C" '):
            replacement = 'extern "C" ' + attribute + anchor[len('extern "C" '):]
        else:
            replacement = '  ' + attribute + anchor.lstrip()
        text = checked_replace(text, anchor, replacement)
    path.write_text(text)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checked_replace(text, before, after):
    if text.count(before) != 1:
        raise ValueError('Unexpected pipeline preparation anchor: ' + before)
    return text.replace(before, after, 1)


def adapt_pipeline(out, source, renderer, adaptive_three, cycles):
    """Replace legacy worker mode, never its recovery or lifecycle bodies."""
    app = out / 'apps/demo/demo_hello'
    main = app / 'app_main.c'
    main.write_text(checked_replace(main.read_text(),
        'os_task_create(lunar_devkit_worker, NULL, 10, 2048, 0, "lunar_devkit");',
        'os_task_create(lunar_devkit_worker, NULL, 16, 2048, 0, "#C0lunar_parent");'))
    staging = out / 'lunar-source'
    flags = ('CFLAGS += -DLUNAR_DEVKIT_RENDERER_PIPELINE=1 '
             '-DLUNAR_DEVKIT_RENDERER_PIPELINE_DAC=1 -DFM1_APP_RENDER_PIPELINE=1\n'
             f'CFLAGS += -DLUNAR_PIPELINE_CYCLES={cycles}\n'
             f'CFLAGS += -I{staging / "firmware/devkit"}\n')
    if adaptive_three:
        flags += 'CFLAGS += -DLUNAR_PIPELINE_ADAPTIVE_THREE=1\n'
    makefile = app / 'board/wl82/Makefile'
    makefile.write_text(checked_replace(makefile.read_text(),
        'CFLAGS += -DLUNAR_DEVKIT_RENDERER_TIMING=1\n', flags))
    # The pinned compiler's code_seg pragma is retained only in private copies.
    # Original functions remain unchanged; newly split hot paths need placement.
    place_pipeline_xip(staging)
    app_source = staging / 'sim/web/src/fm1_app.c'
    app_source.write_bytes(renderer.place_hook_ram(app_source.read_bytes(), PIPELINE_APP_HOT))
    live = staging / 'firmware/devkit/renderer_live.c'
    live.write_bytes(renderer.place_hook_ram(live.read_bytes(), (b'static int pipeline_convert',)))
    shutil.copyfile(source / 'firmware/devkit/renderer_pipeline_dac.h', app / 'renderer_pipeline_dac.h')
    receipt_path = out / 'lunar-devkit-input.json'
    receipt = json.loads(receipt_path.read_text())
    receipt.update({
        'measurement': 'tracked pipelined shared renderer through dev-board internal DAC',
        'timing_only': False, 'outer_timing_only': False,
        'renderer_pipeline': True, 'renderer_pipeline_dac': True,
        'pipeline_cycles': cycles,
        'pipeline_polyphony': 'adaptive65/60-floor3' if adaptive_three else 'fixed12',
        'parent_task_priority': 16, 'uart_task_priority': 18,
        'worker_stack_words': 2048, 'worker_stack_bytes': 8192,
        'pipeline_worker_stack_words': 1536, 'pipeline_worker_priority': 16,
        'pipeline_work_slots': 2, 'pipeline_output_slots': 8,
        'pipeline_deadline_ticks': 34829,
        'pipeline_protocol_budget_ticks': 2400000,
        'pipeline_system_correction': SELECTOR_CORRECTION,
        'pipeline_system_original_sha256': ORIGINAL_SYSTEM_SHA256,
        'pipeline_system_sha256': PIPELINE_SYSTEM_SHA256,
        'pipeline_xip_functions': PIPELINE_XIP,
        'pipeline_hot_functions': [x.decode() for x in PIPELINE_APP_HOT] + ['static int pipeline_convert'],
        'prepared_app_main_sha256': sha256(main),
        'prepared_board_makefile_sha256': sha256(makefile),
        'renderer_integration_complete': False, 'hardware_acceptance': False,
        'cleanup': 'Remove only this generated SDK after evidence export and process exit; retain logs/receipts.',
    })
    for directory in ('engines', 'sim/web/src', 'sim/web/mk', 'firmware/devkit'):
        for path in sorted((staging / directory).rglob('*')):
            if path.is_file():
                receipt['inputs'][str(path.relative_to(staging))] = sha256(path)
    receipt['inputs']['tools/jieli/prepare-pipeline-devkit.py'] = sha256(source / 'tools/jieli/prepare-pipeline-devkit.py')
    receipt_path.write_text(json.dumps(receipt, indent=2) + '\n')


def prepare_pipeline(sdk, source, out, system_archive, adaptive_three=False, cycles=3):
    if isinstance(cycles, bool) or not 1 <= cycles <= 57:
        raise ValueError('Pipeline cycles must be 1..57')
    if out.exists() or out.is_symlink():
        raise ValueError('Output must be a new private build directory')
    # Refuse any unreviewed scheduler input before copying a large SDK. Exact
    # archive hashes also pin all 46 members; vendor IR never enters this repo.
    if sha256(sdk / SYSTEM) != ORIGINAL_SYSTEM_SHA256:
        raise ValueError('Expected original pinned SDK system.a')
    corrected_bytes = system_archive.read_bytes()
    if hashlib.sha256(corrected_bytes).hexdigest() != PIPELINE_SYSTEM_SHA256:
        raise ValueError('Expected reviewed pipeline scheduler archive')
    spec = importlib.util.spec_from_file_location('renderer_prepare', source / 'tools/jieli/prepare-renderer-devkit.py')
    renderer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(renderer)
    renderer.prepare_renderer(sdk, source, out, **PRESET)
    target = out / SYSTEM
    if target.is_symlink() or sha256(target) != ORIGINAL_SYSTEM_SHA256:
        raise ValueError('Prepared scheduler must be a separate original SDK file')
    target.write_bytes(corrected_bytes)
    if sha256(target) != PIPELINE_SYSTEM_SHA256:
        raise ValueError('Prepared scheduler copy mismatch')
    adapt_pipeline(out, source, renderer, adaptive_three, cycles)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sdk', type=Path, required=True)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--pipeline-system-archive', type=Path, required=True,
                        help='Private reviewed scheduler archive; copied only to output SDK')
    parser.add_argument('--adaptive-three', action='store_true', help='Explicit adaptive65/60 floor3 experiment; default fixed12')
    parser.add_argument('--cycles', type=int, default=3, help='Four-case cycles, 1..57; 57 is about 30.4 minutes')
    args = parser.parse_args()
    prepare_pipeline(args.sdk.resolve(), args.source.resolve(), args.out.absolute(),
                     args.pipeline_system_archive.resolve(), args.adaptive_three, args.cycles)
