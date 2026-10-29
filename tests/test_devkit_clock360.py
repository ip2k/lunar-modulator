"""The dev kit's 360 MHz / stock-power option: preparation and decision logic, host only.

Nothing here touches a board. The behavioural test runs firmware/devkit/clock360.c
against a simulated SDK (tests/fixtures/clock360/fake_sdk.c); it checks the order
of writes and the fail-closed paths, not the silicon.
"""
import filecmp
import importlib.util
import re
import shutil
import subprocess
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT/'tests/fixtures/clock360'
DAC_STUB = ROOT/'tests/fixtures/renderer_pipeline/dac_sdk_stub'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


helpers = load('prepare_pipeline_tests', ROOT/'tests/test_prepare_pipeline_devkit.py')


def compiler():
    cc = shutil.which('clang')
    if not cc:
        pytest.skip('clang unavailable')
    return cc


@pytest.fixture(scope='module')
def fakes(tmp_path_factory):
    cc = compiler()
    out = tmp_path_factory.mktemp('clock360')
    built = {}
    for baud in (1, 2):
        exe = out/f'fake{baud}'
        subprocess.run([cc, '-std=gnu99', '-Wall', '-Wextra', '-Werror',
                        '-DLUNAR_DEVKIT_SYS_CLK=360000000', '-DLUNAR_DEVKIT_STOCK_POWER=1',
                        f'-DLUNAR_DEVKIT_SFC_BAUD={baud}', '-I'+str(FIXTURES/'sdk_stub'),
                        '-I'+str(ROOT/'firmware/devkit'), str(FIXTURES/'fake_sdk.c'),
                        str(ROOT/'firmware/devkit/clock360.c'), '-o', str(exe)], check=True)
        built[baud] = exe
    return built


def run(fakes, scenario, baud=2):
    text = subprocess.run([str(fakes[baud]), scenario], check=True, capture_output=True, text=True).stdout
    final = dict(re.findall(r'(\w+)=(-?\d+)', next(l for l in text.splitlines() if l.startswith('FAKE result='))))
    return text, {k: int(v) for k, v in final.items()}


KIT_RAILS = dict(sysvdd=11, vdc14=3, vddiom=4, vddiow=0, vlvd=6)
STOCK_RAILS = dict(sysvdd=15, vdc14=7, vddiom=4, vddiow=3, vlvd=7)


def p33_rails(line):
    """Decode a receipt's raw p33=ana_con0,ana_con5,ana_con6,ana_con9,vlvd_con
    bytes with the field map documented in clock360.c."""
    con0, con5, con6, con9, vlvd = (int(v, 16) for v in re.search(r' p33=([0-9a-f,]+) ', line)[1].split(','))
    return dict(sysvdd=con9 & 15, vdc14=con6 & 7, vddiom=con5 & 7, vddiow=(con5 >> 4) & 3,
                vlvd=(vlvd >> 3) & 7, vlvd_en=vlvd & 1, dcdc13=(con0 >> 3) & 1)


def test_pass_raises_rails_before_the_clock_then_slows_sfc_held(fakes):
    text, final = run(fakes, 'pass')
    assert final['result'] == 1 and final['sys'] == 360000000 and final['hsb'] == 180000000
    assert final['sfc'] == 60000000 and final['clock_sets'] == 1
    assert final['critical'] == 0 and final['critical_max'] == 1
    assert {k: final[k] for k in STOCK_RAILS} == STOCK_RAILS
    assert 'FAKE system_clock_set 360000000 rails_set_before=5' in text
    assert 'FAKE sfc_flash_baud_div 2 held=1' in text
    assert text.index('system_clock_set 360000000') < text.index('sfc_flash_baud_div 2')
    after = receipt(text, 'after')
    for field in ('after=PASS', 'sys=360000000', 'hsb=180000000', 'lsb=60000000', 'sfc=60000000',
                  'baud=2', 'tick=2400311', 'rc=0'):
        assert field in after.split()
    assert p33_rails(after) == dict(STOCK_RAILS, vlvd_en=1, dcdc13=1)
    before = receipt(text, 'before')
    assert 'before=-' in before.split() and 'baud=1' in before.split()
    assert p33_rails(before) == dict(KIT_RAILS, vlvd_en=1, dcdc13=1)
    # The end-of-run readback repeats the after line's clocks, BAUD and rails.
    end = receipt(text, 'end')
    assert end.replace('end=-', 'after=PASS') == after
    assert 'FAIL' not in text.split('LUNAR_CLOCK360 audio')[0]
    assert 'restored=' not in text and 'reason=' not in text


