"""The desktop tools load and save state files (stage E3; engines/host/
render_state.h, fm1-seq --load/--save; notes/2026-10-06-state-files.md
§10, §12.6): fm1-render's --load gives the engines exactly what the same
state given as flags gives (the renders are byte-identical), --save writes
back what was loaded, the refusals of §10.3 hold (RAM at 44,118 Hz always,
an engine this build lacks unless --without, a full rack), and clips go
into a set and out of one with their lanes matched by label.
"""
import json
import subprocess

import pytest

from tests import state_canon as canon
from tests.engine_helpers import ENGINES, ROOT, renderer  # noqa: F401
from tools import lunar_state as ls

R = ENGINES / "build" / "fm1-render"
SEQ = ENGINES / "build" / "fm1-seq"
EXAMPLES = ENGINES / "state" / "examples"
GOLD = ROOT / "tests" / "fixtures" / "state" / "1.0"
INFO = ("made", "name", "title", "about", "author", "licence", "view")


@pytest.fixture(scope="module")
def names(renderer):    # noqa: F811
    return ls.Names.from_build()


def run(*args, check=True):
    return subprocess.run([str(a) for a in args], capture_output=True, text=True, check=check)


def content(path):
    """A file's document less what the desktop tools do not carry (its
    info, its view)."""
    doc = canon.loads(path.read_text())
    return {k: v for k, v in doc.items() if k not in INFO}


def flags_for_sound(names, doc, script):
    """The same state as fm1-render's flags: the sound unit, its inserts and
    level, and its modulation as a --mod script."""
    s = doc["sound"]
    e = names.engine(ls.SOUND, s["engine"])
    by = {p.name: p for p in e.params}

    def val(p, v):
        return str(p.entries.index(v) + int(p.min)) if isinstance(v, str) else repr(float(v))
    out = ["--engine", s["engine"]]
    for k, v in s["params"].items():
        out += ["--param", f"{k}={val(by[k], v)}"]
    for j, u in enumerate(s["inserts"]):
        if u:
            fx = names.engine(ls.INSERT, u["engine"])
            fby = {p.name: p for p in fx.params}
            out += ["--insert", f"0:{u['engine']}"]
            for k, v in u["params"].items():
                out += ["--insert-param", f"0:{k}={val(fby[k], v)}"]
    out += ["--level", f"0:{s['level']}"]
    lines = []
    for x in doc.get("mod", {}).get("rack", []):
        kd = names.kinds[x["kind"]]
        kby = {p.name: p for p in kd.params}
        lines.append(f"mod {x['pos']} {x['kind']} " +
                     " ".join(f"{k}={val(kby[k], v)}" for k, v in x["params"].items()))
    for c in doc.get("mod", {}).get("cables", []):
        frm = c["from"]
        src = frm["source"].lower() if "source" in frm else f"mod{frm['module']}.{frm['port']}"
        to = c["to"]
        dst = f"{to['unit']}:{to['param']}" if "unit" in to else f"mod{to['module']}.{to.get('param') or to['gate']}"
        lines.append(f"slot {c['slot']} {src} > {dst} amt={c['amount']} ofs={c['offset']} pol={c['polarity']} "
                     f"curve={c['curve']}" + (" voice" if c["voice"] else "") + ("" if c["on"] else " off"))
    script.write_text("\n".join(lines) + "\n")
    return out + (["--mod", str(script)] if lines else [])


def test_load_sounds_as_the_same_flags_do(names, tmp_path):
    src = EXAMPLES / "deep-bass.sound.lunar"
    doc = canon.loads(src.read_text())
    common = ["--note", "0:36:100:0.6", "--note", "0.3:43:90:0.4", "--seconds", "1"]
    a, b = tmp_path / "a.wav", tmp_path / "b.wav"
    run(R, "--load", src, *common, "--out", a)
    run(R, *flags_for_sound(names, doc, tmp_path / "m.txt"), *common, "--out", b)
    assert a.read_bytes() == b.read_bytes()
    # The same into sound unit 2, which a note there plays.
    c = tmp_path / "c.wav"
    run(R, "--engine", "test-sine", "--load", f"s2:{src}", "--sound-note", "1:0:36:100:0.6", "--seconds", "1",
        "--out", c)
    assert c.read_bytes() != a.read_bytes()


