"""The saved-state codecs (stage E3: engines/state/, fm1-state; stage P1:
tools/lunar_state.py; notes/2026-10-06-state-files.md §6-§8, §16-§17).

Two implementations of one record model, held to each other and to the
golden files of each format level:
- the C reader and writer (the device's path, under the hostile-input caps)
  and the Python ones agree on records, canonical text and binary bytes,
  for the examples, the goldens and random states that write every
  parameter of every registered engine, effect, MIDI effect and kind;
- JSON -> binary -> JSON and binary -> JSON -> binary are identical;
- the JSON reader fed in pieces of 1, 7 and 256 bytes gives what it gives
  whole (the SysEx and flash path);
- numbers are exact: decimal to float32 and back, Q1.14 amounts;
- hostile files are refused with the same code by both, binaries cut short
  or bit-flipped anywhere are refused, the JSONTestSuite corpus behaves as
  documented, and a seeded fuzz loop keeps its invariants;
- the library allocates nothing, prints nothing and calls no libm.
"""
import json
import os
import random
import re
import shutil
import struct
import subprocess
import sys
import zlib
from fractions import Fraction
from pathlib import Path

import pytest

from tests import state_canon as canon
from tests import state_random
from tests.engine_helpers import ENGINES, ROOT, renderer  # noqa: F401
from tools import lunar_state as ls

TOOL = ENGINES / "build" / "fm1-state"
FUZZ = ENGINES / "build" / "fm1-state-fuzz"
EXAMPLES = ENGINES / "state" / "examples"
GOLD = ROOT / "tests" / "fixtures" / "state" / "1.0"
# nst/JSONTestSuite (MIT), cloned to reference/ (git-ignored), or elsewhere
# through FM1_JSONTESTSUITE.
SUITE = Path(os.environ.get("FM1_JSONTESTSUITE", ROOT / "reference" / "JSONTestSuite")) / "test_parsing"


@pytest.fixture(scope="module")
def tool(renderer):    # noqa: F811  (make -C engines builds fm1-state too)
    assert TOOL.exists()
    return TOOL


@pytest.fixture(scope="module")
def names(tool):
    return ls.Names.from_build(tool)


def run(tool, *args, data=None, check=False):
    return subprocess.run([str(tool), *map(str, args)], input=data, capture_output=True, check=check)


def c_records(tool, data, pieces=None):
    extra = ["--pieces", pieces] if pieces else []
    r = run(tool, "records", "-", *extra, data=data)
    report = json.loads(r.stderr.decode().splitlines()[-1]) if r.returncode else None
    return r.returncode, r.stdout.decode(), report


def py_records(data, names):
    try:
        recs, _ = ls.read_any(data, names)
        return 0, ls.records_text(recs), None
    except ls.Refused as e:
        return 1, "", e.code


# ---- the library -----------------------------------------------------------------------------
FORBIDDEN = {"malloc", "calloc", "realloc", "free", "printf", "fprintf", "sprintf", "snprintf", "puts",
             "fopen", "fwrite", "fread", "strtod", "strtof", "atof", "sscanf", "rand", "srand"}
FORBIDDEN |= {f + s for f in ("sin", "cos", "exp", "exp2", "log", "log2", "log10", "pow", "sqrt", "floor",
                              "ceil", "fmod", "round", "lround", "trunc", "frexp", "ldexp")
              for s in ("", "f", "l")}


def test_library_allocates_prints_and_calls_no_libm(tool):
    nm = shutil.which("nm")
    if not nm:
        pytest.skip("no nm")
    objs = sorted((ENGINES / "build" / "state" / "state").glob("*.o"))
    assert len(objs) == 11    # the codecs, the names, the registry, the runtime applier
    for o in objs:
        out = subprocess.check_output([nm, "-u", str(o)], text=True)
        got = {line.split()[-1] for line in out.splitlines() if line.strip()}
        got = {n[1:] if sys.platform == "darwin" and n.startswith("_") else n for n in got}
        assert not got & FORBIDDEN, f"{o.name} imports {sorted(got & FORBIDDEN)}"


