#!/usr/bin/env python3
"""Parse a dev-board pipeline DAC run's UART log; never audio acceptance.

Reads the receipts printed by firmware/devkit/renderer_pipeline_dac.c:
LUNAR_DAC103 end/case lines, LUNAR_LATE146, LUNAR_POLYPHONY (policy fixed12
or cap8), LUNAR_PIPELINE_SOAK and, in --worst-block builds, LUNAR_WORST_*.
Ticks are the 24 MHz timer: 34,829 ticks (1,451 us) per 64-frame block.

The worst-block vector is each case's maximum producer block split at the
existing stage boundaries. Its stage deltas must sum to p_ticks; the parser
refuses a vector that does not. The recorder's own cost is reported by the
firmware (LUNAR_WORST_OVERHEAD, cache-warm, measured before audio starts).
That cost is inside every p_ticks of a --worst-block image: compare such
images with each other, never directly with V225 or any build without the
recorder.

Images built with --sys-clk 360 (firmware/devkit/clock360.c) also print
LUNAR_CLOCK360 receipts. With --sys-clk 360, or whenever such lines appear, a
run counts only with one before=- line, after=PASS, audio=preroll result=PASS
and an end=- readback after the run that still shows 360/180/60 MHz, the after
line's SFC clock and rails and a 10 ms tick; any result=FAIL or restored= line
refuses it. Those images
run XIP code with the SFC at 60 MHz (80 MHz at 320, presumably 90 on the
FM-1), so their numbers are not the FM-1's.
"""
import argparse
import json
from pathlib import Path
import re

TICKS_PER_US = 24
BUDGET_TICKS = 34829
STAGES = ('controls', 'preflight', 'seq', 'dispatch', 'inserts', 'capture', 'ui')
HEX_FIELDS = ('hash', 'fold')
TICK_RANGE = (2352000, 2424000)  # ten 10 ms OS ticks in TIMER4 counts, -2 %..+1 %
FM1_CLOCKS = dict(sys=360000000, hsb=180000000, lsb=60000000)
# Where each stage's code runs. Only the DX7 note path is placed in XIP by
# name (tools/jieli/prepare-pipeline-devkit.py PIPELINE_XIP); the rest of each
# stage has not been attributed to SRAM or XIP code.
STAGE_XIP = dict(
    dispatch='partly mapped: DX7 NoteOn, Allocate, SetVoiceLimit and EnforceVoiceLimit run from XIP '
             '(PIPELINE_XIP); its other XIP callees are not mapped',
    **{s: 'not mapped' for s in ('controls', 'preflight', 'seq', 'inserts', 'capture', 'ui')})
OVERHEAD_NOTE = ('p_ticks include the recorder (about 6 marks per block plus LTO and register changes); '
                 'compare --worst-block images with each other, not with V225 or recorder-free builds')
SFC_NOTE = ('360 MHz kit images run the SFC at 60 MHz against 80 at 320 and presumably 90 on the FM-1: '
            'XIP code is slower here than on either, so these numbers are not the FM-1\'s')
TIMESTAMP = re.compile(r'^\[\d{2}:\d{2}:\d{2}\.\d{3}\]')


def fields(line):
    pairs = re.findall(r'(\w+)=(\S+)', line)
    values = dict(pairs)
    if len(values) != len(pairs):
        raise ValueError('Duplicate receipt field: ' + line)
    out = {}
    for key, value in values.items():
        if key in HEX_FIELDS:
            if not re.fullmatch(r'[0-9a-f]{8}', value):
                raise ValueError('Malformed hex field: ' + key)
            out[key] = value
        elif re.fullmatch(r'\d+', value):
            out[key] = int(value)
        elif re.fullmatch(r'-\d+', value):
            out[key] = int(value)
        else:
            out[key] = value
    return out


def us(ticks):
    return round(ticks / TICKS_PER_US, 1)


def pct(ticks):
    return round(100.0 * ticks / BUDGET_TICKS, 1)


def by_case(rows, name):
    cases = {}
    for row in rows:
        c = row.get('case')
        if not isinstance(c, int) or not 0 <= c < 4 or c in cases:
            raise ValueError(f'{name}: cases must be 0..3, once each')
        cases[c] = row
    if sorted(cases) != [0, 1, 2, 3]:
        raise ValueError(f'{name}: expected all four cases')
    return [cases[c] for c in range(4)]


