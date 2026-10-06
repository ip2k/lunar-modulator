"""The saved state as one whole: the stage-E integration of 2026-10-06 (E1's
song core, E2's saveable engines and metadata export, E3's records and
codecs, P1; notes/2026-10-06-state-files.md §21):

- save -> load -> save is byte-identical, in JSON and in binary, for every
  file kind (project, sound, effects chain, mod rack, clip, set, settings)
  and for the guide-like project of §3.4, through the desktop tools and
  through the codecs, and C and P1 write the same bytes;
- a project saved from an fm1-render session (four sound units, a pad kit
  with pads edited one by one, inserts, a MIDI effect, two master effects,
  a mod rack with Register's pattern data, a per-voice cable and a cable's
  lock, and a set with a song, scene names, an end mode and a default
  quantize; and, apart, FM6's user voices from a .syx bank) reloads from
  JSON and from binary and renders the same WAV, byte for byte;
- every golden file, every file the tools wrote here, the guide-like
  project and the build's metadata export validate against the schemas;
- a file naming an engine the build lacks is refused with its known-ids
  reason, from JSON and from binary, by fm1-state, fm1-render and P1;
- an old parameter or entry name resolves through the aliases in C and in
  P1 alike, and a pad kit's every pad is saved as its engine holds it.
"""
import json
import subprocess

import pytest

from tests import state_canon as canon
from tests.engine_helpers import ENGINES, ROOT, renderer  # noqa: F401
from tools import lunar_state as ls
from tools import state_examples as se

R = ENGINES / "build" / "fm1-render"
SEQ = ENGINES / "build" / "fm1-seq"
TOOL = ENGINES / "build" / "fm1-state"
ALIAS = ENGINES / "build" / "fm1-state-alias-test"
GOLD = ROOT / "tests" / "fixtures" / "state" / "1.0"
EXAMPLES = ENGINES / "state" / "examples"
SYX = ROOT / "sim" / "web" / "test" / "dx7" / "lunar-test-bank.syx"


@pytest.fixture(scope="module")
def names(renderer):    # noqa: F811
    return ls.Names.from_build()


def run(*args, data=None, check=True):
    return subprocess.run([str(a) for a in args], input=data, capture_output=True, check=check)


def tool(*args, data=None):
    return run(TOOL, *args, data=data).stdout


def schema_ok(path_or_doc):
    pytest.importorskip("jsonschema")
    doc = path_or_doc if isinstance(path_or_doc, dict) else canon.loads(path_or_doc.read_text())
    assert ls.validate(doc) == [], doc.get("kind")


def cycle(render_args, kind, ext, tmp_path, load_prefix=""):
    """fm1-render: the session's state saved (a), loaded and saved again (b),
    and once more (c); returns the three files' bytes."""
    a, b, c = (tmp_path / f"{n}.{kind.split(':')[0]}.{ext}" for n in "abc")
    wav = tmp_path / "x.wav"
    run(R, *render_args, "--save", f"{kind}:{a}", "--seconds", "0.01", "--out", wav)
    ctx = [x for x in render_args if x not in render_args[render_args.index("--load"):render_args.index("--load") + 2]] \
        if "--load" in render_args else list(render_args)
    run(R, *ctx, "--load", f"{load_prefix}{a}", "--save", f"{kind}:{b}", "--seconds", "0.01", "--out", wav)
    run(R, *ctx, "--load", f"{load_prefix}{b}", "--save", f"{kind}:{c}", "--seconds", "0.01", "--out", wav)
    return a.read_bytes(), b.read_bytes(), c.read_bytes()


# ---- Every kind: save -> load -> save ------------------------------------------------------------
KINDS = [
    ("sound", "deep-bass.sound.lunar", []),
    ("sound", "tin-kit.sound.lunar", []),
    ("fx", "space-verbs.fx.lunar", ["--input", "impulse"]),
    ("fx", "four-way.fx.lunar", ["--input", "impulse"]),
    ("mods", "wobble.mods.lunar", ["--engine", "shapes", "--insert", "0:filter"]),
]


@pytest.mark.parametrize("kind,name,extra", KINDS, ids=[k[1] for k in KINDS])
def test_render_save_load_save_is_byte_identical(tmp_path, kind, name, extra):
    (tmp_path / "j").mkdir()
    (tmp_path / "b").mkdir()
    j = cycle([*extra, "--load", str(GOLD / name)], kind, "lunar", tmp_path / "j")
    b = cycle([*extra, "--load", str(GOLD / name)], kind, "lunarb", tmp_path / "b")
    assert j[0] == j[1] == j[2]
    assert b[0] == b[1] == b[2] and b[0][:8] == ls.MAGIC
    # The binary is the same state as the JSON the same session saves.
    assert tool("unpack", "-", data=b[0]) == j[0]
    schema_ok(canon.loads(j[0].decode()))


