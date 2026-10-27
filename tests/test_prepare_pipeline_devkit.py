"""Offline full-source preparation with a tiny synthetic SDK, never hardware."""
import hashlib
import importlib.util
import json
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]


def load_prepare():
    spec = importlib.util.spec_from_file_location('pipeline_prepare', ROOT/'tools/jieli/prepare-pipeline-devkit.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sdk_fixture(tmp_path):
    sdk = tmp_path/'sdk'
    app = sdk/'apps/demo/demo_hello'
    (app/'include').mkdir(parents=True)
    (app/'board/wl82').mkdir(parents=True)
    (sdk/'include_lib/driver/cpu/wl82').mkdir(parents=True)
    (sdk/'include_lib/driver/cpu/wl82/system.ld').write_text(
        '       *(.syscfg.2.ops)\n       *(.syscfg.1.ops)\n       *(.syscfg.0.ops)\n'
        '    _syscfg_ops_end = .;\n    PROVIDE(syscfg_ops_end = .);\n')
    (app/'include/app_config.h').write_text(
        '#define __FLASH_SIZE__    (4 * 1024 * 1024)\n'
        '#define __SDRAM_SIZE__    (2 * 1024 * 1024)\n#define CONFIG_CXX_SUPPORT\n')
    (app/'app_main.c').write_text('void app_main() {os_task_create(hello_demo_task, NULL, 10, 1000, 0, "hello_demo_task");}')
    (app/'board/wl82/Makefile').write_text(
        'OUT_ELF := sdk.elf\nifeq ($(LINK_AT), 1)\nendif\nc_SRC_FILES := \\\n\toriginal.c\ncc_SRC_FILES :=\n'
        'all: pre_build $(OUT_ELF)\n\t$(QUITE) $(RUN_POST_SCRIPT) sdk\n')
    (app/'board/wl82/board.c').write_text('UART2_PLATFORM_DATA_BEGIN(uart2_data)\n'
        '\t.rx_pin = -1,\nUART2_PLATFORM_DATA_END();\n\t{"uart2", &uart_dev_ops, (void *)&uart2_data },\n')
    (sdk/'cpu/wl82/liba').mkdir(parents=True)
    (sdk/'cpu/wl82/sdk_ld_sfc.c').write_text('        *(.text*)\n        *(.rodata*)\n'
        '        *(.volatile_ram_code)\n    .cache_ram_data ALIGN(4):\n    {\n    } > cache_ram\n')
    (sdk/'cpu/wl82/liba/system.a').write_bytes(b'original fixture archive')
    correction = tmp_path/'corrected.a'
    correction.write_bytes(b'reviewed fixture archive')
    return sdk, correction


@pytest.mark.parametrize('adaptive,cycles', [(False, 3), (True, 57)])
def test_pipeline_prepares_actual_tracked_sources(tmp_path, monkeypatch, adaptive, cycles):
    module = load_prepare()
    sdk, correction = sdk_fixture(tmp_path)
    # Substitute only private input identities in this synthetic SDK test.
    monkeypatch.setattr(module, 'ORIGINAL_SYSTEM_SHA256', module.sha256(sdk/module.SYSTEM))
    monkeypatch.setattr(module, 'PIPELINE_SYSTEM_SHA256', module.sha256(correction))
    out = tmp_path/'prepared'
    module.prepare_pipeline(sdk, ROOT, out, correction, adaptive, cycles)
    assert (sdk/module.SYSTEM).read_bytes() == b'original fixture archive'
    assert (out/module.SYSTEM).read_bytes() == correction.read_bytes()
    app = out/'apps/demo/demo_hello'
    main = (app/'app_main.c').read_text()
    assert main.index('lunar_devkit_boot_control_start()') < main.index('os_task_create(')
    assert '16, 2048, 0, "#C0lunar_parent"' in main
    flags = (app/'board/wl82/Makefile').read_text()
    assert '-DLUNAR_DEVKIT_RENDERER_PIPELINE_DAC=1' in flags
    assert '-DFM1_APP_RENDER_PIPELINE=1' in flags
    assert ('-DLUNAR_PIPELINE_ADAPTIVE_THREE=1' in flags) == adaptive
    assert f'-DLUNAR_PIPELINE_CYCLES={cycles}' in flags
    for old in ('-DLUNAR_DEVKIT_ENGINE_QUEUE', '-DLUNAR_DEVKIT_RENDERER_TIMING',
                '-DFM1_APP_RENDER_PROFILE', '-DLUNAR_DEVKIT_RENDERER_AUDIO'):
        assert old not in flags
    assert flags.index('-DFM1_APP_RENDER_PIPELINE=1') < flags.index('include lunar-renderer.mk')
    assert (app/'sdk_worker.c').read_bytes() == (ROOT/'firmware/devkit/sdk_worker.c').read_bytes()
    assert (app/'renderer_pipeline_dac.h').exists()
    receipt = json.loads((out/'lunar-devkit-input.json').read_text())
    assert not receipt['timing_only'] and not receipt['render_profile']
    assert receipt['pipeline_polyphony'] == ('adaptive65/60-floor3' if adaptive else 'fixed12')
    assert receipt['pipeline_deadline_ticks'] == 34829
    assert receipt['uart_task_priority'] == 18
    assert not receipt['hardware_acceptance']
    for name, digest in receipt['inputs'].items():
        path = out/'lunar-source'/name
        if path.exists():
            assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
    dx7 = (out/'lunar-source/engines/src/msfa_dx7.cc').read_text()
    assert '  __attribute__((noinline, section(".text"))) void NoteOn(uint8_t key, uint8_t velocity)' in dx7
    assert 'extern "C" __attribute__((noinline, section(".text"))) int fm1_dx7_set_voice_limit(' in dx7
    assert dx7.count('__attribute__((noinline, section(".text")))') == 8
    assert 'BlockControls common = {};' in dx7
    assert receipt['pipeline_dx7_block_controls']
    assert receipt['pipeline_sound1_frontier_frames'] == 8
    seq = (out/'lunar-source/engines/seq/seq_host.c').read_text()
    assert seq.count('slot_upto(h, &slots[1], &cur[1], 8);') == 2
    assert module.sha256(app/'app_main.c') == receipt['prepared_app_main_sha256']
    assert module.sha256(app/'board/wl82/Makefile') == receipt['prepared_board_makefile_sha256']
    # The chosen actual pipeline functions, not just legacy serial code, are hot.
    staged = (out/'lunar-source/sim/web/src/fm1_app.c').read_text()
    assert '#pragma code_seg(".volatile_ram_code")\nstatic void pipeline_produce_block(' in staged
    assert '#pragma code_seg(".volatile_ram_code")\nstatic const float *pipeline_consume_block(' in staged


@pytest.mark.parametrize('cycles', [0, 58, True])
def test_bad_cycles_refused_before_sdk_access(tmp_path, cycles):
    with pytest.raises(ValueError, match='1..57'):
        load_prepare().prepare_pipeline(tmp_path/'missing', ROOT, tmp_path/'out', tmp_path/'missing.a', cycles=cycles)
    assert not (tmp_path/'out').exists()


def test_unreviewed_scheduler_refused_before_staging(tmp_path, monkeypatch):
    module = load_prepare()
    sdk, correction = sdk_fixture(tmp_path)
    out = tmp_path/'prepared'
    with pytest.raises(ValueError, match='original pinned'):
        module.prepare_pipeline(sdk, ROOT, out, correction)
    monkeypatch.setattr(module, 'ORIGINAL_SYSTEM_SHA256', module.sha256(sdk/module.SYSTEM))
    with pytest.raises(ValueError, match='reviewed pipeline'):
        module.prepare_pipeline(sdk, ROOT, out, correction)
    assert not out.exists()


@pytest.mark.parametrize('sanitize', [False, True])
def test_vcf_main_full_output_and_state_exact(tmp_path, sanitize):
    import os
    import shutil
    import subprocess
    compiler = shutil.which('clang++')
    if not compiler:
        pytest.skip('clang++ unavailable')
    module = load_prepare()
    inc = ROOT/'engines/third_party/mutable'
    relative = 'plaits/dsp/engine2/virtual_analog_vcf_engine'
    header = (inc/(relative+'.h')).read_text()
    body = (inc/(relative+'.cc')).read_text()
    macro = (ROOT/'engines/src/mi_macro.cc').read_text()
    (tmp_path/'reference.h').write_text(header.replace('VirtualAnalogVCFEngine', 'ReferenceVirtualAnalogVCFEngine')
        .replace('PLAITS_DSP_ENGINE_VIRTUAL_ANALOG_VCF_ENGINE_H_', 'REFERENCE_VCF_H_'))
    (tmp_path/'reference.cc').write_text(body.replace('VirtualAnalogVCFEngine', 'ReferenceVirtualAnalogVCFEngine')
        .replace('"'+relative+'.h"', '"reference.h"'))
    h, c, _ = module.vcf_main_output(header, body, macro)
    target = tmp_path/(relative+'.h')
    target.parent.mkdir(parents=True)
    target.write_text(h)
    (tmp_path/'optimized.cc').write_text(c)
    flags = ['-fsanitize=address,undefined', '-fno-sanitize=shift', '-fno-omit-frame-pointer'] if sanitize else []
    exe = tmp_path/'state'
    subprocess.run([compiler, '-std=c++11', '-DTEST', '-O2', '-ffp-contract=off', *flags,
        '-I'+str(tmp_path), '-I'+str(inc), str(ROOT/'tests/fixtures/renderer_pipeline/vcf_main.cc'),
        str(tmp_path/'reference.cc'), str(tmp_path/'optimized.cc'), str(inc/'plaits/resources.cc'),
        str(inc/'stmlib/dsp/units.cc'), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True, timeout=30, env=dict(os.environ,
        ASAN_OPTIONS='detect_leaks=1:halt_on_error=1', UBSAN_OPTIONS='halt_on_error=1'))


def test_pipeline_transforms_refuse_reapplication():
    module = load_prepare()
    dx7 = (ROOT/'engines/src/msfa_dx7.cc').read_text()
    with pytest.raises(ValueError, match='already prepared'):
        module.dx7_block_controls(module.dx7_block_controls(dx7))
    seq = (ROOT/'engines/seq/seq_host.c').read_text()
    # Original anchors survive inserted prefixes: explicitly reject duplicate
    # transformations rather than silently publishing the frontier twice.
    modified = module.pipeline_sound_frontier(seq)
    assert modified.count('cur[1] < 8') == 2
    with pytest.raises(ValueError, match='already prepared'):
        module.pipeline_sound_frontier(modified)


@pytest.mark.parametrize('sanitize', [False, True])
def test_prepared_pipeline_full_pcm_and_faults(tmp_path, sanitize):
    import shutil
    module = load_prepare()
    source = tmp_path/'source'
    for directory in ('engines', 'sim/web/src', 'sim/web/mk', 'firmware/devkit'):
        shutil.copytree(ROOT/directory, source/directory,
            ignore=shutil.ignore_patterns('build', 'build-*', '__pycache__'))
    for directory in ('tests', 'tools'):
        (source/directory).symlink_to(ROOT/directory, target_is_directory=True)
    module.prepare_vcf_main(source)
    dx7 = source/'engines/src/msfa_dx7.cc'
    dx7.write_text(module.dx7_block_controls(dx7.read_text()))
    seq = source/'engines/seq/seq_host.c'
    seq.write_text(module.pipeline_sound_frontier(seq.read_text()))
    spec = importlib.util.spec_from_file_location('app_proof', ROOT/'tests/test_app_renderer_pipeline.py')
    proof = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(proof)
    proof.ROOT = source
    replay = (ROOT/'tests/fixtures/renderer_pipeline/app_replay.c').read_text()
    anchor = '#ifdef FM1_APP_RENDER_PIPELINE\n        void *slot='
    # Exercise cache reset, absent offsets and all eight combinations of the
    # three independent per-note controls across successive native blocks.
    replay = module.checked_replace(replay, anchor, """        if (!(block % 97u)) {
            unsigned variant = (block / 97u) & 7u;
            fm1_app_set_param(&app, fm1_app_sound_unit(0), 1, (variant&1)?1.f:0.f);
            fm1_app_set_param(&app, fm1_app_sound_unit(0), 2, (variant&2)?1.f:0.f);
            fm1_app_set_param(&app, fm1_app_sound_unit(0), 3, (variant&4)?7.f:-7.f);
            for (unsigned n=0; n<12; ++n) {
                unsigned mask=(variant+n)&7u;
                app.unit[0].e->set_param_note(app.unit[0].self,48+n,1,(mask&1)?-0.75f:0.f);
                app.unit[0].e->set_param_note(app.unit[0].self,48+n,2,(mask&2)?0.75f:0.f);
                app.unit[0].e->set_param_note(app.unit[0].self,48+n,3,(mask&4)?-6.5f:0.f);
            }
        }
""" + anchor)
    proof.REPLAY_SOURCE = tmp_path/'per_note_replay.c'
    proof.REPLAY_SOURCE.write_text(replay)
    proof.test_app_pipeline_pcm_and_refusal(tmp_path, sanitize)
