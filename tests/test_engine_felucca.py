"""Drawbar, Trio and Phase Bend: three engines of Felucca (Leo Kuroshita,
Hügelton Instruments; GPL-3.0-only), WHEEL, TRIO and PHASE, vendored
unmodified in engines/third_party/felucca and played through our API by
engines/src/felucca_shim.cc and felucca_bridge.c (engines/README.md, "The
Felucca engines"). GPL modules: the whole file skips with the GPL switch off.

- The oracle (fm1-felucca-oracle, engines/test/felucca_oracle.c): Felucca's
  own voice.c drives the same engine files on one part, with a sound in
  Felucca's integers, and our engine plays it through the API with its
  parameters in units, computed here from Felucca's own curves. Every
  factory sound of the three engines (read here from the vendored sources)
  and their defaults give the same samples, bit for bit, through a phrase
  with a chord, overlaps, accents, retriggers and steals past the eight
  voices, at host blocks of 1, 7, 32 and 64 and at 44,100 and 44,118 Hz:
  the voice code, the envelope, the modulation and the parameter maps are
  Felucca's.
- Listen-free checks: finite output, no subnormal sample, nothing past full
  scale for a chord at the defaults; every list value at the parameters'
  extremes, the lowest and highest keys and full bends, finite; the rate
  band; the same output from any instance memory and at any host block;
  two instances in one process stay apart (WHEEL's state is lent to its
  arrays per call); the lists read at note-on keep a sounding note;
  Drawbar's lists switch without a step; per-note offsets as the API
  defines them, on lone notes.
"""
import json
import math
import re
import struct
import subprocess
import wave

import pytest

from tests.engine_helpers import ENGINES, GPL_MODS, RATE, cents, pitch_hz, render, renderer  # noqa: F401

pytestmark = pytest.mark.skipif(not GPL_MODS, reason="GPL modules: built only with FM1_GPL_MODS=1")

ORACLE = ENGINES / "build" / "fm1-felucca-oracle"
SRC = ENGINES / "third_party" / "felucca" / "src"
IDS = ["drawbar", "trio", "phase-bend"]
FEL = {"drawbar": "eng_wheel.c", "trio": "eng_trio.c", "phase-bend": "eng_phase.c"}

# A phrase in 32-sample blocks: a chord, an overlap, accents (velocity above
# 110 opens the filter), a key struck again while it sounds, ten keys held
# at once (two steals past the eight voices), releases, and a tail.
PHRASE = (["0:48:100", "0:55:90", "0:60:120", "0:64:80", "40:67:127", "60:60:100"]
          + [f"{80 + 2 * i}:{40 + 3 * i}:{60 + 6 * i}" for i in range(8)]
          + ["150:-48", "150:-55", "160:72:115", "200:-60", "200:-64", "210:-67", "220:-72"]
          + [f"{260 + i}:-{40 + 3 * i}" for i in range(8)])
BLOCKS = 700


def phrase_args():
    out = []
    for ev in PHRASE:
        b, k = ev.split(":")[:2]
        if k.startswith("-"):
            out += ["--off", f"{b}:{k[1:]}"]
        else:
            out += ["--on", ev]
    return out


@pytest.fixture(scope="module")
def listing(renderer):
    out = subprocess.run([str(renderer), "--list"], check=True, capture_output=True, text=True)
    return {e["id"]: e for e in json.loads(out.stdout)}


@pytest.fixture(scope="module")
def oracle(renderer):
    assert ORACLE.is_file(), "make -C engines builds fm1-felucca-oracle with the switch on"
    return ORACLE


def run_oracle(oracle, engine, *args):
    res = subprocess.run([str(oracle), engine, *args], capture_output=True, text=True)
    assert res.returncode in (0, 1), res.stderr
    return json.loads(res.stdout)


# ---- Felucca's sounds, read from its sources ---------------------------------------------------

def presets(engine):
    """(name, e[8], env[4], fenv, mono) of the engine's preset_t table."""
    src = (SRC / FEL[engine]).read_text()
    table = src[src.index("_PRESETS[] = {"):]
    table = table[:table.index("};")]
    row = re.compile(r'\{"([^"]+)", \{([^}]*)\}, \{([^}]*)\}, (-?\d+), (\d+)')
    out = []
    for m in row.finditer(table):
        e = [int(x) for x in m.group(2).split(",")]
        env = [int(x) for x in m.group(3).split(",")]
        out.append((m.group(1), e + [0] * (8 - len(e)), env, int(m.group(4)), int(m.group(5))))
    assert out, engine
    return out