def light_project(names, set_lines):
    """The example project inside the FM-1's budget (Six-op for Shapes, one
    master effect), with set_lines for its set."""
    doc = canon.loads((EXAMPLES / "first-orbit.lunar").read_text())
    six = names.engine(ls.SOUND, "sixop")
    doc["sounds"][1]["engine"] = "sixop"
    doc["sounds"][1]["params"] = {p.name: (p.entries[0] if p.enum else p.default)
                                  for p in sorted(six.params, key=lambda p: p.uid)}
    doc["master"] = [doc["master"][1], None]
    doc["mod"]["cables"] = [c for c in doc["mod"]["cables"] if c["to"].get("unit") != "snd2.fx1"]
    doc["set"] = set_lines
    return doc


@pytest.fixture(scope="module")
def guide(renderer):    # noqa: F811
    """The guide-like project of §3.4: 40 clips, 1,444 notes, the 4-minute song."""
    reg = se.Registry()
    return se.Examples(reg).project(se.guide_like_set())


@pytest.mark.parametrize("ext", ["lunar", "lunarb"])
@pytest.mark.parametrize("which", ["example", "guide-like"])
def test_render_project_save_load_save(tmp_path, names, guide, ext, which):
    src_set = guide["set"] if which == "guide-like" else canon.loads(
        (EXAMPLES / "first-orbit.lunar").read_text())["set"]
    src = tmp_path / "in.lunar"
    src.write_bytes(tool("canon", "-", data=canon.dumps(light_project(names, src_set)).encode()))
    a, b, c = cycle(["--load", str(src)], "project", ext, tmp_path)
    assert a == b == c
    doc = canon.loads((tool("unpack", "-", data=a) if ext == "lunarb" else a).decode())
    # fm1-render routes a set's unrouted tracks to the sound units (rt lines).
    assert [ln for ln in doc["set"] if not ln.startswith("rt ")] == [ln for ln in src_set if not ln.startswith("rt ")]
    schema_ok(doc)


def test_clip_and_set_save_load_save(tmp_path):
    set_text = "\n".join(canon.loads((EXAMPLES / "first-orbit.lunar").read_text())["set"]) + "\n"
    s0 = tmp_path / "s0.movy1"
    s0.write_text(set_text)
    for ext in ("lunar", "lunarb"):
        a, b, c = (tmp_path / f"{n}.clip.{ext}" for n in "abc")
        run(R, "--seq", s0, "--load", f"t3.5:{EXAMPLES / 'bass-a.clip.lunar'}", "--save", f"clip:3.5:{a}",
            "--seconds", "0.01", "--out", tmp_path / "x.wav")
        run(R, "--seq", s0, "--load", f"t3.5:{a}", "--save", f"clip:3.5:{b}", "--seconds", "0.01",
            "--out", tmp_path / "x.wav")
        run(SEQ, "--tracks", "8", "--seq", s0, "--load", f"t3.5:{b}", "--save", f"clip:3.5:{c}")
        assert a.read_bytes() == b.read_bytes() == c.read_bytes()
    # A set: movy1 text, and its binary file (kind 7).
    s1, s2 = tmp_path / "s1.movy1", tmp_path / "s2.movy1"
    run(R, "--seq", s0, "--save", f"set:{s1}", "--seconds", "0.01", "--out", tmp_path / "x.wav")
    run(R, "--seq", s1, "--save", f"set:{s2}", "--seconds", "0.01", "--out", tmp_path / "x.wav")
    assert s1.read_bytes() == s2.read_bytes() == set_text.encode()
    b1 = tool("from-movy1", s1)
    (tmp_path / "s.lunarb").write_bytes(b1)
    run(SEQ, "--tracks", "8", "--load", tmp_path / "s.lunarb", "--export", s2)
    assert s2.read_bytes() == set_text.encode()
    assert tool("from-movy1", s2) == b1


@pytest.mark.parametrize("path", sorted(GOLD.glob("*.lunar")), ids=lambda p: p.name)
def test_codecs_save_load_save_every_kind(names, path):
    """The codecs: canonical JSON is a fixed point, JSON -> binary -> JSON
    and binary -> JSON -> binary give the same bytes, and P1 writes what C
    writes, for every kind (the settings file included)."""
    j = path.read_bytes()
    assert tool("canon", "-", data=j) == j
    b = tool("pack", "-", data=j)
    assert b == path.with_suffix(".lunarb").read_bytes()
    assert tool("unpack", "-", data=b) == j
    assert tool("pack", "-", data=tool("unpack", "-", data=b)) == b
    recs, _ = ls.read_json(j, names)
    assert ls.write_json(recs, names)[0].encode() == j
    assert ls.write_bin(recs) == b
    assert ls.write_json(ls.read_bin(b)[0], names)[0].encode() == j
    schema_ok(path)