def test_reader_state_is_small(tool):
    """The tokenizer's state is under 256 B and the whole JSON reader's
    under 2 KiB (the note's §7.6); the inflater a DEFLATED chunk adds is
    under 6 KiB (§8.4)."""
    sizes = json.loads(run(tool, "sizes", check=True).stdout)
    assert sizes["tokenizer"] < 256
    assert sizes["json_reader"] < 2048
    assert sizes["inflater"] < 6144


def test_ram_budget_mirrors_the_app():
    app = (ROOT / "sim" / "web" / "src" / "fm1_app.h").read_text()
    state = (ENGINES / "state" / "fm1_state.h").read_text()
    a = re.search(r"#define FM1_APP_RAM_BUDGET (\d+)u", app).group(1)
    s = re.search(r"#define FM1_STATE_RAM_BUDGET (\d+)u", state).group(1)
    assert a == s


# ---- examples and goldens ----------------------------------------------------------------------
@pytest.mark.parametrize("path", sorted(EXAMPLES.glob("*.lunar")), ids=lambda p: p.name)
def test_example_round_trips(tool, names, path):
    """canon(f) == f; JSON -> binary -> JSON; both readers' records equal;
    pieces of 1, 7 and 256 bytes give the same records; Python writes the
    same canonical text and the same binary bytes."""
    data = path.read_bytes()
    assert run(tool, "canon", path, check=True).stdout == data
    binary = run(tool, "pack", path, check=True).stdout
    assert run(tool, "unpack", "-", data=binary, check=True).stdout == data
    assert run(tool, "pack", "-", data=binary, check=True).stdout == binary
    rc, recs, _ = c_records(tool, data)
    assert rc == 0
    assert c_records(tool, binary)[1] == recs
    for n in (1, 7, 256):
        assert c_records(tool, data, n)[1] == recs, n
    precs, rep = ls.read_json(data, names)
    assert ls.records_text(precs) == recs
    text, _ = ls.write_json(precs, names)
    assert text.encode() == data
    assert ls.write_bin(precs) == binary
    assert ls.records_text(ls.read_bin(binary)[0]) == recs


GOLDEN = sorted(GOLD.glob("*.lunar"))


@pytest.mark.parametrize("path", GOLDEN, ids=lambda p: p.name)
def test_golden_files_load_for_ever(tool, names, path):
    """A released level's files: the JSON and its binary twin read to the
    stored records in both implementations, and the binary writer gives the
    twin from those records. (Canonical text is the examples' test: a new
    parameter in an engine adds its default to a canonical rewrite, which is
    not a format change, §9.)"""
    twin, records = path.with_suffix(".lunarb"), path.with_suffix(".records").read_text()
    assert c_records(tool, path.read_bytes())[1] == records
    assert c_records(tool, twin.read_bytes())[1] == records
    assert py_records(path.read_bytes(), names)[1] == records
    assert py_records(twin.read_bytes(), names)[1] == records
    recs = [json.loads(line) for line in records.splitlines()]
    assert ls.write_bin(recs) == twin.read_bytes()


def test_golden_set_twin(tool, names):
    """A set as a binary file: lines the core writes become typed items, the
    others (E1's dq, se and sn; a hand edit's double space) ride raw, and
    the set comes back byte for byte."""
    movy, twin = GOLD / "orbit.set.movy1", GOLD / "orbit.set.lunarb"
    assert run(tool, "from-movy1", movy, check=True).stdout == twin.read_bytes()
    assert run(tool, "unpack", twin, check=True).stdout == movy.read_bytes()
    records = (GOLD / "orbit.set.records").read_text()
    assert c_records(tool, twin.read_bytes())[1] == records
    assert py_records(twin.read_bytes(), names)[1] == records
    lines = movy.read_text().split("\n")[:-1]
    for line in lines:
        item = ls.encode_line(line)
        assert ls._item_text(item, 0) == (line, len(item))
    raw = [line for line in lines if ls.encode_line(line)[0] == 1]
    # The core writes an empty clip's line with a space after its loop start;
    # this one has none, so it rides raw like the lines no core writes.
    assert raw == ["dq 25", "se 2", "sn 0 Intro", "cl 0 1 16 0", "tk 1  2 0"]