def receipt(text, phase):
    found = [l for l in text.splitlines() if l.startswith(f'LUNAR_CLOCK360 {phase}=')]
    assert len(found) == 1, (phase, text)
    return found[0]


def test_end_readback_catches_an_sdk_path_that_moved_the_sfc_baud(fakes):
    text, final = run(fakes, 'end_drift')
    assert final['result'] == 1 and final['sfc'] == 90000000
    end = receipt(text, 'end')
    for field in ('end=-', 'sys=360000000', 'sfc=90000000', 'baud=1'):
        assert field in end.split()


def test_sfc_90_keeps_the_sdk_baud_and_takes_no_critical_section(fakes):
    text, final = run(fakes, 'pass', baud=1)
    assert final['result'] == 1 and final['sfc'] == 90000000 and final['critical_max'] == 0
    assert 'sfc_flash_baud_div' not in text


# Reason numbers as listed in clock360.h: 1 not at 320, 2 PLL source, 6 DCDC off.
@pytest.mark.parametrize('scenario,reason', [('at_240', 1), ('pll_source', 2), ('dcdc_off', 6)])
def test_preconditions_fail_before_any_write(fakes, scenario, reason):
    text, final = run(fakes, scenario)
    assert final['result'] == 0 and final['clock_sets'] == 0 and final['critical_max'] == 0
    assert {k: final[k] for k in KIT_RAILS} == KIT_RAILS
    assert f"LUNAR_CLOCK360 result=FAIL reason={reason}" in text.splitlines() and text.count("reason=") == 1
    assert 'after=' not in text and 'end=' not in text


def test_rail_readback_failure_restores_rails_and_never_touches_the_clock(fakes):
    text, final = run(fakes, 'rail_stuck')
    assert final['result'] == 0 and final['clock_sets'] == 0
    assert {k: final[k] for k in KIT_RAILS} == KIT_RAILS
    assert 'LUNAR_CLOCK360 result=FAIL reason=7' in text.splitlines()
    assert 'after=' not in text and 'restored=' not in text


# refuse: the switch is refused and the clock never moved. moved: refused,
# but the clock moved anyway, so the module puts it back first.
@pytest.mark.parametrize('scenario,clock_sets', [('bad_hsb', 2), ('stale_tick', 2), ('refuse', 1),
                                                 ('moved', 2)])
def test_readback_failure_goes_back_to_320_then_lowers_rails(fakes, scenario, clock_sets):
    text, final = run(fakes, scenario)
    assert final['result'] == 0 and final['clock_sets'] == clock_sets
    assert final['sys'] == 320000000 and final['hsb'] == 160000000 and final['critical'] == 0
    assert {k: final[k] for k in KIT_RAILS} == KIT_RAILS
    assert 'after=FAIL' in receipt(text, 'after').split()
    restored = receipt(text, 'restored')
    assert restored.startswith('LUNAR_CLOCK360 restored=OK rails=kit sys=320000000 hsb=160000000 ')
    assert p33_rails(restored) == dict(KIT_RAILS, vlvd_en=1, dcdc13=1)
    assert text.count('reason=') == 1 and 'LUNAR_CLOCK360 result=FAIL reason=8' in text.splitlines()
    assert 'end=' not in text
    if clock_sets == 2:
        # The rails stay up until the clock is back down.
        assert 'FAKE system_clock_set 320000000 rails_set_before=5' in text