def test_the_guide_like_project_round_trips(names, guide):
    j = tool("canon", "-", data=canon.dumps(guide).encode())
    assert tool("canon", "-", data=j) == j
    b = tool("pack", "-", data=j)
    assert tool("unpack", "-", data=b) == j
    assert tool("pack", "-", data=tool("unpack", "-", data=b)) == b
    recs, _ = ls.read_json(j, names)
    assert ls.write_json(recs, names)[0].encode() == j
    assert ls.write_bin(recs) == b
    assert ls.records_text(ls.read_bin(b)[0]) == ls.records_text(recs)
    assert run(TOOL, "records", "-", data=b).stdout.decode() == ls.records_text(recs)
    doc = canon.loads(j.decode())
    assert len([ln for ln in doc["set"] if ln.startswith("cl ")]) == 40
    schema_ok(doc)
    # Fed to the readers in pieces of any size, the records do not change.
    for pieces in (1, 7, 64):
        assert run(TOOL, "records", "-", "--pieces", pieces, data=j).stdout.decode() == ls.records_text(recs)


def test_the_metadata_export_validates(renderer):    # noqa: F811
    meta = canon.loads(run(R, "--meta").stdout.decode())
    assert meta == canon.loads(tool("meta").decode())
    pytest.importorskip("jsonschema")
    import jsonschema
    import referencing
    schemas = {p.name: json.loads(p.read_text()) for p in (ENGINES / "state" / "schema").glob("*.schema.json")}
    reg = referencing.Registry().with_resources(
        [(s["$id"], referencing.Resource.from_contents(s)) for s in schemas.values()])
    v = jsonschema.Draft202012Validator(schemas["metadata.schema.json"], registry=reg)
    assert [e.message for e in v.iter_errors(meta)] == []


# ---- A session's project renders the same audio -----------------------------------------------------
SET = """movy1
bpm 12000
swing 50
link 0
dq 25
sg 0 1 0
se 2
sn 0 Intro
sn 1 Drop
tk 0 0 0
au 0 0 64 synth:Decay
rt 0 1 0
cl 0 0 16 0 0:12:36:110:0;96:12:38:100:4;192:12:40:110:8;288:12:42:100:12
cp 0 0 1 1 0 0
lk 0 0 0:0:20;0:8:110
cl 0 1 16 0 0:12:36:110:0;48:12:37:90:2;192:12:39:110:8
cp 0 1 1 1 0 0
tk 1 0 0
rt 1 1 1
cl 1 0 16 0 0:40:48:100:0;96:40:55:100:4;192:40:51:100:8
cp 1 0 1 1 0 0
cl 1 1 16 0 0:80:43:100:0
cp 1 1 1 1 0 0
tk 2 0 0
rt 2 1 2
cl 2 0 16 0 0:300:60:85:0;0:300:63:85:0
cp 2 0 1 1 0 0
"""
MOD = """seed 4242
mod 1 lfo Rate=0.3 Shape=Triangle
mod 2 register Change=1 Length=8
data 2 1 a5c3f00e08
slot 1 lfo1 > snd2.fx1:Cutoff amt=30 lock=400
slot 2 register2.cv > snd3:Timbre amt=25 voice
slot 3 vel > host:amp amt=-10 pol=uni curve=square
"""
SESSION = ["--engine", "drums", "--param", "Kit=1", "--param", "Pad=3", "--param", "Tune=5", "--param", "Decay=0.3",
           "--param", "Pad=1", "--param", "Model=1",
           "--sound", "1:shapes", "--sound-param", "1:Timbre=0.4", "--insert", "1:filter",
           "--insert-param", "1:Cutoff=900", "--level", "1:70",
           "--sound", "2:macro", "--mfx", "2:arp", "--mfx-param", "2:Rate=3", "--level", "2:60",
           "--sound", "3:sixop", "--level", "3:50",
           "--fx", "hall", "--fx-param", "Mix=0.2", "--fx", "limit"]


