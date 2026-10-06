"""The modulation runtime (docs/16 stage MG1: include/fm1_mod.h,
fm1_mod_host.h, engines/mod/mod_*.c and kinds/), through fm1-render's
--mod, --log-mod and --list-mod and the C checks of fm1-mod-core-test:

- zero-route identity: a rack with no slot on, or only zero amounts, renders
  byte for byte what the same render without --mod gives, with the same
  splits, through the sequencer or not, effects included;
- byte identity at host blocks of 1, 7 and 64 frames with routes active on
  the sound, an effect, PITCH and AMP, and the same tick log;
- the planner (idempotent, permutation-invariant, fuzzed in C), a chain
  entered backwards arriving in the tick a direct cable does, feedback
  exactly one tick late;
- construction from any fill, NaN and infinity never reaching a write;
- rules M1-M7 on the host side: a zero amount is a no-op, NOLOCK and ENUMs
  without MOD are refused, a sequencer lock moves the base while an LFO
  swings round it, D6's revert at Stop restores the base with modulation
  running;
- system sources at their frames (KEY, TRIG, the sequencer's CLOCK, BEAT,
  BAR, RUN, START and track gates), a tempo-synced LFO, gate cables as
  seeded probability, gate inputs that never strand a gate when a cable is
  edited, patched or pulled;
- no allocator, stdio or libm in the runtime's objects; the curve tables
  generated; every kind's uids, ports and the system source ids pinned in
  tests/fixtures/mod-uids.json; fm1_mod_size() pinned, the same at 32 and
  64 bits (CI's -m32 job runs this file).
"""
import json
import re
import shutil
import subprocess
import sys
import wave
from pathlib import Path

import pytest

from tests.engine_helpers import ENGINES, RATE, renderer  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]
CORE_TEST = ENGINES / "build" / "fm1-mod-core-test"
FIXTURE = ROOT / "tests" / "fixtures" / "mod-uids.json"
TICK = 32
# fm1_mod_size(): 8,192 B of arena and 15,328 B of fixed state, the same in
# 32- and 64-bit builds (no pointers; every 64-bit member 8-aligned). 23,200 B
# until glide's two parameters on Macro Heavy took eight more records.
MOD_BYTES = 23520
FLAG_BITS = ["latch", "smooth", "nolock", "mod", "input"]