def edit_defaults(engine):
    """The engine's EDIT defaults (engine_t.edit[k].def)."""
    src = (SRC / FEL[engine]).read_text()
    edit = src[src.index(".edit = {"):]
    edit = edit[:edit.index("},\n    .presets")]
    rows = re.findall(r'\{"[^"]*", F_\w+, (-?\d+), (-?\d+), (-?\d+),', edit)
    assert len(rows) == 8, engine
    return [int(d) for _, _, d in rows]


def g(x):
    return f"{x:.9g}"


def ms(v):
    """Felucca's time curve (gen_tables.py): 10,000^(v / 127) ms."""
    return 10000.0 ** (v / 127.0)


def pct(v):
    return v / 1.27


def hz(v):
    """Felucca's cutoff curve: 30 x (16,000 / 30)^(v / 127) Hz."""
    return 30.0 * (16000.0 / 30.0) ** (v / 127.0)


def units(engine, e, env, fenv):
    """Our parameters for a Felucca sound, in their units."""
    p = []
    if engine == "drawbar":
        p += [f"Drawbars={e[0]}", f"Sub={e[1]}", f"Body={e[2]}", f"Top={e[3]}", f"Perc={e[4]}",
              f"Click={g(pct(e[5]))}", f"Drive={g(pct(e[6]))}", f"Rotor={e[7]}"]
        assert fenv == 0
    elif engine == "trio":
        p += [f"Wave={e[0]}", f"Int 2={e[1]}", f"Int 3={e[2]}", f"Detune={e[3]}", f"Mode={e[4]}",
              f"Cutoff={g(hz(e[5]))}", f"Resonance={g(pct(e[6]))}", f"PW={g(pct(e[7]))}",
              f"Env Amt={g(fenv / 0.64)}"]
    else:
        p += [f"Wave={e[0]}", f"Wave 2={e[1]}", f"DCW={g(pct(e[2]))}", f"Env={g(pct(e[3]))}",
              f"Detune={e[4]}", f"Line={e[5]}", f"Sub={g(pct(e[6]))}"]
        assert fenv == 0 and e[7] == 0
    p += [f"Attack={g(ms(env[0]))}", f"Decay={g(ms(env[1]))}", f"Sustain={g(pct(env[2]))}",
          f"Release={g(ms(env[3]))}"]
    return p


def fel_args(e, env, fenv):
    spec = ",".join([f"E{k}={v}" for k, v in enumerate(e)]
                    + [f"ATK={env[0]}", f"DEC={env[1]}", f"SUS={env[2]}", f"REL={env[3]}", f"FLT={fenv}"])
    return ["--fel", spec]


def sound_args(engine, e, env, fenv):
    out = fel_args(e, env, fenv)
    for kv in units(engine, e, env, fenv):
        out += ["--param", kv]
    return out


PRESETS = [(engine, i) for engine in IDS for i in range(len(presets(engine)))]


# ---- The engines ------------------------------------------------------------------------------

def test_the_three_engines(listing):
    """Sound engines of eight voices, GPL in the licence table, with
    Felucca's code from its own directory; at most 14 parameters (the
    modulation runtime's records, tests/test_engines_mod_runtime.py), four
    to a page, Glide and Voice Mode only where they fit (Phase Bend)."""
    for eid, name, n in (("drawbar", "Drawbar", 13), ("trio", "Trio", 14), ("phase-bend", "Phase Bend", 14)):
        e = listing[eid]
        assert (e["name"], e["kind"], e["max_voices"], e["pads"]) == (name, "sound", 8, None)
        assert e["licence"] == "GPL-3.0-only AND MIT" and e["source"] == "engines/third_party/felucca"
        assert "Felucca" in e["credits"] and "Leo Kuroshita" in e["credits"]
        assert len(e["params"]) == n
        pages = [p["page"] for p in e["params"]]
        assert all(pages.count(k) <= 4 for k in set(pages)) and pages == sorted(pages)
        assert all(len(p["name"]) <= 12 for p in e["params"])
        names = {p["name"] for p in e["params"]}
        assert ({"Glide", "Voice Mode"} <= names) == (eid == "phase-bend")
        assert e["params"][0]["type"] == 1, "ALGORITHM turns the first list"