def test_a_saved_session_renders_the_same(tmp_path):
    (tmp_path / "set.movy1").write_text(SET)
    (tmp_path / "mod.txt").write_text(MOD)
    p, pb = tmp_path / "p.lunar", tmp_path / "p.lunarb"
    a, b, c = (tmp_path / f"{n}.wav" for n in "abc")
    run(R, *SESSION, "--mod", tmp_path / "mod.txt", "--seq", tmp_path / "set.movy1", "--seconds", "6",
        "--save", f"project:{p}", "--save", f"project:{pb}", "--out", a)
    run(R, "--load", p, "--seconds", "6", "--out", b)
    run(R, "--load", pb, "--seconds", "6", "--out", c)
    assert a.read_bytes() == b.read_bytes() == c.read_bytes()
    doc = canon.loads(p.read_text())
    schema_ok(doc)
    # What made it: the song's lines, Register's loop, the lock, every pad.
    assert {"dq 25", "se 2", "sn 0 Intro", "sn 1 Drop"} <= set(doc["set"])
    reg = next(m for m in doc["mod"]["rack"] if m["kind"] == "register")
    assert reg["data"] == {"version": 1, "hex": "a5c3f00e08"}
    assert next(x for x in doc["mod"]["cables"] if x["slot"] == 1)["lock"] == 400
    pads = doc["sounds"][0]["pads"]                     # Pad=3 is the fourth pad, Pad=1 the second
    assert len(pads) == 16 and pads[3]["Tune"] == 5 and pads[3]["Decay"] == pytest.approx(0.3)
    assert pads[1]["Model"] != pads[0]["Model"] == pads[2]["Model"]
    # And the binary is the same state.
    assert tool("unpack", pb) == p.read_bytes()
    # The state alone matters: rendering the reloaded file twice is stable,
    # and the session without its rack and set renders differently.
    run(R, *SESSION, "--seconds", "6", "--out", tmp_path / "bare.wav")
    assert (tmp_path / "bare.wav").read_bytes() != a.read_bytes()


def test_a_kits_every_pad_is_saved_as_its_engine_holds_it(tmp_path):
    """Engine API v4's get_param: Sophie's pads start from the module's own
    patches, so a pad the session never touched is saved with its own
    values (a default for every pad would change the kit), and the kit
    reloads to the same sound on every pad."""
    notes = [x for k in range(16) for x in ("--note", f"{k * 0.1}:{36 + k}:100:0.08")] + ["--seconds", "1.8"]
    p = tmp_path / "k.sound.lunar"
    a, b = tmp_path / "a.wav", tmp_path / "b.wav"
    run(R, "--engine", "sw-sophie", "--param", "Pad=2", "--param", "Tune=0.75", *notes, "--save", f"sound:{p}",
        "--out", a)
    run(R, "--load", p, *notes, "--out", b)
    assert a.read_bytes() == b.read_bytes()
    pads = canon.loads(p.read_text())["sound"]["pads"]
    varies = [k for k in pads[0] if len({json.dumps(x[k]) for x in pads}) > 1]
    assert len(varies) >= 3, varies
    assert pads[2]["Tune"] == 0.75


def test_fm6_user_voices_render_the_same(tmp_path):
    notes = ["--note", "0:48:100:0.5", "--note", "0.4:55:90:0.5", "--seconds", "1.5"]
    p, pb = tmp_path / "d.lunar", tmp_path / "d.lunarb"
    a, b, c, d = (tmp_path / f"{n}.wav" for n in "abcd")
    run(R, "--engine", "dx7", "--sysex", SYX, "--param", "Patch=34", *notes, "--save", f"project:{p}",
        "--save", f"project:{pb}", "--out", a)
    run(R, "--load", p, *notes, "--out", b)
    run(R, "--load", pb, *notes, "--out", c)
    assert a.read_bytes() == b.read_bytes() == c.read_bytes()
    doc = canon.loads(p.read_text())
    assert doc["sounds"][0]["params"]["Patch"] == "User 3" and len(doc["dx7"]) == 32
    run(R, "--engine", "dx7", "--param", "Patch=34", *notes, "--out", d)     # the INIT VOICE there
    assert d.read_bytes() != a.read_bytes()


