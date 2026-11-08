"""Fail-open boot core (firmware/failopen) and its dev-kit preparer, on the desktop."""
from pathlib import Path
import hashlib
import importlib.util
import json
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]

HARNESS = r'''
#include "failopen_core.h"
#include <assert.h>
#include <string.h>

#define WARM 0x10u            /* SYS_RST_SOFT */
#define WDT 0x4u              /* SYS_RST_WDT */
#define POWER_ON 0x100u       /* SYS_RST_VDDIO_PWR_ON */
#define LOW_POWER 0x200u      /* SYS_RST_VDDIO_LOW_PWR */

static enum lunar_failopen_decision boot(struct lunar_failopen_record *r, uint32_t build,
                                         uint32_t reason, enum lunar_failopen_start expect) {
    enum lunar_failopen_start start = (enum lunar_failopen_start)99;
    enum lunar_failopen_decision d = lunar_failopen_boot(r, build, reason, 3, &start);
    assert(start == expect);
    assert(lunar_failopen_valid(r));
    assert(r->build_id == build && r->last_reason == reason);
    return d;
}

static void records(void) {
    struct lunar_failopen_record r;
    unsigned i;
    memset(&r, 0xa5, sizeof(r));                 /* SRAM garbage */
    assert(!lunar_failopen_valid(&r));
    assert(boot(&r, 7, POWER_ON, LUNAR_FAILOPEN_FRESH_INVALID) == LUNAR_FAILOPEN_RUN);
    assert(r.count == 1 && r.boots == 1 && r.flags == 0 && r.fault == 0);
    /* Two more failed warm boots still run; the fourth falls back. */
    lunar_failopen_note_fault(&r, LUNAR_FAILOPEN_FAULT_TEST + 1);
    assert(boot(&r, 7, WARM, LUNAR_FAILOPEN_CONTINUED) == LUNAR_FAILOPEN_RUN);
    assert(r.count == 2 && r.fault == 0);
    assert(boot(&r, 7, WDT, LUNAR_FAILOPEN_CONTINUED) == LUNAR_FAILOPEN_RUN);
    assert(r.count == 3);
    lunar_failopen_note_fault(&r, LUNAR_FAILOPEN_FAULT_STALL);
    assert(boot(&r, 7, WARM, LUNAR_FAILOPEN_CONTINUED) == LUNAR_FAILOPEN_FALLBACK);
    assert(r.count == 3 && r.boots == 4);
    assert(r.fault == LUNAR_FAILOPEN_FAULT_STALL);   /* kept for the report */
    /* Early entry is claimed once; a return to this point defers to later. */
    assert(lunar_failopen_claim_early(&r) == 1 && lunar_failopen_valid(&r));
    assert(boot(&r, 7, WARM, LUNAR_FAILOPEN_CONTINUED) == LUNAR_FAILOPEN_FALLBACK);
    assert(lunar_failopen_claim_early(&r) == 0);
    /* Sticky across many warm resets, and the counter never wraps. */
    for (i = 0; i < 100; ++i)
        assert(boot(&r, 7, WARM, LUNAR_FAILOPEN_CONTINUED) == LUNAR_FAILOPEN_FALLBACK);
    assert(r.count == 3 && r.boots == 105);
    /* A new build starts again, so a fix installed from UBOOT runs. */
    assert(boot(&r, 8, WARM, LUNAR_FAILOPEN_FRESH_BUILD) == LUNAR_FAILOPEN_RUN);
    assert(r.count == 1 && r.boots == 1 && !(r.flags & LUNAR_FAILOPEN_FLAG_EARLY_TRIED));
    /* Healthy clears the count and the early-entry claim. */
    assert(boot(&r, 8, WARM, LUNAR_FAILOPEN_CONTINUED) == LUNAR_FAILOPEN_RUN);
    r.flags |= LUNAR_FAILOPEN_FLAG_EARLY_TRIED;
    lunar_failopen_mark_healthy(&r);
    assert(lunar_failopen_valid(&r) && r.count == 0);
    assert(r.flags == LUNAR_FAILOPEN_FLAG_HEALTHY);
    assert(boot(&r, 8, WARM, LUNAR_FAILOPEN_CONTINUED) == LUNAR_FAILOPEN_RUN);
    assert(r.count == 1 && r.flags == 0);
    /* Power-on and brown-out start again even with a valid record. */
    assert(boot(&r, 8, WARM, LUNAR_FAILOPEN_CONTINUED) == LUNAR_FAILOPEN_RUN);
    assert(boot(&r, 8, WARM, LUNAR_FAILOPEN_CONTINUED) == LUNAR_FAILOPEN_RUN);
    assert(boot(&r, 8, WARM, LUNAR_FAILOPEN_CONTINUED) == LUNAR_FAILOPEN_FALLBACK);
    assert(boot(&r, 8, POWER_ON | WARM, LUNAR_FAILOPEN_FRESH_COLD) == LUNAR_FAILOPEN_RUN);
    assert(r.count == 1);
    assert(boot(&r, 8, LOW_POWER, LUNAR_FAILOPEN_FRESH_COLD) == LUNAR_FAILOPEN_RUN);
    /* Any single changed bit invalidates the record. */
    for (i = 0; i < 8 * sizeof(r); ++i) {
        struct lunar_failopen_record c = r;
        ((unsigned char *)&c)[i / 8] ^= (unsigned char)(1u << (i % 8));
        assert(!lunar_failopen_valid(&c));
    }
    /* Key request survives in the record until the next boot. */
    lunar_failopen_note_key(&r);
    assert(lunar_failopen_valid(&r) && (r.flags & LUNAR_FAILOPEN_FLAG_KEY));
    assert(boot(&r, 8, WARM, LUNAR_FAILOPEN_CONTINUED) == LUNAR_FAILOPEN_RUN);
    assert(!(r.flags & LUNAR_FAILOPEN_FLAG_KEY));
    /* Limit 0 behaves as 1; limit 1 falls back on the second failed boot. */
    memset(&r, 0, sizeof(r));
    assert(lunar_failopen_boot(&r, 9, WARM, 0, NULL) == LUNAR_FAILOPEN_RUN);
    assert(lunar_failopen_boot(&r, 9, WARM, 0, NULL) == LUNAR_FAILOPEN_FALLBACK);
    assert(sizeof(r) == 32);
}

static void monitor(void) {
    struct lunar_failopen_monitor m;
    int slot = -1, a, b;
    uint32_t t0 = 0xfffff000u;                    /* wraps during the test */
    lunar_failopen_monitor_init(&m, t0, 10000);
    assert(lunar_failopen_monitor_poll(&m, t0 + 20000, &slot) == LUNAR_FAILOPEN_WAIT);
    a = lunar_failopen_monitor_add(&m, 6000, t0);
    b = lunar_failopen_monitor_add(&m, 1000, t0 + 100);
    assert(a == 0 && b == 1);
    assert(lunar_failopen_monitor_add(&m, 0, t0) == -1);
    lunar_failopen_monitor_beat(&m, a, t0 + 500);
    lunar_failopen_monitor_beat(&m, 7, t0 + 500);     /* ignored */
    lunar_failopen_monitor_beat(&m, -1, t0 + 500);    /* ignored */
    /* b has not beaten yet: not healthy, and stalled once its timeout passes. */
    assert(lunar_failopen_monitor_poll(&m, t0 + 1000, &slot) == LUNAR_FAILOPEN_WAIT);
    assert(lunar_failopen_monitor_poll(&m, t0 + 1101, &slot) == LUNAR_FAILOPEN_STALLED);
    assert(slot == 1);
    lunar_failopen_monitor_beat(&m, b, t0 + 1101);
    for (uint32_t t = t0 + 1500; t < t0 + 10000; t += 500) {
        lunar_failopen_monitor_beat(&m, a, t);
        lunar_failopen_monitor_beat(&m, b, t);
        assert(lunar_failopen_monitor_poll(&m, t, &slot) == LUNAR_FAILOPEN_WAIT);
    }
    lunar_failopen_monitor_beat(&m, a, t0 + 10000);
    lunar_failopen_monitor_beat(&m, b, t0 + 10000);
    assert(lunar_failopen_monitor_poll(&m, t0 + 10000, &slot) == LUNAR_FAILOPEN_HEALTHY);
    assert(lunar_failopen_monitor_poll(&m, t0 + 10100, &slot) == LUNAR_FAILOPEN_WAIT);
    /* Stall after healthy is still reported; the lowest stalled slot wins. */
    assert(lunar_failopen_monitor_poll(&m, t0 + 17000, &slot) == LUNAR_FAILOPEN_STALLED);
    assert(slot == 0);
    /* A slot caught half-registered (published, timeout not yet stored) is
     * neither stalled nor counted as seen, however old its timestamp. */
    lunar_failopen_monitor_init(&m, 0, 1000);
    m.slots = 1;
    m.last_ms[0] = 0;
    assert(lunar_failopen_monitor_poll(&m, 50000, &slot) == LUNAR_FAILOPEN_WAIT);
    m.timeout_ms[0] = 100;
    m.last_ms[0] = 50000;
    m.beats[0] = 1;
    assert(lunar_failopen_monitor_poll(&m, 50050, &slot) == LUNAR_FAILOPEN_HEALTHY);
    /* Slots are bounded. */
    lunar_failopen_monitor_init(&m, 0, 1000);
    for (a = 0; a < (int)LUNAR_FAILOPEN_SLOTS; ++a)
        assert(lunar_failopen_monitor_add(&m, 100, 0) == a);
    assert(lunar_failopen_monitor_add(&m, 100, 0) == -1);
}

int main(void) {
    records();
    monitor();
    return 0;
}
'''


