#!/usr/bin/env python3
"""The FM6 engine's built-in voices: 32 DX7-format voices of our own, made
here and written into engines/src/dx7_bank.h as a packed (VMEM) bank.

    python3 tools/dx7_bank.py                 # rewrite engines/src/dx7_bank.h
    python3 tools/dx7_bank.py --check         # exit 1 if the header is stale
    python3 tools/dx7_bank.py --syx FILE.syx  # the bank as a 32-voice SysEx dump
    python3 tools/dx7_bank.py --list          # number, name, algorithm
    python3 tools/dx7_bank.py --test-bank     # rewrite the simulator's test files

Every voice is written from scratch from textbook FM recipes (Chowning's
brass and bells, 1:1 and 1:2 stacks, a 14:1 tine, drawbar ratios on
algorithm 32, a pitch-envelope kick); none is copied from a factory or
third-party cartridge, so the bank is ours to publish under the
repository's MIT licence. Names are descriptive and no longer than the
format's 10 characters.

The helpers below speak the keyboards' own units: rates and levels 0-99,
output level 0-99 (about 0.75 dB a step), ratios as the coarse and fine
values the format stores (coarse 0 is 0.5; fine adds 1 % of the coarse
value a step), detune 0-14 with 7 for none. Operators are listed from the
first to the sixth, as an algorithm chart numbers them; the dump stores the
sixth first.

Also used by tests/test_engines_dx7.py to build voices for the tests (every
algorithm, the LFO, the pitch envelope...) and to pack them as SysEx.
MIT licence, like the rest of this repository.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HEADER = ROOT / "engines" / "src" / "dx7_bank.h"
USER_SLOTS = 32
# The simulator's "Load DX7 patches" tests (sim/web/README.md, "DX7 patches"): the
# test bank as one 32-voice dump, and the same voices as 32 single-voice
# dumps in one file.
TEST_DIR = ROOT / "sim" / "web" / "test" / "dx7"
TEST_BANK = TEST_DIR / "lunar-test-bank.syx"
TEST_VOICES = TEST_DIR / "lunar-test-voices.syx"


@dataclass
class Op:
    """One operator in VCED terms."""
    level: int = 99                      # output level
    ratio: float | None = 1.0            # ratio mode: frequency / note
    fixed: float | None = None           # fixed mode: Hz (1 .. 9,772)
    rates: tuple = (99, 99, 99, 99)
    levels: tuple = (99, 99, 99, 0)
    detune: int = 7
    vel: int = 0                         # key velocity sensitivity 0-7
    rate_scaling: int = 0                # 0-7
    ams: int = 0                         # amplitude modulation sensitivity 0-3
    bp: int = 39                         # break point (39 = C3)
    ld: int = 0                          # left depth
    rd: int = 0                          # right depth
    lc: int = 0                          # curves: 0 -lin, 1 -exp, 2 +exp, 3 +lin
    rc: int = 0


@dataclass
class Voice:
    name: str
    alg: int                             # 1..32
    ops: list                            # operators 1..6
    feedback: int = 0
    pitch_rates: tuple = (99, 99, 99, 99)
    pitch_levels: tuple = (50, 50, 50, 50)
    lfo_speed: int = 35
    lfo_delay: int = 0
    lfo_pmd: int = 0
    lfo_amd: int = 0
    lfo_sync: int = 1
    lfo_wave: int = 0                    # triangle, saw down, saw up, square, sine, S/H
    pms: int = 3
    transpose: int = 24                  # 24 = none
    osc_sync: int = 1
    notes: str = field(default="", compare=False)


def coarse_fine(ratio: float) -> tuple[int, int]:
    """The coarse and fine values nearest a ratio (frequency = coarse' x
    (1 + fine / 100), coarse' = 0.5 for coarse 0)."""
    best = None
    for coarse in range(32):
        base = 0.5 if coarse == 0 else float(coarse)
        for fine in range(100):
            err = abs(base * (1 + fine / 100) / ratio - 1)
            if best is None or err < best[0] - 1e-12:
                best = (err, coarse, fine)
    return best[1], best[2]


def fixed_coarse_fine(hz: float) -> tuple[int, int]:
    """Fixed mode: frequency = 10 ** ((coarse % 4) + fine / 100) Hz."""
    import math
    x = round(100 * math.log10(hz))
    x = max(0, min(399, x))
    return x // 100, x % 100


def vced(v: Voice) -> list[int]:
    """The voice's 155 VCED bytes."""
    assert 1 <= v.alg <= 32 and len(v.ops) == 6 and len(v.name) <= 10, v.name
    out: list[int] = []
    for op in reversed(v.ops):           # the sixth operator first
        if op.fixed is not None:
            mode = 1
            coarse, fine = fixed_coarse_fine(op.fixed)
        else:
            mode = 0
            coarse, fine = coarse_fine(op.ratio)
        out += list(op.rates) + list(op.levels)
        out += [op.bp, op.ld, op.rd, op.lc, op.rc, op.rate_scaling, op.ams, op.vel,
                op.level, mode, coarse, fine, op.detune]
    out += list(v.pitch_rates) + list(v.pitch_levels)
    out += [v.alg - 1, v.feedback, v.osc_sync, v.lfo_speed, v.lfo_delay, v.lfo_pmd, v.lfo_amd,
            v.lfo_sync, v.lfo_wave, v.pms, v.transpose]
    out += [ord(c) for c in v.name.ljust(10)]
    assert len(out) == 155
    limits = ([99] * 8 + [99, 99, 99, 3, 3, 7, 3, 7, 99, 1, 31, 99, 14]) * 6 + \
             [99] * 8 + [31, 7, 1, 99, 99, 99, 99, 1, 5, 7, 48] + [126] * 10
    for i, (b, m) in enumerate(zip(out, limits)):
        assert 0 <= b <= m, (v.name, i, b, m)
    return out


def pack(v: Voice) -> list[int]:
    """The voice's 128 packed (VMEM) bytes."""
    d = vced(v)
    out: list[int] = []
    for k in range(6):
        o = d[21 * k:21 * k + 21]
        out += o[0:11]                                   # rates, levels, BP, LD, RD
        out.append(o[12] << 2 | o[11])                   # RC, LC
        out.append(o[20] << 3 | o[13])                   # detune, rate scaling
        out.append(o[15] << 2 | o[14])                   # KVS, AMS
        out.append(o[16])                                # output level
        out.append(o[18] << 1 | o[17])                   # coarse, mode
        out.append(o[19])                                # fine
    out += d[126:134]                                    # pitch envelope
    out.append(d[134])                                   # algorithm
    out.append(d[136] << 3 | d[135])                     # osc key sync, feedback
    out += d[137:141]                                    # LFO speed, delay, PMD, AMD
    out.append(d[143] << 4 | d[142] << 1 | d[141])       # PMS, wave, sync
    out += d[144:155]                                    # transpose, name
    assert len(out) == 128
    return out


def checksum(data: list[int]) -> int:
    return (128 - (sum(data) & 127)) & 127


def vced_syx(v: Voice, channel: int = 0) -> bytes:
    d = vced(v)
    return bytes([0xF0, 0x43, channel, 0x00, 0x01, 0x1B] + d + [checksum(d), 0xF7])


def vmem_syx(voices: list[Voice], channel: int = 0) -> bytes:
    assert len(voices) == 32
    d = [b for v in voices for b in pack(v)]
    return bytes([0xF0, 0x43, channel, 0x09, 0x20, 0x00] + d + [checksum(d), 0xF7])


# ---------------------------------------------------------------- shapes --
#
# Levels in decibels and modulation as an index: msfa plays a modulator at
# output level 99 (full velocity, no scaling) as +-2 cycles of phase, an
# index of 4 pi, and every output-level or envelope-level step below 99 is
# 0.75 dB (32 of msfa's microsteps; levels 20 and up).

def ol_for(beta: float) -> int:
    """The output level that gives a modulator a peak index of beta (rad)."""
    import math
    return max(0, min(99, round(99 + 20 * math.log10(beta / (4 * math.pi)) / 0.75)))


def lv(db: float) -> int:
    """The envelope level db decibels under level 99 (0 for silence)."""
    return 0 if db is None else max(20, min(99, round(99 - db / 0.75)))


def eg(level, ratio=1.0, attack=99, decay=50, d1=6.0, decay2=40, d2=None, release=60,
       vel=1, rs=1, **kw) -> Op:
    """An operator: attack to the top, `decay` to d1 dB down, `decay2` to
    d2 dB down (None: to silence) where it holds while the key is down,
    `release` to silence."""
    return Op(level=level, ratio=ratio, rates=(attack, decay, decay2, release),
              levels=(99, lv(d1), lv(d2) if d2 is not None else 0, 0), vel=vel,
              rate_scaling=rs, **kw)


def mod(beta, ratio=1.0, **kw) -> Op:
    """A modulator of peak index beta."""
    return eg(ol_for(beta), ratio, **kw)


def silent() -> Op:
    return Op(level=0)


def organ(level, ratio=1.0, **kw) -> Op:
    return Op(level=level, ratio=ratio, rates=(99, 99, 99, 80), levels=(99, 99, 99, 0), **kw)


def pad(level, ratio=1.0, attack=55, release=50, d=3.0, **kw) -> Op:
    return eg(level, ratio, attack=attack, decay=40, d1=d, decay2=30, d2=d, release=release, **kw)


# ---------------------------------------------------------------- voices --

def bank() -> list[Voice]:
    v: list[Voice] = []
    struck = dict(d2=None)                 # rings down while held

    # Keys -----------------------------------------------------------------
    v.append(Voice("TINE EP", 5, feedback=3,
                   notes="1:1 stacks; a 14:1 ping for the tine; brightness with velocity", ops=[
        eg(97, 1.0, decay=34, d1=14, decay2=28, release=62, vel=2, rs=3, detune=8, **struck),
        mod(3.0, 1.0, decay=46, d1=12, decay2=35, d2=40, release=62, vel=6, rs=2),
        eg(88, 1.0, decay=40, d1=20, decay2=32, release=62, vel=3, rs=3, detune=6, **struck),
        mod(0.6, 14.0, decay=72, d1=None, decay2=60, release=70, vel=6, rs=3),
        eg(82, 1.0, decay=36, d1=16, decay2=30, release=62, vel=2, rs=3, **struck),
        mod(1.2, 1.0, decay=50, d1=15, decay2=40, d2=40, release=62, vel=4, rs=2),
    ]))
    v.append(Voice("BARK EP", 5, feedback=5, notes="harder: more index, more velocity", ops=[
        eg(96, 1.0, decay=36, d1=14, decay2=30, release=64, vel=3, rs=3, detune=9, **struck),
        mod(4.5, 1.0, decay=44, d1=12, decay2=36, d2=40, release=64, vel=7, rs=2),
        eg(86, 1.0, decay=42, d1=20, decay2=32, release=64, vel=3, rs=3, detune=5, **struck),
        mod(1.0, 14.0, decay=70, d1=None, decay2=60, release=70, vel=7, rs=3),
        eg(80, 1.0, decay=38, d1=16, decay2=30, release=64, vel=3, rs=3, **struck),
        mod(2.0, 1.0, decay=48, d1=14, decay2=40, d2=40, release=64, vel=6, rs=2),
    ]))
    v.append(Voice("CLAV", 3, feedback=6, notes="two bright 3-operator stacks, plucked", ops=[
        eg(97, 1.0, decay=42, d1=10, decay2=32, release=78, vel=2, rs=3, **struck),
        mod(2.5, 3.0, decay=48, d1=10, decay2=36, d2=30, release=78, vel=5, rs=3),
        mod(1.5, 1.0, decay=50, d1=12, decay2=40, d2=30, release=78, vel=4, rs=3),
        eg(90, 1.0, decay=42, d1=10, decay2=32, release=78, vel=2, rs=3, detune=9, **struck),
        mod(3.0, 1.0, decay=44, d1=8, decay2=36, d2=24, release=78, vel=5, rs=3),
        mod(1.0, 5.0, decay=55, d1=12, decay2=45, d2=36, release=78, vel=4, rs=3),
    ]))
    v.append(Voice("HARPSI", 5, feedback=5, notes="unison and octave plucked, 3:1 and 5:1 bite", ops=[
        eg(95, 1.0, decay=36, d1=12, decay2=30, release=72, vel=1, rs=3, **struck),
        mod(3.5, 3.0, decay=42, d1=10, decay2=34, d2=30, release=72, vel=2, rs=3),
        eg(88, 2.0, decay=38, d1=12, decay2=30, release=72, vel=1, rs=3, detune=9, **struck),
        mod(2.5, 5.0, decay=44, d1=10, decay2=36, d2=30, release=72, vel=2, rs=3),
        eg(84, 1.0, decay=36, d1=12, decay2=30, release=72, vel=1, rs=3, detune=5, **struck),
        mod(2.0, 1.0, decay=42, d1=10, decay2=34, d2=30, release=72, vel=2, rs=3),
    ]))
    v.append(Voice("KOTO", 5, feedback=3, notes="plucked silk: a 3:1 attack that fades to round", ops=[
        eg(98, 1.0, decay=40, d1=14, decay2=32, release=70, vel=3, rs=3, **struck),
        mod(2.5, 3.0, decay=60, d1=24, decay2=40, release=70, vel=6, rs=3, **struck),
        eg(80, 2.0, decay=50, d1=20, decay2=36, release=70, vel=3, rs=3, **struck),
        mod(1.5, 1.0, decay=55, d1=20, decay2=40, release=70, vel=5, rs=3, **struck),
        eg(70, 1.0, decay=40, d1=14, decay2=32, release=70, vel=2, rs=3, detune=9, **struck),
        mod(1.0, 7.0, decay=75, d1=None, decay2=60, release=70, vel=5, rs=3),
    ]))

    # Mallets and bells ----------------------------------------------------
    v.append(Voice("MARIMBA", 5, feedback=0, notes="the fundamental, a quick fourth partial, a knock", ops=[
        eg(98, 1.0, decay=46, d1=20, decay2=40, release=66, vel=2, rs=4, **struck),
        mod(0.6, 1.0, decay=70, d1=None, decay2=60, release=70, vel=4, rs=3),
        eg(80, 4.0, decay=58, d1=24, decay2=50, release=70, vel=3, rs=4, **struck),
        mod(0.4, 1.0, decay=72, d1=None, decay2=60, release=70, vel=4, rs=3),
        eg(68, 10.0, decay=76, d1=None, decay2=70, release=80, vel=3, rs=4),
        silent(),
    ]))
    v.append(Voice("VIBES", 5, feedback=0, lfo_speed=48, lfo_amd=38, lfo_wave=4, lfo_sync=0,
                   notes="a struck bar, its fourth partial, tremolo (AMS on the carriers)", ops=[
        eg(97, 1.0, decay=34, d1=12, decay2=26, release=52, vel=2, rs=2, ams=2, **struck),
        mod(0.5, 4.0, decay=70, d1=None, decay2=60, release=70, vel=5, rs=3),
        eg(80, 4.0, decay=50, d1=20, decay2=40, release=60, vel=3, rs=3, ams=2, **struck),
        mod(0.3, 1.0, decay=60, d1=None, decay2=60, release=70, vel=3, rs=3),
        eg(76, 1.0, decay=36, d1=12, decay2=28, release=52, vel=2, rs=2, detune=9, ams=2, **struck),
        mod(0.6, 10.0, decay=84, d1=None, decay2=70, release=80, vel=4, rs=3),
    ]))
    v.append(Voice("TUBE BELL", 5, feedback=2, notes="Chowning's bell: 1:3.5, long decay", ops=[
        eg(97, 1.0, decay=30, d1=20, decay2=24, release=40, vel=2, rs=1, **struck),
        mod(3.0, 3.5, decay=34, d1=20, decay2=28, release=40, vel=3, rs=1, **struck),
        eg(84, 1.0, decay=28, d1=20, decay2=24, release=40, vel=2, rs=1, detune=10, **struck),
        mod(2.5, 3.5, decay=36, d1=20, decay2=30, release=40, vel=3, rs=1, detune=4, **struck),
        eg(74, 2.0, decay=36, d1=20, decay2=30, release=40, vel=2, rs=1, **struck),
        mod(1.5, 5.3, decay=40, d1=20, decay2=34, release=40, vel=3, rs=1, **struck),
    ]))
    v.append(Voice("GLASS BELL", 7, feedback=0, notes="1:2.76 and 1:1.41: inharmonic shimmer", ops=[
        eg(96, 1.0, decay=30, d1=20, decay2=26, release=44, vel=2, rs=2, **struck),
        mod(2.0, 2.76, decay=34, d1=20, decay2=30, release=44, vel=4, rs=2, **struck),
        eg(86, 2.0, decay=32, d1=20, decay2=28, release=44, vel=2, rs=2, detune=9, **struck),
        mod(1.2, 1.41, decay=40, d1=20, decay2=34, release=44, vel=4, rs=2, **struck),
        mod(0.8, 5.19, decay=48, d1=20, decay2=40, release=44, vel=4, rs=2, **struck),
        silent(),
    ]))
    v.append(Voice("CHIMES", 5, feedback=0, notes="1:1.41 stacks over inharmonic partials", ops=[
        eg(95, 1.0, decay=28, d1=20, decay2=24, release=40, vel=2, rs=1, **struck),
        mod(2.5, 1.41, decay=34, d1=20, decay2=30, release=40, vel=3, rs=1, **struck),
        eg(80, 2.76, decay=32, d1=20, decay2=28, release=40, vel=2, rs=1, **struck),
        mod(1.0, 1.0, decay=40, d1=20, decay2=34, release=40, vel=3, rs=1, **struck),
        eg(74, 5.4, decay=40, d1=20, decay2=34, release=40, vel=2, rs=2, **struck),
        mod(1.5, 1.5, decay=44, d1=20, decay2=38, release=40, vel=3, rs=1, **struck),
    ]))
    v.append(Voice("STEEL DRUM", 5, feedback=0, notes="a 1:2.82 stack ringing over its octave", ops=[
        eg(97, 1.0, decay=40, d1=16, decay2=34, release=58, vel=2, rs=3, **struck),
        mod(1.5, 2.82, decay=50, d1=20, decay2=40, release=58, vel=5, rs=3, **struck),
        eg(82, 2.0, decay=44, d1=18, decay2=36, release=58, vel=3, rs=3, **struck),
        mod(1.0, 1.0, decay=56, d1=24, decay2=44, release=58, vel=4, rs=3, **struck),
        eg(74, 4.0, decay=48, d1=20, decay2=40, release=58, vel=2, rs=3, detune=9, **struck),
        silent(),
    ]))

    # Organs ---------------------------------------------------------------
    v.append(Voice("ORGAN 1", 32, feedback=0, notes="drawbars on algorithm 32: 1/2, 1, 2, 3, 4, 8", ops=[
        organ(94, 1.0), organ(90, 0.5), organ(86, 2.0), organ(80, 3.0), organ(76, 4.0),
        organ(70, 8.0),
    ]))
    v.append(Voice("ORGAN PERC", 32, feedback=2, notes="drawbars and a decaying third-harmonic click", ops=[
        organ(94, 1.0), organ(88, 0.5), organ(84, 2.0),
        eg(88, 3.0, decay=60, d1=None, decay2=60, release=80, vel=0, rs=1),
        organ(74, 4.0), organ(66, 6.0),
    ]))
    v.append(Voice("ROCK ORGAN", 32, feedback=5, lfo_speed=62, lfo_pmd=3, lfo_wave=4, pms=3,
                   notes="drawbars with grit (feedback on 6) and a fast vibrato", ops=[
        organ(94, 1.0), organ(90, 0.5), organ(88, 2.0), organ(80, 3.0), organ(78, 4.0),
        organ(72, 1.0, detune=9),
    ]))

    # Brass, winds ---------------------------------------------------------
    v.append(Voice("BRASS", 22, feedback=6, notes="Chowning's brass: the index follows the level", ops=[
        eg(96, 1.0, attack=72, decay=55, d1=4, decay2=40, d2=6, release=62, vel=1, rs=2),
        mod(3.5, 1.0, attack=66, decay=50, d1=4, decay2=40, d2=8, release=62, vel=3, rs=2),
        eg(90, 1.0, attack=72, decay=55, d1=4, decay2=40, d2=6, release=62, vel=1, rs=2, detune=9),
        eg(90, 1.0, attack=72, decay=55, d1=4, decay2=40, d2=6, release=62, vel=1, rs=2, detune=5),
        eg(84, 2.0, attack=72, decay=55, d1=4, decay2=40, d2=6, release=62, vel=1, rs=2),
        mod(3.0, 1.0, attack=64, decay=48, d1=4, decay2=40, d2=8, release=62, vel=3, rs=2),
    ]))
    v.append(Voice("SOFT BRASS", 22, feedback=4, lfo_speed=30, lfo_delay=60, lfo_pmd=4, lfo_wave=4,
                   notes="slower attack, darker, delayed vibrato", ops=[
        pad(95, 1.0, attack=58, release=55, d=2),
        pad(ol_for(2.0), 1.0, attack=50, release=55, d=6),
        pad(90, 1.0, attack=58, release=55, d=2, detune=9),
        pad(90, 1.0, attack=58, release=55, d=2, detune=5),
        pad(80, 2.0, attack=58, release=55, d=3),
        pad(ol_for(1.6), 1.0, attack=50, release=55, d=6),
    ]))
    v.append(Voice("FLUTE", 16, feedback=7, lfo_speed=34, lfo_delay=55, lfo_pmd=5, lfo_wave=4,
                   notes="nearly pure, a little 2nd harmonic, breath from op6's noise", ops=[
        eg(98, 1.0, attack=76, decay=50, d1=2, decay2=40, d2=3, release=66, vel=1),
        mod(0.7, 1.0, attack=72, decay=50, d1=4, decay2=40, d2=6, release=66, vel=2),
        mod(0.3, 2.0, attack=70, decay=50, d1=4, decay2=40, d2=6, release=66, vel=2),
        silent(),
        mod(0.25, 1.0, attack=80, decay=60, d1=6, decay2=40, d2=10, release=66, vel=2),
        mod(2.0, 3.0, attack=88, decay=70, d1=6, decay2=40, d2=10, release=66, vel=2),
    ]))
    v.append(Voice("CLARINET", 16, feedback=0, lfo_speed=30, lfo_delay=60, lfo_pmd=3, lfo_wave=4,
                   notes="2:1 modulation: odd harmonics", ops=[
        eg(98, 1.0, attack=74, decay=50, d1=2, decay2=40, d2=3, release=66, vel=1),
        mod(1.8, 2.0, attack=70, decay=50, d1=3, decay2=40, d2=5, release=66, vel=3),
        mod(0.4, 1.0, attack=70, decay=50, d1=3, decay2=40, d2=5, release=66, vel=2),
        mod(0.3, 3.0, attack=70, decay=50, d1=3, decay2=40, d2=5, release=66, vel=2),
        mod(0.3, 2.0, attack=70, decay=50, d1=3, decay2=40, d2=5, release=66, vel=2),
        silent(),
    ]))

    # Strings and pads -----------------------------------------------------
    v.append(Voice("STRINGS", 2, feedback=6, lfo_speed=30, lfo_delay=50, lfo_pmd=6, lfo_wave=0,
                   notes="two detuned saw-like stacks, a slow bow, delayed vibrato", ops=[
        pad(95, 1.0, attack=52, release=48, d=2, detune=9),
        pad(ol_for(2.5), 1.0, attack=50, release=48, d=4),
        pad(92, 1.0, attack=52, release=48, d=2, detune=5),
        pad(ol_for(2.0), 1.0, attack=50, release=48, d=4),
        pad(ol_for(0.6), 3.0, attack=48, release=48, d=4),
        pad(ol_for(0.5), 1.0, attack=48, release=48, d=4),
    ]))
    v.append(Voice("WARM PAD", 5, feedback=3, lfo_speed=22, lfo_pmd=4, lfo_wave=4, lfo_sync=0,
                   notes="three soft stacks, one an octave up, one down, slow swell", ops=[
        pad(94, 1.0, attack=46, release=44, d=2, detune=8),
        pad(ol_for(1.2), 1.0, attack=40, release=44, d=4),
        pad(86, 2.0, attack=44, release=44, d=2, detune=6),
        pad(ol_for(0.8), 1.0, attack=40, release=44, d=4),
        pad(90, 0.5, attack=46, release=44, d=2),
        pad(ol_for(1.0), 1.0, attack=40, release=44, d=4),
    ]))
    v.append(Voice("GLASS PAD", 5, feedback=0, lfo_speed=26, lfo_amd=20, lfo_wave=4, lfo_sync=0,
                   notes="inharmonic shimmer over a pad, gentle tremolo", ops=[
        pad(94, 1.0, attack=48, release=46, d=2, ams=1),
        pad(ol_for(1.0), 2.76, attack=40, release=46, d=6),
        pad(84, 2.0, attack=50, release=46, d=2, detune=9, ams=1),
        pad(ol_for(0.8), 1.41, attack=40, release=46, d=6),
        pad(80, 1.0, attack=46, release=46, d=2, detune=5, ams=1),
        pad(ol_for(0.5), 5.0, attack=44, release=46, d=8),
    ]))
    v.append(Voice("SWEEP", 1, feedback=6, lfo_speed=12, lfo_wave=0, lfo_sync=0,
                   notes="modulators swelling and falling back over seconds", ops=[
        pad(96, 1.0, attack=60, release=50, d=2),
        Op(level=ol_for(3.0), ratio=1.0, rates=(30, 20, 25, 50), levels=(99, 60, 80, 0), vel=2),
        pad(90, 1.0, attack=60, release=50, d=2, detune=9),
        Op(level=ol_for(2.5), ratio=2.0, rates=(24, 22, 28, 50), levels=(99, 50, 75, 0), vel=2),
        Op(level=ol_for(1.5), ratio=1.0, rates=(20, 30, 30, 50), levels=(99, 60, 85, 0)),
        Op(level=ol_for(1.5), ratio=1.0, rates=(40, 30, 30, 50), levels=(99, 70, 85, 0)),
    ]))

    # Basses ---------------------------------------------------------------
    v.append(Voice("FM BASS", 5, feedback=5, notes="1:1 with a falling index, a sub octave, a click", ops=[
        eg(97, 1.0, decay=48, d1=4, decay2=40, d2=8, release=72, vel=2, rs=2),
        mod(3.0, 1.0, decay=52, d1=10, decay2=40, d2=14, release=72, vel=5, rs=2),
        eg(86, 0.5, decay=44, d1=4, decay2=40, d2=6, release=72, vel=1, rs=2),
        mod(1.0, 1.0, decay=50, d1=8, decay2=40, d2=12, release=72, vel=3, rs=2),
        eg(80, 1.0, decay=50, d1=6, decay2=40, d2=10, release=72, vel=2, rs=2, detune=9),
        mod(2.0, 3.0, decay=70, d1=None, decay2=60, release=72, vel=5, rs=2),
    ]))
    v.append(Voice("PLUCK BASS", 5, feedback=0, notes="short and round, brighter with velocity", ops=[
        eg(98, 1.0, decay=44, d1=14, decay2=36, release=72, vel=2, rs=2, **struck),
        mod(3.5, 1.0, decay=60, d1=None, decay2=50, release=72, vel=6, rs=2),
        eg(88, 0.5, decay=40, d1=12, decay2=34, release=72, vel=1, rs=2, **struck),
        mod(1.5, 2.0, decay=65, d1=None, decay2=55, release=72, vel=5, rs=2),
        eg(70, 1.0, decay=50, d1=16, decay2=40, release=72, vel=2, rs=2, detune=9, **struck),
        silent(),
    ]))
    v.append(Voice("SAW BASS", 4, feedback=6,
                   notes="algorithm 4's loop (4 back to 6) makes a saw; a 3-operator stack under it", ops=[
        eg(97, 1.0, decay=50, d1=4, decay2=40, d2=8, release=72, vel=1, rs=2),
        mod(1.5, 1.0, decay=60, d1=8, decay2=40, d2=12, release=72, vel=4, rs=2),
        mod(0.8, 2.0, decay=60, d1=8, decay2=40, d2=12, release=72, vel=3, rs=2),
        eg(94, 1.0, decay=52, d1=4, decay2=40, d2=8, release=72, vel=1, rs=2, detune=9),
        mod(2.0, 1.0, decay=56, d1=4, decay2=40, d2=6, release=72, vel=2, rs=2),
        mod(1.5, 1.0, decay=60, d1=4, decay2=40, d2=6, release=72, vel=1, rs=2),
    ]))

    # Leads ----------------------------------------------------------------
    v.append(Voice("SAW LEAD", 1, feedback=7, lfo_speed=36, lfo_delay=45, lfo_pmd=6, lfo_wave=0,
                   notes="a feedback-7 chain: a bright saw, delayed vibrato", ops=[
        eg(98, 1.0, attack=90, decay=55, d1=2, decay2=40, d2=4, release=66, vel=1),
        mod(2.0, 1.0, attack=90, decay=55, d1=4, decay2=40, d2=8, release=66, vel=2),
        eg(95, 1.0, attack=90, decay=55, d1=2, decay2=40, d2=4, release=66, detune=10),
        mod(2.5, 1.0, attack=90, decay=55, d1=4, decay2=40, d2=6, release=66),
        mod(2.0, 1.0, attack=90, decay=55, d1=4, decay2=40, d2=6, release=66),
        mod(2.0, 1.0, attack=90, decay=55, d1=4, decay2=40, d2=6, release=66),
    ]))
    v.append(Voice("SQUARE LD", 16, feedback=0, lfo_speed=36, lfo_delay=45, lfo_pmd=5, lfo_wave=4,
                   notes="2:1 modulation from two operators: hollow, square-like", ops=[
        eg(98, 1.0, attack=90, decay=55, d1=2, decay2=40, d2=3, release=66, vel=1),
        mod(2.0, 2.0, attack=90, decay=55, d1=3, decay2=40, d2=5, release=66, vel=2),
        mod(0.8, 2.0, attack=90, decay=55, d1=3, decay2=40, d2=5, release=66),
        mod(0.8, 2.0, attack=90, decay=55, d1=3, decay2=40, d2=5, release=66),
        mod(0.6, 3.0, attack=90, decay=55, d1=3, decay2=40, d2=5, release=66),
        silent(),
    ]))
    v.append(Voice("SYNC LEAD", 18, feedback=5, notes="a 1.5:1 modulator falling: a sync-like sweep", ops=[
        eg(98, 1.0, attack=92, decay=55, d1=2, decay2=40, d2=4, release=66, vel=1),
        mod(1.5, 1.0, attack=92, decay=40, d1=10, decay2=40, d2=14, release=66, vel=3),
        Op(level=ol_for(4.0), ratio=1.5, rates=(99, 40, 40, 66), levels=(99, 70, 70, 0), vel=4),
        mod(1.0, 2.0, attack=92, decay=55, d1=6, decay2=40, d2=10, release=66),
        mod(0.8, 1.0, attack=92, decay=55, d1=6, decay2=40, d2=10, release=66),
        mod(0.6, 3.0, attack=92, decay=55, d1=6, decay2=40, d2=10, release=66),
    ]))

    # Drums ----------------------------------------------------------------
    v.append(Voice("KICK", 16, feedback=0,
                   pitch_rates=(99, 99, 99, 0), pitch_levels=(50, 50, 50, 82),
                   notes="the pitch envelope drops an octave at the hit; play it low", ops=[
        eg(99, 1.0, decay=52, d1=None, decay2=50, release=70, vel=2),
        mod(1.0, 1.0, decay=80, d1=None, decay2=70, release=70, vel=4),
        mod(0.6, 2.0, decay=86, d1=None, decay2=70, release=70, vel=4),
        silent(),
        mod(0.4, 3.5, decay=90, d1=None, decay2=70, release=70, vel=4),
        silent(),
    ]))
    v.append(Voice("SNARE", 1, feedback=7, notes="a noisy chain (feedback 7) over a short body", ops=[
        eg(96, 1.0, decay=70, d1=None, decay2=60, release=74, vel=2, rs=0),
        mod(1.0, 1.62, decay=78, d1=None, decay2=60, release=74, vel=4, rs=0),
        eg(97, 3.1, decay=64, d1=None, decay2=60, release=70, vel=2, rs=0),
        Op(level=99, ratio=11.3, rates=(99, 66, 50, 70), levels=(99, 0, 0, 0), vel=1),
        Op(level=99, ratio=7.4, rates=(99, 60, 50, 70), levels=(99, 0, 0, 0)),
        Op(level=99, ratio=13.7, rates=(99, 99, 99, 70), levels=(99, 99, 99, 0)),
    ]))
    v.append(Voice("HI-HAT", 1, feedback=7, notes="fixed, inharmonic, noisy and short", ops=[
        Op(level=93, fixed=4200.0, ratio=None, rates=(99, 80, 80, 78), levels=(99, 0, 0, 0), vel=2),
        Op(level=99, fixed=3520.0, ratio=None, rates=(99, 99, 99, 70), levels=(99, 99, 99, 0)),
        Op(level=90, fixed=7300.0, ratio=None, rates=(99, 76, 76, 76), levels=(99, 0, 0, 0), vel=2),
        Op(level=99, fixed=2340.0, ratio=None, rates=(99, 99, 99, 70), levels=(99, 99, 99, 0)),
        Op(level=99, fixed=5700.0, ratio=None, rates=(99, 99, 99, 70), levels=(99, 99, 99, 0)),
        Op(level=99, fixed=8100.0, ratio=None, rates=(99, 99, 99, 70), levels=(99, 99, 99, 0)),
    ]))

    # A reference ----------------------------------------------------------
    v.append(Voice("PURE SINE", 32, feedback=0, notes="one operator alone: a sine at the key", ops=[
        organ(99, 1.0), silent(), silent(), silent(), silent(), silent(),
    ]))

    return v


# ---------------------------------------------------------------- output --

def test_bank() -> list[Voice]:
    """32 plain test voices of our own, LUNAR 01 to LUNAR 32: voice k on
    algorithm k with feedback k mod 8, all six operators sounding at mixed
    ratios and levels, a held envelope and a release, no LFO depth (so a
    voice sounds the same whenever it starts). Only for tests: they are
    meant to be told apart by name and algorithm, not played."""
    ratios = (1.0, 2.0, 1.0, 3.0, 0.5, 1.0)
    voices = []
    for k in range(1, 33):
        ops = [Op(level=88 - 3 * ((i + k) % 4), ratio=ratios[(i + k) % 6], detune=7 + (i + k) % 3 - 1,
                  rates=(95, 50, 35, 60), levels=(99, 90, 80, 0)) for i in range(6)]
        voices.append(Voice(f"LUNAR {k:02d}", k, ops, feedback=k % 8))
    return voices


def header(voices: list[Voice]) -> str:
    names = [x.name.rstrip() for x in voices]
    assert len(set(names)) == len(names), "names must be unique"
    lines = [
        "// dx7_bank.h -- the FM6 engine's built-in voices (engines/src/msfa_dx7.cc).",
        "// Generated by tools/dx7_bank.py from the voices defined there; do not",
        "// edit. Our own voices, MIT licence like the rest of this repository.",
        "",
        "#ifndef FM1_DX7_BANK_H_",
        "#define FM1_DX7_BANK_H_",
        "",
        "#include <stdint.h>",
        "",
        "namespace fm1 {",
        "namespace dx7 {",
        "",
        f"const int kBankSize = {len(voices)};",
        "",
        "// The voices as a VMEM bank stores them, 128 packed bytes each.",
        "const uint8_t kBank[kBankSize][128] = {",
    ]
    for i, x in enumerate(voices):
        p = pack(x)
        lines.append(f"  {{  // {i}: {x.name}, algorithm {x.alg}")
        for k in range(0, 128, 16):
            lines.append("    " + ", ".join(str(b) for b in p[k:k + 16]) + ",")
        lines.append("  },")
    lines += [
        "};",
        "",
        "// The Patch list: the built-in voices, then the user slots.",
        f"const char *const kPatchNames[kBankSize + {USER_SLOTS}] = {{",
    ]
    for k in range(0, len(names), 4):
        lines.append("  " + " ".join(f'"{n}",' for n in names[k:k + 4]))
    for k in range(0, USER_SLOTS, 8):
        lines.append("  " + " ".join(f'"User {n + 1}",' for n in range(k, k + 8)))
    lines += [
        "};",
        "",
        "}  // namespace dx7",
        "}  // namespace fm1",
        "",
        "#endif  // FM1_DX7_BANK_H_",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--check", action="store_true", help="exit 1 if the header is stale")
    ap.add_argument("--syx", type=Path, help="write the bank as a VMEM SysEx dump")
    ap.add_argument("--list", action="store_true", help="list the voices")
    ap.add_argument("--test-bank", action="store_true",
                    help="write the simulator's test files (with --check: compare them)")
    a = ap.parse_args()
    if a.test_bank:
        files = {TEST_BANK: vmem_syx(test_bank()), TEST_VOICES: b"".join(vced_syx(v) for v in test_bank())}
        for path, data in files.items():
            if a.check:
                if not path.exists() or path.read_bytes() != data:
                    print(f"{path} is stale: run tools/dx7_bank.py --test-bank", file=sys.stderr)
                    return 1
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
        return 0
    voices = bank()
    if len(voices) != 32:
        print(f"the bank has {len(voices)} voices, not 32", file=sys.stderr)
        return 1
    text = header(voices)
    if a.list:
        for i, x in enumerate(voices):
            print(f"{i:2} {x.name:10} alg {x.alg:2} fb {x.feedback}  {x.notes}")
    if a.syx:
        a.syx.write_bytes(vmem_syx(voices))
    if a.check:
        if not HEADER.exists() or HEADER.read_text() != text:
            print(f"{HEADER} is stale: run tools/dx7_bank.py", file=sys.stderr)
            return 1
        return 0
    if not a.list and not a.syx:
        HEADER.write_text(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