# ---- Names: known ids, aliases ------------------------------------------------------------------------
def test_a_known_absent_engine_is_refused_with_its_reason(tmp_path, names):
    doc = b'{"lunar": "1.0", "kind": "sound", "sound": {"engine": "acid-bass", "params": {"#3": 0.5}}}'
    r = run(TOOL, "canon", "-", data=doc, check=False)
    rep = json.loads(r.stderr.decode().splitlines()[-1])
    assert r.returncode == 1 and rep["code"] == "UNKNOWN" and rep["name"] == "acid-bass"
    assert rep["known"] == "gpl" and "in the GPL build only" in rep["what"]
    binary = tool("pack", "-", "--without", data=doc)
    r = run(TOOL, "check", "-", data=binary, check=False)
    rep = json.loads(r.stdout)["report"]
    assert rep["code"] == "UNKNOWN" and rep["known"] == "gpl"
    for f, data in (("a.sound.lunar", doc), ("a.sound.lunarb", binary)):
        (tmp_path / f).write_bytes(data)
        r = run(R, "--load", tmp_path / f, "--seconds", "0.01", "--out", tmp_path / "x.wav", check=False)
        assert r.returncode == 1 and "acid-bass" in r.stderr.decode() and "in the GPL build only" in r.stderr.decode()
        _, rep = ls.read_any(data, names)
        assert rep.unknown == 1 and rep.name == "acid-bass" and rep.known == "gpl"
    # An id nobody lists is refused without a reason.
    r = run(TOOL, "canon", "-", data=doc.replace(b"acid-bass", b"kazoo"), check=False)
    assert json.loads(r.stderr.decode().splitlines()[-1])["known"] == ""


ALIASED = {"lunar": "1.0", "kind": "sound",
           "sound": {"engine": "shapes", "params": {"Old Timbre": 0.25},
                     "inserts": [{"engine": "filter", "params": {"Type": "moogish"}}, None]},
           "mod": {"rack": [{"pos": 1, "kind": "lfo", "params": {"speed": 0.5, "Shape": "Tri"}}],
                   "cables": [{"slot": 1, "on": True, "from": {"module": 1, "port": "Out"}, "via": None,
                               "to": {"unit": "snd", "param": "Old Timbre"}, "amount": 10, "offset": 0,
                               "polarity": "auto", "curve": "lin", "voice": False, "lock": 0}]}}


def test_old_names_resolve_alike_in_c_and_p1(renderer):    # noqa: F811
    """fm1_known.h's aliases (none yet in the build): the test's own table
    in C (engines/test/state_alias_test.c) and the same in P1's names."""
    names = ls.Names.from_build()             # its own: the aliases are added to it
    data = json.dumps(ALIASED).encode()
    r = run(ALIAS, data=data)
    assert r.stderr.decode().strip() == "skipped 0"
    by = {e.id: e for e in names.engines}
    p = {q.name: q for q in by["shapes"].params}
    p["Timbre"].aliases.append("Old Timbre")
    {q.name: q for q in by["filter"].params}["Type"].entry_aliases["Moogish"] = 1
    lfo = {q.name: q for q in names.kinds["lfo"].params}
    lfo["Rate"].aliases.append("Speed")
    lfo["Shape"].entry_aliases["Tri"] = 1
    recs, rep = ls.read_json(data, names)
    assert rep.skipped == 0
    assert ls.records_text(recs) == r.stdout.decode()
    params = [x for x in recs if x["rec"] == "param"]
    assert [x["uid"] for x in params] == [p["Timbre"].uid, 1, lfo["Rate"].uid, lfo["Shape"].uid]
    assert params[1]["index"] == 1 and params[3]["index"] == 1
    assert next(x for x in recs if x["rec"] == "cable")["dst"] == p["Timbre"].uid
    # Without the aliases the build skips them, in both.
    r = run(TOOL, "records", "-", data=data, check=True)
    assert len([ln for ln in r.stdout.decode().splitlines() if '"param"' in ln]) < len(params)


def test_a_cable_to_a_parameter_its_kind_lacks_passes_through(names):
    """A cable to a module's `#UID` the kind does not have (a newer build's
    parameter) is kept by uid, as a unit's is, so canonical text stays a
    fixed point (the fuzz loop found the binary reader passing one that the
    JSON reader then dropped)."""
    doc = {"lunar": "1.0", "kind": "mods",
           "mod": {"seed": 7, "rack": [{"pos": 1, "kind": "lfo"}],
                   "cables": [{"slot": 2, "on": True, "from": {"source": "VEL"}, "via": None,
                               "to": {"module": 1, "param": "#256"}, "amount": 30, "offset": 0,
                               "polarity": "bi", "curve": "lin", "voice": False, "lock": 0}]}}
    j = tool("canon", "-", data=json.dumps(doc).encode())
    assert canon.loads(j.decode())["mod"]["cables"][0]["to"] == {"module": 1, "param": "#256"}
    assert tool("canon", "-", data=j) == j
    b = tool("pack", "-", data=j)
    assert tool("unpack", "-", data=b) == j
    recs, rep = ls.read_json(j, names)
    assert rep.skipped == 0 and ls.write_json(recs, names)[0].encode() == j and ls.write_bin(recs) == b