@pytest.mark.parametrize("name,kind,extra", [
    ("deep-bass.sound.lunar", "sound", []),
    ("tin-kit.sound.lunar", "sound", []),
    ("space-verbs.fx.lunar", "fx", ["--input", "impulse"]),
    ("four-way.fx.lunar", "fx", ["--input", "impulse"]),
    ("wobble.mods.lunar", "mods", ["--engine", "shapes", "--insert", "0:filter"]),
])
def test_save_writes_back_what_load_read(names, tmp_path, name, kind, extra):
    src = GOLD / name
    out = tmp_path / f"out.{kind}.lunar"
    run(R, *extra, "--load", src, "--save", f"{kind}:{out}", "--seconds", "0.01", "--out", tmp_path / "x.wav")
    want, got = content(src), content(out)
    # fm1-render keeps no gap between a sound's inserts or in its effects
    # chain: a null closes up and its cables move with their units.
    if name == "tin-kit.sound.lunar":
        assert want["sound"]["inserts"][0] is None
        want["sound"]["inserts"] = want["sound"]["inserts"][::-1]
        want["mod"]["cables"][0]["to"]["unit"] = "snd.fx1"
    if name == "four-way.fx.lunar":
        # It modulates the first two effects; and a cable to an empty rack
        # position names nothing there.
        assert want["chain"][1] is None
        want["chain"] = [u for u in want["chain"] if u]
        want["mod"]["cables"] = [dict(want["mod"]["cables"][0], to={"unit": "fx2", "param": "Resonance"})]
        # An LFO keeps no pattern data, so the runtime refuses the file's
        # (counted) and keeps none.
        for x in want["mod"]["rack"]:
            x.pop("data", None)
    assert got == want
    # The binary form is the same state.
    outb = tmp_path / f"out.{kind}.lunarb"
    run(R, *extra, "--load", src, "--save", f"{kind}:{outb}", "--seconds", "0.01", "--out", tmp_path / "x.wav")
    assert outb.read_bytes()[:8] == ls.MAGIC
    assert ls.read_bin(outb.read_bytes())[0] == ls.read_json(out.read_bytes(), names)[0]


def light_project(names):
    """A project inside the budget, with every part a project has."""
    doc = canon.loads((EXAMPLES / "first-orbit.lunar").read_text())
    shapes = doc["sounds"][1]
    macro = names.engine(ls.SOUND, "sixop")
    shapes["engine"] = "sixop"
    shapes["params"] = {p.name: (p.entries[0] if p.enum else p.default) for p in sorted(macro.params, key=lambda p: p.uid)}
    doc["master"] = [doc["master"][1], None]
    doc["mod"]["cables"] = [c for c in doc["mod"]["cables"] if c["to"].get("unit") != "snd2.fx1"]
    return doc


def test_a_project_round_trips(names, tmp_path):
    doc = light_project(names)
    src = tmp_path / "light.lunar"
    src.write_text(canon.dumps(doc))
    canonical = run(ENGINES / "build" / "fm1-state", "canon", src).stdout
    src.write_text(canonical)
    out = tmp_path / "out.lunar"
    run(R, "--load", src, "--save", f"project:{out}", "--seconds", "0.01", "--out", tmp_path / "x.wav")
    want, got = content(src), content(out)
    want.pop("session", None)                 # fm1-render has no panel session
    assert got == want


