"""The modulation kinds of docs/16 stage MG2 (engines/mod/kinds/: Function,
Bounce, Register, Coin, Divide, Burst, Slew, Quantize, Compare, Logic, Calc,
Mix and Filter), through fm1-render --mod and the two C tools:

- fm1-mod-kinds-test: each kind's behaviour, the Filter's frequency response
  and ringing against its analytic transfer function and poles, every kind
  from any memory fill and under random and extreme parameters;
- fm1-mod-mi-ref: the ports of Peaks' bouncing ball, pulse shaper and pulse
  randomizer and of Braids' quantizer against the vendored originals, call
  for call, and Bounce and Burst as kinds against upstream Peaks over the
  same timeline;
- a golden trace per kind (tests/fixtures/mod-golden.json): a hash of every
  tick's parameters, outputs and edges in a scripted patch, with an excerpt;
  FM1_UPDATE_GOLDEN=1 rewrites it;
- byte identity of audio and tick log at host blocks of 1, 7 and 64 frames,
  and across memory fills, with two racks of the new kinds routed into the
  sound, an effect, PITCH and AMP;
- a chain of glue modules entered backwards in the rack arriving in the
  tick a direct cable does (CV and gates), and feedback loops one tick late;
- the kinds' tables: gate inputs named apart from parameters, outputs
  unique; the generated tables current; the vendored originals pinned.
"""
import hashlib
import json
import os
import re
import struct
import subprocess
import sys

import pytest

from tests.engine_helpers import ENGINES, RATE, renderer  # noqa: F401
from tests.test_engines_mod_runtime import listed, run, script, seq_text

ROOT = ENGINES.parent
BUILD = ENGINES / "build"
GOLDEN = ROOT / "tests" / "fixtures" / "mod-golden.json"
MUTABLE = ENGINES / "third_party" / "mutable"
TICK = 32
MG2 = ["function", "bounce", "register", "coin", "divide", "burst", "slew", "quantize",
       "compare", "logic", "calc", "mix", "filter"]