# restore_refuse: the switch worked, a readback failed, and the SDK refused the
# way back. moved_stuck: the switch was refused but moved the clock, and the
# way back was refused. Either way the core is still fast, so the stock rails
# stay (never undervolt a 360 MHz core) and audio stays halted.
@pytest.mark.parametrize('scenario', ['restore_refuse', 'moved_stuck'])
def test_clock_not_back_keeps_the_stock_rails(fakes, scenario):
    text, final = run(fakes, scenario)
    assert final['result'] == 0 and final['clock_sets'] == 2 and final['critical'] == 0
    assert final['sys'] == 360000000 and final['sysvdd'] == 15
    assert {k: final[k] for k in STOCK_RAILS} == STOCK_RAILS
    restored = receipt(text, 'restored')
    assert restored.startswith('LUNAR_CLOCK360 restored=FAIL rails=kept sys=360000000 ')
    assert 'rc=-22' in restored.split()
    assert p33_rails(restored) == dict(STOCK_RAILS, vlvd_en=1, dcdc13=1)
    assert text.count('reason=') == 1 and 'LUNAR_CLOCK360 result=FAIL reason=9' in text.splitlines()


def test_audio_rate_gate(fakes):
    text, _ = run(fakes, 'pass')
    assert 'LUNAR_CLOCK360 audio=preroll cb=10000 t4=348299319 rate_mhz=44100000 result=PASS' in text
    assert 'audio=preroll cb=10000 t4=309602515 rate_mhz=49612000 result=FAIL' in text


def test_module_refuses_other_clocks():
    cc = compiler()
    for flags, message in ((['-DLUNAR_DEVKIT_SYS_CLK=400000000'], 'Only the FM-1'),
                           ([], 'needs LUNAR_DEVKIT_SYS_CLK'),
                           (['-DLUNAR_DEVKIT_SYS_CLK=360000000', '-DLUNAR_DEVKIT_SFC_BAUD=0'], 'BAUD 1')):
        result = subprocess.run([cc, '-std=gnu99', '-fsyntax-only', *flags, '-I'+str(FIXTURES/'sdk_stub'),
                                 '-I'+str(ROOT/'firmware/devkit'), str(ROOT/'firmware/devkit/clock360.c')],
                                capture_output=True, text=True)
        assert result.returncode != 0 and message in result.stderr


def prepare(tmp_path, monkeypatch, name, **options):
    module = helpers.load_prepare()
    base = tmp_path/name
    base.mkdir()
    sdk, correction = helpers.sdk_fixture(base)
    monkeypatch.setattr(module, 'ORIGINAL_SYSTEM_SHA256', module.sha256(sdk/module.SYSTEM))
    monkeypatch.setattr(module, 'PIPELINE_SYSTEM_SHA256', module.sha256(correction))
    out = base/'prepared'
    module.prepare_pipeline(sdk, ROOT, out, correction, False, 3, False, 'cap8', True,
                            poly47_at_44100=True, **options)
    return module, out


def differing(a, b):
    """Relative paths whose bytes differ, or that exist on one side only. Each
    tree's own location (the Makefile's -I and the receipt name it) is masked."""
    def body(root, name):
        return (root/name).read_bytes().replace(str(root.parent).encode(), b'<BASE>')
    names = {p.relative_to(a) for p in a.rglob('*') if p.is_file()} | \
            {p.relative_to(b) for p in b.rglob('*') if p.is_file()}
    return {str(n) for n in names
            if not (a/n).is_file() or not (b/n).is_file() or
            (not filecmp.cmp(a/n, b/n, shallow=False) and body(a, n) != body(b, n))}


APP = 'apps/demo/demo_hello'
DAC = 'lunar-source/firmware/devkit/renderer_pipeline_dac.c'