def worst_block(row):
    if row.get('valid') != 1:
        raise ValueError('Worst block missing for case %s' % row.get('case'))
    stages = {name: row[name] for name in STAGES if name in row}
    if len(stages) != len(STAGES):
        raise ValueError('Worst block lacks a stage field')
    if row.get('complete') == 1:
        if sum(stages.values()) != row['p_ticks']:
            raise ValueError('Worst block stages do not sum to p_ticks')
    elif any(stages.values()):
        raise ValueError('Incomplete worst block carries stage values')
    largest = max(stages, key=stages.get) if row.get('complete') == 1 else None
    return dict(case=row['case'], tag=row['tag'], complete=row['complete'] == 1,
                p_ticks=row['p_ticks'], p_us=us(row['p_ticks']), p_budget_pct=pct(row['p_ticks']),
                c_ticks=row['c_ticks'] if row.get('c_seen') == 1 else None,
                ready=row['ready'], stages_ticks=stages,
                stages_us={k: us(v) for k, v in stages.items()}, largest_stage=largest)


def clock360(rows, sys_clk):
    """Gate the LUNAR_CLOCK360 receipts; None when a 320 MHz run has none."""
    if not rows:
        if sys_clk == 360:
            raise ValueError('A 360 MHz image needs its LUNAR_CLOCK360 receipts')
        return None
    if sys_clk == 320:
        raise ValueError('LUNAR_CLOCK360 receipts in a 320 MHz run')
    if any(r.get('result') == 'FAIL' or 'restored' in r for r in rows):
        raise ValueError('LUNAR_CLOCK360 switch failed: ' + str(next(
            r for r in rows if r.get('result') == 'FAIL' or 'restored' in r)))

    def phase(name):
        found = [r for r in rows if name in r]
        if len(found) != 1:
            raise ValueError(f'Require exactly one LUNAR_CLOCK360 {name} receipt')
        return found[0]
    before, after, end = phase('before'), phase('after'), phase('end')
    audio = phase('audio')
    if before['before'] != '-' or after['after'] != 'PASS' or end['end'] != '-':
        raise ValueError('LUNAR_CLOCK360 before/after/end not -/PASS/-')
    if audio['audio'] != 'preroll' or audio.get('result') != 'PASS':
        raise ValueError('LUNAR_CLOCK360 audio=preroll did not PASS')
    for row in (after, end):
        if any(row.get(k) != v for k, v in FM1_CLOCKS.items()) or row.get('rc') != 0:
            raise ValueError('LUNAR_CLOCK360 clocks not at 360/180/60 MHz')
    if end.get('sfc') != after.get('sfc') or end.get('p33') != after.get('p33'):
        raise ValueError('LUNAR_CLOCK360 SFC clock or rails moved during the run')
    if not TICK_RANGE[0] <= end.get('tick', 0) <= TICK_RANGE[1]:
        raise ValueError('LUNAR_CLOCK360 OS tick not 10 ms at the end')
    # JL_SFC->BAUD is write-only in WL82.h. Hold the end line to the after
    # line's value only where the before line shows it reads back (1, the
    # kit's boot divider: 160 MHz / 2 = 80); any other read says nothing.
    if before.get('baud') == 1 and end.get('baud') != after.get('baud'):
        raise ValueError('LUNAR_CLOCK360 SFC BAUD moved during the run')
    return dict(before=before, after=after, audio=audio, end=end,
                sfc_hz=after['sfc'], note=SFC_NOTE)


