"""Worst-block recorder, policy receipts and their parser; no target timing claim."""
# Keep the ASan leak-detection default: enabled on Linux, unsupported on macOS.
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT/'tests/fixtures/renderer_pipeline'
spec = importlib.util.spec_from_file_location('pipeline_result', ROOT/'tools/devkit_pipeline_result.py')
result_parser = importlib.util.module_from_spec(spec)
spec.loader.exec_module(result_parser)

PIPELINE = ['-DLUNAR_DEVKIT_RENDERER_PIPELINE=1', '-DFM1_APP_RENDER_PIPELINE=1',
            '-DLUNAR_DEVKIT_RENDERER_PIPELINE_DAC=1']
WORST = ['-DLUNAR_PIPELINE_WORST_BLOCK=1', '-DFM1_APP_PIPELINE_MARKS=1']
CAP8 = ['-DLUNAR_RENDERER_POLICY_CAP8=1']


def dac_receipts(p_max=(33463, 36000, 37367, 40000), policy='cap8', voices=8):
    lines = ['[00:03:20.001]LUNAR_DAC103 end=1 produced=66156 harvested=66156 submitted=66156 callbacks=66220 '
             'drain=64 fault=0 backend=0 off=-1 close=-1 cb_max=900 irq_max=1200 gap_max=36000 late=0 gaps=0 '
             'ready_min=3 parent_unused=900']
    for c in range(4):
        lines.append(f'LUNAR_DAC103_CASE case={c} blocks=16539 hash=0a1b2c3{c} p_mean=23779 p_max={p_max[c]} '
                     f'p_late=0 c_mean=31522 c_max=33088 c_late=0')
    lines += ['LUNAR_LATE146 count=0 overflow=0',
              f'LUNAR_POLYPHONY fixed={voices} adaptive=0 policy={policy}',
              f'LUNAR_POLYPHONY fixed={voices} adaptive=0 policy={policy} unit0_active=0 '
              f'unit0_limit={voices} unit0_retired=0 unit0_stolen=46',
              'LUNAR_PIPELINE_SOAK cases=12 expected_cases=12 cycles=3 total=66156 elapsed_ms=190000 '
              'fold=deadbeef replay_required=1']
    return '\n'.join(lines) + '\n'


def compiler():
    cc = shutil.which('clang')
    if not cc:
        pytest.skip('clang unavailable')
    return cc


@pytest.mark.parametrize('sanitize', [False, True])
def test_recorder_selection_wrap_faults_and_report(tmp_path, sanitize):
    cc = compiler()
    flags = ['-fsanitize=address,undefined', '-fno-omit-frame-pointer'] if sanitize else []
    exe = tmp_path/'worst'
    subprocess.run([cc, '-std=c99', '-O2', '-g', '-Wall', '-Wextra', '-Werror', *flags,
                    '-I'+str(ROOT/'firmware/devkit'), str(FIXTURES/'worst_block.c'), '-o', str(exe)], check=True)
    out = subprocess.run([str(exe)], check=True, capture_output=True, text=True, timeout=30,
                         env=dict(os.environ, ASAN_OPTIONS='halt_on_error=1', UBSAN_OPTIONS='halt_on_error=1')).stdout
    assert out.count('LUNAR_WORST_BLOCK ') == 4 and out.count('LUNAR_WORST_CONSUMER ') == 4
    assert 'incomplete=1 misordered=1 unmatched=1 record_bytes=256' in out
    # The fixture's synthetic report is a well-formed receipt set; its incomplete
    # cases are reported as such. Join it to DAC receipts whose p_max agree.
    with pytest.raises(ValueError, match='p_max'):
        result_parser.parse(dac_receipts() + out)
    parsed = result_parser.parse(dac_receipts(p_max=(40000, 30000, 27000, 26000)) + out)
    blocks = parsed['worst_block']['blocks']
    assert [b['complete'] for b in blocks] == [True, True, False, False]
    assert blocks[0]['largest_stage'] == 'dispatch' and blocks[0]['c_ticks'] == 32000
    assert blocks[0]['stages_ticks']['capture'] == 15000 and blocks[0]['tag'] == 2
    assert blocks[1]['p_ticks'] == 30000 and sum(blocks[1]['stages_ticks'].values()) == 30000
    assert blocks[2]['c_ticks'] == 30000 and blocks[3]['c_ticks'] is None
    assert parsed['worst_block']['faults'] == 3
    assert parsed['worst_block']['overhead_per_block_ticks'] == 10
    assert parsed['policy'] == 'cap8'