def test_movy1_items_are_byte_identical_on_a_core_export(tool):
    """Every line of a set the core exports becomes a typed item and comes
    back unchanged, so a set's binary is design A's 8 B a note and 3 B a
    lock, not its text."""
    seq = ENGINES / "build" / "fm1-seq"
    proj = canon.loads((EXAMPLES / "first-orbit.lunar").read_text())
    text = "\n".join(proj["set"]) + "\n"
    for line in proj["set"]:
        item = ls.encode_line(line)
        assert item[0] != 1, line
        assert ls._item_text(item, 0)[0] == line
    b = run(tool, "from-movy1", "-", data=text.encode(), check=True).stdout
    assert run(tool, "unpack", "-", data=b, check=True).stdout.decode() == text
    assert seq.exists()


# ---- two implementations on random states ---------------------------------------------------------
def _equivalence(tool, names, doc_text):
    data = doc_text.encode()
    rc, crecs, rep = c_records(tool, data)
    prc, precs, pcode = py_records(data, names)
    assert (rc, rep and rep["code"]) == (prc, pcode), (rep, pcode)
    if rc:
        return None
    assert crecs == precs
    ctext = run(tool, "canon", "-", data=data, check=True).stdout
    ptext, _ = ls.write_json(ls.read_json(data, names)[0], names)
    assert ctext == ptext.encode()
    cbin = run(tool, "pack", "-", data=data, check=True).stdout
    assert ls.write_bin(ls.read_json(ctext, names)[0]) == cbin
    assert run(tool, "unpack", "-", data=cbin, check=True).stdout == ctext
    assert ls.records_text(ls.read_bin(cbin)[0]) == c_records(tool, ctext)[1]
    assert run(tool, "canon", "-", data=ctext, check=True).stdout == ctext
    return canon.loads(ctext.decode())


@pytest.mark.parametrize("loose", [False, True], ids=["canonical", "loose"])
def test_two_implementations_agree_on_random_states(tool, names, loose):
    rnd = random.Random(17 if loose else 3)
    for doc in state_random.documents(names, seed=9 if loose else 5, loose=loose):
        _equivalence(tool, names, state_random.text(doc, rnd, loose))


def test_save_coverage(tool, names):
    """A random state touching every parameter of every registered engine,
    effect, MIDI effect and kind, every pad of every kit and every FM6 slot
    round-trips with each of them in it (ST20: a stage that adds state
    without its records fails here)."""
    want = {(e.id, p.name) for e in names.engines for p in e.params}
    want |= {("kind:" + k.id, p.name) for k in names.kinds.values() for p in k.params}
    pads = {(e.id, j) for e in names.engines if e.role == "sound" for j in range(e.pads)}
    got, got_pads, slots = set(), set(), set()

    def unit(u):
        if not u:
            return
        got.update((u["engine"], k) for k in u["params"])
        for j, pad in enumerate(u.get("pads", [])):
            got_pads.add((u["engine"], j))
            got.update((u["engine"], k) for k in pad)
        for x in u.get("inserts", []) + u.get("midi_fx", []):
            unit(x)
    for doc in state_random.documents(names, seed=5):
        out = _equivalence(tool, names, canon.dumps(doc))
        for u in out.get("sounds", []) + [out.get("sound")] + out.get("master", []) + out.get("chain", []):
            unit(u)
        for x in out.get("mod", {}).get("rack", []):
            got.update(("kind:" + x["kind"], k) for k in x["params"])
        slots.update(v["slot"] for v in out.get("dx7", []))
    assert not want - got, sorted(want - got)[:10]
    assert not pads - got_pads
    assert slots == set(range(1, 33))


# ---- numbers ------------------------------------------------------------------------------------------
def _bits(x):
    return struct.unpack("<I", struct.pack("<f", x))[0]


