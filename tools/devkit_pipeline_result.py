#!/usr/bin/env python3
"""Parse a dev-board pipeline DAC run's UART log; never audio acceptance.

Reads the receipts printed by firmware/devkit/renderer_pipeline_dac.c:
LUNAR_DAC103 end/case lines, LUNAR_LATE146, LUNAR_POLYPHONY (policy fixed12
or cap8), LUNAR_PIPELINE_SOAK and, in --worst-block builds, LUNAR_WORST_*.
With a LUNAR_PIPELINE_SOAK line it adds a 'buffered' summary for the owner's
release rule (2026-10-28): the whole run's underrun counters, both cores'
means per case and over the run against 29,604 ticks (85 %), and the queue
latency from the LUNAR_PIPELINE ready line's slots (x 64 frames at 44,100 Hz).
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
refuses it, and the refusal names the clock360.h reason. Since 2026-10-29
every kit build of clock360.c refuses by design (reason 10: the kit boots on a
fixed 320 MHz tap, from which no reviewed switch to 360 MHz exists), so no
360 MHz kit run counts. Such images would run XIP code with the SFC at 60 MHz
(80 MHz at 320, presumably 90 on the FM-1), so their numbers would not be the
FM-1's.
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
# firmware/devkit/clock360.h. 7-9 come only from the host switch model.
CLOCK360_REASONS = {
    1: 'not at 320 MHz / 160 MHz HSB',
    2: 'CLK_CON2[7:0] is not 2, the kit\'s fixed 320 MHz tap (an r2 image: PLL source not 6)',
    3: 'bus dividers not HSB /2, LSB /3', 4: 'OS tick not 10 ms', 5: 'UART clock not 48 MHz',
    6: 'DCDC off', 7: 'a rail did not read back', 8: 'readback failed at 360 MHz, back at 320',
    9: 'readback failed at 360 MHz and the clock did not come back to 320',
    10: 'kit in the analysed state; no reviewed 360 MHz switch from the fixed 320 MHz tap',
}
TIMESTAMP = re.compile(r'^\[\d{2}:\d{2}:\d{2}\.\d{3}\]')
# The owner's buffered release rule (2026-10-28): zero underruns over a
# 30-minute analog soak, both cores' mean <= 85 % of the block budget, the
# worst block explained, the queue latency stated.
RULE_MEAN_TICKS = BUDGET_TICKS * 85 // 100  # 29,604
FRAMES_PER_BLOCK = 64
DAC_RATE_HZ = 44100  # renderer_pipeline_dac.c: dac_set_sample_rate(44100)
DMA_WINDOWS = 3  # the DAC ring the driver checks: DAC_LEN 192 frames
IDLE_QUIET_MS = 250  # zero-idle wait inside elapsed_ms, after the last block


def buffered_rule(end, cases, soak, ready, final_lines):
    """Whole-run summary under the buffered rule; the analog capture is separate.

    The receipts are cumulative over the run, so one end-of-run set covers the
    whole soak. An empty queue at a DAC callback faults the transport (10304)
    and stops the run, so fault=0 with every block submitted means no
    underrun; gaps counts DAC callbacks more than 1.5 blocks apart and late
    those that ran a whole block. A per-block producer or consumer overrun is
    not an underrun while the queue covers it: the firmware's own end check
    still applies the old per-block deadline and prints failure_line and
    complete=0 for it, which this summary reports but does not count.
    """
    total = soak['total']
    blocks = sum(c['blocks'] for c in cases)
    p_mean = sum(c['p_mean'] * c['blocks'] for c in cases) / blocks if blocks else 0
    c_mean = sum(c['c_mean'] * c['blocks'] for c in cases) / blocks if blocks else 0
    underrun_checks = dict(
        fault_zero=end['fault'] == 0, backend_zero=end['backend'] == 0,
        all_blocks_submitted=end['submitted'] == end['produced'] == end['harvested'] == total == blocks,
        all_cases_checked=soak['cases'] == soak['expected_cases'],
        drain_complete=end['drain'] >= 64, dac_gaps_zero=end['gaps'] == 0, dac_late_zero=end['late'] == 0,
        irq_within_block=end['irq_max'] < BUDGET_TICKS, queue_never_empty=end['ready_min'] >= 1)
    mean_checks = {f'case{c["case"]}_{core}': c[f'{core}_mean'] <= RULE_MEAN_TICKS
                   for c in cases for core in ('p', 'c')}
    mean_checks.update(whole_p=p_mean <= RULE_MEAN_TICKS, whole_c=c_mean <= RULE_MEAN_TICKS)
    slots = ready.get('outputs') if ready else None
    audio_s = total * FRAMES_PER_BLOCK / DAC_RATE_HZ
    queue = None
    if slots:
        queue = dict(slots=slots, frames=slots * FRAMES_PER_BLOCK, rate_hz=DAC_RATE_HZ,
                     queue_ms=round(1000.0 * slots * FRAMES_PER_BLOCK / DAC_RATE_HZ, 2),
                     dma_ring_frames=DMA_WINDOWS * FRAMES_PER_BLOCK,
                     queue_plus_ring_ms=round(1000.0 * (slots + DMA_WINDOWS) * FRAMES_PER_BLOCK / DAC_RATE_HZ, 2),
                     min_ready_slots=end['ready_min'],
                     min_margin_ms=round(1000.0 * end['ready_min'] * FRAMES_PER_BLOCK / DAC_RATE_HZ, 2))
    run_ms = soak['elapsed_ms'] - IDLE_QUIET_MS
    lifetime = ready.get('lifetime_ms') if ready else None
    fail_line = [r['failure_line'] for r in final_lines if 'failure_line' in r]
    late_only = bool(fail_line) and all(underrun_checks.values()) and any(c['p_late'] or c['c_late'] for c in cases)
    return dict(
        rule_mean_ticks=RULE_MEAN_TICKS, blocks=total, audio_s=round(audio_s, 1),
        audio_min=round(audio_s / 60, 2), elapsed_ms=soak['elapsed_ms'],
        rate_hz_estimate=round((total + end['drain']) * FRAMES_PER_BLOCK * 1000 / run_ms) if run_ms > 0 else None,
        within_cpu1_lifetime=None if lifetime is None else soak['elapsed_ms'] < lifetime,
        whole_p_mean=round(p_mean), whole_p_mean_pct=pct(p_mean),
        whole_c_mean=round(c_mean), whole_c_mean_pct=pct(c_mean),
        producer_late_blocks=sum(c['p_late'] for c in cases), consumer_late_blocks=sum(c['c_late'] for c in cases),
        underrun_checks=underrun_checks, zero_underruns=all(underrun_checks.values()),
        mean_checks=mean_checks, means_pass=all(mean_checks.values()), queue_latency=queue,
        firmware_failure_line=fail_line[0] if fail_line else None,
        firmware_failure_is_per_block_deadline_only=late_only if fail_line else None,
        soak_30_min=audio_s >= 1800,
        pass_timing=all(underrun_checks.values()) and all(mean_checks.values()) and (not fail_line or late_only),
        pass_soak_receipts=(audio_s >= 1800 and all(underrun_checks.values()) and all(mean_checks.values())
                            and (not fail_line or late_only)),
        note='Receipts only: the KA6 analog capture, the host replay of the case hashes and fold, '
             'and the worst-block explanation remain separate gates')


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
        failed = [r for r in rows if r.get('result') == 'FAIL' and 'reason' in r]
        named = (f"reason {failed[0]['reason']} ({CLOCK360_REASONS.get(failed[0]['reason'], 'unknown')}): "
                 if failed else '')
        raise ValueError('LUNAR_CLOCK360 switch failed: ' + named + str(next(
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

    # The clock receipts first: a refused switch halts before the DAC opens,
    # so its log has no DAC receipts and the reason is the useful refusal.
    clock = clock360(rows('LUNAR_CLOCK360'), sys_clk)
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

    service = []
    for row in cases:
        service.append(dict(case=row['case'], blocks=row['blocks'], hash=row['hash'],
            p_mean=row['p_mean'], p_mean_us=us(row['p_mean']), p_mean_pct=pct(row['p_mean']),
            p_max=row['p_max'], p_max_us=us(row['p_max']), p_max_pct=pct(row['p_max']),
            p_late=row['p_late'], c_mean=row['c_mean'], c_mean_pct=pct(row['c_mean']),
            c_max=row['c_max'], c_max_pct=pct(row['c_max']), c_late=row['c_late']))
    result = dict(policy=policy, end=end, cases=service, late_events=late,
                  late_count=late_count[0], polyphony=poly, soak=soak)
    if soak:
        pipeline = rows('LUNAR_PIPELINE')
        ready = [r for r in pipeline if r.get('ready') == 1]
        if len(ready) > 1:
            raise ValueError('Require at most one LUNAR_PIPELINE ready receipt')
        result['buffered'] = buffered_rule(end, service, soak, ready[0] if ready else None, pipeline)
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
