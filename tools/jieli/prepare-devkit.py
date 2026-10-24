#!/usr/bin/env python3
"""Prepare an offline-only SDK hello diagnostic; never execute a downloader.

Input SDK must be a private archive of AC79 V1.2.13, commit e30b1ee.
Output remains private: SDK libraries and generated firmware are not redistributable.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil


FM6_SOURCES = ['msfa_dx7.cc', 'dx7_voice.cc', 'dx7_loop.cc', 'msfa_tables.cc', 'msfa_rom.cc']
FM6_HEADERS = ['dx7_voice.h', 'dx7_loop.h', 'dx7_bank.h', 'msfa.h', 'msfa_prelude.h',
               'glide.h', 'note_offsets.h']
FM6_API_HEADERS = ['fm1_engine.h', 'fm1_math.h', 'fm1_midi_ev.h', 'fm1_dx7.h', 'fm1_smooth.h']
MSFA_UNITS = ['dx7note', 'env', 'fm_core', 'fm_op_kernel', 'freqlut', 'lfo', 'patch', 'pitchenv']


def prepare(sdk, source, out, audio_probe=False, fm6_benchmark=False, boot_control=False,
            fm6_ram=False, fm6_audio=False):
    if sum((audio_probe, fm6_benchmark, fm6_audio)) > 1:
        raise ValueError('Choose one diagnostic; FM6 timing does not enable DAC output')
    if fm6_ram and not (fm6_benchmark or fm6_audio):
        raise ValueError('FM6 SRAM placement requires the FM6 benchmark or audio mode')
    if fm6_audio and not (fm6_ram and boot_control):
        raise ValueError('Live FM6 requires SRAM placement and unattended UART control')
    if out.exists():
        raise ValueError('Output must not exist; preserve prior build evidence')
    shutil.copytree(sdk, out)
    app = out/'apps/demo/demo_hello'
    config = app/'include/app_config.h'
    text = config.read_text()
    assert '#define __FLASH_SIZE__    (4 * 1024 * 1024)' in text
    text = text.replace('(4 * 1024 * 1024)', '(8 * 1024 * 1024)', 1)
    assert '#define __SDRAM_SIZE__    (2 * 1024 * 1024)' in text
    text = text.replace('#define __SDRAM_SIZE__    (2 * 1024 * 1024)',
                        '#define __SDRAM_SIZE__    (8 * 1024 * 1024)', 1)
    text = text.replace('#define CONFIG_CXX_SUPPORT', '// #define CONFIG_CXX_SUPPORT')
    config.write_text(text)
    # This diagnostic needs no settings backend. Keep vendor records linked
    # outside the registered range rather than patching their implementations.
    # system.ld is the source used by sdk_ld.c's pre-build preprocessing.
    system_ld = out/'include_lib/driver/cpu/wl82/system.ld'
    text = system_ld.read_text()
    entries = '       *(.syscfg.2.ops)\n       *(.syscfg.1.ops)\n       *(.syscfg.0.ops)\n'
    end = '    PROVIDE(syscfg_ops_end = .);'
    if text.count(entries) != 1 or text.count(end) != 1:
        raise ValueError('Unexpected SDK settings-table layout; review before building')
    text = text.replace(entries, '', 1).replace(end, end+'\n'+entries, 1)
    system_ld.write_text(text)
    main = app/'app_main.c'
    text = main.read_text()
    text = text.replace('void app_main()', 'extern void lunar_devkit_worker(void *);\nvoid app_main()')
    assert 'os_task_create(hello_demo_task, NULL, 10, 1000, 0, "hello_demo_task");' in text
    text = text.replace('os_task_create(hello_demo_task, NULL, 10, 1000, 0, "hello_demo_task");',
                        'os_task_create(lunar_devkit_worker, NULL, 10, 2048, 0, "lunar_devkit");')
    main.write_text(text)
    names = ['benchmark.c', 'benchmark.h', 'sdk_worker.c']
    if audio_probe or fm6_audio:
        names += ['audio_probe.c', 'audio_probe.h']
    if fm6_benchmark:
        names += ['fm6_benchmark.cc', 'fm6_benchmark.h']
    if fm6_audio:
        names += ['fm6_live.cc', 'fm6_live.h']
    if boot_control:
        names += ['boot_command.c', 'boot_command.h', 'boot_control.c']
    for name in names:
        shutil.copyfile(source/'firmware/devkit'/name, app/name)
    shutil.copyfile(source/'engines/include/fm1_resampler.h', app/'fm1_resampler.h')
    makefile = app/'board/wl82/Makefile'
    text = makefile.read_text()
    assert 'all: pre_build $(OUT_ELF)' in text
    text = text.replace('c_SRC_FILES := ' + chr(92), 'c_SRC_FILES := \\\n\t../../../../../apps/demo/demo_hello/benchmark.c \\\n\t../../../../../apps/demo/demo_hello/sdk_worker.c \\', 1)
    # Eliminate the post-build path, including command-line overrides. No USB
    # devices are passed into the build container either.
    text = text.replace('$(QUITE) $(RUN_POST_SCRIPT) sdk', '@echo "Offline build only: downloader disabled"')
    # SDK's C-only script collects .bss, but .bss.* only when CXX is enabled.
    # Keep this non-LTO object's state out of orphan sections in SDRAM.
    text += '\nobjs/apps/demo/demo_hello/benchmark.c.o: CFLAGS := $(filter-out -Oz -flto,$(CFLAGS)) -O2 -ffp-contract=off -fno-data-sections\n'
    if boot_control:
        text = text.replace('c_SRC_FILES := ' + chr(92),
                            'c_SRC_FILES := \\\n\t../../../../../apps/demo/demo_hello/boot_command.c \\\n\t../../../../../apps/demo/demo_hello/boot_control.c \\', 1)
        text += '\nCFLAGS += -DLUNAR_DEVKIT_BOOT_CONTROL=1\n'
        board = app/'board/wl82/board.c'
        board_text = board.read_text()
        anchor = 'UART2_PLATFORM_DATA_BEGIN(uart2_data)'
        registration = '\t{"uart2", &uart_dev_ops, (void *)&uart2_data },'
        if board_text.count(anchor) != 1 or board_text.count(registration) != 1:
            raise ValueError('Unexpected debug UART layout; review command RX pin ownership')
        # Dedicated RX peripheral: do not reopen or repurpose the logging UART.
        # PA5 is exposed on this carrier's UART header. This opt-in build requires
        # a separate, owner-wired Tigard TX connection, not present in v3.
        receiver = '''UART1_PLATFORM_DATA_BEGIN(lunar_control_uart)
    .baudrate = 1000000,
    .port = PORT_REMAP,
    .input_channel = INPUT_CHANNEL0,
    .tx_pin = -1,
    .rx_pin = IO_PORTA_05,
    .max_continue_recv_cnt = 32,
    .idle_sys_clk_cnt = 500000,
    .clk_src = PLL_48M,
    .flags = UART_RX_USE_DMA,
UART1_PLATFORM_DATA_END();

'''
        board.write_text(board_text.replace(anchor, receiver + anchor, 1).replace(
            registration, registration+'\n\t{"uart1", &uart_dev_ops, (void *)&lunar_control_uart },', 1))
    if audio_probe or fm6_audio:
        text = text.replace('c_SRC_FILES := ' + chr(92),
                            'c_SRC_FILES := \\\n\t../../../../../apps/demo/demo_hello/audio_probe.c \\', 1)
        text += '\nCFLAGS += -DLUNAR_DEVKIT_AUDIO_PROBE=1\n'
        if fm6_audio:
            text += '\nCFLAGS += -DLUNAR_DEVKIT_FM6_AUDIO=1\n'
        # := snapshots the global flags now, so every mode define must precede
        # the target-specific override. A later += does not update this object.
        text += 'objs/apps/demo/demo_hello/audio_probe.c.o: CFLAGS := $(filter-out -Oz -flto,$(CFLAGS)) -O2 -ffp-contract=off -fno-data-sections\n'
    engine_inputs = []
    if fm6_benchmark or fm6_audio:
        for subdir, files in [('src', FM6_SOURCES + FM6_HEADERS), ('include', FM6_API_HEADERS)]:
            dest = app/'lunar_engines'/subdir
            dest.mkdir(parents=True)
            for name in files:
                p = source/'engines'/subdir/name
                shutil.copyfile(p, dest/name)
                engine_inputs.append(p)
        # Preserve the upstream code and licence. Generated wrappers keep each
        # translation unit separate, exactly as engines/mk/msfa.mk does.
        msfa = source/'engines/third_party/msfa'
        shutil.copytree(msfa, app/'lunar_engines/third_party/msfa')
        engine_inputs += sorted(p for p in msfa.rglob('*') if p.is_file())
        prefix = '../../../../../apps/demo/demo_hello/'
        files = ['fm6_live.cc' if fm6_audio else 'fm6_benchmark.cc'] + ['lunar_engines/src/'+s for s in FM6_SOURCES]
        for unit in MSFA_UNITS:
            name = 'fm6_unit_'+unit+'.cc'
            (app/name).write_text('#define FM1_MSFA_UNIT "'+unit+'.cc"\n#include "msfa_unit.cc"\n')
            files.append(name)
        shutil.copyfile(source/'engines/src/msfa_unit.cc', app/'lunar_engines/src/msfa_unit.cc')
        engine_inputs.append(source/'engines/src/msfa_unit.cc')
        if text.count('cc_SRC_FILES :=\n') != 1:
            raise ValueError('Unexpected SDK C++ source list; review before building')
        text = text.replace('cc_SRC_FILES :=\n', 'cc_SRC_FILES := '+' '.join(prefix+f for f in files)+'\n')
        if fm6_benchmark:
            text += '\nCFLAGS += -DLUNAR_DEVKIT_FM6_BENCHMARK=1\n'
        text += ('INCLUDES += -I'+prefix+'lunar_engines/include -I'+prefix+
                 'lunar_engines/src -isystem '+prefix+'lunar_engines/third_party/msfa\n')
        for name in files:
            obj = 'objs/apps/demo/demo_hello/'+name+'.o'
            text += obj+': CFLAGS := $(filter-out -Oz -flto,$(CFLAGS)) -O2 -ffp-contract=off -fwrapv -fno-data-sections\n'
            text += obj+': CXXFLAGS := -std=c++11 -fno-exceptions -fno-rtti\n'
        if fm6_ram:
            # Change object placement only, preserving per-function GC and all
            # engine source/flags. The pinned startup already copies ram0_data.
            # External SDK/libc callees can still be in XIP; inspect the ELF.
            linker = out/'cpu/wl82/sdk_ld_sfc.c'
            script = linker.read_text()
            objects = ['*'+Path(name).name+'.o' for name in files
                       if name != 'fm6_benchmark.cc']
            exclusions = ' '.join(objects)
            for section in ('.text*', '.rodata*'):
                anchor = '        *('+section+')'
                if script.count(anchor) != 1:
                    raise ValueError('Unexpected SDK XIP collection; review FM6 placement')
                script = script.replace(anchor, '        *(EXCLUDE_FILE ('+
                                        exclusions+') '+section+')', 1)
            anchor = '        *(.volatile_ram_code)'
            if script.count(anchor) != 1:
                raise ValueError('Unexpected SDK SRAM collection; review startup copy')
            script = script.replace(anchor, anchor+'\n'+''.join(
                '        '+obj+'(.text* .rodata*)\n' for obj in objects), 1)
            linker.write_text(script)
    makefile.write_text(text)
    receipts = {'sdk_commit_required': 'e30b1ee375d1f2993fc23bf92c8b99006a6e5f9d',
                'placement': ('FM6 object code/constants in startup-copied ram0_data; external callees may remain XIP'
                              if fm6_ram else 'XIP code/constants; internal SRAM state; SDK CONFIG_NO_SDRAM_ENABLE'),
                'measurement': ('live FM6 through internal DAC; no mixer/effects; includes note events' if fm6_audio
                                else 'internal-DAC reference tone; no instrument workload' if audio_probe
                                else 'real FM6, no DAC/mixer/effects, raw oscillator timer ticks' if fm6_benchmark
                                else 'resampler-only, IRQ enabled, raw oscillator timer ticks'),
                'download_disabled': True,
                'settings_backends': 'empty registered range; records retained outside it',
                'boot_control': 'UART1 RX PA5, 1Mbaud, explicit ARM/ENTER, linked ROM path requires review' if boot_control else False,
                'inputs': {str(p.relative_to(source)): hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in [*(source/'firmware/devkit'/name for name in names),
                                     source/'tools/jieli/prepare-devkit.py',
                                     source/'engines/include/fm1_resampler.h', *engine_inputs]}}
    (out/'lunar-devkit-input.json').write_text(json.dumps(receipts, indent=2)+'\n')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--sdk', type=Path, required=True)
    ap.add_argument('--source', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument('--audio-probe', action='store_true',
                    help='Build low-level internal-DAC reference tone instead of resampler timings')
    mode.add_argument('--fm6-benchmark', action='store_true',
                      help='Time real FM6 instrument rendering without DAC output')
    mode.add_argument('--fm6-audio', action='store_true',
                      help='Play real FM6 through DAC; requires --fm6-ram --boot-control')
    ap.add_argument('--boot-control', action='store_true',
                    help='Opt in to dev-kit-only UART1 command input on PA5 (requires extra TX wire)')
    ap.add_argument('--fm6-ram', action='store_true',
                    help='Place FM6 object code/constants in SRAM; requires an FM6 mode')
    a = ap.parse_args()
    prepare(a.sdk, a.source, a.out, audio_probe=a.audio_probe, fm6_benchmark=a.fm6_benchmark,
            boot_control=a.boot_control, fm6_ram=a.fm6_ram, fm6_audio=a.fm6_audio)