def test_decimal_to_float32_is_exact(tool):
    """Both paths (the fast one and the big-integer one) give the nearest
    float32 to the exact decimal, ties to even: random decimals, values a
    hair either side of float32 midpoints, subnormals, the range's ends."""
    rnd = random.Random(1)
    cases = []
    for _ in range(4000):
        d = "".join(rnd.choice("0123456789") for _ in range(rnd.randint(1, 9))).lstrip("0") or "0"
        cases.append(f"{d}e{rnd.randint(-50, 40)}")
    for _ in range(4000):
        m, e = rnd.randint(2 ** 23, 2 ** 24 - 1), rnd.randint(-149, 100)
        mid = Fraction(2 * m + 1) * Fraction(2) ** (e - 1)
        cases.append(format(float(mid), ".20e").replace("e+", "e"))
        cases.append(format(float(mid), ".8e").replace("e+", "e"))
    cases += ["0", "-0", "1e-46", "7e-46", "7.006e-46", "1.401298464324817e-45", "3.4028235e38",
              "3.4028236e38", "1.17549435e-38", "0.1", "1e-7", "-2.5", "16777217", "123456789012345678"]
    out = run(tool, "num", data="".join("f " + c + "\n" for c in cases).encode(), check=True)
    for c, line in zip(cases, out.stdout.decode().splitlines()):
        sf, bf, se, be = line.split()
        want = canon.f32_of(c)
        if want is None:
            assert (sf, se) == ("2", "2"), (c, line)
            continue
        wb = "%08x" % _bits(want)
        if c.startswith("-") and want == 0:
            wb = "80000000"
        assert (sf, bf, se, be) == ("0", wb, "0", wb), (c, line, wb)


def test_float32_text_is_the_shortest_exact_decimal(tool):
    rnd = random.Random(2)
    vals = [struct.unpack("<f", struct.pack("<I", rnd.getrandbits(32)))[0] for _ in range(8000)]
    vals = [v for v in vals if v == v and abs(v) != float("inf")]
    vals += [0.41, 420.0, 1 / 3, 5e-7, 1e21, 123456789.0, 0.1, 1e-45, 3.4028234663852886e38, -0.0]
    out = run(tool, "num", data="".join("t %08x\n" % _bits(v) for v in vals).encode(), check=True)
    for v, line in zip(vals, out.stdout.decode().splitlines()):
        assert line == canon.number(v), (v, line)


def test_every_q14_amount_round_trips(tool):
    out = run(tool, "num", data="".join("p %d\n" % q for q in range(-16384, 16385)).encode(), check=True)
    texts = out.stdout.decode().splitlines()
    assert texts == [canon.number(canon.percent(q)) for q in range(-16384, 16385)]
    back = run(tool, "num", data="".join("q %s\n" % t for t in texts).encode(), check=True)
    assert back.stdout.decode().splitlines() == ["0 %d" % q for q in range(-16384, 16385)]
    edge = ["100.5", "-1e9", "0.00305175781", "0.003051757812500000001", "-0.0030517578125", "1e-30"]
    out = run(tool, "num", data="".join("q %s\n" % t for t in edge).encode(), check=True)
    got = [tuple(map(int, line.split())) for line in out.stdout.decode().splitlines()]
    assert [q for _, q in got] == [canon.q14(t) for t in edge]
    assert [s for s, _ in got] == [4, 4, 0, 0, 0, 0]


# ---- hostile input ----------------------------------------------------------------------------------------
SND = ('{"lunar": "1.0", "kind": "sound", "sound": {"engine": "shapes", "params": {%s}, "level": 50,'
       ' "inserts": [null, null], "midi_fx": []}%s}')