def test_refusals(tmp_path):
    r = run(R, "--load", EXAMPLES / "first-orbit.lunar", "--seconds", "0.01", "--out", tmp_path / "x.wav",
            check=False)
    assert r.returncode == 1 and "RAM: needs" in r.stderr
    rings = tmp_path / "rings.sound.lunar"
    rings.write_text('{"lunar": "1.0", "kind": "sound", "sound": {"engine": "rings"}}')
    r = run(R, "--load", rings, "--seconds", "0.01", "--out", tmp_path / "x.wav", check=False)
    assert r.returncode == 1 and "UNKNOWN" in r.stderr and "rings" in r.stderr
    r = run(R, "--engine", "test-sine", "--load", rings, "--without", "--seconds", "0.01", "--out",
            tmp_path / "x.wav", check=False)
    assert r.returncode == 0
    # Nine sounds' worth of modules do not fit the rack's eight positions.
    rack = {"lunar": "1.0", "kind": "sound", "sound": {"engine": "test-sine"},
            "mod": {"rack": [{"pos": p, "kind": "lfo"} for p in range(1, 6)], "cables": []}}
    f = tmp_path / "rack.sound.lunar"
    f.write_text(json.dumps(rack))
    r = run(R, "--load", f, "--load", f"s2:{f}", "--seconds", "0.01", "--out", tmp_path / "x.wav", check=False)
    assert r.returncode == 1 and "NO_ROOM" in r.stderr
    r = run(R, "--load", f, "--load", f"s2:{f}", "--without", "--seconds", "0.01", "--out", tmp_path / "x.wav",
            check=False)
    assert r.returncode == 0


def _set_text():
    return "\n".join(canon.loads((EXAMPLES / "first-orbit.lunar").read_text())["set"]) + "\n"


@pytest.mark.parametrize("tool", ["fm1-render", "fm1-seq"])
def test_clips_into_a_set_and_out(tmp_path, tool):
    """A clip goes into a track and a slot, its lanes matched by label (the
    same label, else a free lane), and comes out as it went in."""
    set_path = tmp_path / "set.movy1"
    set_path.write_text(_set_text())
    clip = EXAMPLES / "bass-a.clip.lunar"
    out_clip, out_set = tmp_path / "out.clip.lunar", tmp_path / "out.movy1"
    if tool == "fm1-render":
        run(R, "--seq", set_path, "--load", f"t3.5:{clip}", "--save", f"clip:3.5:{out_clip}", "--save",
            f"set:{out_set}", "--seconds", "0.01", "--out", tmp_path / "x.wav")
    else:
        run(SEQ, "--tracks", "8", "--seq", set_path, "--load", f"t3.5:{clip}", "--save", f"clip:3.5:{out_clip}",
            "--export", out_set)
    assert content(out_clip) == content(clip)
    lines = out_set.read_text().split("\n")
    assert "au 2 0 40 synth:Timbre" in lines                     # a free lane for its label
    assert any(line.startswith("cl 2 4 16 0 0:40:36") for line in lines)
    assert "lk 2 4 0:0:40;0:4:64;0:8:90;0:12:64" in lines
    # Onto the slot it came from: the set is unchanged.
    if tool == "fm1-seq":
        run(SEQ, "--tracks", "8", "--seq", set_path, "--load", f"t2.1:{clip}", "--export", out_set)
        assert out_set.read_text() == set_path.read_text()


def test_fm1_seq_loads_a_projects_set_and_a_binary_set(tmp_path):
    out = tmp_path / "out.movy1"
    run(SEQ, "--tracks", "8", "--load", EXAMPLES / "first-orbit.lunar", "--export", out)
    assert out.read_text() == _set_text()
    run(SEQ, "--tracks", "8", "--load", GOLD / "orbit.set.lunarb", "--export", out)
    core = tmp_path / "core.movy1"
    run(SEQ, "--tracks", "8", "--seq", GOLD / "orbit.set.movy1", "--export", core)
    assert out.read_text() == core.read_text()
