"""Offline contract checks: transport denial and real resampler workload."""
import importlib.util
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import devkit_flash_backup as backup


@pytest.mark.parametrize('op', [0xFC12, 0xFD06, 0xFC0B, 0xA1, 0xFB09])
def test_flash_writes_and_unknown_commands_denied(op):
    with pytest.raises(ValueError):
        backup.request(op, 'loader')


@pytest.mark.parametrize('address', [-256, 1, 0x800000, 0x1000000])
def test_backup_read_bounds(address):
    with pytest.raises(ValueError):
        backup.request(0xFD05, 'loader', address=address)


def test_last_flash_read():
    cdb, data, size = backup.request(0xFD05, 'loader', address=0x7fff00)
    assert cdb[:8] == bytes.fromhex('fd05007fff000100')
    assert data == b'' and size == 256


def test_loader_rejected_before_any_device_command():
    reader = backup.DevkitReader.__new__(backup.DevkitReader)
    reader.cmd = lambda *a, **k: pytest.fail('must reject before device commands')
    with pytest.raises(ValueError, match='fixed-configuration'):
        reader.load(bytes(backup.base.LOADER_SIZE))


def test_devkit_loader_pin_differs_from_historical_original():
    assert backup.LOADER_SHA != backup.base.LOADER_SHA
    assert backup.LOADER_SHA == 'fe6d1bd36c8ffe4674e4a05ee748fe87480b5867fac58230b14ff089d411012c'