def test_the_oracle_is_felucca(oracle):
    """The sources the oracle and the bridge include are upstream's, byte for
    byte, and the generated tables are gen_tables.py's (UPSTREAM.md)."""
    clone = ENGINES.parent / "reference" / "Felucca"
    if not (clone / ".git").exists():
        pytest.skip("no clone of Felucca at reference/Felucca")
    res = subprocess.run(["python3", str(ENGINES / "third_party" / "felucca" / "vendor.py"), str(clone),
                          "--check"], capture_output=True, text=True)
    assert res.returncode == 0, res.stderr


@pytest.mark.parametrize("engine,index", PRESETS)
def test_every_factory_sound_is_feluccas_bit_for_bit(oracle, engine, index):
    """The factory sound through our API, its parameters in units, against
    Felucca's voice.c with the sound's integers: the same samples. (A MONO
    sound plays here in POLY on both sides: the voice mode is the host's.)"""
    name, e, env, fenv, _ = presets(engine)[index]
    r = run_oracle(oracle, engine, "--rate", "44118", "--host-block", "64", "--blocks", str(BLOCKS),
                   *sound_args(engine, e, env, fenv), *phrase_args())
    assert r["identical"], (name, r)
    assert r["loud"] > 5000 and r["peak"] > 0.01, name
    assert r["ours_nonfinite"] == 0 and r["ours_subnormal"] == 0, name


@pytest.mark.parametrize("engine", IDS)
@pytest.mark.parametrize("host_block,rate", [("1", "44118"), ("7", "44100"), ("32", "44100")])
def test_any_host_block_and_both_rates(oracle, engine, host_block, rate):
    """The first factory sound at host blocks of 1, 7 and 32 frames and at
    44,100 Hz (Felucca's tables' rate) and 44,118 Hz: still Felucca's."""
    _, e, env, fenv, _ = presets(engine)[0]
    r = run_oracle(oracle, engine, "--rate", rate, "--host-block", host_block, "--blocks", str(BLOCKS),
                   *sound_args(engine, e, env, fenv), *phrase_args())
    assert r["identical"], r


@pytest.mark.parametrize("engine", IDS)
def test_the_defaults_are_feluccas(oracle, engine):
    """Our defaults are the engine's EDIT defaults with Felucca's part
    envelope (attack 10, decay 70, sustain 90, release 60), or, for
    Drawbar, the envelope all five of WHEEL's sounds share (0, 64, 127,
    45), and no envelope to the filter: no --param, the same samples."""
    env = [0, 64, 127, 45] if engine == "drawbar" else [10, 70, 90, 60]
    r = run_oracle(oracle, engine, "--blocks", "400", *fel_args(edit_defaults(engine), env, 0),
                   *phrase_args())
    assert r["identical"], r


# ---- Listen-free checks -----------------------------------------------------------------------

def run(renderer, tmp_path, name, engine, params=(), notes=(), extra=(), seconds=0.8):
    """(summary, WAV bytes, left channel as int16)."""
    s, _, wav = render(renderer, tmp_path, engine, params=list(params), notes=list(notes),
                       seconds=seconds, name=name, extra=list(extra))
    with wave.open(str(wav), "rb") as w:
        raw = w.readframes(w.getnframes())
    left = [int.from_bytes(raw[i:i + 2], "little", signed=True) for i in range(0, len(raw), 4)]
    assert s["nonfinite"] == 0
    return s, wav.read_bytes(), left


CHORD = ["0:48:100:1.0", "0:55:100:1.0", "0:60:100:1.0", "0:64:100:1.0"]


@pytest.mark.parametrize("engine", IDS)
def test_a_chord_at_the_defaults_stays_inside_full_scale(renderer, tmp_path, engine):
    """Four notes at the defaults: finite, under full scale before the bus
    limiter (raw_peak, raw_clipped), and not quiet."""
    s, _, _ = run(renderer, tmp_path, "chord", engine, notes=CHORD, seconds=1.4)
    assert s["raw_clipped"] == 0 and s["raw_peak"] < 1.0, s
    assert s["rms"] > 0.02, s