def worst_lines(p_max=(33463, 36000, 37367, 40000)):
    lines = ['LUNAR_WORST_OVERHEAD reps=256 mark_ticks=40 observe_ticks=8 marks=6']
    for c in range(4):
        stages = [120, 40, 300, p_max[c] - 120 - 40 - 300 - 3000 - 500 - 2000, 3000, 500, 2000]
        names = ' '.join(f'{n}={v}' for n, v in zip(result_parser.STAGES, stages))
        lines.append(f'LUNAR_WORST_BLOCK case={c} valid=1 complete=1 tag={c * 5513 + 7} p_ticks={p_max[c]} '
                     f'c_ticks=32000 c_seen=1 ready=6 {names}')
        lines.append(f'LUNAR_WORST_CONSUMER case={c} seen=1 tag={c * 5513 + 9} c_ticks=33088')
    lines.append('LUNAR_WORST_SUMMARY marks=6 stages=7 blocks=66156 incomplete=0 misordered=0 unmatched=0 '
                 'record_bytes=256 reps=256 overhead_mark_ticks=40 overhead_observe_ticks=8')
    return '\n'.join(lines) + '\n'


def test_parser_reads_a_full_run():
    parsed = result_parser.parse((dac_receipts() + worst_lines()).encode())
    assert parsed['policy'] == 'cap8'
    assert parsed['cases'][3]['p_max_pct'] == round(100 * 40000 / 34829, 1)
    assert parsed['cases'][0]['hash'] == '0a1b2c30'
    w = parsed['worst_block']
    assert w['overhead_per_block_ticks'] == 48 and w['overhead_per_block_us'] == 2.0
    assert w['blocks'][3]['largest_stage'] == 'dispatch' and not w['faults']
    assert w['consumer'][2] == dict(case=2, tag=11035, c_ticks=33088)
    assert 'separate gates' in parsed['acceptance']


def test_parser_reads_the_v225_fixed12_format_without_recorder():
    old = dac_receipts(policy='fixed12', voices=12)
    old = old.replace(' policy=fixed12 unit0_active=0 unit0_limit=12 unit0_retired=0 unit0_stolen=46', '')
    old = old.replace(' policy=fixed12', '')
    parsed = result_parser.parse(old)
    assert parsed['policy'] == 'fixed12' and 'worst_block' not in parsed


@pytest.mark.parametrize('before,after,message', [
    ('policy=cap8', 'policy=fixed12', 'Inconsistent'),
    ('fixed=8 adaptive=0 policy=cap8\n', 'fixed=12 adaptive=0 policy=cap8\n', 'Inconsistent|disagree'),
    ('unit0_limit=8', 'unit0_limit=12', 'limit'),
    ('LUNAR_DAC103_CASE case=3', 'LUNAR_DAC103_CASE case=2', 'once each'),
    ('hash=0a1b2c30', 'hash=xyz', 'hex'),
    ('LUNAR_LATE146 count=0 overflow=0\n', '', 'LATE146'),
    ('ui=2000', 'ui=2001', 'sum'),
    ('LUNAR_WORST_BLOCK case=1 valid=1', 'LUNAR_WORST_BLOCK case=1 valid=0', 'missing'),
    ('marks=6 stages=7', 'marks=5 stages=7', 'layout'),
    ('p_ticks=40000', 'p_ticks=40001', 'p_max|sum'),
    ('LUNAR_WORST_SUMMARY', 'LUNAR_WORST_SUMMARY_GONE', 'SUMMARY'),
    ('drain=64 fault=0', 'drain=64 drain=64 fault=0', 'Duplicate'),
])
def test_parser_refuses_malformed_receipts(before, after, message):
    text = dac_receipts() + worst_lines()
    if before == 'policy=cap8':
        text = text.replace(before, after, 1)
    else:
        assert before in text
        text = text.replace(before, after)
    with pytest.raises(ValueError, match=message):
        result_parser.parse(text)


@pytest.mark.parametrize('extra', [[], CAP8, WORST, CAP8 + WORST])
def test_dac_driver_compiles_for_each_policy(extra):
    cc = compiler()
    subprocess.run([cc, '-std=gnu99', '-Wall', '-Wextra', '-Werror', '-Wno-unknown-pragmas', '-fsyntax-only',
                    *PIPELINE, *extra, '-I'+str(FIXTURES/'dac_sdk_stub'), '-I'+str(ROOT/'firmware/devkit'),
                    '-I'+str(ROOT/'engines/include'), '-I'+str(ROOT/'engines/mod'), '-I'+str(ROOT/'sim/web/src'),
                    str(ROOT/'firmware/devkit/renderer_pipeline_dac.c')], check=True)


@pytest.mark.parametrize('source,extra,message', [
    ('firmware/devkit/renderer_pipeline_dac.c', ['-DLUNAR_PIPELINE_WORST_BLOCK=1'], 'requires the app pipeline stage marks'),
    ('firmware/devkit/renderer_live.c', CAP8 + ['-DLUNAR_PIPELINE_ADAPTIVE_THREE=1', '-DFM1_APP_EXTERNAL_ARENAS=1'],
     'separate policies'),
])
def test_invalid_combinations_refuse_to_build(source, extra, message):
    cc = compiler()
    result = subprocess.run([cc, '-std=gnu99', '-fsyntax-only', '-Wno-unknown-pragmas', *PIPELINE, *extra,
                             '-I'+str(FIXTURES/'dac_sdk_stub'), '-I'+str(ROOT/'firmware/devkit'),
                             '-I'+str(ROOT/'engines/include'), '-I'+str(ROOT/'engines/mod'),
                             '-I'+str(ROOT/'sim/web/src'), str(ROOT/source)], capture_output=True, text=True)
    assert result.returncode != 0 and message in result.stderr