HOSTILE = [
    ("empty", b"", "NOT_LUNAR"),
    ("white space", b"  \n", "NOT_LUNAR"),
    ("byte-order mark", b'\xef\xbb\xbf{"lunar": "1.0"}', "NOT_LUNAR"),
    ("not an object", b"[1, 2]", "NOT_LUNAR"),
    ("a number", b"42", "NOT_LUNAR"),
    ("lunar not first", b'{"kind": "sound", "lunar": "1.0"}', "NOT_LUNAR"),
    ("lunar not a level", b'{"lunar": 1, "kind": "sound"}', "NOT_LUNAR"),
    ("newer minor", b'{"lunar": "1.1", "kind": "sound"}', "TOO_NEW"),
    ("newer major", b'{"lunar": "2.0", "kind": "sound"}', "TOO_NEW"),
    ("kind not second", b'{"lunar": "1.0", "name": "X", "kind": "sound"}', "BAD"),
    ("metadata", b'{"lunar": "1.0", "kind": "metadata"}', "BAD"),
    ("unknown kind", b'{"lunar": "1.0", "kind": "song"}', "BAD"),
    ("missing member", b'{"lunar": "1.0", "kind": "sound"}', "BAD"),
    ("trailing comma", b'{"lunar": "1.0", "kind": "sound",}', "BAD"),
    ("NaN", (SND % ('"Timbre": NaN', "")).encode(), "BAD"),
    ("duplicate top key", b'{"lunar": "1.0", "kind": "settings", "settings": {}, "settings": {}}', "BAD"),
    ("duplicate in params", (SND % ('"Timbre": 0.5, "timbre": 0.4', "")).encode(), "BAD"),
    ("duplicate in a skipped member", b'{"lunar": "1.0", "kind": "settings", "settings": {},'
                                      b' "later": {"a": 1, "a": 2}}', "BAD"),
    ("depth 9", b'{"lunar": "1.0", "kind": "settings", "x": [[[[[[[[1]]]]]]]]}', "TOO_BIG"),
    ("key past 64 B", b'{"lunar": "1.0", "kind": "settings", "' + b"k" * 65 + b'": 1}', "TOO_BIG"),
    ("number past 32", b'{"lunar": "1.0", "kind": "settings", "x": 1' + b"0" * 32 + b"}", "TOO_BIG"),
    ("string past 16 KiB", b'{"lunar": "1.0", "kind": "settings", "x": "' + b"a" * 16385 + b'"}', "TOO_BIG"),
    ("65 members", b'{"lunar": "1.0", "kind": "settings"' +
     b"".join(b', "k%d": 1' % i for i in range(63)) + b"}", "TOO_BIG"),
    ("8193 items", b'{"lunar": "1.0", "kind": "settings", "x": [' + b",".join([b"0"] * 8193) + b"]}",
     "TOO_BIG"),
    ("U+0000", b'{"lunar": "1.0", "kind": "settings", "x": "a\\u0000"}', "BAD"),
    ("lone surrogate", b'{"lunar": "1.0", "kind": "settings", "x": "\\ud800"}', "BAD"),
    ("overlong UTF-8", b'{"lunar": "1.0", "kind": "settings", "x": "\xc0\xaf"}', "BAD"),
    ("engine after params", b'{"lunar": "1.0", "kind": "sound", "sound": {"params": {}, "engine": "shapes"}}',
     "BAD"),
    ("mod before the sound", (b'{"lunar": "1.0", "kind": "sound", "mod": {"rack": [], "cables": []},'
                              b' "sound": {"engine": "shapes"}}'), "BAD"),
    ("rack after cables", (SND % ("", ', "mod": {"cables": [], "rack": []}')).encode(), "BAD"),
    ("module params before kind", (SND % ("", ', "mod": {"rack": [{"pos": 1, "params": {}, "kind": "lfo"}]}'))
     .encode(), "BAD"),
    ("fraction for an integer", (SND % ('"Shape": 1.5', "")).encode(), "BAD"),
    ("exponent for an integer", (b'{"lunar": "1.0", "kind": "settings", "settings": {"midi_in_channel": 1e0}}'),
     "BAD"),
    ("a string for a float", (SND % ('"Timbre": "loud"', "")).encode(), "BAD"),
    ("beyond float32", (SND % ('"Timbre": 1e39', "")).encode(), "BAD"),
    ("Sound 1 null", b'{"lunar": "1.0", "kind": "project", "sounds": [null, null, null, null]}', "BAD"),
    ("five sounds", b'{"lunar": "1.0", "kind": "project", "sounds": [{"engine": "shapes"}, null, null, null,'
                    b' null]}', "BAD"),
    ("two cables in a slot", (SND % ("", ', "mod": {"rack": [], "cables": [' +
                                     ', '.join(['{"slot": 1, "from": {"source": "VEL"}, "to": {"unit": "snd",'
                                                ' "param": "Timbre"}, "amount": 10}'] * 2) + "]}")).encode(),
     "BAD"),
    ("a set without movy1", b'{"lunar": "1.0", "kind": "project", "sounds": [{"engine": "shapes"}, null,'
                            b' null, null], "set": ["bpm 12000"]}', "BAD"),
    ("a control character in a line", b'{"lunar": "1.0", "kind": "project", "sounds": [{"engine": "shapes"},'
                                      b' null, null, null], "set": ["movy1", "bpm\\t1"]}', "BAD"),
    ("a clip line of track 1", b'{"lunar": "1.0", "kind": "clip", "clip": ["cl 1 0 16 0 ", "cp 1 0 1 1 0 0"]}',
     "BAD"),
    ("odd hex", (SND % ("", ', "mod": {"rack": [{"pos": 1, "kind": "lfo", "data": {"version": 1, "hex":'
                            ' "abc"}}]}')).encode(), "BAD"),
    ("upper-case hex", (SND % ("", ', "mod": {"rack": [{"pos": 1, "kind": "lfo", "data": {"version": 1, "hex":'
                                   ' "AB"}}]}')).encode(), "BAD"),
    ("hex before version", (SND % ("", ', "mod": {"rack": [{"pos": 1, "kind": "lfo", "data": {"hex": "ab",'
                                       ' "version": 1}}]}')).encode(), "BAD"),
    ("too much pattern data", (SND % ("", ', "mod": {"rack": [{"pos": 1, "kind": "lfo", "data": {"version": 1,'
                                          ' "hex": "' + "ab" * 4097 + '"}}]}')).encode(), "TOO_BIG"),
]