@pytest.mark.parametrize("engine", IDS)
def test_every_factory_sound_in_a_chord(renderer, oracle, engine):
    """Every factory sound, the oracle's phrase (up to ten keys, accents):
    finite, no subnormal sample, inside full scale."""
    for name, e, env, fenv, _ in presets(engine):
        r = run_oracle(oracle, engine, "--blocks", str(BLOCKS), *sound_args(engine, e, env, fenv),
                       *phrase_args())
        assert r["ours_nonfinite"] == 0 and r["ours_subnormal"] == 0, name
        assert r["ours_peak"] < 1.0, (name, r["ours_peak"])


def lists(listing, engine):
    return [p for p in listing[engine]["params"] if p["type"] == 1]


@pytest.mark.parametrize("engine", IDS)
@pytest.mark.parametrize("end", ["min", "max"])
def test_every_list_value_at_the_extremes_renders_finite(renderer, tmp_path, listing, engine, end):
    """Every value of every list, every other parameter at an end, keys 0
    and 127 with velocities 1 and 127, bends of +/-48 over them: finite (and,
    under the sanitizer build, no undefined behaviour)."""
    ps = listing[engine]["params"]
    floats = [f"{p['name']}={p[end]:.9g}" for p in ps if p["type"] == 0]
    notes = ["0:0:127:0.15", "0:127:1:0.15", "0.05:64:127:0.1"]
    for p in lists(listing, engine):
        for k in range(int(p["max"]) + 1):
            others = [f"{q['name']}={int(q[end])}" for q in lists(listing, engine) if q is not p]
            s, _, _ = run(renderer, tmp_path, "x", engine, floats + others + [f"{p['name']}={k}"], notes,
                          ["--bend", "0:48", "--bend", "0.08:-48", "--frames", "7"], seconds=0.3)
            assert s["nonfinite"] == 0, (p["name"], k)


@pytest.mark.parametrize("engine", IDS)
def test_nan_and_infinities_clamp(renderer, tmp_path, listing, engine):
    """NaN is the default and +/-inf an end, as set_param clamps them."""
    _, plain, _ = run(renderer, tmp_path, "plain", engine, notes=CHORD[:2], seconds=0.3)
    for p in listing[engine]["params"]:
        if p["type"] == 1:
            continue
        _, nan, _ = run(renderer, tmp_path, "nan", engine, [f"{p['name']}=nan"], CHORD[:2], seconds=0.3)
        assert nan == plain, p["name"]
        for value, end in (("inf", p["max"]), ("-inf", p["min"])):
            _, a, _ = run(renderer, tmp_path, "a", engine, [f"{p['name']}={value}"], CHORD[:2], seconds=0.3)
            _, b, _ = run(renderer, tmp_path, "b", engine, [f"{p['name']}={end:.9g}"], CHORD[:2], seconds=0.3)
            assert a == b, (p["name"], value)


@pytest.mark.parametrize("engine", IDS)
def test_the_rate_band(renderer, tmp_path, engine):
    """Felucca's tables are for 44,100 Hz: the engines play at 44,100 and
    44,118 Hz (the FM-1's rate, as Felucca does there) and refuse a host
    outside 44,100 Hz +/- 0.25 %, where they would be out of tune."""
    for rate in ("44100", "44118", "44000", "44200"):
        res = subprocess.run([str(renderer), "--engine", engine, "--rate", rate, "--note", "0:60:100:0.1",
                              "--seconds", "0.2", "--out", str(tmp_path / "r.wav")],
                             capture_output=True, text=True)
        assert res.returncode == 0, (rate, res.stderr)
    for rate in ("48000", "22050", "43900", "44300", "96000"):
        res = subprocess.run([str(renderer), "--engine", engine, "--rate", rate, "--note", "0:60:100:0.1",
                              "--seconds", "0.2", "--out", str(tmp_path / "r.wav")],
                             capture_output=True, text=True)
        assert res.returncode != 0 and "refused" in res.stderr, rate