def test_off_is_the_320_build_unchanged(tmp_path, monkeypatch):
    module, default = prepare(tmp_path, monkeypatch, 'default')
    _, explicit = prepare(tmp_path, monkeypatch, 'explicit', sys_clk=320, stock_power=False, sfc_mhz=60)
    # The receipt differs only by the Makefile's hash, and the Makefile only by
    # the tree's own -I path (masked by differing()).
    assert differing(default, explicit) <= {'lunar-devkit-input.json'}
    receipts = [module.json.loads((tree/'lunar-devkit-input.json').read_text()) for tree in (default, explicit)]
    for receipt in receipts:
        receipt.pop('prepared_board_makefile_sha256')
    assert receipts[0] == receipts[1]
    app = default/APP
    assert not (app/'clock360.c').exists() and not (app/'clock360.h').exists()
    assert (app/'sdk_worker.c').read_bytes() == (ROOT/'firmware/devkit/sdk_worker.c').read_bytes()
    assert (default/DAC).read_bytes() == (ROOT/'firmware/devkit/renderer_pipeline_dac.c').read_bytes()
    makefile = (app/'board/wl82/Makefile').read_text()
    assert 'LUNAR_DEVKIT_SYS_CLK' not in makefile and 'clock360' not in makefile
    receipt = module.json.loads((default/'lunar-devkit-input.json').read_text())
    for key in ('sys_clk_hz', 'stock_power', 'sfc_hz', 'clock_switch', 'prepared_sdk_worker_sha256'):
        assert key not in receipt


@pytest.mark.parametrize('sfc_mhz,baud', [(60, 2), (90, 1)])
def test_on_changes_only_the_clock_files(tmp_path, monkeypatch, sfc_mhz, baud):
    module, off = prepare(tmp_path, monkeypatch, 'off')
    _, on = prepare(tmp_path, monkeypatch, 'on', sys_clk=360, stock_power=True, sfc_mhz=sfc_mhz)
    assert differing(off, on) == {f'{APP}/clock360.c', f'{APP}/clock360.h', f'{APP}/sdk_worker.c',
                                  f'{APP}/board/wl82/Makefile', DAC, 'lunar-devkit-input.json'}
    app = on/APP
    for name in ('clock360.c', 'clock360.h'):
        assert (app/name).read_bytes() == (ROOT/'firmware/devkit'/name).read_bytes()
    makefile = (app/'board/wl82/Makefile').read_text()
    assert (f'CFLAGS += -DLUNAR_DEVKIT_SYS_CLK=360000000 -DLUNAR_DEVKIT_STOCK_POWER=1 '
            f'-DLUNAR_DEVKIT_SFC_BAUD={baud}\n') in makefile
    assert 'c_SRC_FILES := \\\n\t../../../../../apps/demo/demo_hello/clock360.c \\\n' in makefile
    worker = (app/'sdk_worker.c').read_text()
    assert '#include "clock360.h"' in worker
    call = worker.index('if (!lunar_clock360_apply(now))')
    # After the 2 s recovery window, before the arithmetic probe and the DAC.
    assert worker.rindex('os_time_dly(200);', 0, call) < call
    assert call < worker.index('#if defined(LUNAR_DEVKIT_RENDERER_TIMING) || defined(LUNAR_DEVKIT_RENDERER_PIPELINE_DAC)',
                               call)
    assert worker.index('JL_TIMER4->CON = 9u;') < call
    dac = (on/DAC).read_text()
    assert dac.count('lunar_clock360_audio_rate(') == 1 and dac.count('clock360_snap(&') == 2
    # A failed preroll window is a transport fault, caught by the driver's own
    # check before the music starts; no new failure exit.
    preroll = dac.index('task_fault103(36001);')
    assert dac.index('preroll_ms=timer_get_ms()-pre;') < preroll
    assert preroll < dac.index('if(transport.fault||lunar_pipeline_error())return v110_failure(__LINE__);', preroll) \
        < dac.index('preroll_phase=PRE_ARM;')
    assert dac.count('return v110_failure(') == (ROOT/'firmware/devkit/renderer_pipeline_dac.c').read_text().count('return v110_failure(')
    # The end-of-run readback: in the worker, once, right after the DAC run
    # returns and before its completion line; none in the driver.
    assert 'lunar_clock360_end' not in dac and worker.count('lunar_clock360_end(') == 1
    assert worker.index('    int complete = lunar_pipeline_dac_run(now);\n    lunar_clock360_end(now);\n'
                        '    printf("LUNAR_DEVKIT complete=') > call
    receipt = module.json.loads((on/'lunar-devkit-input.json').read_text())
    assert receipt['sys_clk_hz'] == 360000000 and receipt['hsb_hz'] == 180000000
    assert receipt['lsb_hz'] == 60000000 and receipt['sfc_hz'] == sfc_mhz*1000000
    assert receipt['sfc_baud'] == baud and receipt['stock_power'] is True
    assert receipt['stock_power_levels']['sysvdd'] == '1.38 V'
    assert receipt['prepared_sdk_worker_sha256'] == module.sha256(app/'sdk_worker.c')
    assert receipt['prepared_renderer_pipeline_dac_sha256'] == module.sha256(on/DAC)
    assert not receipt['hardware_acceptance']


