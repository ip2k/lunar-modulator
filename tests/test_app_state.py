"""The virtual FM-1's whole state through the state core (stage A1;
sim/web/src/fm1_app_state.h, notes/2026-10-06-state-files.md §10, §12).

- save -> load -> save gives the same bytes, in JSON and in binary, for the
  start chain, the example project and sessions with a pad kit's every pad,
  FM6 user voices, GPL engines and MIDI effects, the arp, a rack with
  Register's pattern data, locks and per-voice cables, and a song;
- a loaded project is the file: everything the example says comes back
  (the app adds only its bypassed arps and `made`);
- every kind loads into its target, and every refusal of §10.3 leaves the
  app's state as it was (its saved project unchanged);
- the project key has one home, the set's `key` line, and `session.key` is
  written from it.
"""
import json
import subprocess

import pytest

from tests import state_canon as canon
from tests.engine_helpers import ROOT, gpl_only, renderer  # noqa: F401
from tests.test_sim_web import tools  # noqa: F401
from tools import lunar_state as ls

EX = ROOT / "engines" / "state" / "examples"
DX7 = ROOT / "sim" / "web" / "test" / "dx7" / "lunar-test-voices.syx"


def sim(tools, *args, check=True):  # noqa: F811
    r = subprocess.run([str(tools["sim"]), "--seconds", "0", *[str(a) for a in args]], capture_output=True,
                       text=True)
    if check:
        assert r.returncode == 0, r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1]) if r.stdout.strip() else None


def cycle(tools, tmp_path, *start):  # noqa: F811
    """The state `start` gives, saved (a, and binary, deflated and plain as
    the page's autosave writes it), loaded and saved (b), and each binary
    loaded and saved (c, d)."""
    a, ab, ap, b, c, d = (tmp_path / n for n in ("a.lunar", "a.lunarb", "a.plain.lunarb", "b.lunar", "c.lunar",
                                                  "d.lunar"))
    sim(tools, *start, "--save", f"project:{a}", "--save", f"project:{ab}", "--save", f"project:{ap}")
    sim(tools, "--load", a, "--save", f"project:{b}")
    sim(tools, "--load", ab, "--save", f"project:{c}")
    sim(tools, "--load", ap, "--save", f"project:{d}")
    assert a.read_bytes() == b.read_bytes() == c.read_bytes() == d.read_bytes()
    assert ap.stat().st_size >= ab.stat().st_size
    return canon.loads(a.read_text())


def schema_ok(doc):
    pytest.importorskip("jsonschema")
    assert ls.validate(doc) == [], doc.get("kind")


def test_the_start_chain_round_trips(tools, tmp_path):  # noqa: F811
    doc = cycle(tools, tmp_path, "--start")
    schema_ok(doc)
    assert doc["made"] == {"by": "simulator"}
    assert [s and s["engine"] for s in doc["sounds"]] == ["macro", None, None, None]
    assert doc["sounds"][0]["midi_fx"][0]["engine"] == "arp" and doc["sounds"][0]["midi_fx"][0]["on"] is False
    assert doc["session"] == {"current": 1, "octave": 0, "transpose": 0, "key": {"root": "C", "scale": "major"}}
    assert doc["view"] == {"mode": "home", "sound": 1, "page": 1}


def test_the_example_project_loads_as_it_says(tools, tmp_path):  # noqa: F811
    """Everything the example holds comes back: every pad, the arp, the FM6
    voice, the rack and its cables, the set with its song and key, the
    session and the view. The app adds its bypassed arps and `made`."""
    src = canon.loads((EX / "first-orbit.lunar").read_text())
    out = sim(tools, "--load", EX / "first-orbit.lunar")
    assert out["load"]["ok"] == 1 and out["load"]["percent"] <= 95, out["load"]
    doc = cycle(tools, tmp_path, "--load", EX / "first-orbit.lunar")
    # the autosave's form leaves the deflate out, so it is the larger here
    assert (tmp_path / "a.plain.lunarb").stat().st_size > (tmp_path / "a.lunarb").stat().st_size
    schema_ok(doc)
    for k in ("name", "title", "about", "licence", "session", "master", "dx7", "mod", "set", "view"):
        assert doc[k] == src[k], k
    for mine, theirs in zip(doc["sounds"], src["sounds"]):
        for k in ("engine", "params", "pads", "level", "inserts"):
            assert mine.get(k) == theirs.get(k), (theirs["engine"], k)
        assert [m for m in mine["midi_fx"] if m["on"] or theirs["midi_fx"]] == theirs["midi_fx"]