@pytest.mark.parametrize('mode', ['cpu1', 'cpu1-long', 'cpu1-ring', 'resampler', 'audio', 'fm6', 'fm6-ram', 'fm6-audio', 'control', 'renderer', 'renderer-timing', 'renderer-profile', 'renderer-hot-profile', 'renderer-sine-profile', 'renderer-resampler-profile', 'renderer-cache-profile', 'renderer-fx-profile', 'renderer-outline-profile', 'renderer-filter-profile', 'renderer-control-profile', 'renderer-plaits-cache-profile', 'renderer-slopes-profile', 'renderer-engine-profile', 'renderer-unroll-profile', 'renderer-o3-profile', 'renderer-mixer-profile', 'renderer-schedule-profile', 'renderer-keys-profile', 'renderer-keys-live', 'renderer-dispatch-profile', 'renderer-ui-profile', 'renderer-prep-profile'])
def test_sdk_preparation_disables_downloader_and_orphan_bss(tmp_path, mode):
    keys = mode in ('renderer-keys-profile', 'renderer-keys-live')
    if keys:
        mode = 'renderer-mixer-profile' if mode.endswith('profile') else 'renderer'
    engine_profile = mode == 'renderer-engine-profile'
    prep_profile = mode == 'renderer-prep-profile'
    if prep_profile:
        mode = 'renderer-ui-profile'
    ui_ram = mode == 'renderer-ui-profile'
    dispatch = mode == 'renderer-dispatch-profile' or ui_ram
    schedule = mode == 'renderer-schedule-profile'
    mixer_ram = mode == 'renderer-mixer-profile' or schedule or dispatch
    renderer_o3 = mode == 'renderer-o3-profile' or mixer_ram
    unroll = mode == 'renderer-unroll-profile' or renderer_o3
    if engine_profile or unroll:
        mode = 'renderer-slopes-profile'
    slopes = mode == 'renderer-slopes-profile'
    plaits_cache = mode in ('renderer-plaits-cache-profile', 'renderer-slopes-profile')
    control = mode in ('renderer-control-profile', 'renderer-plaits-cache-profile', 'renderer-slopes-profile')
    outline = mode == 'renderer-outline-profile'
    filter_process = mode in ('renderer-filter-profile', 'renderer-control-profile', 'renderer-plaits-cache-profile', 'renderer-slopes-profile')
    if outline or filter_process:
        mode = 'renderer-fx-profile'
    renderer = mode in ('renderer', 'renderer-timing', 'renderer-profile', 'renderer-hot-profile', 'renderer-sine-profile', 'renderer-resampler-profile', 'renderer-cache-profile', 'renderer-fx-profile')
    timing = mode in ('renderer-timing', 'renderer-profile', 'renderer-hot-profile', 'renderer-sine-profile', 'renderer-resampler-profile', 'renderer-cache-profile', 'renderer-fx-profile')
    live = mode == 'fm6-audio'
    audio_probe, fm6 = mode in ('audio', 'renderer'), mode in ('fm6', 'fm6-ram')
    spec = importlib.util.spec_from_file_location('prepare_devkit', ROOT/'tools/jieli/prepare-devkit.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sdk = tmp_path/'sdk'
    app = sdk/'apps/demo/demo_hello'
    (app/'include').mkdir(parents=True)
    (app/'board/wl82').mkdir(parents=True)
    system_ld = sdk/'include_lib/driver/cpu/wl82/system.ld'
    system_ld.parent.mkdir(parents=True)
    system_ld.write_text('    PROVIDE(syscfg_ops_begin = .);\n'
                         '       *(.syscfg.2.ops)\n       *(.syscfg.1.ops)\n       *(.syscfg.0.ops)\n'
                         '    _syscfg_ops_end = .;\n    PROVIDE(syscfg_ops_end = .);\n')
    (app/'include/app_config.h').write_text('#define __FLASH_SIZE__    (4 * 1024 * 1024)\n#define __SDRAM_SIZE__    (2 * 1024 * 1024)\n#define CONFIG_CXX_SUPPORT\n')
    (app/'app_main.c').write_text('void app_main() {os_task_create(hello_demo_task, NULL, 10, 1000, 0, "hello_demo_task");}')
    (app/'board/wl82/Makefile').write_text('OUT_ELF := sdk.elf\nifeq ($(LINK_AT), 1)\nendif\nc_SRC_FILES := \\\n\toriginal.c\ncc_SRC_FILES :=\nall: pre_build $(OUT_ELF)\n\t$(QUITE) $(RUN_POST_SCRIPT) sdk\n')
    (app/'board/wl82/board.c').write_text('UART2_PLATFORM_DATA_BEGIN(uart2_data)\n'
                                       '\t.rx_pin = -1,\nUART2_PLATFORM_DATA_END();\n'
                                       '\t{"uart2", &uart_dev_ops, (void *)&uart2_data },\n')
    (sdk/'cpu/wl82').mkdir(parents=True)
    (sdk/'cpu/wl82/sdk_ld_sfc.c').write_text('        *(.text*)\n        *(.rodata*)\n'
                                          '        *(.volatile_ram_code)\n    .cache_ram_data ALIGN(4):\n    {\n    } > cache_ram\n')
    out = tmp_path/'prepared'
    if renderer:
        renderer_spec = importlib.util.spec_from_file_location('prepare_renderer', ROOT/'tools/jieli/prepare-renderer-devkit.py')
        renderer_module = importlib.util.module_from_spec(renderer_spec)
        renderer_spec.loader.exec_module(renderer_module)
        renderer_module.prepare_renderer(
            sdk, ROOT, out, timing_only=timing,
            profile=mode in ('renderer-profile', 'renderer-hot-profile', 'renderer-sine-profile', 'renderer-resampler-profile', 'renderer-cache-profile', 'renderer-fx-profile'),
            hot_ram=mode in ('renderer-hot-profile', 'renderer-sine-profile', 'renderer-resampler-profile', 'renderer-cache-profile', 'renderer-fx-profile'),
            sine_ram=mode in ('renderer-sine-profile', 'renderer-resampler-profile', 'renderer-cache-profile', 'renderer-fx-profile'),
            resampler_ram=mode in ('renderer-resampler-profile', 'renderer-cache-profile', 'renderer-fx-profile'),
            cache_tables=mode in ('renderer-cache-profile', 'renderer-fx-profile'),
            fx_ram=mode == 'renderer-fx-profile', resampler_outline=outline, filter_process_ram=filter_process, control_ram=control, plaits_cache=plaits_cache, resampler_slopes=slopes, engine_profile=engine_profile, resampler_unroll=unroll, renderer_o3=renderer_o3, mixer_ram=mixer_ram, resampler_schedule=schedule, workload="keys" if keys else "mixed", dispatch_ram=dispatch, ui_ram=ui_ram, prep_profile=prep_profile)
    elif mode in ('cpu1', 'cpu1-long', 'cpu1-ring'):
        cpu_spec = importlib.util.spec_from_file_location('prepare_cpu1', ROOT/'tools/jieli/prepare-cpu1-devkit.py')
        cpu_module = importlib.util.module_from_spec(cpu_spec)
        cpu_spec.loader.exec_module(cpu_module)
        cpu_module.prepare(sdk, ROOT, out, long_publication=mode == 'cpu1-long', paced_ring=mode == 'cpu1-ring')
        import hashlib, json
        receipt = json.loads((out/'lunar-devkit-input.json').read_text())
        assert 'firmware/devkit/sdk_worker.c' not in receipt['inputs']
        probe_path = ('firmware/devkit/cpu1_ring_probe.c' if mode == 'cpu1-ring' else
                      'firmware/devkit/cpu1_publication_long.c' if mode == 'cpu1-long' else
                      'firmware/devkit/cpu1_probe.c')
        probe = ROOT/probe_path
        assert receipt['inputs'][probe_path] == hashlib.sha256(probe.read_bytes()).hexdigest()
        assert (out/'apps/demo/demo_hello/sdk_worker.c').read_bytes() == probe.read_bytes()
        assert '10, 2048, 0, "#C0lunar_parent"' in (out/'apps/demo/demo_hello/app_main.c').read_text()
        assert receipt['rounds'] == (413607 if mode == 'cpu1-ring' else
                                     100000000 if mode == 'cpu1-long' else 4096)
        assert receipt['recovery_window_ticks'] == 200
        if mode == 'cpu1-long':
            assert receipt['phases'] == 2 and receipt['total_budget_ticks'] == 3840000000
        if mode == 'cpu1-ring':
            assert receipt['total_budget_ms'] == 625000
            assert receipt['frames'] == 64 and receipt['rate'] == 44118
            assert receipt['fpu_irq_acceptance'] is False
            prepared_make = (out/'apps/demo/demo_hello/board/wl82/Makefile').read_text()
            assert 'c_SRC_FILES := ' + chr(92) + '\n\t../../../../../apps/demo/demo_hello/arithmetic_probe.c ' + chr(92) in prepared_make
            for name in ('arithmetic_probe.c', 'arithmetic_probe.h'):
                original = ROOT/'firmware/devkit'/name
                assert (out/'apps/demo/demo_hello'/name).read_bytes() == original.read_bytes()
                assert receipt['inputs'][str(original.relative_to(ROOT))] == hashlib.sha256(original.read_bytes()).hexdigest()
        assert receipt['worker_task'] == '#C1lunar_worker'
        with pytest.raises(ValueError, match='Output must not exist'):
            cpu_module.prepare(sdk, ROOT, out)
    else:
        module.prepare(sdk, ROOT, out, audio_probe=audio_probe, fm6_benchmark=fm6,
                       boot_control=mode == 'control' or live,
                       fm6_ram=mode == 'fm6-ram' or live, fm6_audio=live)
    result = (out/'apps/demo/demo_hello/board/wl82/Makefile').read_text()
    assert '\\ \\' not in result
    assert '$(RUN_POST_SCRIPT) sdk' not in result
    assert '-fno-data-sections' in result
    assert '#define __SDRAM_SIZE__    (8 * 1024 * 1024)' in (out/'apps/demo/demo_hello/include/app_config.h').read_text()
    assert 'benchmark.c' in result and 'sdk_worker.c' in result
    assert ('-DLUNAR_DEVKIT_AUDIO_PROBE=1' in result) == (audio_probe or live)
    assert (out/'apps/demo/demo_hello/audio_probe.c').exists() == (audio_probe or live)
    assert ('-DLUNAR_DEVKIT_FM6_AUDIO=1' in result) == live
    if mode in ('control', 'cpu1', 'cpu1-long', 'cpu1-ring') or live or renderer:
        main_text = (out/'apps/demo/demo_hello/app_main.c').read_text()
        assert 'if (!lunar_devkit_boot_control_start()) {' in main_text
        assert main_text.index('boot_control_start())') < main_text.index('int lunar_status = os_task_create')
    if renderer:
        assert ('-DLUNAR_RENDERER_WORKLOAD=1' in result) == keys
        stack_words = 2048 if filter_process else 3072
        assert f'10, {stack_words}, 0, "lunar_devkit"' in (out/'apps/demo/demo_hello/app_main.c').read_text()
    if timing:
        assert '-DLUNAR_DEVKIT_RENDERER_TIMING=1' in result
        assert ('-DLUNAR_RENDERER_PROFILE=1' in result) == (mode in ('renderer-profile', 'renderer-hot-profile', 'renderer-sine-profile', 'renderer-resampler-profile', 'renderer-cache-profile', 'renderer-fx-profile'))
        assert ('-DFM1_APP_RENDER_PROFILE=1' in result) == (mode in ('renderer-profile', 'renderer-hot-profile', 'renderer-sine-profile', 'renderer-resampler-profile', 'renderer-cache-profile', 'renderer-fx-profile'))
        assert (out/'apps/demo/demo_hello/renderer_timing.h').exists()
        assert not (out/'apps/demo/demo_hello/audio_probe.c').exists()
        makefile = out/'apps/demo/demo_hello/board/wl82/Makefile'
        with makefile.open('a') as fp:
            fp.write('\nprint-renderer-flags:\n\t@echo $(LUNAR_EXTRA)\n')
        flags = subprocess.run(['make', '-s', '-f', str(makefile), 'print-renderer-flags'],
                               cwd=makefile.parent, check=True, capture_output=True, text=True).stdout
        assert '-DLUNAR_DEVKIT_RENDERER_TIMING=1' in flags
        assert ('-DLUNAR_RENDERER_POOL_BYTES=139264' in flags) == control
        assert ('-DLUNAR_RENDERER_PROFILE=1' in flags) == (mode in ('renderer-profile', 'renderer-hot-profile', 'renderer-sine-profile', 'renderer-resampler-profile', 'renderer-cache-profile', 'renderer-fx-profile'))
        assert ('-DFM1_APP_RENDER_PROFILE=1' in flags) == (mode in ('renderer-profile', 'renderer-hot-profile', 'renderer-sine-profile', 'renderer-resampler-profile', 'renderer-cache-profile', 'renderer-fx-profile'))
    if audio_probe or live:
        # Exercise Make's immediate target-variable expansion, not merely the
        # presence of a later global define in the generated text.
        makefile = out/'apps/demo/demo_hello/board/wl82/Makefile'
        target = 'objs/apps/demo/demo_hello/audio_probe.c.o'
        with makefile.open('a') as fp:
            fp.write('\n'+target+':\n\t@echo $(CFLAGS)\n')
        flags = subprocess.run(['make', '-s', '-f', str(makefile), target],
                               cwd=makefile.parent, check=True, capture_output=True, text=True).stdout
        assert '-DLUNAR_DEVKIT_AUDIO_PROBE=1' in flags
        assert ('-DLUNAR_DEVKIT_FM6_AUDIO=1' in flags) == live
        assert ('-DLUNAR_DEVKIT_RENDERER_AUDIO=1' in flags) == renderer
        if renderer:
            # Both the non-LTO DAC callback and the normal SDK worker must
            # retain UART control. Routine tests cannot require physical reset.
            assert '-DLUNAR_DEVKIT_BOOT_CONTROL=1' in flags
            assert (out/'apps/demo/demo_hello/boot_control.c').exists()
            import json
            receipt = json.loads((out/'lunar-devkit-input.json').read_text())
            assert receipt['download_disabled'] is True
            assert receipt['boot_control']
            assert receipt['hardware_acceptance'] is False
    if renderer:
        import hashlib, json
        receipt = json.loads((out/'lunar-devkit-input.json').read_text())
        assert receipt['renderer_workload'] == ('keys' if keys else 'mixed')
        assert bool(receipt['hot_ram_sources']) == (mode in ('renderer-hot-profile', 'renderer-sine-profile', 'renderer-resampler-profile', 'renderer-cache-profile', 'renderer-fx-profile'))
        for name, digest in receipt['hot_ram_sources'].items():
            original = (ROOT/name).read_bytes()
            assert digest == hashlib.sha256(original).hexdigest()
            prepared = (out/'lunar-source'/name).read_bytes()
            actual_prepared = prepared
            if engine_profile and name in ('engines/src/mi_macro.cc', 'engines/src/drums.cc'):
                import re
                assert prepared.startswith(b'extern \"C\" void lunar_devkit_engine_profile(unsigned, unsigned, int);\n')
                prepared = re.sub(rb'^extern \"C\" void lunar_devkit_engine_profile[^\n]+\n|^ +lunar_devkit_engine_profile\([^\n]+\n', b'', prepared, flags=re.M)
                assert prepared != actual_prepared
                assert receipt['engine_profile_original_sha256'][name] == hashlib.sha256(prepared).hexdigest()
            prefix = b'#pragma code_seg(".volatile_ram_code")\n' + original
            if mode in ('renderer-resampler-profile', 'renderer-cache-profile', 'renderer-fx-profile') and name == 'engines/src/mi_macro.cc':
                assert prepared.startswith(prefix)
            else:
                assert prepared == prefix
            assert receipt['inputs'][name] == hashlib.sha256(actual_prepared).hexdigest()
        original = (ROOT/'engines/src/msfa_rom.cc').read_bytes()
        prepared = (out/'lunar-source/engines/src/msfa_rom.cc').read_bytes()
        section = b'.lunar_cache_tables' if mode in ('renderer-cache-profile', 'renderer-fx-profile') else b'.volatile_ram'
        if mode in ('renderer-sine-profile', 'renderer-resampler-profile', 'renderer-cache-profile', 'renderer-fx-profile'):
            assert receipt['sine_ram_original_sha256'] == hashlib.sha256(original).hexdigest()
            expected = original.replace(b'extern const int32_t kSinTab[2048] = {',
                b'extern const int32_t kSinTab[2048] __attribute__((section("' + section + b'"))) = {', 1)
            if mode in ('renderer-cache-profile', 'renderer-fx-profile'):
                expected = expected.replace(b'extern const int32_t kExp2Tab[2048] = {',
                    b'extern const int32_t kExp2Tab[2048] __attribute__((section(".lunar_cache_tables"))) = {', 1)
            assert prepared == expected
        else:
            assert receipt['sine_ram_original_sha256'] is None and prepared == original
        original = (ROOT/'engines/include/fm1_resampler.h').read_bytes()
        prepared = (out/'lunar-source/engines/include/fm1_resampler.h').read_bytes()
        if mode in ('renderer-resampler-profile', 'renderer-cache-profile', 'renderer-fx-profile'):
            import re
            assert receipt['resampler_ram_original_sha256'] == hashlib.sha256(original).hexdigest()
            # Kernel, low-pass and the 51/47 fast path's two-dimensional table.
            definitions = re.findall(rb'static const float fm1_resampler_\w+\[[^\]]+\](?:\[[^\]]+\])? = \{.*?\n\};', original, re.S)
            assert len(definitions) == 3
            macro = (out/'lunar-source/engines/src/mi_macro.cc').read_bytes()
            for definition in definitions:
                if slopes and b"fm1_resampler_kernel[" in definition:
                    definition = renderer_module.resampler_slope_definition(definition.decode()).encode()
                    assert b"fm1_resampler_kernel[" not in prepared
                    assert b"fm1_resampler_kernel[" not in macro
                    assert b"return k[0] + (float)(t & 0xFFFFu) * k[1];" in prepared
                external = definition.replace(b'static const float', b'extern const float', 1)
                assert external.replace(b' = {', b' __attribute__((section("' + section + b'"))) = {', 1) in macro
                declaration = definition.split(b' = {', 1)[0].replace(b'static const', b'extern const', 1) + b';'
                assert declaration in prepared
                if b"fm1_resampler_poly47[" in definition:
                    assert b"#if FM1_RESAMPLER_POLY47\n" + external.split(b' = {', 1)[0] in macro
            assert b'static const float fm1_resampler_' not in prepared
        else:
            assert receipt['resampler_ram_original_sha256'] is None
            assert prepared == original
        assert receipt['cache_tables'] == (mode in ('renderer-cache-profile', 'renderer-fx-profile'))
        assert receipt['fx_ram'] == (mode == 'renderer-fx-profile')
        assert receipt['resampler_outline'] == outline
        assert receipt['filter_process_ram'] == filter_process
        assert receipt['worker_stack_words'] == (2048 if filter_process else 3072)
        assert receipt['worker_stack_bytes'] == receipt['worker_stack_words'] * 4
        assert receipt['renderer_pool_bytes'] == (136 if control else 148) * 1024
        assert receipt['plaits_cache'] == plaits_cache
        assert receipt['resampler_slopes'] == slopes
        assert receipt['resampler_unroll'] == unroll
        assert receipt['resampler_schedule'] == schedule
        fragment = (out/'apps/demo/demo_hello/board/wl82/lunar-renderer.mk').read_bytes()
        assert receipt['prepared_renderer_fragment_sha256'] == hashlib.sha256(fragment).hexdigest()
        opt = '-O3' if renderer_o3 else '-O2'
        assert receipt['renderer_optimization'] == opt
        assert ('OPT=' + opt).encode() in fragment
        expected_fragment = (ROOT/'tools/jieli/devkit-renderer-sdk.mk').read_bytes()
        if renderer_o3:
            expected_fragment = expected_fragment.replace(b'OPT=-O2', b'OPT=-O3', 1)
        assert fragment == expected_fragment
        assert receipt['engine_profile'] == engine_profile
        assert ('-DLUNAR_RENDERER_ENGINE_PROFILE=1' in result) == engine_profile
        if not engine_profile:
            assert receipt['engine_profile_original_sha256'] == {}
        tables = {
            'engines/third_party/mutable/stmlib/dsp/units.cc': ('lut_pitch_ratio_high', 'lut_pitch_ratio_low'),
            'engines/third_party/mutable/plaits/resources.cc': ('lut_sine',),
        }
        for name, selected_tables in tables.items():
            original_tables = (ROOT/name).read_bytes()
            prepared_tables = (out/'lunar-source'/name).read_bytes()
            expected_tables = original_tables
            if plaits_cache:
                for table in selected_tables:
                    declaration = b'const float ' + table.encode() + b'[]'
                    expected_tables = expected_tables.replace(declaration + b' = {',
                        declaration + b' __attribute__((section(".lunar_cache_tables"))) = {', 1)
                assert receipt['plaits_table_original_sha256'][name] == hashlib.sha256(original_tables).hexdigest()
            assert prepared_tables == expected_tables
        if not plaits_cache:
            assert receipt['plaits_table_original_sha256'] == {}
        assert receipt['prep_profile'] == prep_profile
        if prep_profile:
            assert set(receipt['prep_profile_original_sha256']) == {
                'sim/web/src/fm1_app.c', 'engines/mod/mod_plan.c',
                'engines/seq/seq_host.c', 'engines/mod/mod_glue.c', 'engines/mod/mod_core.c',
            }
            assert '-DLUNAR_RENDERER_PREP_PROFILE=1' in (out/'apps/demo/demo_hello/board/wl82/Makefile').read_text()
            for name, planner in (('sim/web/src/fm1_app.c', False), ('engines/mod/mod_plan.c', True)):
                observed = (out/'lunar-source'/name).read_text()
                assert 'extern void lunar_devkit_prep_profile(unsigned, int);' in observed
                # Manifest hashes the exact input after any section annotations.
                prep_original = (ROOT/name).read_text()
                if name.endswith('mod_plan.c'):
                    assert receipt['prep_profile_original_sha256'][name] == hashlib.sha256(prep_original.encode()).hexdigest()
            for name, functions in renderer_module.DISPATCH_PROFILE_CALLS.items():
                observed = (out/'lunar-source'/name).read_text()
                assert observed.startswith('extern void lunar_devkit_prep_profile(unsigned, int);\n')
                unobserved = observed.split('\n', 1)[1]
                unobserved = re.sub(r'^ *lunar_devkit_prep_profile\(\d+, [01]\);\n', '', unobserved, flags=re.M)
                # Observer insertion changes indentation only; its recorded input
                # remains checked by the dedicated source-preservation test.
                assert 'lunar_devkit_prep_profile(' not in unobserved
                for _, calls in functions:
                    for region, call in calls:
                        assert observed.count(f'lunar_devkit_prep_profile({region}, 1);') == 1
                        assert observed.count(f'lunar_devkit_prep_profile({region}, 0);') == 1
                        assert unobserved.count(call) == 1
        else:
            assert receipt['prep_profile_original_sha256'] == {}
        assert receipt['ui_ram'] == ui_ram
        for name, signatures in (
            ('sim/web/src/fm1_seq_ui.c', ('int fm1_seq_ui_sync(',)),
            ('engines/seq/seq_engine.c', ('void fm1_seq_get_info(',
             'int fm1_seq_get_track(', 'int fm1_seq_get_clip(')),
        ):
            original_ui = (ROOT/name).read_bytes()
            prepared_ui = (out/'lunar-source'/name).read_bytes()
            normalized_ui = prepared_ui.replace(b'#pragma code_seg(".volatile_ram_code")\n', b'').replace(b'\n#pragma code_seg()', b'')
            assert normalized_ui == original_ui
            assert (prepared_ui != original_ui) == ui_ram
            for signature in signatures:
                assert ('#pragma code_seg(".volatile_ram_code")\n' + signature in prepared_ui.decode()) == ui_ram
            if ui_ram:
                assert receipt['ui_ram_original_sha256'][name] == hashlib.sha256(original_ui).hexdigest()
        if not ui_ram:
            assert receipt['ui_ram_original_sha256'] == {}
        assert receipt['dispatch_ram'] == dispatch
        prepared_seq = (out/'lunar-source/engines/seq/seq_host.c').read_text()
        for signature in ('static int walk_next(', 'static void dispatched(', 'static void play_slots_hook('):
            assert ('#pragma code_seg(".volatile_ram_code")\n' + signature in prepared_seq) == dispatch
        assert receipt['mixer_ram'] == mixer_ram
        prepared_app = (out/'lunar-source/sim/web/src/fm1_app.c').read_text()
        for signature in ('static void render_fx(', 'static void render_sounds('):
            assert ('#pragma code_seg(".volatile_ram_code")\n' + signature in prepared_app) == mixer_ram
        assert receipt['control_ram'] == control
        assert ('-DLUNAR_RENDERER_POOL_BYTES=139264' in result) == control
        for name in ('sim/web/src/fm1_app.c', 'engines/mod/mod_core.c', 'engines/seq/seq_host.c'):
            original_control = (ROOT/name).read_bytes()
            prepared_control = (out/'lunar-source'/name).read_bytes()
            normalized = prepared_control.replace(b'#pragma code_seg(".volatile_ram_code")\n', b'').replace(b'\n#pragma code_seg()', b'')
            if prep_profile:
                normalized = re.sub(rb'^extern void lunar_devkit_prep_profile\(unsigned, int\);\n', b'', normalized, flags=re.M)
                normalized = re.sub(rb'^ *lunar_devkit_prep_profile\(\d+, [01]\);\n', b'', normalized, flags=re.M)
                assert re.sub(rb'\s+', b'', normalized) == re.sub(rb'\s+', b'', original_control)
            else:
                assert normalized == original_control
            assert (prepared_control != original_control) == control
            if control:
                assert receipt['control_ram_original_sha256'][name] == hashlib.sha256(original_control).hexdigest()
        if not control:
            assert receipt['control_ram_original_sha256'] == {}

        original_filter = (ROOT/'engines/src/fx_filter.cc').read_bytes()
        prepared_filter = (out/'lunar-source/engines/src/fx_filter.cc').read_bytes()
        if filter_process:
            import re
            body, = re.findall(rb'static void FiltProcess\([^\n]+\) \{.*?\n\}', original_filter, re.S)
            expected_filter = original_filter.replace(body, b'#pragma code_seg(".volatile_ram_code")\n' + body + b'\n#pragma code_seg()', 1)
            assert prepared_filter == expected_filter
            assert receipt['filter_process_original_sha256'] == hashlib.sha256(original_filter).hexdigest()
        else:
            assert prepared_filter == original_filter
            assert receipt['filter_process_original_sha256'] is None

        for name in (b'fm1_resampler_intermediate_', b'fm1_resampler_pop'):
            signature = b'static __attribute__((noinline)) float ' + name + b'(fm1_resampler_t *r) {'
            assert (signature in prepared) == outline
        # Verify exact table, qualifier and optional fixed-loop transformations.
        if mode == 'renderer-fx-profile':
            expected = original
            for definition in definitions:
                declaration = definition.split(b' = {', 1)[0].replace(b'static const', b'extern const', 1) + b';'
                if slopes and b"fm1_resampler_kernel[" in definition:
                    declaration = b"extern const float fm1_resampler_kernel_pairs[(FM1_RESAMPLER_KERNEL_LEN - 1) * 2];"
                expected = expected.replace(definition, declaration, 1)
            if slopes:
                expected = expected.replace(b"&fm1_resampler_kernel[t >> 16]",
                    b"&fm1_resampler_kernel_pairs[(t >> 16) * 2]", 1).replace(
                    b"(1.0f / 65536.0f) * (k[1] - k[0])", b"k[1]", 1)
            normalized = prepared.replace(b'static __attribute__((noinline)) float ', b'static inline float ')
            if unroll:
                assert receipt['resampler_unroll_original_sha256'] == hashlib.sha256(expected).hexdigest()
                expected = renderer_module.unroll_resampler_lowpass(expected.decode()).encode()
            if schedule:
                assert receipt["resampler_schedule_original_sha256"] == hashlib.sha256(expected).hexdigest()
                expected = renderer_module.schedule_resampler_lowpass(expected.decode()).encode()
            assert normalized == expected

        effects = {'engines/src/fx_comp.cc', 'engines/src/fx_drive.cc', 'engines/src/fx_echo.cc'}
        assert effects.intersection(receipt['hot_ram_sources']) == (effects if mode == 'renderer-fx-profile' else set())
        linked = (out/'cpu/wl82/sdk_ld_sfc.c').read_bytes()
        assert receipt['prepared_link_script_sha256'] == hashlib.sha256(linked).hexdigest()
        if mode in ('renderer-cache-profile', 'renderer-fx-profile'):
            assert receipt['cache_link_original_sha256']
            assert b'    .cache_ram_data ALIGN(4):\n    {\n        *(.lunar_cache_tables)\n' in linked
            assert b'FREE_DACHE_WAY' not in linked  # No way-allocation edits.
        else:
            assert receipt['cache_link_original_sha256'] is None
            assert b'.lunar_cache_tables' not in linked
        # Unselected hot-path callers are not silently pulled into the change.
        if not control:
            assert (out/'lunar-source/sim/web/src/fm1_app.c').read_bytes() == (ROOT/'sim/web/src/fm1_app.c').read_bytes()
    assert ('-DLUNAR_DEVKIT_FM6_BENCHMARK=1' in result) == fm6
    assert ('-DLUNAR_DEVKIT_BOOT_CONTROL=1' in result) == (mode in ('control', 'cpu1', 'cpu1-long', 'cpu1-ring') or live or renderer)
    if mode in ('control', 'cpu1', 'cpu1-long', 'cpu1-ring'):
        board = (out/'apps/demo/demo_hello/board/wl82/board.c').read_text()
        assert '.rx_pin = IO_PORTA_05' in board and '.tx_pin = -1' in board
        assert '.rx_pin = -1' in board  # Logging UART stays transmit-only.
        assert 'boot_control.c' in result and 'boot_command.c' in result
    if fm6 or live:
        import json
        receipt = json.loads((out/'lunar-devkit-input.json').read_text())
        assert 'engines/src/msfa_dx7.cc' in receipt['inputs']
        assert 'engines/third_party/msfa/LICENSE' in receipt['inputs']
        assert ('live FM6 through internal DAC' if live else 'no DAC/mixer/effects') in receipt['measurement']
        assert '-fwrapv' in result and '-std=c++11' in result
        assert (out/'apps/demo/demo_hello/fm6_unit_env.cc').read_text().startswith('#define FM1_MSFA_UNIT "env.cc"')
        script = (out/'cpu/wl82/sdk_ld_sfc.c').read_text()
        assert ('EXCLUDE_FILE' in script) == (mode == 'fm6-ram' or live)
        if mode == 'fm6-ram' or live:
            assert '*msfa_dx7.cc.o(.text* .rodata*)' in script
            assert '*fm6_unit_fm_op_kernel.cc.o(.text* .rodata*)' in script
            assert '*fm6_benchmark.cc.o' not in script
            assert 'startup-copied ram0_data' in receipt['placement']
        if live:
            assert '*fm6_live.cc.o(.text* .rodata*)' in script
            assert 'fm6_benchmark.cc' not in result
    linked = (out/'include_lib/driver/cpu/wl82/system.ld').read_text()
    start = linked.index('PROVIDE(syscfg_ops_begin')
    end = linked.index('PROVIDE(syscfg_ops_end')
    assert '.syscfg.' not in linked[start:end]
    assert linked.count('*(.syscfg.') == 3
    assert linked.index('*(.syscfg.') > end
    with pytest.raises(ValueError):
        module.prepare(sdk, ROOT, out)
    with pytest.raises(ValueError, match='Choose one'):
        module.prepare(sdk, ROOT, tmp_path/'ambiguous', audio_probe=True, fm6_benchmark=True)
    assert not (tmp_path/'ambiguous').exists()
    with pytest.raises(ValueError, match='requires the FM6'):
        module.prepare(sdk, ROOT, tmp_path/'invalid-ram', fm6_ram=True)
    assert not (tmp_path/'invalid-ram').exists()
    with pytest.raises(ValueError, match='requires SRAM'):
        module.prepare(sdk, ROOT, tmp_path/'invalid-live', fm6_audio=True)
    assert not (tmp_path/'invalid-live').exists()


@pytest.mark.parametrize('poly47', [0, 1], ids=['two-stage', 'poly47'])
def test_real_resampler_workload(tmp_path, poly47):
    # With FM1_RESAMPLER_POLY47=0 the 47,872 Hz row is the two-stage converter
    # the dev board ran (notes/2026-10-23-devkit-resampler-results.md). With
    # the 51/47 fast path (the default since 2026-10-28) that row is computed
    # on the host only; the board has not run it yet.
    row = ('{0xbcc31dc5u, 0xd1a8e8ebu, 0x60bcf761u}' if poly47
           else '{0xbcc31dc5u, 0x0c28d304u, 0x18efc0bfu}')
    harness = tmp_path/'main.c'
    harness.write_text('''
#include "benchmark.h"
#include <assert.h>
static unsigned clock_value, count, active_hash;
static unsigned now(void) { clock_value += 17; return clock_value; }
static void emit(const struct lunar_devkit_result *r) {
    /* Captured on the dev board and independently matched on the host:
     * notes/2026-10-23-devkit-resampler-results.md. These are fixture output
     * hashes, not timing expectations or a complete sample-stream oracle. */
    static const unsigned expected[3][3] = {
        {0xbcc31dc5u, 0x80cf1dc5u, 0x4d7705c5u},
        ROW_47872,
        {0xbcc31dc5u, 0x8d5cd591u, 0x0a82150fu}
    };
    unsigned rate_index = r->rate == 44118 ? 0 : r->rate == 47872 ? 1 : 2;
    assert(r->signal < 3 && r->checksum == expected[rate_index][r->signal]);
    assert(r->min_ticks == 17 && r->max_ticks == 17);
    assert(r->ticks == r->blocks * 17);
    assert(r->input_frames >= r->blocks * 64);
    if (r->rate == 44118 && r->signal == 1) {
        if (active_hash) assert(active_hash == r->checksum);
        active_hash = r->checksum;
    }
    ++count;
}
int main(void) {
    assert(!lunar_devkit_benchmark(0, emit));
    assert(lunar_devkit_benchmark(now, emit));
    assert(count == 18 && active_hash);
    return 0;
}
'''.replace('ROW_47872', row))
    binary = tmp_path/'benchmark'
    subprocess.run(['cc', '-std=c99', '-O2', '-ffp-contract=off', '-Wall', '-Wextra', '-Werror',
                    '-fsanitize=undefined,address', f'-DFM1_RESAMPLER_POLY47={poly47}',
                    '-I'+str(ROOT/'firmware/devkit'),
                    '-I'+str(ROOT/'engines/include'), str(harness),
                    str(ROOT/'firmware/devkit/benchmark.c'), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)


def test_real_fm6_workload_and_wrapping_timer(tmp_path):
    """Build the actual source set, not a mock engine; hashes are host fixtures,
    never a claim that the target has produced the same output yet."""
    spec = importlib.util.spec_from_file_location('prepare_devkit', ROOT/'tools/jieli/prepare-devkit.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    harness = tmp_path/'main.cc'
    harness.write_text(r'''
#include "fm6_benchmark.h"
#include <assert.h>
static uint32_t clock_value = 0xfffffff0u, count;
static uint32_t now() { clock_value += 17; return clock_value; }
static void emit(const lunar_fm6_result *r) {
    const uint32_t expected[12] = {
        0xb3891185u, 0xd1d87f07u, 0xc7fae18fu, 0x2b6c31e3u,
        0x323880bdu, 0x6a0d808fu, 0x099ddb63u, 0xffe2fb73u,
        0x11a55cadu, 0x183f0eebu, 0x6bf19151u, 0x86a5a4adu
    };
    const uint32_t patches[] = {0, 19, 25}, voices[] = {1, 4, 8, 12};
    assert(count < 12 && r->checksum == expected[count]);
    assert(r->patch == patches[count / 4] && r->voices == voices[count % 4]);
    assert(r->blocks == 256 && r->ticks == 256 * 17);
    assert(r->min_ticks == 17 && r->max_ticks == 17);
    assert(r->note_on_ticks == 17 && r->note_off_ticks == 17);
    assert(r->instance_bytes > 0 && r->instance_bytes <= 65536);
    assert(!r->invalid_samples && r->nonzero_samples > 0);
    ++count;
}
int main() {
    assert(!lunar_devkit_fm6_benchmark(0, emit));
    assert(!lunar_devkit_fm6_benchmark(now, 0));
    assert(lunar_devkit_fm6_benchmark(now, emit));
    assert(count == 12);
}
''')
    units = []
    for unit in module.MSFA_UNITS:
        path = tmp_path/(unit+'.cc')
        path.write_text('#define FM1_MSFA_UNIT "'+unit+'.cc"\n#include "msfa_unit.cc"\n')
        units.append(path)
    binary = tmp_path/'fm6-benchmark'
    subprocess.run(['c++', '-std=c++11', '-O2', '-ffp-contract=off', '-fwrapv',
                    '-fno-exceptions', '-fno-rtti', '-fsanitize=address',
                    '-I'+str(ROOT/'firmware/devkit'), '-I'+str(ROOT/'engines/include'),
                    '-I'+str(ROOT/'engines/src'), '-isystem', str(ROOT/'engines/third_party/msfa'),
                    str(harness), str(ROOT/'firmware/devkit/fm6_benchmark.cc'),
                    *(str(ROOT/'engines/src'/p) for p in module.FM6_SOURCES),
                    *(str(p) for p in units), '-lm', '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