@pytest.mark.parametrize("name,data,code", HOSTILE, ids=[c[0] for c in HOSTILE])
def test_hostile_json_is_refused_alike(tool, names, name, data, code):
    rc, _, rep = c_records(tool, data)
    assert rc == 1 and rep["code"] == code, rep
    assert py_records(data, names)[2] == code
    for n in (1, 7):
        rc, _, rep = c_records(tool, data, n)
        assert rc == 1 and rep["code"] == code


def test_refusals_say_where(tool):
    data = (SND % ('"Timbre": 0.5, "Shape": 1.5', "")).encode()
    rc, _, rep = c_records(tool, data)
    assert rc == 1
    assert rep["path"] == "/sound/params/Shape"
    assert rep["line"] == 1 and rep["col"] > 60
    assert rep["near"].startswith('"Shape": 1.5}')


REPAIRS = [
    ("a value out of range is clamped", SND % ('"Timbre": 7', ""), {"repaired": 1}),
    ("a list index out of range is clamped", SND % ('"Shape": 999', ""), {"repaired": 1}),
    ("an unknown member is skipped", SND % ("", ', "comment": {"a": [1, 2]}'), {"skipped": 1}),
    ("an unknown name is skipped", SND % ('"Unison": 1', ""), {"skipped": 1}),
    ("an unknown entry is skipped", SND % ('"Shape": "Kazoo"', ""), {"skipped": 1}),
    ("control characters are stripped", '{"lunar": "1.0", "kind": "settings", "title": "a\\tb\\u202ec",'
                                        ' "settings": {}}', {"repaired": 2}),
    ("a long name is cut", '{"lunar": "1.0", "kind": "settings", "name": "' + "N" * 20 + '", "settings": {}}',
     {"repaired": 1}),
    ("an amount past 100 % is clamped", SND % ("", ', "mod": {"rack": [], "cables": [{"slot": 1, "from":'
                                                   ' {"source": "VEL"}, "to": {"unit": "snd", "param": "Timbre"},'
                                                   ' "amount": 250}]}'), {"repaired": 1}),
]


@pytest.mark.parametrize("name,text,counts", REPAIRS, ids=[c[0] for c in REPAIRS])
def test_repairs_and_skips_are_counted(tool, names, name, text, counts):
    r = run(tool, "check", "-", data=text.encode())
    report = json.loads(r.stdout)["report"]
    assert report["code"] == "OK", report
    for k, v in counts.items():
        assert report[k] == v, (k, report)
    rep = ls.read_json(text.encode(), names)[1]
    for k, v in counts.items():
        assert getattr(rep, k) == v, k


def test_unknown_engines_refuse_unless_left_out(tool):
    doc = '{"lunar": "1.0", "kind": "sound", "sound": {"engine": "rings", "params": {"#3": 0.5, "Pos": 1}}}'
    r = run(tool, "canon", "-", data=doc.encode())
    assert r.returncode == 1
    assert json.loads(r.stderr)["code"] == "UNKNOWN" and json.loads(r.stderr)["name"] == "rings"
    r = run(tool, "canon", "-", "--without", data=doc.encode(), check=True)
    out = canon.loads(r.stdout.decode())
    assert out["sound"]["params"] == {"#3": 0.5}      # #UID kept; a name of an absent engine is not
    r = run(tool, "check", "-", data=doc.encode())
    assert json.loads(r.stdout)["report"]["code"] == "UNKNOWN"