def parse(data, sys_clk=None):
    text = data.decode('ascii', errors='replace') if isinstance(data, bytes) else data
    # The SDK's printf splits a long receipt: each continuation arrives as its
    # own timestamped line starting with a space. Join those onto the receipt.
    lines = []
    for raw in text.splitlines():
        stamp = TIMESTAMP.match(raw)
        body = raw[stamp.end():] if stamp else raw
        if stamp and body.startswith(' ') and lines and lines[-1].startswith('LUNAR_'):
            lines[-1] += ' ' + body.strip()
        else:
            lines.append(body.strip())

    def rows(prefix):
        return [fields(line[len(prefix):]) for line in lines if line.startswith(prefix + ' ')]

    def one(prefix, required=True):
        found = rows(prefix)
        if len(found) > 1 or (required and not found):
            raise ValueError('Require exactly one ' + prefix + ' receipt')
        return found[0] if found else None

    ends = [r for r in rows('LUNAR_DAC103') if r.get('end') == 1]
    if len(ends) != 1:
        raise ValueError('Require exactly one LUNAR_DAC103 end receipt')
    end = ends[0]
    cases = by_case(rows('LUNAR_DAC103_CASE'), 'LUNAR_DAC103_CASE')
    late = [r for r in rows('LUNAR_LATE146') if 'event' in r]
    late_count = [r for r in rows('LUNAR_LATE146') if 'count' in r]
    if len(late_count) != 1:
        raise ValueError('Require exactly one LUNAR_LATE146 count receipt')
    poly = rows('LUNAR_POLYPHONY')
    adaptive = rows('LUNAR_ADAPTIVE')
    policy = None
    if poly:
        named = {r.get('policy', 'fixed12' if r.get('fixed') == 12 else None) for r in poly}
        if len(named) != 1 or None in named:
            raise ValueError('Inconsistent LUNAR_POLYPHONY policy')
        policy = named.pop()
        if {'fixed12': 12, 'cap8': 8}.get(policy) != poly[0].get('fixed'):
            raise ValueError('Policy name and voice count disagree')
        for r in poly:
            if 'unit0_limit' in r and r['unit0_limit'] != poly[0]['fixed']:
                raise ValueError('DX7 limit at the end differs from the policy')
    elif adaptive:
        policy = 'adaptive65/60-floor3'
    else:
        raise ValueError('No polyphony policy receipt')
    soak = one('LUNAR_PIPELINE_SOAK', required=False)
    clock = clock360(rows('LUNAR_CLOCK360'), sys_clk)

    service = []
    for row in cases:
        service.append(dict(case=row['case'], blocks=row['blocks'], hash=row['hash'],
            p_mean=row['p_mean'], p_mean_us=us(row['p_mean']), p_mean_pct=pct(row['p_mean']),
            p_max=row['p_max'], p_max_us=us(row['p_max']), p_max_pct=pct(row['p_max']),
            p_late=row['p_late'], c_mean=row['c_mean'], c_mean_pct=pct(row['c_mean']),
            c_max=row['c_max'], c_max_pct=pct(row['c_max']), c_late=row['c_late']))
    result = dict(policy=policy, end=end, cases=service, late_events=late,
                  late_count=late_count[0], polyphony=poly, soak=soak)
    if clock:
        result['clock360'] = clock

    worst_rows = rows('LUNAR_WORST_BLOCK')
    summary = one('LUNAR_WORST_SUMMARY', required=bool(worst_rows))
    if worst_rows:
        worst = [worst_block(r) for r in by_case(worst_rows, 'LUNAR_WORST_BLOCK')]
        for w in worst:
            w['largest_stage_xip'] = STAGE_XIP.get(w['largest_stage'])
        consumers = by_case(rows('LUNAR_WORST_CONSUMER'), 'LUNAR_WORST_CONSUMER')
        overhead = one('LUNAR_WORST_OVERHEAD', required=False)
        if summary.get('marks') != 6 or summary.get('stages') != len(STAGES):
            raise ValueError('Unexpected worst-block layout')
        for w, s in zip(worst, service):
            if w['p_ticks'] != s['p_max']:
                raise ValueError('Worst block p_ticks differs from the case p_max')
        result['worst_block'] = dict(
            blocks=worst, consumer=[dict(case=r['case'], tag=r['tag'], c_ticks=r['c_ticks'])
                                    for r in consumers if r.get('seen') == 1],
            summary=summary, overhead=overhead,
            overhead_per_block_ticks=(summary['overhead_mark_ticks'] + summary['overhead_observe_ticks']),
            overhead_per_block_us=us(summary['overhead_mark_ticks'] + summary['overhead_observe_ticks']),
            faults=summary['incomplete'] + summary['misordered'] + summary['unmatched'],
            comparison=OVERHEAD_NOTE)
    result['acceptance'] = ('Timing receipts only; PCM replay, the buffered release rule '
                            '(30-min analog soak) and the physical FM-1 remain separate gates')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('capture', type=Path)
    parser.add_argument('--sys-clk', type=int, choices=(320, 360),
                        help='the image\'s clock (its lunar-devkit-input.json); 360 requires the '
                             'LUNAR_CLOCK360 gates, 320 refuses such lines; omitted, the lines decide')
    args = parser.parse_args()
    print(json.dumps(parse(args.capture.read_bytes(), args.sys_clk), indent=2))