def tool(name):
    res = subprocess.run([str(BUILD / name)], capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    return json.loads(res.stdout)


# ---- the C tools ---------------------------------------------------------------------------------

def test_the_kinds_check_themselves(renderer):
    out = tool("fm1-mod-kinds-test")
    _, kinds = listed(renderer)
    assert out["failed"] == 0 and out["checks"] > 1_000_000
    assert out["filter_responses"] == 135
    assert out["kinds_filled"] == len(kinds) and out["kinds_fuzzed"] == 2 * len(kinds)


def test_the_ports_match_mutable_instruments(renderer):
    out = tool("fm1-mod-mi-ref")
    assert out["failed"] == 0
    assert out["ball_samples"] == 2_880_000 and out["shaper_calls"] == 4_500_000
    assert out["randomizer_calls"] == 4_500_000 and out["quantizer_calls"] == 1_200_000
    assert out["bounce_ticks"] > 40_000 and out["burst_edges"] > 500


def test_mi_tables_are_generated():
    subprocess.run([sys.executable, str(ENGINES / "mod" / "gen_mi_tables.py"), "--check"], check=True)


# The vendored originals the ports are checked against: eurorack 08460a6 and
# stmlib e3bd7c9, unmodified (UPSTREAM.md). SHA-256 over (path, SHA-256).
VENDORED = ["braids/quantizer.cc", "braids/quantizer.h", "braids/quantizer_scales.h",
            "peaks/gate_processor.h", "peaks/modulations/bouncing_ball.h",
            "peaks/pulse_processor/pulse_randomizer.cc", "peaks/pulse_processor/pulse_randomizer.h",
            "peaks/pulse_processor/pulse_shaper.cc", "peaks/pulse_processor/pulse_shaper.h",
            "peaks/resources.cc", "peaks/resources.h", "stmlib/utils/ring_buffer.h"]
VENDORED_DIGEST = "ba29e48fe0bf1bdceea70446d7c73488ce9dcaeceb45100de7a223566f1e5ae0"


def test_vendored_originals_are_pinned_and_mit():
    h = hashlib.sha256()
    for rel in VENDORED:
        data = (MUTABLE / rel).read_bytes()
        assert b"Permission is hereby granted, free of charge" in data, rel
        assert b"General Public" not in data and b"GPL" not in data, rel
        h.update(rel.encode() + b"\0" + hashlib.sha256(data).digest())
    assert h.hexdigest() == VENDORED_DIGEST


def test_kind_ports_are_named_apart(renderer):
    """A script or a UI names a gate input and a parameter in one space
    (`flt1.ping`), so no kind may use a name for both; outputs are unique."""
    _, kinds = listed(renderer)
    for kid, k in kinds.items():
        params = {p["name"].lower() for p in k["params"]} | {p["abbr"].lower() for p in k["params"]}
        gates = [g["name"].lower() for g in k["gates"]]
        outs = [o["name"].lower() for o in k["outs"]]
        assert not set(gates) & params, kid
        assert len(set(gates)) == len(gates) and len(set(outs)) == len(outs), kid
    assert set(MG2) <= set(kinds)


# ---- golden traces ---------------------------------------------------------------------------------

NOTES = ["--note", "0.05:60:100:0.3", "--note", "0.45:67:90:0.2", "--note", "0.7:55:110:0.25"]
SCENES = {
    "function": ("mod 1 function rise=0.3 fall=0.4 shape=0.4 retrig=1\n"
                 "mod 2 function mode=cycle rise=0.2 fall=0.25 shape=-0.6\n"
                 "mod 3 function mode=slew rise=0.45 fall=0.3\n"
                 "mod 4 function mode=ar rise=0.25 fall=0.35 level=0.8\n"
                 "mod 5 lfo rate=0.66 shape=square\n"
                 "slot 1 note > fun3.in\nslot 2 lfo5 > fun2.hold\nslot 3 fun2 > fun1.rise amt=20\n"),
    "bounce": ("mod 1 bounce gravity=0.6 bounce=0.75\nmod 2 bounce gravity=0.3 velocity=0.5 height=0.6\n"
               "mod 3 lfo rate=0.5\nslot 1 lfo3 > bnc2.gravity amt=30\n"),
    "register": ("mod 1 register change=0.5 length=6 slew=0.3\nmod 2 register change=-1 length=5 span=24\n"
                 "mod 3 lfo rate=0.75 shape=square\nslot 1 lfo3 > reg1.clock\nslot 2 lfo3.wrap > reg2.clock\n"
                 "slot 3 trig > reg1.write\n"),
    "coin": ("mod 1 coin prob=0.4\nmod 2 coin prob=0.7 mode=toggle latch=on\nmod 3 lfo rate=0.78 shape=square\n"
             "slot 1 lfo3 > coi1.in\nslot 2 lfo3.wrap > coi2.in\n"),
    "divide": ("mod 1 divide mode1=mult value1=3 swing=0.4\nmod 2 divide mode1=prob fill1=0.5 value2=7 fill2=0.43 "
               "rot2=2 delay=12\nmod 3 lfo rate=0.72 shape=square\n"
               "slot 1 lfo3 > div1.clock\nslot 2 lfo3.wrap > div2.clock\nslot 3 trig > div2.reset\n"),
    "burst": ("mod 1 burst count=4 spacing=0.3 length=0.2 accel=0.5\nmod 2 burst mode=delay count=2 delay=0.35\n"
              "mod 3 burst mode=random repeat=0.7 jitter=0.5 spacing=0.3\nmod 4 lfo rate=0.7 shape=square\n"
              "slot 1 lfo4.wrap > bst3.trig\nslot 2 lfo4 > bst1.clock\n"),
    "slew": ("mod 1 slew up=0.35 down=0.5 spread=0.6\nmod 2 slew type=expo up=0.4 down=0.25 spread=-0.5\n"
             "mod 3 lfo rate=0.68 shape=square\nslot 1 lfo3 > slw1.in\nslot 2 lfo3 > slw2.in amt=70\n"
             "slot 3 key > slw2.thru\n"),
    "quantize": ("mod 1 quantize scale=dorian root=d\nmod 2 quantize scale=pentamin range=2 trans=5\n"
                 "mod 3 lfo rate=0.6\nslot 1 lfo3 > qnt1.in amt=30\nslot 2 lfo3 > qnt2.in\n"
                 "slot 3 trig > qnt2.clock\n"),
    "compare": ("mod 1 compare thresh=0.2 hyst=0.1\nmod 2 compare mode=window width=0.4\n"
                "mod 3 compare mode=trend thresh=0.02\nmod 4 lfo rate=0.64\nmod 5 lfo rate=0.71 shape=triangle\n"
                "slot 1 lfo4 > cmp1.a\nslot 2 lfo5 > cmp1.b amt=50\nslot 3 lfo4 > cmp2.a\nslot 4 lfo5 > cmp3.a\n"),
    "logic": ("mod 1 logic op=xor\nmod 2 logic op=sr\nmod 3 logic op=d\nmod 4 logic op=toggle\n"
              "mod 5 lfo rate=0.7 shape=square\nmod 6 lfo rate=0.77 shape=square width=0.3\n"
              "slot 1 lfo5 > log1.a\nslot 2 lfo6 > log1.b\nslot 3 lfo5.wrap > log2.a\nslot 4 lfo6.wrap > log2.b\n"
              "slot 5 lfo6 > log3.a\nslot 6 lfo5.wrap > log3.b\nslot 7 lfo6.wrap > log4.a\nslot 8 key > log4.b\n"),
    "calc": ("mod 1 calc op=fade fade=0.3\nmod 2 calc op=slope amount=0.5\nmod 3 calc op=root offset=0.1 snap=semi\n"
             "mod 4 lfo rate=0.6\nmod 5 lfo rate=0.67 shape=2\n"
             "slot 1 lfo4 > clc1.a\nslot 2 lfo5 > clc1.b\nslot 3 lfo4 > clc2.a\nslot 4 lfo5 > clc3.a\n"
             "slot 5 lfo4 > clc1.fade amt=40\n"),
    "mix": ("mod 1 mix gain1=1.5 gain2=-0.5 offset=0.1\nmod 2 lfo rate=0.6\nmod 3 lfo rate=0.69 shape=triangle\n"
            "slot 1 lfo2 > mix1.in1 amt=60\nslot 2 lfo3 > mix1.in2\nslot 3 vel > mix1.in3 amt=40\n"),
    "filter": ("mod 1 filter cutoff=0.45 res=0.95\nmod 2 filter cutoff=0.7 res=0.2 blend=0.75\n"
               "mod 3 filter cutoff=0.3 res=1 strike=0.6\nmod 4 lfo rate=0.66 shape=square\n"
               "slot 1 trig > flt1.ping\nslot 2 lfo4 > flt2.in\nslot 3 lfo4.wrap > flt3.ping\n"
               "slot 4 lfo4 > flt1.cutoff amt=10\n"),
}


def trace(renderer, tmp_path, kid):
    _, _, ticks = run(renderer, tmp_path, ["--engine", "test-sine", "--seconds", "1.0"] + NOTES,
                      mod=SCENES[kid], name=f"golden-{kid}")
    rows = [[t["k"], m["p"], m["v"], m["o"], m["e"]] for t in ticks for m in t["m"] if m["id"] == kid]
    digest = hashlib.sha256(json.dumps(rows, separators=(",", ":")).encode()).hexdigest()
    excerpt = [[r[0], r[1], r[3], r[4]] for r in rows if r[0] % 173 == 0]
    return rows, digest, excerpt


def dump_golden(golden):
    """The fixture, one excerpt row a line."""
    c = lambda x: json.dumps(x, separators=(",", ":"))   # noqa: E731
    lines = ["{", f' "about": {json.dumps(golden["about"])},', ' "kinds": {']
    kinds = sorted(golden["kinds"].items())
    for i, (kid, k) in enumerate(kinds):
        lines.append(f'  "{kid}": {{"ticks": {k["ticks"]}, "sha256": "{k["sha256"]}", "excerpt": [')
        lines += ["   " + c(r) + ("," if j + 1 < len(k["excerpt"]) else "") for j, r in enumerate(k["excerpt"])]
        lines.append("  ]}" + ("," if i + 1 < len(kinds) else ""))
    lines += [" }", "}", ""]
    return "\n".join(lines)


def test_golden_traces_cover_every_new_kind():
    assert sorted(SCENES) == sorted(MG2)


@pytest.mark.parametrize("kid", MG2)
def test_golden_trace(renderer, tmp_path, kid):
    """Every tick of a scripted patch, hashed: a change to what a kind does
    shows here (regenerate with FM1_UPDATE_GOLDEN=1 when it is meant). The
    traces are the same on macOS arm64 clang, Linux x86-64 gcc, gcc -m32
    and the sanitizer build (-ffp-contract=off, no libm)."""
    rows, digest, excerpt = trace(renderer, tmp_path, kid)
    assert len(rows) > 1000
    golden = json.loads(GOLDEN.read_text()) if GOLDEN.exists() else {"kinds": {}}
    if os.environ.get("FM1_UPDATE_GOLDEN") == "1":
        golden.setdefault("about", "Per-kind golden traces of the modulation kinds (tests/"
                          "test_engines_mod_kinds.py): the SHA-256 of every tick's [k, position, "
                          "parameters, outputs, edges] in a scripted patch, and every 173rd tick's "
                          "outputs and edges for diagnosis. Regenerate with FM1_UPDATE_GOLDEN=1 when a change is meant.")
        golden["kinds"][kid] = {"ticks": len(rows), "sha256": digest, "excerpt": excerpt}
        GOLDEN.write_text(dump_golden(golden))
        return
    want = golden["kinds"][kid]
    assert [r[:3] for r in excerpt] == [r[:3] for r in want["excerpt"]]
    assert excerpt == want["excerpt"]
    assert (len(rows), digest) == (want["ticks"], want["sha256"])


# ---- block sizes and fills --------------------------------------------------------------------------

RACK_A = """seed 5
mod 1 function rise=0.25 fall=0.35 shape=0.3
mod 2 divide value1=2 mode2=euclid value2=5 fill2=0.4
mod 3 burst count=3 spacing=0.25 length=0.15
mod 4 bounce gravity=0.6 bounce=0.7
mod 5 filter cutoff=0.55 res=0.85
mod 6 quantize scale=dorian range=1
mod 7 register change=0.6 length=8
mod 8 slew up=0.4 down=0.2 type=expo spread=0.5
slot 1 fun1 > snd:Timbre amt=30
slot 2 div2.out1 > fun1.trig
slot 3 bst3 > flt5.ping
slot 4 flt5.bp > snd:Morph amt=40
slot 5 bnc4 > fx1:Gain amt=25
slot 6 reg7.cv > qnt6.in amt=50
slot 7 qnt6.pitch > host:pitch amt=50
slot 8 seq2 > bst3.trig
slot 9 reg7.bit > slw8.thru
slot 10 bnc4.hit > div2.reset
slot 11 slw8.out3 > snd:Harmonics amt=-20
slot 12 fun1.eoc > bnc4.trig
slot 13 flt5.lp > slw8.in
slot 14 fun1.inv > host:amp amt=-30
"""
RACK_B = """seed 9
mod 1 lfo rate=0.62 shape=triangle
mod 2 compare mode=window width=0.3 hyst=0.1
mod 3 logic op=xor
mod 4 coin prob=0.4 mode=toggle latch=on
mod 5 calc op=mult amount=0.8
mod 6 mix gain1=1.5 gain2=-1 offset=0.1
mod 7 env mode=trigger attack=0.1 decay=0.3
mod 8 chance mode=smooth rate=0.7
slot 1 lfo1 > cmp2.a
slot 2 cmp2.gate > log3.a
slot 3 seq1 > log3.b
slot 4 log3 > coi4.in
slot 5 coi4.b > env7.gate
slot 6 lfo1 > clc5.a
slot 7 chn8 > clc5.b
slot 8 clc5 > mix6.in1
slot 9 env7 > mix6.in2
slot 10 mix6 > snd:Timbre amt=30
slot 11 mix6.avg > fx1:Gain amt=20
slot 12 cmp2.above > snd:Morph amt=20
slot 13 coi4.a > host:amp amt=-30
slot 14 log3.not > host:pitch amt=2
"""


@pytest.mark.parametrize("rack", ["a", "b"])
def test_audio_and_ticks_are_the_same_at_host_blocks_of_1_7_and_64(renderer, tmp_path, rack):
    """docs/16 §2.7 with the MG2 kinds: the WAV and the tick log at host
    blocks of 1, 7 and 64 frames are byte-identical, with chains, gate
    cables and every new kind active into the sound, an effect, PITCH and
    AMP. Commands sit on multiples of 448 frames."""
    mod = RACK_A if rack == "a" else RACK_B
    out = {}
    for block in (1, 7, 64):
        args = ["--engine", "macro", "--fx", "test-gain", "--frames", str(block),
                "--cmd", str(script(tmp_path, seq_text(block), name=f"s{block}"))]
        s, raw, ticks = run(renderer, tmp_path, args, mod=mod, name=f"{rack}{block}")
        out[block] = (raw, ticks, s)
        assert s["mod_sound_writes"] > 1000 and s["mod_other_writes"] > 500
        assert s["mod_refused"] == 0 and s["mod_nonfinite"] == 0 and s["mod_active"] == 14
    assert out[1][0] == out[64][0] and out[7][0] == out[64][0]
    assert out[1][1] == out[64][1] and out[7][1] == out[64][1]
    edges = sum(len(m["e"]) for t in out[64][1] for m in t["m"])
    assert edges > 50


def test_any_fill_renders_the_same_across_fills(renderer, tmp_path):
    for mod in (RACK_A, RACK_B):
        outs = []
        for fill in ("0", "0xA5", "0xFF"):
            args = ["--engine", "macro", "--fx", "test-gain", "--fill", fill,
                    "--cmd", str(script(tmp_path, seq_text(64)))]
            outs.append(run(renderer, tmp_path, args, mod=mod, name=f"f{fill}")[1:])
        assert outs[0] == outs[1] == outs[2]


# ---- chains and feedback -------------------------------------------------------------------------------

def test_a_chain_of_glue_entered_backwards_arrives_in_one_tick(renderer, tmp_path):
    """CV: LFO -> Mix -> Calc (Neg) -> Calc (Neg) -> Timbre, entered with
    the LFO at the bottom of the rack, moves Timbre in the very tick, by the
    very value, a direct cable does. Gates: LFO WRAP -> Logic (OR) -> Coin
    (all to A) -> Divide (every clock) -> an Envelope's gate starts the
    envelope at the very frame a direct cable does."""
    chain = """mod 1 env mode=trigger attack=0.2 decay=0.3
mod 2 calc op=neg
mod 3 calc op=neg
mod 4 mix
mod 5 divide value1=1
mod 6 coin prob=0
mod 7 logic op=or
mod 8 lfo rate=0.72
slot 1 lfo8 > mix4.in1
slot 2 mix4 > clc3.a
slot 3 clc3 > clc2.a
slot 4 clc2 > snd:Timbre amt=45
slot 5 lfo8.wrap > log7.a
slot 6 log7 > coi6.in
slot 7 coi6.a > div5.clock
slot 8 div5.out1 > env1.gate
slot 9 env1 > snd:Morph amt=50
"""
    direct = """mod 1 env mode=trigger attack=0.2 decay=0.3
mod 8 lfo rate=0.72
slot 4 lfo8 > snd:Timbre amt=45
slot 8 lfo8.wrap > env1.gate
slot 9 env1 > snd:Morph amt=50
"""
    args = ["--engine", "macro", "--note", "0:60:100:1.5", "--seconds", "1.5"]
    s1, raw1, t1 = run(renderer, tmp_path, args, mod=chain, name="chain")
    s2, raw2, t2 = run(renderer, tmp_path, args, mod=direct, name="direct")
    assert s1["mod_delayed"] == 0 and s1["mod_active"] == 9
    assert [t["w"] for t in t1] == [t["w"] for t in t2]
    assert raw1 == raw2
    starts = [t["t"] for t in t1 for m in t["m"] if m["p"] == 1 for e in m["e"] if e[0] == 3 and e[2]]
    assert len(starts) >= 6


def f32(x):
    return struct.unpack("<f", struct.pack("<f", x))[0]


def test_feedback_integrates_one_tick_late(renderer, tmp_path):
    """Mix's SUM into its own IN1 plus an offset is an integrator: each tick
    adds the offset to the last tick's sum, in float, exactly."""
    s, _, ticks = run(renderer, tmp_path, ["--engine", "test-sine", "--seconds", "0.1"],
                      mod="mod 1 mix offset=0.01\nslot 1 mix1 > mix1.in1\n")
    assert s["mod_delayed"] == 1
    want, step = 0.0, f32(0.01)
    for t in ticks[:150]:
        want = min(1.0, f32(want + step))
        assert f32(t["m"][0]["o"][0]) == want


def test_a_relaxation_oscillator_settles_into_an_exact_period(renderer, tmp_path):
    """Slew -> Compare -> (NOT) -> Slew: a loop with one delayed cable. It
    swings between the Schmitt trigger's thresholds for ever, with a period
    that repeats to the frame."""
    mod = ("mod 1 slew up=0.3 down=0.3\nmod 2 compare thresh=0.5 hyst=0.5\n"
           "slot 1 slw1 > cmp2.a\nslot 2 cmp2.not > slw1.in\n")
    s, _, ticks = run(renderer, tmp_path, ["--engine", "test-sine", "--seconds", "3"], mod=mod)
    assert s["mod_delayed"] == 1
    rises = [t["t"] - TICK + f for t in ticks for m in t["m"] if m["p"] == 2
             for port, f, h in m["e"] if port == 1 and h]
    periods = {b - a for a, b in zip(rises[2:], rises[3:])}
    assert len(rises) > 10 and len(periods) == 1, periods
    out = [t["m"][0]["o"][0] for t in ticks[1000:]]
    assert 0.2 < min(out) < 0.3 and 0.7 < max(out) < 0.8


def test_a_pinged_resonant_filter_wobbles_the_sound(renderer, tmp_path):
    """The owner's case: each note strikes a resonant Filter, whose ringing
    moves Timbre at the cutoff's frequency and dies away."""
    mod = ("mod 1 filter cutoff=0.5 res=0.8 strike=0.8\nslot 1 trig > flt1.ping\n"
           "slot 2 flt1.bp > snd:Timbre amt=40\n")
    s, raw, ticks = run(renderer, tmp_path, ["--engine", "macro", "--note", "0.1:60:100:1.5",
                                             "--seconds", "1.6"], mod=mod)
    bp = [t["m"][0]["o"][2] for t in ticks]
    start = int(0.1 * RATE / TICK) + 1
    crossings = [i for i in range(start, len(bp) - 1) if bp[i] <= 0 < bp[i + 1]]
    hz = (len(crossings) - 1) * (RATE / TICK) / (crossings[-1] - crossings[0])
    assert abs(hz - 0.05 * 2 ** 6.5) < 0.05
    early = max(abs(v) for v in bp[start:start + 400])
    late = max(abs(v) for v in bp[-400:])
    assert 0.7 < early <= 0.85 and late < 0.5 * early
    assert s["mod_sound_writes"] > 1500