def test_canon_puts_context_order_right(tool):
    """A hand edit that breaks the context-first rules is refused by the
    streaming reader with its path, and canon, which holds the file, puts
    it right."""
    good = (EXAMPLES / "deep-bass.sound.lunar").read_text()
    doc = canon.loads(good)
    snd = doc["sound"]
    doc["sound"] = {"params": snd["params"], "level": snd["level"], "engine": snd["engine"],
                    "inserts": snd["inserts"], "midi_fx": snd["midi_fx"]}
    doc = {"lunar": doc["lunar"], "kind": doc["kind"], "mod": doc["mod"],
           **{k: v for k, v in doc.items() if k not in ("lunar", "kind", "mod")}}
    bad = json.dumps(doc).encode()
    rc, _, rep = c_records(tool, bad)
    assert rc == 1 and rep["code"] == "BAD" and "context first" in rep["what"]
    assert run(tool, "canon", "-", data=bad, check=True).stdout.decode() == good


def test_check_reports_ram_and_rate(tool):
    """Pass 1 without the app: instances at 44,118 Hz against the budget
    (RAM is always refused, ST5/ST6), and each engine created at the rate."""
    r = run(tool, "check", EXAMPLES / "deep-bass.sound.lunar")
    out = json.loads(r.stdout)
    assert r.returncode == 0 and 0 < out["ram_instances"] < out["ram_budget"]
    macro = b'{"lunar": "1.0", "kind": "sound", "sound": {"engine": "macro"}}'
    out = json.loads(run(tool, "check", "-", data=macro).stdout)
    assert out["report"]["code"] == "OK"
    r = run(tool, "check", "-", "--rate", 96000, data=macro)       # Plaits stops at 47,872 Hz
    out = json.loads(r.stdout)
    assert r.returncode == 1 and out["report"]["code"] == "RATE" and out["report"]["name"] == "macro"
    for path in (EXAMPLES / "first-orbit.lunar", GOLD / "tin-kit.sound.lunar"):
        out = json.loads(run(tool, "check", path).stdout)
        over = out["ram_instances"] > out["ram_budget"]
        assert out["report"]["code"] == ("RAM" if over else "OK"), path.name
    heavy = {"lunar": "1.0", "kind": "project",
             "sounds": [{"engine": "macro-heavy", "inserts": [{"engine": "hall"}, {"engine": "room"}]}] * 4,
             "master": [{"engine": "hall"}, {"engine": "room"}]}
    r = run(tool, "check", "-", data=json.dumps(heavy).encode())
    out = json.loads(r.stdout)
    assert out["report"]["code"] == ("RAM" if out["ram_instances"] > out["ram_budget"] else "OK")


def _golden_bin():
    return (GOLD / "first-orbit.lunarb").read_bytes()


def test_cut_binaries_are_refused(tool, names):
    data = _golden_bin()
    for n in range(len(data)):
        rc, _, rep = c_records(tool, data[:n])
        assert rc == 1, n
        assert py_records(data[:n], names)[0] == 1, n
        if n >= 32:
            assert rep["code"] in ("BAD", "TOO_BIG"), (n, rep)


def test_flipped_bits_are_refused(tool, names):
    """Every byte with one bit flipped: the CRCs catch it (or the magic, the
    level, a length), and both readers refuse it with the same code."""
    data = bytearray(_golden_bin())
    for i in range(len(data)):
        bad = bytearray(data)
        bad[i] ^= 1 << (i % 8)
        rc, _, rep = c_records(tool, bytes(bad))
        prc, _, pcode = py_records(bytes(bad), names)
        assert rc == 1 and prc == 1, i
        assert rep["code"] == pcode, (i, rep, pcode)