@pytest.mark.parametrize("engine", IDS)
def test_the_pitch_is_feluccas_at_44118(renderer, tmp_path, engine):
    """A4 on a steady tone sounds 440 Hz x 44,118 / 44,100 at the FM-1's
    rate: 0.7 cent sharp, as Felucca plays on an FM-1 (its tables are for
    44,100 Hz)."""
    tone = {"drawbar": ["Drawbars=0", "Rotor=0", "Click=0", "Sustain=100"],
            "trio": ["Wave=4", "Int 2=0", "Int 3=0", "Detune=0", "Cutoff=16000", "Sustain=100"],
            "phase-bend": ["DCW=0", "Env=0", "Sustain=100"]}[engine]
    _, _, x, = run(renderer, tmp_path, "a4", engine, tone, ["0:69:100:1.6"], seconds=1.6)
    f = pitch_hz([v / 32767.0 for v in x], 0.3, 1.0)
    assert cents(f, 440.0) == pytest.approx(1200 * math.log2(44118 / 44100), abs=0.2)   # 0.71


def at(frame):
    """A time fm1-render applies at `frame` at host blocks of 1, 7 and 64
    alike: frames that are multiples of 448 (it applies an event at the
    first block start at or after its time)."""
    assert frame % 448 == 0
    return "0" if frame == 0 else f"{(frame - 0.5) / RATE:.9f}"


def span(f0, f1):
    return f"{(f1 - f0) / RATE:.9f}"


BUSY = ([f"{at(0)}:48:100:{span(0, 448 * 50)}", f"{at(0)}:55:120:{span(0, 448 * 50)}",
         f"{at(448 * 15)}:60:90:{span(0, 448 * 40)}", f"{at(448 * 30)}:67:127:{span(0, 448 * 30)}"]
        + [f"{at(448 * (35 + i))}:{50 + i}:100:{span(0, 448 * 20)}" for i in range(9)])


@pytest.mark.parametrize("engine", IDS)
def test_the_same_at_any_host_block_and_from_any_memory(renderer, tmp_path, listing, engine):
    """A busy phrase, past the eight voices, with every FLOAT turned while it
    sounds and two bends: the same bytes at host blocks of 1, 7 and 64, and
    from instance memory filled with 0, 0xA5 and 0xFF. Every event is on a
    frame all three host blocks start at (a multiple of 448), so it reaches
    the same 32-sample block of the engine."""
    extra = ["--bend", f"{at(448 * 20)}:2.5", "--bend", f"{at(448 * 45)}:-1"]
    for i, p in enumerate(q for q in listing[engine]["params"] if q["type"] == 0):
        v = p["min"] + (p["max"] - p["min"]) * (0.25 + 0.05 * (i % 6))
        extra += ["--param-at", f"{at(448 * (10 + 2 * i))}:{p['name']}={v:.6g}"]
    outs = []
    for frames, fill in (("64", "0"), ("1", "0xA5"), ("7", "0xFF"), ("64", "0xFF")):
        _, w, _ = run(renderer, tmp_path, f"b{frames}{fill}", engine, notes=BUSY,
                      extra=extra + ["--frames", frames, "--fill", fill], seconds=1.2)
        outs.append(w)
    assert all(o == outs[0] for o in outs[1:])


@pytest.mark.parametrize("engine", IDS)
def test_two_instances_stay_apart(renderer, tmp_path, engine):
    """Two instances in one process (two sound units, at half level each):
    a second unit that plays nothing leaves the first's output as it was,
    byte for byte (Drawbar lends its state to WHEEL's arrays per call, and
    its rotor turns while silent), and two units playing are the two
    played apart, summed (to the 16-bit rounding of each)."""
    notes = ["0:57:100:0.5", "0.1:64:100:0.4"]
    slots = ["--slots", "--level", "0:50"]
    unit1 = ["--sound", f"1:{engine}", "--level", "1:50"]

    def ints(wav):
        with wave.open(str(wav), "rb") as w:
            raw = w.readframes(w.getnframes())
        return struct.unpack(f"<{len(raw) // 2}h", raw)
    _, _, alone = render(renderer, tmp_path, engine, notes=notes, seconds=0.8, name="alone", extra=slots)
    _, _, idle = render(renderer, tmp_path, engine, notes=notes, seconds=0.8, name="idle",
                        extra=slots + unit1)
    assert idle.read_bytes() == alone.read_bytes()
    _, _, two = render(renderer, tmp_path, engine, notes=notes, seconds=0.8, name="two",
                       extra=slots + unit1 + ["--sound-note", "1:0.05:60:100:0.5"])
    _, _, other = render(renderer, tmp_path, engine, notes=[], seconds=0.8, name="other",
                         extra=slots + unit1 + ["--sound-note", "1:0.05:60:100:0.5"])
    a, b, c = ints(two), ints(alone), ints(other)
    assert max(a) > 300 and max(c) > 300
    assert max(abs(p - (q + r)) for p, q, r in zip(a, b, c)) <= 1