def test_transformed_dac_compiles_and_reapplication_is_refused(tmp_path, monkeypatch):
    cc = compiler()
    module, on = prepare(tmp_path, monkeypatch, 'on', sys_clk=360, stock_power=True)
    subprocess.run([cc, '-std=gnu99', '-Wall', '-Wextra', '-Werror', '-Wno-unknown-pragmas', '-fsyntax-only',
                    '-DLUNAR_DEVKIT_RENDERER_PIPELINE=1', '-DFM1_APP_RENDER_PIPELINE=1',
                    '-DLUNAR_DEVKIT_RENDERER_PIPELINE_DAC=1', '-DLUNAR_RENDERER_POLICY_CAP8=1',
                    '-DLUNAR_PIPELINE_WORST_BLOCK=1', '-DFM1_APP_PIPELINE_MARKS=1',
                    '-I'+str(DAC_STUB), '-I'+str(ROOT/'firmware/devkit'), '-I'+str(ROOT/'engines/include'),
                    '-I'+str(ROOT/'engines/mod'), '-I'+str(ROOT/'sim/web/src'), str(on/DAC)], check=True)
    with pytest.raises(ValueError, match='already prepared'):
        module.clock360_dac((on/DAC).read_text())
    with pytest.raises(ValueError, match='anchor'):
        module.clock360_worker((on/APP/'sdk_worker.c').read_text())


@pytest.mark.parametrize('options,message', [
    (dict(sys_clk=400), '320 or 360'),
    (dict(sys_clk=360), 'needs --stock-power'),
    (dict(stock_power=True), 'only with --sys-clk 360'),
    (dict(sfc_mhz=90), '360 MHz choice'),
    (dict(sys_clk=360, stock_power=True, sfc_mhz=80), '360 MHz choice'),
])
def test_bad_clock_options_refused_before_sdk_access(tmp_path, options, message):
    with pytest.raises(ValueError, match=message):
        helpers.load_prepare().prepare_pipeline(tmp_path/'missing', ROOT, tmp_path/'out', tmp_path/'missing.a',
                                                **options)
    assert not (tmp_path/'out').exists()


def test_the_result_parser_reads_the_module_s_own_receipts(fakes):
    # The fake's real printf output, joined to a DAC receipt set, passes the
    # parser's 360 MHz gates; its end-drift and restore paths are refused.
    import importlib.util
    spec = importlib.util.spec_from_file_location('pipeline_worst', ROOT/'tests/test_devkit_pipeline_worst.py')
    worst = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(worst)
    preroll = 'LUNAR_CLOCK360 audio=preroll cb=200 t4=6966000 rate_mhz=44100000 result=PASS\n'

    def receipts(scenario):
        text, _ = run(fakes, scenario)
        return '\n'.join(l for l in text.splitlines()
                         if l.startswith('LUNAR_CLOCK360 ') and ' audio=' not in l) + '\n' + preroll
    parsed = worst.result_parser.parse(receipts('pass') + worst.dac_receipts(), 360)
    assert parsed['clock360']['after']['sfc'] == 60000000 and parsed['clock360']['before']['baud'] == 1
    for scenario, message in (('end_drift', 'SFC clock'), ('refuse', 'failed'),
                              ('restore_refuse', 'failed')):
        with pytest.raises(ValueError, match=message):
            worst.result_parser.parse(receipts(scenario) + worst.dac_receipts(), 360)