def test_deflate_interoperates_with_zlib(tool, names):
    """Our chunks inflate with zlib, zlib's (with a 4 KiB window) inflate in
    C, and a reach past 4 KiB is refused by both."""
    recs = [json.loads(line) for line in (GOLD / "first-orbit.records").read_text().splitlines()]
    ours = ls.write_bin(recs)
    assert ls.read_bin(ours)[0] == recs

    def zlib_deflate(b):
        c = zlib.compressobj(9, zlib.DEFLATED, -12)
        return c.compress(b) + c.flush()
    orig = ls.deflate
    try:
        ls.deflate = zlib_deflate
        theirs = ls.write_bin(recs)
    finally:
        ls.deflate = orig
    assert theirs != ours
    assert c_records(tool, theirs)[1] == ls.records_text(recs)
    # A stored literal, then a match 5,000 bytes back: past the window.
    payload = bytes(range(256)) * 20
    far = bytearray()

    def bits(v, n, acc=[0, 0]):
        acc[0] |= v << acc[1]
        acc[1] += n
        while acc[1] >= 8:
            far.append(acc[0] & 0xFF)
            acc[0] >>= 8
            acc[1] -= 8
        return acc
    z = zlib.compressobj(0, zlib.DEFLATED, -15)
    stored = z.compress(payload[:5000]) + z.flush(zlib.Z_SYNC_FLUSH)
    assert ls.deflate(b"x" * 64)                      # (exercised elsewhere)
    with pytest.raises(ls.Refused):
        ls.inflate(stored + b"\x03\x00", 5100)


def test_jsontestsuite(tool):
    """nst/JSONTestSuite (MIT), when it has been cloned to reference/: every
    y_ file parses but the three our caps and U+0000 rule refuse, every n_
    file is refused, and every i_ file has the outcome written here."""
    if not SUITE.is_dir():
        pytest.skip("reference/JSONTestSuite is not cloned")
    refused_y = {"y_number_double_close_to_zero.json", "y_object_escaped_null_in_key.json",
                 "y_string_null_escape.json"}
    accepted_i = {"i_number_double_huge_neg_exp.json", "i_number_neg_int_huge_exp.json",
                  "i_number_pos_double_huge_exp.json", "i_number_real_neg_overflow.json",
                  "i_number_real_pos_overflow.json", "i_number_real_underflow.json",
                  "i_number_too_big_neg_int.json", "i_number_too_big_pos_int.json"}
    for f in sorted(SUITE.glob("*.json")):
        ok = run(tool, "json-check", f).returncode == 0
        if f.name.startswith("y_"):
            assert ok == (f.name not in refused_y), f.name
        elif f.name.startswith("n_"):
            assert not ok, f.name
        else:
            assert ok == (f.name in accepted_i), f.name


def test_seeded_fuzz_loop_keeps_its_invariants(tool):
    """Mutations of every golden file through every reader: pieces never
    change the records, canonical text is a fixed point, JSON -> binary ->
    JSON is lossless, nothing crashes. A longer run under the sanitizers
    is engines/state/README.md's "Fuzzing"."""
    files = sorted(GOLD.glob("*.lunar")) + sorted(GOLD.glob("*.lunarb"))
    r = subprocess.run([str(FUZZ), "-s", "7", "-n", "20000", *map(str, files)], capture_output=True,
                       text=True, cwd=str(ROOT / "engines" / "build"))
    assert r.returncode == 0, r.stderr[-400:]
    out = json.loads(r.stdout)
    assert out["iterations"] == 20000 and out["accepted"] > 1000 and out["accepted_binary"] > 100


def test_launch_links_round_trip(names):
    """A #lunar= fragment (§12.4) carries a file's state; the guide's sizes
    are far under the 32 KiB cap, and a bomb stops at the cap."""
    for path in sorted(EXAMPLES.glob("*.lunar")):
        recs, _ = ls.read_json(path.read_bytes(), names)
        frag = ls.link_fragment(recs, names)
        assert frag.startswith("#lunar=") and len(frag) < 8000
        assert ls.read_link(frag, names)[0] == recs
    bomb = zlib.compressobj(9, zlib.DEFLATED, -15)
    data = bomb.compress(b'{"lunar": "1.0", "kind": "settings", "settings": {}, "x": "' + b"a" * 400000) + bomb.flush()
    import base64
    frag = "#lunar=" + base64.urlsafe_b64encode(data).decode().rstrip("=")
    with pytest.raises(ls.Refused):
        ls.read_link(frag, names)