def test_worst_blocks_carry_the_xip_note_and_the_recorder_label():
    w = result_parser.parse(dac_receipts() + worst_lines())['worst_block']
    assert w['blocks'][3]['largest_stage_xip'].startswith('partly mapped: DX7 NoteOn')
    assert set(result_parser.STAGE_XIP) == set(result_parser.STAGES)
    assert 'not with V225' in w['comparison']


def test_parser_accepts_the_cap8_and_fixed12_polyphony_lines():
    # Codex's older parse-v2xx scripts matched 'fixed=12 adaptive=0' only.
    assert result_parser.parse(dac_receipts())['policy'] == 'cap8'
    assert result_parser.parse(dac_receipts(policy='fixed12', voices=12))['policy'] == 'fixed12'


AFTER = ('sys=360000000 hsb=180000000 lsb=60000000 sfc=60000000 uart=48000000 baud=2 con2=6 div=12 '
         'pll=1,2 p33=8,24,4,f,31 tick=2400311 t4=9 rc=0')


def clock360_lines(**change):
    lines = dict(
        before='LUNAR_CLOCK360 before=- sys=320000000 hsb=160000000 lsb=53333333 sfc=80000000 uart=48000000 '
               'baud=1 con2=6 div=11 pll=1,2 p33=8,4,3,b,31 tick=2400100 t4=9 rc=0',
        after='LUNAR_CLOCK360 after=PASS ' + AFTER,
        audio='LUNAR_CLOCK360 audio=preroll cb=200 t4=6966000 rate_mhz=44100000 result=PASS',
        end='LUNAR_CLOCK360 end=PASS ' + AFTER)
    lines.update(change)
    return '\n'.join(v for v in lines.values() if v) + '\n'


def test_parser_gates_a_360_mhz_run():
    text = clock360_lines() + dac_receipts() + worst_lines()
    for sys_clk in (None, 360):
        parsed = result_parser.parse(text, sys_clk)
        assert parsed['clock360']['sfc_hz'] == 60000000 and '90' in parsed['clock360']['note']
        assert parsed['clock360']['end']['baud'] == 2
    # A 320 MHz run is unchanged and has no clock360 entry.
    assert 'clock360' not in result_parser.parse(dac_receipts() + worst_lines(), 320)
    with pytest.raises(ValueError, match='320 MHz run'):
        result_parser.parse(text, 320)
    with pytest.raises(ValueError, match='needs its LUNAR_CLOCK360'):
        result_parser.parse(dac_receipts() + worst_lines(), 360)


@pytest.mark.parametrize('change,message', [
    (dict(after='LUNAR_CLOCK360 after=FAIL ' + AFTER), 'before/after/end'),
    (dict(end=''), 'one LUNAR_CLOCK360 end'),
    (dict(audio=''), 'one LUNAR_CLOCK360 audio'),
    (dict(audio='LUNAR_CLOCK360 audio=preroll cb=200 t4=7800000 rate_mhz=39385000 result=FAIL'), 'failed'),
    (dict(end='LUNAR_CLOCK360 end=FAIL ' + AFTER.replace('baud=2', 'baud=1').replace('sfc=60000000', 'sfc=90000000')),
     'before/after/end'),
    (dict(end='LUNAR_CLOCK360 end=PASS ' + AFTER.replace('baud=2', 'baud=1')), 'BAUD moved'),
    (dict(end='LUNAR_CLOCK360 end=PASS ' + AFTER.replace('sfc=60000000', 'sfc=90000000')), 'SFC clock'),
    (dict(end='LUNAR_CLOCK360 end=PASS ' + AFTER.replace('p33=8,24,4,f,31', 'p33=8,4,3,b,31')), 'rails'),
    (dict(end='LUNAR_CLOCK360 end=PASS ' + AFTER.replace('sys=360000000', 'sys=320000000')), '360/180/60'),
    (dict(restored='LUNAR_CLOCK360 restored=OK rails=kit ' + AFTER, fail='LUNAR_CLOCK360 result=FAIL reason=8'),
     'failed'),
    (dict(fail='LUNAR_CLOCK360 result=FAIL reason=1'), 'failed'),
])
def test_parser_refuses_a_failed_or_incomplete_360_mhz_run(change, message):
    with pytest.raises(ValueError, match=message):
        result_parser.parse(clock360_lines(**change) + dac_receipts() + worst_lines(), 360)


def test_baud_is_only_compared_where_it_reads_back():
    # A write-only register that reads 0 everywhere says nothing.
    zero = clock360_lines(before=clock360_lines().splitlines()[0].replace('baud=1', 'baud=0'),
                          end='LUNAR_CLOCK360 end=PASS ' + AFTER.replace('baud=2', 'baud=0'))
    assert result_parser.parse(zero + dac_receipts(), 360)['clock360']['end']['baud'] == 0