def test_the_key_has_one_home(tools, tmp_path):  # noqa: F811
    """The set's `key` line is the project key; session.key is written from
    it and never applied."""
    doc = canon.loads((EX / "first-orbit.lunar").read_text())
    assert "key 0 1" in doc["set"] and doc["session"]["key"] == {"root": "C", "scale": "minor"}
    doc["session"]["key"] = {"root": "E", "scale": "lydian"}       # disagrees with the set
    f = tmp_path / "k.lunar"
    f.write_text(json.dumps(doc))
    out = sim(tools, "--load", f, "--save", f"project:{tmp_path / 'o.lunar'}")
    assert out["key"] == [0, 1]
    assert canon.loads((tmp_path / "o.lunar").read_text())["session"]["key"] == {"root": "C", "scale": "minor"}


SET = """movy1
bpm 11600
swing 54
link 0
key 2 3
sg 0 0 1 1 2
dq 25
se 2
sn 0 Intro
sn 1 Drop
tk 0 0 0
rt 0 1 0
cl 0 0 16 0 0:12:36:110:0;96:12:38:100:4;192:12:36:110:8;288:12:38:100:12
cp 0 0 1 1 0 0
lk 0 0 0:0:20;0:8:110
cl 0 1 16 0 0:12:36:110:0;48:12:37:90:2;192:12:39:110:8
cp 0 1 1 1 0 0
tk 1 0 0
rt 1 1 1
cl 1 0 16 0 0:40:48:100:0;96:40:55:100:4;192:40:51:100:8
cp 1 0 1 1 0 0
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
# Drums with two pads edited, Six-op through a filter, Macro behind the arp,
# the master's hall and limiter: a session fm1-render saves, which the app
# loads and keeps.
SESSION = ["--engine", "drums", "--param", "Kit=1", "--param", "Pad=3", "--param", "Tune=5", "--param", "Decay=0.3",
           "--param", "Pad=1", "--param", "Model=1",
           "--sound", "1:sixop", "--insert", "1:filter", "--insert-param", "1:Cutoff=900", "--level", "1:70",
           "--sound", "2:macro", "--mfx", "2:arp", "--mfx-param", "2:Rate=3", "--level", "2:60",
           "--sound", "3:sixop", "--level", "3:50",
           "--fx", "hall", "--fx-param", "Mix=0.2", "--fx", "limit"]


def rich(renderer, tmp_path, session=SESSION, mod=MOD):  # noqa: F811
    (tmp_path / "set.movy1").write_text(SET)
    (tmp_path / "mod.txt").write_text(mod)
    p = tmp_path / "r.lunar"
    subprocess.run([str(renderer), *session, "--mod", str(tmp_path / "mod.txt"),
                    "--seq", str(tmp_path / "set.movy1"), "--seconds", "0.1", "--out", str(tmp_path / "r.wav"),
                    "--save", f"project:{p}"], check=True, capture_output=True)
    return p


def test_a_rich_session_round_trips(renderer, tools, tmp_path):  # noqa: F811
    p = rich(renderer, tmp_path)
    doc = cycle(tools, tmp_path, "--load", p)
    schema_ok(doc)
    assert {"dq 25", "se 2", "sn 0 Intro", "sn 1 Drop", "key 2 3"} <= set(doc["set"])
    assert doc["session"]["key"] == {"root": "D", "scale": "dorian"}
    reg = next(m for m in doc["mod"]["rack"] if m["kind"] == "register")
    assert reg["data"] == {"version": 1, "hex": "a5c3f00e08"}
    cables = {c["slot"]: c for c in doc["mod"]["cables"]}
    assert cables[1]["lock"] == 400 and cables[2]["voice"] is True
    pads = doc["sounds"][0]["pads"]
    assert len(pads) == 16 and pads[3]["Tune"] == 5 and pads[1]["Model"] != pads[0]["Model"]
    assert doc["sounds"][2]["midi_fx"][0]["on"] is True


def test_fm6_user_voices_travel_with_the_project_and_the_sound(tools, tmp_path):  # noqa: F811
    """ST8: a project keeps FM6's loaded voices; a sound file the one its
    Patch plays, which a load into another sound reuses when the bank holds
    it, or puts in the first free slot, re-pointing Patch."""
    doc = cycle(tools, tmp_path, "--engine", "dx7", "--sysex", DX7, "--param", "Patch=34")
    assert doc["sounds"][0]["params"]["Patch"] == "User 3" and len(doc["dx7"]) >= 3
    snd = tmp_path / "fm.sound.lunar"
    sim(tools, "--engine", "dx7", "--sysex", DX7, "--param", "Patch=34", "--save", f"sound1:{snd}")
    one = canon.loads(snd.read_text())
    assert [v["slot"] for v in one["dx7"]] == [3]
    # Into a start chain: the bank is empty, so the voice goes to User 1.
    out = sim(tools, "--start", "--load", f"s2:{snd}", "--save", f"project:{tmp_path / 'p.lunar'}")
    p = canon.loads((tmp_path / "p.lunar").read_text())
    assert out["load"]["ok"] == 1 and p["sounds"][1]["params"]["Patch"] == "User 1"
    assert [v["slot"] for v in p["dx7"]] == [1] and p["dx7"][0]["ops"] == one["dx7"][0]["ops"]


@gpl_only
def test_gpl_engines_and_kits_round_trip(renderer, tools, tmp_path):  # noqa: F811
    session = ["--engine", "comet", "--param", "Pad=4", "--param", "Tune=0.6", "--param", "Pad=0",
               "--sound", "1:acid-bass", "--mfx", "1:acid-gen", "--level", "1:80",
               "--sound", "2:crater", "--sound", "3:drawbar", "--fx", "echo"]
    p = rich(renderer, tmp_path, session, MOD.split("slot 1")[0] + "slot 1 lfo1 > snd2:Cutoff amt=30 voice\n")
    doc = cycle(tools, tmp_path, "--load", p)
    assert [s["engine"] for s in doc["sounds"]] == ["comet", "acid-bass", "crater", "drawbar"]
    assert len(doc["sounds"][0]["pads"]) == 16 and len(doc["sounds"][2]["pads"]) == 16
    assert doc["sounds"][1]["midi_fx"][0]["engine"] == "acid-gen"


def project(tools, tmp_path, *start):  # noqa: F811
    """The app's whole state as its saved project's bytes."""
    f = tmp_path / "state.lunar"
    sim(tools, *start, "--save", f"project:{f}")
    return f.read_bytes()


def refused(tools, tmp_path, start, spec, code, *flags):  # noqa: F811
    """A load refused with `code`, the state unchanged."""
    before = project(tools, tmp_path, *start)
    f = tmp_path / "after.lunar"
    out = sim(tools, *start, "--load", spec, *flags, "--save", f"project:{f}")
    assert out["load"]["ok"] == 0 and out["load"]["code"] == code, out["load"]
    assert f.read_bytes() == before
    assert out["load"]["screen"][0] == "NOT LOADED"
    return out["load"]


def test_each_kind_loads_into_its_target(tools, tmp_path):  # noqa: F811
    out = sim(tools, "--start", "--load", f"s2:{EX / 'deep-bass.sound.lunar'}",
              "--save", f"sound2:{tmp_path / 's.lunar'}")
    assert out["load"]["ok"] == 1 and out["load"]["kind"] == "sound", out["load"]
    s = canon.loads((tmp_path / "s.lunar").read_text())
    src = canon.loads((EX / "deep-bass.sound.lunar").read_text())
    assert s["sound"]["params"] == src["sound"]["params"] and s["sound"]["inserts"] == src["sound"]["inserts"]
    assert s["mod"]["cables"][0]["to"] == {"unit": "snd.fx1", "param": "Cutoff"}
    out = sim(tools, "--start", "--load", f"fxM:{EX / 'space-verbs.fx.lunar'}", "--save", f"fx:{tmp_path / 'f.lunar'}")
    assert out["load"]["ok"] == 1 and out["fx"] == ["echo", "hall"]
    out = sim(tools, "--start", "--load", EX / "wobble.mods.lunar", "--save", f"mods:{tmp_path / 'm.lunar'}")
    assert out["load"]["ok"] == 1 and out["load"]["modules"] == 2
    out = sim(tools, "--start", "--load", f"t2.1:{EX / 'bass-a.clip.lunar'}", "--save", f"clip:2.1:{tmp_path / 'c.lunar'}")
    assert out["load"]["ok"] == 1
    assert canon.loads((tmp_path / "c.lunar").read_text())["clip"] == canon.loads((EX / "bass-a.clip.lunar").read_text())["clip"]
    out = sim(tools, "--start", "--load", EX / "settings.lunar", "--save", f"settings:{tmp_path / 'st.lunar'}")
    st = canon.loads((tmp_path / "st.lunar").read_text())
    assert st["settings"] == canon.loads((EX / "settings.lunar").read_text())["settings"]
    # A .movy1 set replaces the set; with no track routed, track 1 plays Sound 1.
    (tmp_path / "x.movy1").write_text("movy1\nbpm 9000\nswing 50\nlink 0\ntk 0 0 0\n")
    out = sim(tools, "--start", "--load", tmp_path / "x.movy1", "--save", f"set:{tmp_path / 'y.movy1'}")
    assert out["load"]["ok"] == 1 and out["load"]["kind"] == "set"
    assert "rt 0 1 0" in (tmp_path / "y.movy1").read_text().split("\n")


@pytest.mark.parametrize("missing", [False, True])
@pytest.mark.parametrize("binary", [False, True])
def test_sound_import_cannot_apply_unknown_mfx_to_old_slot(tools, tmp_path, missing, binary):
    source = canon.loads((EX / "deep-bass.sound.lunar").read_text())
    source["sound"]["engine"] = "macro"
    source["sound"]["params"] = {}
    source["sound"]["inserts"] = []
    source.pop("mod", None)
    source["sound"]["midi_fx"] = [] if missing else [
        {"engine": "future-arp", "on": True, "params": {"Rate": 7, "Latch": 1}}]
    incoming = tmp_path / ("incoming.lunarb" if binary else "incoming.lunar")
    if binary:
        names = ls.Names.from_build(tools["render"])
        if not missing:
            source["sound"]["midi_fx"][0]["engine"] = "arp"
        records, _ = ls.read_json(json.dumps(source), names)
        for record in records:
            if record["rec"] == "unit" and record["role"] == "mfx":
                record["engine"] = "future-arp"
        incoming.write_bytes(ls.write_bin(records))
    else:
        incoming.write_text(json.dumps(source))
    saved = tmp_path / "after.lunar"
    out = sim(tools, "--start", "--mfx", "2:arp", "--mfx-param", "2:Rate=3",
              "--mfx-param", "2:Latch=1", "--load", f"s2:{incoming}", "--without",
              "--save", f"project:{saved}")
    assert out["load"]["ok"] == 1, out["load"]
    after = canon.loads(saved.read_text())["sounds"][1]["midi_fx"][0]
    # An omitted/unavailable effect becomes the bypassed default, as preflight budgets.
    baseline = canon.loads(project(tools, tmp_path, "--start"))["sounds"][0]["midi_fx"][0]
    assert after == baseline


def test_every_refusal_changes_nothing(tools, tmp_path):  # noqa: F811
    bad = tmp_path / "bad.lunar"
    bad.write_text("hello")
    assert refused(tools, tmp_path, ["--start"], bad, "NOT_LUNAR")["message"] == "This is not a Lunar Modulator file."
    new = canon.loads((EX / "settings.lunar").read_text())
    new["lunar"] = "1.7"
    (tmp_path / "new.lunar").write_text(json.dumps(new))
    refused(tools, tmp_path, ["--start"], tmp_path / "new.lunar", "TOO_NEW")
    # An engine this build lacks, unless "load without".
    snd = canon.loads((EX / "deep-bass.sound.lunar").read_text())
    snd["sound"]["engine"] = "rings"
    snd["sound"]["params"] = {}
    (tmp_path / "u.lunar").write_text(json.dumps(snd))
    r = refused(tools, tmp_path, ["--start"], f"s2:{tmp_path / 'u.lunar'}", "UNKNOWN")
    assert "uses rings" in r["message"] and r["message"].endswith("Nothing was changed.")
    out = sim(tools, "--start", "--load", f"s2:{tmp_path / 'u.lunar'}", "--without")
    assert out["load"]["ok"] == 1 and out["load"]["left_out"] >= 1
    # Over the budget, always; the figure is a percent.
    p = tmp_path / "heavy.lunar"
    doc = canon.loads((EX / "first-orbit.lunar").read_text())
    doc["sounds"][1]["engine"] = "shapes"
    doc["sounds"][1]["params"] = {}
    p.write_text(json.dumps(doc))
    r = refused(tools, tmp_path, ["--start"], p, "RAM")
    assert r["percent"] > 100 and r["message"] == f"Needs {r['percent']}% of the FM-1's RAM."
    assert r["screen"][1] == f"Needs {r['percent']}% RAM"
    # The rate: Plaits' engines refuse a host above 47,872 Hz.
    out = sim(tools, "--rate", "96000", "--start", "--load", EX / "first-orbit.lunar")
    assert out["load"]["code"] == "RATE" and "96 kHz" in out["load"]["message"]
    # Two master slots, a three-effect chain.
    fx = canon.loads((EX / "space-verbs.fx.lunar").read_text())
    fx["chain"].append(fx["chain"][0])
    (tmp_path / "three.fx.lunar").write_text(json.dumps(fx))
    refused(tools, tmp_path, ["--start"], f"fxM:{tmp_path / 'three.fx.lunar'}", "NO_ROOM")
    out = sim(tools, "--start", "--load", f"fxM:{tmp_path / 'three.fx.lunar'}", "--without")
    assert out["load"]["ok"] == 1 and out["load"]["left_out"] == 1
    # A full rack: a sound's modulation, unless without it.
    full = canon.loads((EX / "wobble.mods.lunar").read_text())
    full["mod"]["rack"] = [dict(full["mod"]["rack"][0], pos=k) for k in range(1, 9)]
    full["mod"]["cables"] = []
    (tmp_path / "full.mods.lunar").write_text(json.dumps(full))
    base = tmp_path / "base.lunar"
    sim(tools, "--start", "--load", tmp_path / "full.mods.lunar", "--save", f"project:{base}")
    r = refused(tools, tmp_path, ["--load", base], f"s2:{EX / 'deep-bass.sound.lunar'}", "NO_ROOM")
    assert r["message"].startswith("The rack is full (8 of 8)")
    out = sim(tools, "--load", base, "--load", f"s2:{EX / 'deep-bass.sound.lunar'}", "--without")
    assert out["load"]["ok"] == 1 and out["load"]["left_out"] == 2      # its LFO and its cable
    # A clip into a slot that holds one asks first.
    refused(tools, tmp_path, ["--start"], f"t1.1:{EX / 'bass-a.clip.lunar'}", "NO_ROOM")
    out = sim(tools, "--start", "--load", f"t1.1:{EX / 'bass-a.clip.lunar'}", "--replace")
    assert out["load"]["ok"] == 1