@pytest.mark.parametrize("engine,name", [("trio", "Wave"), ("trio", "Mode"), ("phase-bend", "Wave"),
                                         ("phase-bend", "Wave 2"), ("phase-bend", "Line")])
def test_a_list_read_at_note_on_keeps_a_sounding_note(renderer, tmp_path, listing, engine, name):
    """LATCH: a change reaches the notes that start after it. A held note
    plays on unchanged (byte for byte as without the change) until the next
    note, which takes the new value."""
    p = next(q for q in listing[engine]["params"] if q["name"] == name)
    to = int(p["max"]) if p["def"] != p["max"] else 0
    held = ["0:57:100:0.8"]
    _, a, _ = run(renderer, tmp_path, "a", engine, notes=held, extra=["--param-at", f"0.2:{name}={to}"])
    _, b, _ = run(renderer, tmp_path, "b", engine, notes=held)
    assert a == b
    later = held + ["0.4:64:100:0.3"]
    _, c, _ = run(renderer, tmp_path, "c", engine, notes=later, extra=["--param-at", f"0.2:{name}={to}"])
    _, d, _ = run(renderer, tmp_path, "d", engine, notes=later)
    assert c != d


@pytest.mark.parametrize("name,values", [("Drawbars", range(16)), ("Perc", range(7)),
                                         ("Rotor", range(3))])
def test_drawbar_lists_switch_without_a_step(renderer, tmp_path, name, values):
    """Drawbar's lists are read every block and glide (each partial's gain
    ramps over the block, the rotor eases): turned every 3 ms under a held
    chord, the output steps by no more than its own largest step held at
    any of the values, plus what a gain ramp over one block allows."""
    held = ["0:48:100:1.2", "0:60:100:1.2", "0:67:100:1.2"]
    base = ["Click=0"]

    def step(x):
        a = int(0.1 * RATE)
        return max(abs(x[i] - x[i - 1]) for i in range(a, len(x)))
    steady = 0
    for v in values:
        _, _, x = run(renderer, tmp_path, "s", "drawbar", base + [f"{name}={v}"], held, seconds=0.6)
        steady = max(steady, step(x))
    extra = []
    vs = list(values)
    for i in range(150):
        extra += ["--param-at", f"{0.15 + 0.003 * i:.3f}:{name}={vs[(i * 5) % len(vs)]}"]
    _, _, x = run(renderer, tmp_path, "t", "drawbar", base, held, extra, seconds=0.7)
    assert step(x) <= 1.5 * steady, (step(x), steady)


# ---- Per-note offsets, on lone notes ---------------------------------------------------------

def f32(x):
    return struct.unpack("<f", struct.pack("<f", x))[0]


def exact(x):
    return f"{f32(x):.9g}"


def poly(listing, engine):
    return [p for p in listing[engine]["params"] if "poly" in p["flags"]]


TONE = {"drawbar": [], "trio": ["Wave=1"], "phase-bend": []}


def test_which_parameters_take_per_note_offsets(listing):
    """The FLOATs a voice reads itself: everywhere the envelope and Volume;
    Trio's and Phase Bend's knobs too (read in each voice's render).
    Drawbar's bars, click and drive are the part's (WHEEL reads them once a
    block for all its voices), and Glide is between notes, not of one."""
    assert [p["name"] for p in poly(listing, "drawbar")] == ["Attack", "Decay", "Sustain", "Release", "Volume"]
    assert [p["name"] for p in poly(listing, "trio")] == \
        ["Int 2", "Int 3", "Detune", "Cutoff", "Resonance", "PW", "Env Amt", "Attack", "Decay", "Sustain",
         "Release", "Volume"]
    assert [p["name"] for p in poly(listing, "phase-bend")] == \
        ["DCW", "Env", "Detune", "Sub", "Attack", "Decay", "Sustain", "Release", "Volume"]