def test_core(tmp_path):
    harness = tmp_path/'main.c'
    harness.write_text(HARNESS)
    binary = tmp_path/'test'
    subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror',
                    '-fsanitize=address,undefined', '-I'+str(ROOT/'firmware/failopen'),
                    str(harness), str(ROOT/'firmware/failopen/failopen_core.c'),
                    '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)


def fake_sdk(tmp_path):
    sdk = tmp_path/'sdk'
    app = sdk/'apps/demo/demo_hello'
    (app/'include').mkdir(parents=True)
    (app/'board/wl82').mkdir(parents=True)
    system_ld = sdk/'include_lib/driver/cpu/wl82/system.ld'
    system_ld.parent.mkdir(parents=True)
    system_ld.write_text('    PROVIDE(syscfg_ops_begin = .);\n'
                         '       *(.syscfg.2.ops)\n       *(.syscfg.1.ops)\n       *(.syscfg.0.ops)\n'
                         '    _syscfg_ops_end = .;\n    PROVIDE(syscfg_ops_end = .);\n')
    (app/'include/app_config.h').write_text('#define __FLASH_SIZE__    (4 * 1024 * 1024)\n'
                                            '#define __SDRAM_SIZE__    (2 * 1024 * 1024)\n'
                                            '#define CONFIG_CXX_SUPPORT\n')
    (app/'app_main.c').write_text('void app_main()\n{\n    os_task_create(hello_demo_task, NULL, 10, 1000, 0, "hello_demo_task");\n}\n')
    (app/'board/wl82/Makefile').write_text('OUT_ELF := sdk.elf\nc_SRC_FILES := \\\n\toriginal.c\n'
                                           'cc_SRC_FILES :=\nall: pre_build $(OUT_ELF)\n'
                                           '\t$(QUITE) $(RUN_POST_SCRIPT) sdk\n')
    (app/'board/wl82/board.c').write_text('UART2_PLATFORM_DATA_BEGIN(uart2_data)\n'
                                          '\t.rx_pin = -1,\nUART2_PLATFORM_DATA_END();\n'
                                          '\t{"uart2", &uart_dev_ops, (void *)&uart2_data },\n')
    (sdk/'cpu/wl82').mkdir(parents=True)
    (sdk/'cpu/wl82/sdk_ld_sfc.c').write_text(
        'RAM0_SIZE = 0x1c7fe00 - 0x1c00000 - TLB_SIZE - BOOT_INFO_SIZE - 128;\n'
        '        *(.text*)\n        *(.rodata*)\n        *(.volatile_ram_code)\n'
        '    _HEAP_END = 0x1c00000 + RAM0_SIZE - 32;\n'
        '    PROVIDE(HEAP_END = 0x1c00000 + RAM0_SIZE - 32);\n'
        '    _MALLOC_SIZE = _HEAP_END - _HEAP_BEGIN;\n')
    (sdk/'cpu/wl82/setup.c').write_text('void setup_arch()\n{\n    wdt_init(0xc);\n'
                                        '    system_reset_reason_get();\n    puts("x");\n}\n')
    return sdk