def run(renderer, tmp_path, args, mod=None, name="r", log=True):
    """Renders; returns (summary, wav bytes, tick log or None)."""
    wav = tmp_path / f"{name}.wav"
    cmd = [str(renderer), "--out", str(wav)] + list(args)
    lpath = tmp_path / f"{name}.mod.jsonl"
    if mod is not None:
        mpath = tmp_path / f"{name}.mod"
        mpath.write_text(mod)
        cmd += ["--mod", str(mpath)]
        if log:
            cmd += ["--log-mod", str(lpath)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    summary = json.loads(res.stdout)
    with wave.open(str(wav), "rb") as w:
        raw = w.readframes(w.getnframes())
    ticks = None
    if mod is not None and log:
        ticks = [json.loads(line) for line in lpath.read_text().splitlines()]
    return summary, raw, ticks


def script(tmp_path, text, name="s"):
    p = tmp_path / f"{name}.txt"
    p.write_text(text)
    return p


def strip(summary):
    return {k: v for k, v in summary.items()
            if not k.startswith("mod_") and "ns_per_block" not in k and k != "realtime_x"}


SEQ = (f"#! rate={RATE} block={{block}} tracks=2 end={{end}}\n"
       "@0 tog 0 0 60 100 64 90;tog 0 3 67 100;tog 0 6 72 80;tog 0 9 55 70;cscl 0 3 2;swing 62\n"
       "@0 tog 1 1 48 100;tog 1 5 55 70\n"
       "@0 alabel 0 1 synth:Timbre;alabel 0 2 synth:Volume;abase 0 2 100;abase 0 1 40;"
       "aset 0 1 3 20 1;aset 0 1 6 110 1;aset 0 2 6 60 1\n"
       "@0 route 1 1 0;play\n@{stop} stop\n@{play} play\n")


def seq_text(block, end=448 * 100, stop=448 * 60, play=448 * 70):
    return SEQ.format(block=block, end=end, stop=stop, play=play)


# ---- C checks, sizes, symbols, tables, fixture ------------------------------------------------

def test_the_core_checks_itself(renderer):
    res = subprocess.run([str(CORE_TEST)], capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    out = json.loads(res.stdout)
    assert out["failed"] == 0 and out["size"] == MOD_BYTES
    assert out["plans"] == 3000 and out["plans_with_loops"] > 500
    assert out["chain_ticks"] > 300 and out["feedback_ticks"] == 12 and out["nan_writes"] > 50
    assert out["continuity"] == 6


def test_size_is_pinned_and_listed(renderer):
    d = json.loads(subprocess.check_output([str(renderer), "--list-mod"]))
    assert d["bytes"] == MOD_BYTES
    assert (d["tick"], d["positions"], d["slots"], d["arena"]) == (TICK, 8, 32, 8192)
    # Under 256 B each, but Burst: it ports Peaks' 32-pulse buffer whole
    # (docs/16 §4.2, engines/mod/README.md).
    assert all(k["instance_bytes"] <= (320 if k["id"] == "burst" else 256) for k in d["kinds"])


FORBIDDEN = {"malloc", "calloc", "realloc", "free", "_Znwm", "_Znwj", "_Znam", "_Znaj",
             "_ZdlPv", "_ZdaPv", "printf", "fprintf", "snprintf", "sprintf", "puts", "fputs",
             "fopen", "fwrite", "rand", "srand", "random"}
FORBIDDEN |= {f + s for f in ("sin", "cos", "tan", "exp", "exp2", "expm1", "log", "log2", "log10",
                              "pow", "sqrt", "floor", "ceil", "fmod", "round", "lround", "trunc",
                              "modf", "frexp", "ldexp", "tanh", "atan", "atan2")
              for s in ("", "f", "l")}


def test_no_heap_no_stdio_no_libm(renderer):
    nm = shutil.which("nm")
    if not nm:
        pytest.skip("no nm")
    base = ENGINES / "build" / "mod" / "mod"
    objs = sorted(base.glob("mod_*.o")) + sorted((base / "kinds").glob("*.o"))
    kinds = json.loads(subprocess.check_output([str(renderer), "--list-mod"]))["kinds"]
    assert len(objs) == 7 + len(kinds)    # core, plan, registry, curves, glue, mi, mi_tables
    objs.append(ENGINES / "build" / "c" / "seq" / "seq_host.o")   # 7-bit locks (the LOG law)
    objs.append(ENGINES / "build" / "c" / "seq" / "fx_host.o")    # the effects' beats
    for o in objs:
        out = subprocess.check_output([nm, "-u", str(o)], text=True)
        names = {line.split()[-1] for line in out.splitlines() if line.strip()}
        names = {n[1:] if sys.platform == "darwin" and n.startswith("_") else n for n in names}
        assert not names & FORBIDDEN, f"{o.name} imports {sorted(names & FORBIDDEN)}"


def test_curve_tables_are_generated():
    subprocess.run([sys.executable, str(ENGINES / "mod" / "gen_curves.py"), "--check"], check=True)


def listed(renderer):
    d = json.loads(subprocess.check_output([str(renderer), "--list-mod"]))
    kinds = {}
    for k in d["kinds"]:
        kinds[k["id"]] = dict(k, params=[dict(p, type="enum" if p["type"] == 1 else "float")
                                         for p in k["params"]])
    return d, kinds


def test_uids_ports_and_sources_match_the_fixture(renderer):
    """The fixture is the contract: a reordered table keeps its uids and
    passes; a changed, reused or dropped uid, port or source id fails."""
    d, kinds = listed(renderer)
    pinned = json.loads(FIXTURE.read_text())
    assert set(kinds) == set(pinned["kinds"])
    for kid, k in kinds.items():
        want = pinned["kinds"][kid]
        assert k["guid"] == want["guid"] and k["abbr"] == want["abbr"], kid
        have = {p["name"]: (p["uid"], p["type"], p["flags"]) for p in k["params"]}
        assert have == {p["name"]: (p["uid"], p["type"], p["flags"]) for p in want["params"]}, kid
        assert [g["name"] for g in k["gates"]] == want["gates"], kid
        assert [o["name"] for o in k["outs"]] == want["outs"], kid
    assert {str(s["id"]): s["name"] for s in d["sources"]} == pinned["sources"]
    assert [{"name": p["name"], "uid": p["uid"]} for p in d["host"]] == pinned["host"]


def test_kind_tables_follow_the_rules(renderer):
    """Uids 1-4095 and unique; NOLOCK never with MOD; every FLOAT takes
    modulation (MOD) or is an INPUT; INPUT only on a FLOAT -1..1 with
    default 0; names unique without case, abbreviations 1-6 characters and
    unique cut to 5; ports up to 5 characters; guids 4 characters and
    unique; a three-letter abbreviation per kind."""
    d, kinds = listed(renderer)
    assert len({k["guid"] for k in kinds.values()}) == len(kinds)
    for kid, k in kinds.items():
        assert len(k["guid"]) == 4 and re.fullmatch(r"[A-Z]{3}", k["abbr"]), kid
        uids = [p["uid"] for p in k["params"]]
        assert all(0 < u <= 0x0FFF for u in uids) and len(set(uids)) == len(uids), kid
        names = [p["name"].lower() for p in k["params"]]
        assert len(set(names)) == len(names), kid
        abbrs = [p["abbr"] for p in k["params"]]
        assert all(re.fullmatch(r"[ -~]{1,6}", a) for a in abbrs), kid
        assert len({a[:5] for a in abbrs}) == len(abbrs), kid
        for p in k["params"]:
            f = set(p["flags"])
            assert not {"nolock", "mod"} <= f, (kid, p["name"])
            if p["type"] == "float":
                assert ("mod" in f) != ("input" in f), (kid, p["name"])
            if "input" in f:
                assert p["type"] == "float" and (p["min"], p["max"], p["def"]) == (-1, 1, 0)
            if p["type"] == "enum":
                assert len(p["names"]) == p["max"] - p["min"] + 1
        for port in k["gates"] + k["outs"]:
            assert 1 <= len(port["name"]) <= 5, (kid, port)
        assert k["credits"] and len(k["params"]) <= 32
    for s in d["sources"]:
        assert 1 <= len(s["name"]) <= 6


# ---- zero-route identity -----------------------------------------------------------------------

# A full default rack, modules turned, slots that are off or at zero amount.
ZERO = """rack default
mod 6 chance mode=smooth rate=0.9
set 1 rate=0.8 shape=s&h
slot 3 lfo2.wrap > env4.gate amt=0
slot 4 chn5 > host:pitch amt=0
slot 5 chance6.smth > host:amp amt=0
slot 6 key > lfo1.reset
"""
SND_ZERO = "slot 1 lfo1 > snd:{a} amt=40 off\nslot 2 env3 > snd:{b} amt=0\n"
SND_PARAMS = {"macro": ("Timbre", "Morph"), "sixop": ("Brightness", "Envelope"),
              "shapes": ("Timbre", "Color")}
FX_ZERO = "slot 7 lfo1 > fx1:Mix amt=0\nslot 8 env3 > fx2:Fold amt=0\n"


@pytest.mark.parametrize("case", ["notes", "seq", "fx", "fill", "seq-fx"])
def test_zero_route_identity(renderer, tmp_path, case):
    """docs/16 §2.4: a destination with no enabled slot is never written, so
    every render stays byte-identical; zero amounts write nothing either.
    The same splits, too (a split cannot show in the WAV)."""
    if case == "notes":
        args = ["--engine", "macro", "--note", "0:60:100:1.2", "--note", "0.4:64:80:0.5",
                "--bend", "0.6:2", "--param-at", "0.8:Harmonics=0.2", "--param", "Timbre=0.3",
                "--seconds", "1.5"]
    elif case in ("seq", "seq-fx"):
        args = ["--engine", "sixop" if case == "seq" else "macro",
                "--cmd", str(script(tmp_path, seq_text(64)))]
        if case == "seq-fx":
            args += ["--fx", "crush", "--fx-param", "Bits=6", "--fx", "fold"]
    elif case == "fx":
        args = ["--input", "noise", "--fx", "crush", "--fx", "fold", "--seconds", "1"]
    else:
        args = ["--engine", "shapes", "--note", "0:57:100:1", "--seconds", "1.2",
                "--fill", "0xA5", "--frames", "7"]
    s0, raw0, _ = run(renderer, tmp_path, args, name="plain")
    mod = ZERO + (FX_ZERO if args.count("--fx") == 2 else "")
    if "--engine" in args:
        a, b = SND_PARAMS[args[args.index("--engine") + 1]]
        mod += SND_ZERO.format(a=a, b=b)
    s1, raw1, ticks = run(renderer, tmp_path, args, mod=mod, name="mod")
    assert raw1 == raw0
    assert strip(s1) == strip(s0)
    assert s1["mod_writes"] == 0 and s1["mod_splits"] == s0.get("seq_splits", 0)
    assert s1["mod_active"] >= 4 and s1["mod_refused"] == 0
    assert len(ticks) == s1["mod_ticks"] > 0
    assert not [k for k in s0 if k.startswith("mod_")]


def test_mod_flags_need_mod(renderer, tmp_path):
    bad = subprocess.run([str(renderer), "--engine", "test-sine", "--log-mod", str(tmp_path / "x")],
                         capture_output=True, text=True)
    assert bad.returncode == 2 and "--log-mod needs --mod" in bad.stderr
    p = tmp_path / "bad.mod"
    for text, msg in [("mod 9 lfo", "mod wants"), ("mod 1 nosuch", "unknown kind"),
                      ("mod 1 lfo\nslot 1 lfo2 > snd:Timbre", "position 2"),
                      ("mod 1 lfo\nslot 1 lfo1 > snd:Nope", "no parameter"),
                      ("mod 1 lfo bogus=1", "no parameter"), ("frobnicate", "unknown line")]:
        p.write_text(text + "\n")
        res = subprocess.run([str(renderer), "--engine", "macro", "--seconds", "0.1",
                              "--mod", str(p)], capture_output=True, text=True)
        assert res.returncode == 2 and msg in res.stderr, (text, res.stderr)
    # A bad @FRAME, and a bad line that only fails when its frame comes, with
    # the sequencer's script loaded: each exits 2 with everything released
    # (the sanitizer build's leak check runs these).
    cmd = script(tmp_path, seq_text(64, end=448 * 4))
    for text, msg, extra in [("@x mod 1 lfo", "bad @FRAME", []),
                             ("mod 1 lfo\n@2000 frobnicate", "unknown line", ["--cmd", str(cmd)])]:
        p.write_text(text + "\n")
        res = subprocess.run([str(renderer), "--engine", "macro", "--seconds", "0.1",
                              "--mod", str(p)] + extra, capture_output=True, text=True)
        assert res.returncode == 2 and msg in res.stderr, (text, res.stderr)
    res = subprocess.run([str(renderer), "--engine", "macro", "--seconds", "0.1", "--mod",
                          str(tmp_path / "missing.mod")], capture_output=True, text=True)
    assert res.returncode == 1 and "cannot read" in res.stderr


# ---- block-size identity with routes ----------------------------------------------------------

ROUTES = """seed 77
rack default
set 1 rate=0.62 shape=triangle
set 2 rate=0.55 shape=s&h mode=trig
set 3 attack=0.3 decay=0.45 sustain=0.4 release=0.5
set 4 mode=trigger attack=0.1 decay=0.3 loop=ad
set 5 mode=smooth rate=0.7 slew=0.3
slot 1 lfo1 > snd:Timbre amt=30
slot 2 env3 > snd:Morph amt=50
slot 3 chn5 > snd:Harmonics amt=-20
slot 4 lfo1 > host:pitch amt=0.4
slot 5 env4 > host:amp amt=-40 pol=uni
slot 6 lfo2 > fx1:Gain amt=25
slot 7 seq2 > env4.gate amt=70
slot 8 lfo2.wrap > chn5.trig
slot 9 env3.eoc > lfo1.reset
slot 10 lfo1 > lfo2.rate amt=20 via=vel
slot 11 chn5.smth > lfo1.depth amt=-30 curve=square
"""


@pytest.mark.parametrize("engine", ["macro", "test-sine", "sixop"])
def test_audio_and_ticks_are_the_same_at_host_blocks_of_1_7_and_64(renderer, tmp_path, engine):
    """docs/16 §2.7: the same WAV and the same tick log at host blocks of 1,
    7 and 64 frames with routes active into the sound, an effect, PITCH and
    AMP, through gate cables and chains. Commands sit on multiples of 448
    frames (lcm of 7 and 64)."""
    if engine == "test-sine":
        routes = ROUTES.replace("snd:Timbre", "snd:Volume").replace(
            "slot 2 env3 > snd:Morph amt=50\n", "").replace(
            "slot 3 chn5 > snd:Harmonics amt=-20\n", "")
    elif engine == "sixop":
        routes = ROUTES.replace("snd:Timbre", "snd:Brightness").replace(
            "snd:Morph", "snd:Envelope").replace("snd:Harmonics", "snd:Patch")
    else:
        routes = ROUTES
    out = {}
    for block in (1, 7, 64):
        args = ["--engine", engine, "--fx", "test-gain", "--frames", str(block),
                "--cmd", str(script(tmp_path, seq_text(block), name=f"s{block}"))]
        s, raw, ticks = run(renderer, tmp_path, args, mod=routes, name=f"b{block}")
        out[block] = (raw, ticks, s)
        assert s["mod_sound_writes"] > 1000 and s["mod_other_writes"] > 1000
        assert s["mod_refused"] == 0 and s["mod_nonfinite"] == 0
    assert out[1][0] == out[64][0] and out[7][0] == out[64][0]
    assert out[1][1] == out[64][1] and out[7][1] == out[64][1]
    for k in ("mod_ticks", "mod_writes", "seq_notes_to_engine", "seq_locks_to_engine"):
        assert out[1][2][k] == out[7][2][k] == out[64][2][k], k
    _, plain, _ = run(renderer, tmp_path, ["--engine", engine, "--fx", "test-gain", "--cmd",
                                          str(script(tmp_path, seq_text(64), name="p"))], name="p")
    assert plain != out[64][0], "the routes change the sound"


def test_any_fill_renders_the_same_across_fills(renderer, tmp_path):
    outs = []
    for fill in ("0", "0xA5", "0xFF"):
        args = ["--engine", "macro", "--fx", "test-gain", "--fill", fill,
                "--cmd", str(script(tmp_path, seq_text(64)))]
        outs.append(run(renderer, tmp_path, args, mod=ROUTES, name=f"g{fill}")[1:])
    assert outs[0] == outs[1] == outs[2]


# ---- chains and feedback -------------------------------------------------------------------------

def test_a_chain_entered_backwards_arrives_in_one_tick(renderer, tmp_path):
    """D <- C <- B <- A with A (an LFO) at the bottom of the rack: the
    planner runs A, B, C, D, so Timbre moves in the very tick a direct cable
    from A moves it, and the WAVs are identical."""
    chain = """mod 1 chance mode=t&h
mod 2 chance mode=t&h
mod 3 chance mode=t&h
mod 4 lfo rate=0.7
slot 1 lfo4 > chance3.in
slot 2 chance3 > chance2.in
slot 3 chance2 > chance1.in
slot 4 chance1 > snd:Timbre amt=45
"""
    direct = "mod 4 lfo rate=0.7\nslot 4 lfo4 > snd:Timbre amt=45\n"
    args = ["--engine", "macro", "--note", "0:60:100:1", "--seconds", "1"]
    s1, raw1, t1 = run(renderer, tmp_path, args, mod=chain, name="chain")
    s2, raw2, t2 = run(renderer, tmp_path, args, mod=direct, name="direct")
    assert raw1 == raw2 and s1["mod_delayed"] == 0
    assert [t["w"] for t in t1] == [t["w"] for t in t2]


def test_feedback_is_exactly_one_tick_late(renderer, tmp_path):
    """A self-cable reads the previous tick: Chance tracking its own HELD
    plus an offset climbs by the offset each tick. In a two-module loop the
    cable that runs up the rack is the delayed one."""
    s, _, ticks = run(renderer, tmp_path, ["--engine", "test-sine", "--seconds", "0.02"],
                      mod="mod 1 chance mode=t&h\nslot 1 chance1 > chance1.in ofs=10\n")
    assert s["mod_delayed"] == 1
    held = [t["m"][0]["o"][0] for t in ticks[:12]]
    step = 1638 / 16384
    for k, v in enumerate(held):
        assert v == pytest.approx(min(1.0, (k + 1) * step), abs=1e-6)
    loop = "mod 1 lfo\nmod 2 chance mode=t&h\nslot 1 lfo1 > chance2.in\nslot 2 chance2 > lfo1.rate amt=10\n"
    s, _, _ = run(renderer, tmp_path, ["--engine", "test-sine", "--seconds", "0.02"], mod=loop,
                  name="loop")
    assert s["mod_delayed"] == 1


# ---- rules M1-M7 on the host side --------------------------------------------------------------

def test_a_zero_amount_writes_nothing(renderer, tmp_path):
    args = ["--engine", "macro", "--note", "0:60:100:0.5", "--seconds", "0.6"]
    _, raw0, _ = run(renderer, tmp_path, args, name="plain")
    s, raw, ticks = run(renderer, tmp_path, args,
                        mod="mod 1 lfo rate=1\nslot 1 lfo1 > snd:Timbre amt=0\n")
    assert raw == raw0 and s["mod_writes"] == 0 and s["mod_splits"] == 0
    assert all(t["s"][0]["v"] == t["s"][0]["b"] for t in ticks)


@pytest.mark.parametrize("dst", ["snd:Model", "snd:LPG"])
def test_nolock_and_enum_without_mod_are_refused(renderer, tmp_path, dst):
    """M4: Macro's Model is NOLOCK and its LPG an ENUM without MOD; a cable
    to either is refused, writes nothing and changes nothing."""
    args = ["--engine", "macro", "--note", "0:60:100:0.5", "--seconds", "0.6"]
    _, raw0, _ = run(renderer, tmp_path, args, name="plain")
    s, raw, _ = run(renderer, tmp_path, args, mod=f"mod 1 lfo rate=1\nslot 1 lfo1 > {dst}\n")
    assert s["mod_refused"] == 1 and s["mod_active"] == 0 and s["mod_writes"] == 0
    assert raw == raw0


def lock_script(stop_at=None):
    text = (f"#! rate={RATE} block=64 tracks=1 end={RATE * 2}\n"
            "@0 tog 0 0 60 100;tog 0 8 62 100;slen 0 0 15 -1 300\n"
            "@0 alabel 0 0 synth:Timbre;abase 0 0 32;aset 0 0 4 100 1;aset 0 0 12 10 1\n"
            "@0 play\n")
    if stop_at:
        text += f"@{stop_at} stop\n"
    return text


def test_a_lock_moves_the_base_while_the_lfo_swings_round_it(renderer, tmp_path):
    """M1: a lock writes Timbre's base; the value sent is the base plus the
    LFO's offset (amount x LFO x range), so the LFO swings round each
    locked value instead of being replaced by it."""
    s, _, ticks = run(renderer, tmp_path, ["--engine", "macro", "--cmd",
                                           str(script(tmp_path, lock_script()))],
                      mod="mod 1 lfo rate=0.75\nslot 1 lfo1 > snd:Timbre amt=20\n")
    assert s["seq_locks_to_engine"] > 4
    bases = set()
    for t in ticks:
        sink = t["s"][0]
        lfo = t["m"][0]["o"][0]
        amt = 3277 / 16384                  # 20 % in Q1.14
        assert sink["v"] == pytest.approx(min(1.0, max(0.0, sink["b"] + amt * lfo)), abs=1e-6)
        bases.add(round(sink["b"] * 127))
    assert {32, 100, 10} <= bases, bases


def test_d6_revert_restores_the_base_with_modulation_running(renderer, tmp_path):
    """M2: Stop reverts the lane to its base (abase 32/127); the LFO keeps
    running round it."""
    stop = 448 * 120
    s, _, ticks = run(renderer, tmp_path, ["--engine", "macro", "--cmd",
                                           str(script(tmp_path, lock_script(stop)))],
                      mod="mod 1 lfo rate=0.75\nslot 1 lfo1 > snd:Timbre amt=20\n")
    after = [t for t in ticks if t["t"] > stop + 64]
    assert after and all(t["s"][0]["b"] == pytest.approx(32 / 127, abs=1e-6) for t in after)
    assert len({t["s"][0]["v"] for t in after}) > 50, "the LFO keeps swinging"


def test_bend_is_the_base_of_pitch(renderer, tmp_path):
    """HOST PITCH: --bend sets its base; the LFO swings round it."""
    s, _, ticks = run(renderer, tmp_path, ["--engine", "macro", "--note", "0:60:100:1",
                                           "--bend", "0.25:3", "--seconds", "0.6"],
                      mod="mod 1 lfo rate=0.8\nslot 1 lfo1 > host:pitch amt=1\n")
    late = [t for t in ticks if t["t"] > 0.3 * RATE]
    assert all(t["s"][0]["b"] == 3.0 for t in late)
    amt = 164 / 16384 * 96                  # 1 % in Q1.14 of PITCH's 96 semitones
    assert all(t["s"][0]["v"] == pytest.approx(3.0 + amt * t["m"][0]["o"][0], abs=1e-4)
               for t in late)
    assert s["mod_sound_writes"] > 100


def test_fx_param_at_is_the_base_of_an_effect_parameter(renderer, tmp_path):
    """M1 on an effect: --fx-param-at moves the base of crush's Mix and the
    LFO swings round the new value."""
    s, _, ticks = run(renderer, tmp_path, ["--input", "noise", "--fx", "crush", "--fx-param",
                                           "Mix=0.5", "--fx-param-at", "0.25:1:Mix=0.8",
                                           "--seconds", "0.5"],
                      mod="mod 1 lfo rate=0.8\nslot 1 lfo1 > fx1:Mix amt=10\n")
    early = [t for t in ticks if t["t"] < 0.2 * RATE]
    late = [t for t in ticks if t["t"] > 0.3 * RATE]
    assert early and all(t["s"][0]["u"] == "fx1" and t["s"][0]["b"] == 0.5 for t in early)
    amt = 1638 / 16384                      # 10 % in Q1.14 of Mix's 0..1
    assert late and all(t["s"][0]["b"] == pytest.approx(0.8) and t["s"][0]["v"] ==
                        pytest.approx(min(1.0, 0.8 + amt * t["m"][0]["o"][0]), abs=1e-6)
                        for t in late)
    assert s["mod_other_writes"] > 100


def test_rtrg_retriggers_on_every_note_on(renderer, tmp_path):
    """RTRG (docs/16 MG3; the owner's decision of 2026-10-05: envelopes
    trigger from every note): KEY, retriggered. Two overlapping notes, then
    a two-note chord: KEY rises and falls once for each phrase, RTRG falls
    and rises again at the second note's frame and rises once for the chord.
    Into an envelope's GATE (the virtual FM-1's default cables) the second note
    restarts the attack; with KEY it would only sustain."""
    notes = ["--note", "0.1:60:100:0.6", "--note", "0.3:64:100:0.2",
             "--note", "0.9:67:100:0.1", "--note", "0.9:71:100:0.1"]
    args = ["--engine", "test-sine", "--seconds", "1.2"] + notes
    rack = "mod 1 env attack=0.3 decay=0.4 sustain=0.4\n"
    at = lambda t: -(-int(t * RATE) // 64) * 64     # noqa: E731  (the block a --note applies at)

    def edges(ticks, sid):
        return [(t["t"] - 32 + f, high) for t in ticks for s_, f, high in t["g"] if s_ == sid]

    _, _, rt = run(renderer, tmp_path, args, mod=rack + "slot 1 rtrg > env1:gate\n", name="rtrg")
    _, _, kt = run(renderer, tmp_path, args, mod=rack + "slot 1 key > env1:gate\n", name="key")
    on1, on2, off1, chord = at(0.1), at(0.3), at(0.7), at(0.9)
    assert edges(rt, 16)[:3] == [(on1, 1), (off1, 0), (chord, 1)]
    assert edges(rt, 23)[:5] == [(on1, 1), (on2, 0), (on2, 1), (off1, 0), (chord, 1)]
    assert edges(rt, 16) == edges(kt, 16)
    env = lambda ticks: {t["t"]: t["m"][0]["o"][0] for t in ticks}   # noqa: E731
    er, ek = env(rt), env(kt)
    before = max(t for t in er if t <= on2)
    after = [t for t in sorted(er) if on2 < t < on2 + 0.1 * RATE]
    assert er[before] == ek[before]                  # the same until the second note
    assert er[after[-1]] > er[after[0]]              # RTRG: the attack again
    assert ek[after[-1]] <= ek[after[0]]             # KEY: decaying toward sustain


def test_the_record_pool_holds_every_chain(renderer):
    """docs/16 MG3: the bound units share FM1_MOD_SINK_PARAMS parameter
    records. The largest chain the virtual FM-1 can hold, four sound units
    of the engine with the most parameters and ten effects (two inserts on
    each, two master slots) of the effect with the most, fits with HOST's
    two; the sinks are listed in their order with their script names."""
    d = json.loads(subprocess.check_output([str(renderer), "--list-mod"]))
    engines = json.loads(subprocess.check_output([str(renderer), "--list"]))
    most = {k: max(min(len(e["params"]), d["unit_params"]) for e in engines if e["kind"] == k)
            for k in ("sound", "audio_fx")}
    assert 4 * most["sound"] + 10 * most["audio_fx"] + 2 <= d["sink_params"] == 188
    assert [n for _, n in d["sinks"]] == ["snd", "fx1", "fx2", "host", "snd2", "snd3", "snd4",
                                          "snd1.fx1", "snd1.fx2", "snd2.fx1", "snd2.fx2",
                                          "snd3.fx1", "snd3.fx2", "snd4.fx1", "snd4.fx2"]
    assert [u for u, _ in d["sinks"]] == [0, 1, 2, 3, 17, 18, 19, 20, 21, 24, 25, 28, 29, 32, 33]


def test_mod_runs_over_sound_units(renderer, tmp_path):
    """With slots (docs/16 MG3) the runtime runs over every sound unit: a
    cable into the sound moves sound unit 0 as without slots, a note on
    another unit feeds KEY, and with nothing routed the render is the plain
    slots render to the byte."""
    base = ["--engine", "test-sine", "--sound", "1:test-sine", "--seconds", "0.5",
            "--sound-note", "1:0.05:64:100:0.3"]
    plain, raw_plain, _ = run(renderer, tmp_path, base, name="plain")
    s, raw, _ = run(renderer, tmp_path, base, mod="rack default\n", name="idle")
    assert raw == raw_plain and s["mod_writes"] == 0
    s, _, ticks = run(renderer, tmp_path, base, mod="rack default\nslot 1 key > env3:gate\n", name="key")
    assert any(sid == 16 and high == 1 for t in ticks for sid, _, high in t["g"])
    one, raw_one, _ = run(renderer, tmp_path, ["--engine", "test-sine", "--seconds", "0.5", "--slots"],
                          mod="mod 1 lfo rate=0.8\nslot 1 lfo1 > snd:Volume amt=-50\n", name="slots")
    two, raw_two, _ = run(renderer, tmp_path, ["--engine", "test-sine", "--seconds", "0.5"],
                          mod="mod 1 lfo rate=0.8\nslot 1 lfo1 > snd:Volume amt=-50\n", name="noslots")
    assert raw_one == raw_two and one["mod_sound_writes"] == two["mod_sound_writes"] > 0
    # Cables into sound unit 2 and its insert: their writes, by name; at a
    # zero amount, the plain render to the byte.
    units = base + ["--insert", "1:test-gain"]
    plain2, raw_plain2, _ = run(renderer, tmp_path, units, name="plain2")
    cables = "rack default\nslot 1 lfo1 > snd2:Volume amt={a}\nslot 2 lfo2 > snd2.fx1:Gain amt={a}\n"
    zero, raw_zero, _ = run(renderer, tmp_path, units, mod=cables.format(a=0), name="zero")
    assert raw_zero == raw_plain2 and zero["mod_writes"] == 0
    s, raw, ticks = run(renderer, tmp_path, units, mod=cables.format(a=-40), name="sound2")
    assert {x["u"] for x in ticks[-1]["s"]} == {"snd2", "snd2.fx1"} and raw != raw_plain2
    assert s["mod_sound_writes"] > 0 and s["mod_other_writes"] > 0 and s["mod_refused"] == 0


def test_amp_makes_a_tremolo(renderer, tmp_path):
    args = ["--engine", "test-sine", "--note", "0:69:100:1", "--seconds", "1"]
    _, raw0, _ = run(renderer, tmp_path, args, name="plain")
    s, raw, _ = run(renderer, tmp_path, args, mod="mod 1 lfo rate=0.55 shape=square\n"
                                                  "slot 1 lfo1 > host:amp amt=-25 pol=uni\n")
    assert raw != raw0 and s["mod_other_writes"] > 1

    def level(r, a, b):
        x = [int.from_bytes(r[i:i + 2], "little", signed=True) for i in range(a * 4, b * 4, 4)]
        return max(abs(v) for v in x)
    # A square LFO between 1 (base) and 0.5: the loud and the soft halves.
    levels = [level(raw, int(k * 0.05 * RATE), int((k + 1) * 0.05 * RATE)) for k in range(4, 18)]
    assert max(levels) > 1.8 * min(levels)


# ---- sources, sync, probability -----------------------------------------------------------------

def test_system_gates_land_at_their_frames(renderer, tmp_path):
    """The sequencer's notes and clock reach the runtime at their own
    frames: each tick's SEQ1, KEY, TRIG, CLOCK, BEAT, BAR, RUN and START
    edges sit at the offset of the event inside the previous tick period."""
    text = (f"#! rate={RATE} block=64 tracks=2 end={RATE * 3}\n"
            "@0 tog 0 0 60 100;tog 0 4 62 100;tog 1 2 48 100;route 1 0 2\n@0 play\n"
            f"@{RATE * 2} stop\n")
    log = tmp_path / "ev.jsonl"
    s, _, ticks = run(renderer, tmp_path, ["--engine", "test-sine", "--cmd",
                                           str(script(tmp_path, text)), "--log-events", str(log)],
                      mod="mod 1 lfo\n")
    events = [json.loads(line) for line in log.read_text().splitlines()]
    got = {}
    for t in ticks:
        for sid, frame, high in t["g"]:
            got.setdefault(sid, []).append((t["t"] - TICK + frame, high))

    def rises(sid):
        return [f for f, h in got.get(sid, []) if h]

    def at(e):
        return e["frame"]                   # the log's frame is absolute
    on0 = [at(e) for e in events if e["kind"] == "on" and e["track"] == 0]
    on1 = [at(e) for e in events if e["kind"] == "on" and e["track"] == 1]
    clocks = [e for e in events if e["kind"] == "clock"]
    assert on0 and on1 and clocks
    assert rises(16) and set(rises(16)) <= set(rises(17))           # KEY rises at a note-on
    assert rises(17) == on0                                          # TRIG: track 0 plays the sound
    assert rises(24) == on0 and rises(25) == on1                    # SEQ1, SEQ2: any route
    assert rises(18) == [at(e) for e in clocks if e["tick"] % 24 == 0]
    assert rises(19) == [at(e) for e in clocks if e["tick"] % 96 == 0]
    assert rises(20) == [at(e) for e in clocks if e["tick"] % 384 == 0]
    starts = [at(e) for e in events if e["kind"] == "start"]
    stops = [at(e) for e in events if e["kind"] == "stop"]
    assert rises(22) == starts and rises(21) == starts
    assert [f for f, h in got[21] if not h] == stops


def test_a_synced_lfo_wraps_on_the_beat(renderer, tmp_path):
    """Sync 1/4 at 120 BPM: WRAP every 22,059 frames, the first at Start."""
    text = f"#! rate={RATE} block=64 tracks=1 end={RATE * 3}\n@0 bpm 12000\n@448 play\n"
    _, _, ticks = run(renderer, tmp_path, ["--engine", "test-sine", "--cmd", str(script(tmp_path, text))],
                      mod="mod 1 lfo sync=1/4\n")
    wraps = [t["t"] - TICK + f for t in ticks for port, f, h in t["m"][0]["e"] if port == 2 and h]
    gaps = {b - a for a, b in zip(wraps, wraps[1:])}
    assert wraps[0] == 448 and gaps == {22059} and len(wraps) >= 5, (wraps[:5], gaps)


def test_editing_or_repatching_a_gate_never_strands_it(renderer, tmp_path):
    """Gate inputs carry on from tick to tick: turning a gate cable's amount
    while the key is held keeps the cable high, so the release still
    reaches the envelope; a cable patched into a normalled input while the
    key is held is a fall at the next tick's first frame, and pulling it a
    rise; a reset envelope's ACT falls as an edge. The same at host blocks
    of 7 and 64 (edits sit on multiples of 448 frames; the key is held
    throughout, since a live note-off lands on a block boundary)."""
    edit = ("mod 1 env attack=0.2 decay=0.3 sustain=0.6 release=0.3\n"
            "slot 1 key > env1.gate\n"
            "@8960 slot 1 key > env1.gate amt=90\n")
    args = ["--engine", "test-sine", "--note", "0:60:100:0.4", "--seconds", "1"]
    _, _, ticks = run(renderer, tmp_path, args, mod=edit, name="edit")
    off = int(0.4 * RATE)
    env = [(t["t"], t["m"][0]["o"]) for t in ticks]
    assert all(o[2] == 1 for t, o in env if 8960 < t <= off)
    assert env[-1][1] == [0, 0, 0], "the envelope released"
    eoc = [t["t"] - TICK + f for t in ticks for port, f, h in t["m"][0]["e"] if port == 2 and h]
    assert len(eoc) == 1 and eoc[0] > off

    repatch = ("mod 1 env attack=0 decay=0.2 sustain=0.8 release=0\n"
               "@4480 slot 1 seq1 > env1.gate\n@8960 slot 1 off\n@13440 reset\n")
    logs = {}
    held = ["--engine", "test-sine", "--note", "0:60:100:2", "--seconds", "0.5"]
    for block in (7, 64):
        _, raw, ticks = run(renderer, tmp_path, held + ["--frames", str(block)], mod=repatch,
                            name=f"repatch{block}")
        logs[block] = (raw, ticks)
    assert logs[7] == logs[64]
    act = {t["t"]: [e for e in t["m"][0]["e"] if e[0] == 3] for t in logs[64][1]}
    # An edit applies before the tick at its frame, which sees the jump at
    # its frame 0: patched low, the gate falls there and ACT falls when the
    # 0.5 ms release ends, inside that tick; pulled, the key's gate rises at
    # frame 0 and so does ACT; reset, ACT falls at frame 0.
    assert [h for _, f, h in act[4480]] == [0] and act[4480][0][1] <= 24
    assert act[8960] == [[3, 0, 1]]
    assert act[13440] == [[3, 0, 0]]


def test_a_gate_cable_is_a_seeded_probability(renderer, tmp_path):
    """docs/16 §2.3: below 100 % a gate cable passes each rising edge with
    that probability, from the slot's own generator: the same seed gives the
    same pattern, another seed another; 100 % passes all."""
    steps = ";".join(f"tog 0 {k} 60 100" for k in range(16))
    text = (f"#! rate={RATE} block=64 tracks=1 end={RATE * 6}\n"
            f"@0 bpm 24000;{steps}\n@0 play\n")
    cmd = str(script(tmp_path, text))

    def passes(seed, amt):
        mod = (f"seed {seed}\nmod 1 env mode=trigger attack=0 decay=0\n"
               f"slot 1 trig > env1.gate amt={amt}\n")
        _, _, ticks = run(renderer, tmp_path, ["--engine", "test-sine", "--cmd", cmd], mod=mod,
                          name=f"p{seed}-{amt}")
        return [t["t"] for t in ticks for port, f, h in t["m"][0]["e"] if port == 3 and h]
    all_ = passes(1, 100)
    a, b, c = passes(1, 50), passes(1, 50), passes(2, 50)
    assert len(all_) >= 90
    assert a == b and a != c
    assert 0.3 * len(all_) < len(a) < 0.7 * len(all_)
    assert set(a) <= set(all_)