@pytest.mark.parametrize("engine", IDS)
def test_an_offset_on_a_lone_note_is_a_base_change(renderer, tmp_path, listing, engine):
    """Each POLY parameter's offset from the note-on is, for a note alone,
    the base moved by as much, byte for byte; mid-note a second offset and
    0 compare with the same offsets against a base that holds the first
    (an offset is not ramped, a base change would be)."""
    note = ["0:60:110:0.35"]
    for p in poly(listing, engine):
        b0 = p["def"]
        span = p["max"] - p["min"]
        sign = 1 if b0 + span / 4 <= p["max"] else -1
        x, y = sign * span / 4, sign * span / 8
        _, a, _ = run(renderer, tmp_path, "a", engine, TONE[engine], note,
                      ["--note-param-at", f"0:60:{p['name']}={exact(x)}",
                       "--note-param-at", f"0.2:60:{p['name']}={exact(y)}",
                       "--note-param-at", f"0.5:60:{p['name']}=0"], seconds=0.7)
        _, b, _ = run(renderer, tmp_path, "b", engine, TONE[engine], note,
                      ["--param-at", f"0:{p['name']}={exact(f32(f32(b0) + f32(x)))}",
                       "--note-param-at", f"0.2:60:{p['name']}={exact(y - x)}",
                       "--note-param-at", f"0.5:60:{p['name']}={exact(-x)}"], seconds=0.7)
        assert a == b, p["name"]


@pytest.mark.parametrize("engine", IDS)
def test_a_pitch_offset_on_a_lone_note_is_a_bend(renderer, tmp_path, engine):
    for semis in (7, -12, 0.5, 0.03):
        _, a, _ = run(renderer, tmp_path, "a", engine, TONE[engine], ["0:60:100:0.35"],
                      ["--note-pitch-at", f"0:60:{semis}", "--note-pitch-at", "0.25:60:-3"], seconds=0.5)
        _, b, _ = run(renderer, tmp_path, "b", engine, TONE[engine], ["0:60:100:0.35"],
                      ["--bend", f"0:{semis}", "--bend", "0.25:-3"], seconds=0.5)
        assert a == b, semis


@pytest.mark.parametrize("engine", IDS)
def test_offsets_end_with_their_voice_and_ignore_the_rest(renderer, tmp_path, listing, engine):
    """A retrigger starts at no offset; indices that are not POLY, past the
    table, and keys no voice sounds are ignored; NaN is no offset; +/-inf
    pin the parameter at an end."""
    vol = next(p for p in poly(listing, engine) if p["name"] == "Volume")
    notes = ["0:60:100:0.6", "0.3:60:100:0.3"]
    _, a, _ = run(renderer, tmp_path, "a", engine, TONE[engine], notes,
                  ["--note-param-at", "0:60:Volume=-0.4", "--note-pitch-at", "0:60:3"])
    _, b, _ = run(renderer, tmp_path, "b", engine, TONE[engine], notes,
                  ["--note-param-at", "0:60:Volume=-0.4", "--note-pitch-at", "0:60:3",
                   "--note-param-at", "0.3:60:Volume=0", "--note-pitch-at", "0.3:60:0"])
    assert a == b
    ignored = [f"#{i}" for i, p in enumerate(listing[engine]["params"]) if "poly" not in p["flags"]]
    ignored += [f"#{len(listing[engine]['params'])}", "#999", "#65534"]
    extra = []
    for idx in ignored:
        extra += ["--note-param-at", f"0:60:{idx}=0.7"]
    extra += ["--note-param-at", "0.1:99:Volume=-0.5", "--note-pitch-at", "0.1:99:12",
              "--note-param-at", "0:60:Sustain=nan", "--note-pitch-at", "0:60:nan"]
    _, plain, _ = run(renderer, tmp_path, "plain", engine, TONE[engine], notes[:1])
    _, c, _ = run(renderer, tmp_path, "c", engine, TONE[engine], notes[:1], extra)
    assert c == plain
    _, d, _ = run(renderer, tmp_path, "d", engine, TONE[engine], notes[:1],
                  ["--note-param-at", "0:60:Volume=inf"])
    _, e, _ = run(renderer, tmp_path, "e", engine, TONE[engine] + [f"Volume={vol['max']}"], notes[:1])
    assert d == e