def load():
    spec = importlib.util.spec_from_file_location('prepare_failopen',
                                                  ROOT/'tools/jieli/prepare-failopen-devkit.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_preparer(tmp_path):
    module = load()
    sdk = fake_sdk(tmp_path)
    ids = {}
    for mode in ('cycle', 'recover'):
        out = tmp_path/mode
        ids[mode] = module.prepare(sdk, ROOT, out, mode)
        app = out/'apps/demo/demo_hello'
        main = (app/'app_main.c').read_text()
        assert main.startswith('#include "failopen_sdk.h"\n')
        # Fail-open runs before UART control and before any worker task.
        assert main.index('lunar_failopen_app_start();') < main.index('lunar_devkit_boot_control_start')
        assert (app/'sdk_worker.c').read_bytes() == (ROOT/'firmware/devkit/failopen_worker.c').read_bytes()
        for name in ('failopen_core.c', 'failopen_core.h', 'failopen_sdk.c', 'failopen_sdk.h'):
            assert (app/name).read_bytes() == (ROOT/'firmware/failopen'/name).read_bytes()
        setup = (out/'cpu/wl82/setup.c').read_text()
        assert 'lunar_failopen_early(system_reset_reason_get());' in setup
        assert setup.index('wdt_init(0xc)') < setup.index('lunar_failopen_early')
        linker = (out/'cpu/wl82/sdk_ld_sfc.c').read_text()
        assert '_HEAP_END = 0x1c00000 + RAM0_SIZE - 32 - 64;' in linker
        assert 'PROVIDE(HEAP_END = 0x1c00000 + RAM0_SIZE - 32 - 64);' in linker
        assert 'PROVIDE(lunar_failopen_record = 0x1c00000 + RAM0_SIZE - 32 - 64);' in linker
        assert 'RAM0_SIZE = 0x1c7fe00 - 0x1c00000 - TLB_SIZE - BOOT_INFO_SIZE - 128;' in linker
        make = (app/'board/wl82/Makefile').read_text()
        assert 'apps/demo/demo_hello/failopen_core.c' in make
        assert 'apps/demo/demo_hello/failopen_sdk.c' in make
        assert '-DLUNAR_FAILOPEN_BUILD_ID=0x{:08x}u'.format(ids[mode]) in make
        assert '-DLUNAR_FAILOPEN_LIMIT=3 -DLUNAR_FAILOPEN_HEALTHY_MS=10000' in make
        assert ('-DLUNAR_FAILOPEN_TEST_CYCLE=1' in make) == (mode == 'cycle')
        assert ('-DLUNAR_FAILOPEN_TEST_RECOVER=1' in make) == (mode == 'recover')
        assert '-DLUNAR_DEVKIT_BOOT_CONTROL=1' in make
        assert 'downloader disabled' in make and '$(RUN_POST_SCRIPT)' not in make
        receipt = json.loads((out/'lunar-devkit-input.json').read_text())
        assert receipt['failopen_mode'] == mode
        assert receipt['failopen_build_id'] == '0x{:08x}'.format(ids[mode])
        assert 'firmware/devkit/sdk_worker.c' not in receipt['inputs']
        worker = ROOT/'firmware/devkit/failopen_worker.c'
        assert receipt['inputs']['firmware/devkit/failopen_worker.c'] == hashlib.sha256(worker.read_bytes()).hexdigest()
        with pytest.raises(ValueError, match='Output must not exist'):
            module.prepare(sdk, ROOT, out, mode)
    assert ids['cycle'] != ids['recover']
    assert module.build_id(ROOT, 'cycle', 3, 10000) == ids['cycle']
    assert module.build_id(ROOT, 'cycle', 4, 10000) != ids['cycle']
    with pytest.raises(ValueError, match='mode'):
        module.prepare(sdk, ROOT, tmp_path/'bad', 'healthy')
    with pytest.raises(ValueError, match='Limit'):
        module.prepare(sdk, ROOT, tmp_path/'bad', 'cycle', limit=0)


def test_preparer_refuses_unknown_layout(tmp_path):
    module = load()
    sdk = fake_sdk(tmp_path)
    setup = sdk/'cpu/wl82/setup.c'
    setup.write_text(setup.read_text().replace('system_reset_reason_get();', 'reason();'))
    with pytest.raises(ValueError, match='setup_arch'):
        module.prepare(sdk, ROOT, tmp_path/'a', 'cycle')
    sdk2 = fake_sdk(tmp_path/'second')
    linker = sdk2/'cpu/wl82/sdk_ld_sfc.c'
    linker.write_text(linker.read_text().replace('RAM0_SIZE - 32);', 'RAM0_SIZE - 16);'))
    with pytest.raises(ValueError, match='heap layout'):
        module.prepare(sdk2, ROOT, tmp_path/'b', 'cycle')


def test_sources_avoid_banned_paths():
    """The glue uses the reviewed cpu.a ROM path only: no eFuse, no loader."""
    for name in ('firmware/failopen/failopen_sdk.c', 'firmware/devkit/failopen_worker.c',
                 'firmware/failopen/failopen_core.c'):
        text = (ROOT/name).read_text().lower()
        for banned in ('efuse_w', 'fc12', '0xa1', 'mkey', 'chip_key', 'norflash_', 'sfc_erase',
                       'flash_write', 'uac_audio'):
            assert banned not in text, (name, banned)
    sdk_glue = (ROOT/'firmware/failopen/failopen_sdk.c').read_text()
    assert sdk_glue.count('nvram_set_boot_state(2);') == 1
