#!/usr/bin/env python3
"""Writes the golden files of a format level (tests/fixtures/state/<level>/;
notes/2026-10-06-state-files.md §17): JSON files, their binary twins and
their records, which tests/test_state_codec.py loads in CI for ever, so an
accidental format change fails there.

    make -C engines
    python3 tools/state_goldens.py            # writes the level's files that are missing
    python3 tools/state_goldens.py --force    # rewrites them: only before the level is released

A released level's files never change; a new level gets a directory of its
own. The JSON files are the examples of engines/state/examples/ at the time
of writing, plus a pad kit, a four-effect chain with pattern data and
cables kept by name, and a set with lines the binary keeps raw. The binary
twins are `fm1-state pack`'s output (.lunarb: binary files are the device's,
and *.bin is kept out of git); the records are `fm1-state records` of the
JSON. Our own values throughout; MIT, as the repository.
"""
import argparse
import random
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tests import state_canon as canon  # noqa: E402
from tools import lunar_state as ls  # noqa: E402

LEVEL = "1.0"
OUT = ROOT / "tests" / "fixtures" / "state" / LEVEL
EXAMPLES = ROOT / "engines" / "state" / "examples"
TOOL = ROOT / "engines" / "build" / "fm1-state"

ORBIT_SET = """movy1
bpm 11600
swing 54
link 0
sg 0 0 1 1 2
dq 25
se 2
sn 0 Intro
tk 0 0 0
au 0 0 64 synth:Decay
rt 0 1 0
cl 0 0 16 0 0:12:36:110:0;96:12:38:100:4;192:12:36:110:8;288:12:38:100:12
cp 0 0 1 1 0 0
lk 0 0 0:0:40;0:4:64;0:8:90;0:12:64
tg 0 0 4:-1:50:1:1:0;12:0:100:2:4:1
cl 0 1 16 0
cp 0 1 3 2 -5 50
tk 1  2 0
pm 1 36
ps 1 38
cl 1 2 32 4 0:24:60:100:0
cp 1 2 1 1 12 0
"""


def value(rnd, p):
    if p.enum:
        return p.entries[rnd.randrange(p.count())]
    v = canon.f32(p.min + rnd.random() * (p.max - p.min))
    v = min(max(v, p.min), p.max)
    return int(v) if v == int(v) else v


def unit(rnd, names, role, eid):
    e = names.engine(role, eid)
    u = {"engine": eid}
    if role == ls.MFX:
        u["on"] = False
    u["params"] = {p.name: value(rnd, p) for p in sorted(e.params, key=lambda p: p.uid) if p.focus != 2}
    if role == ls.SOUND and e.pads:
        u["pads"] = [{p.name: value(rnd, p) for p in sorted(e.params, key=lambda p: p.uid) if p.focus == 2}
                     for _ in range(e.pads)]
    return u


def kit_sound(names):
    rnd = random.Random(11)
    head = {"lunar": "1.0", "kind": "sound", "made": {"by": "hand"}, "name": "TIN KIT",
            "title": "Tin kit", "about": "A metallic kit, its pads tuned apart, behind an arpeggiator held off.",
            "licence": "MIT"}
    s = unit(rnd, names, ls.SOUND, "sw-sophie")
    s["level"] = 64.5
    s["inserts"] = [None, unit(rnd, names, ls.INSERT, "filter")]
    s["midi_fx"] = [unit(rnd, names, ls.MFX, "arp")]
    head["sound"] = s
    head["mod"] = {"rack": [{"pos": 2, "kind": "env", "params": {p.name: value(rnd, p) for p in
                                                                    sorted(names.kinds["env"].params,
                                                                           key=lambda p: p.uid)}}],
                   "cables": [{"slot": 3, "on": True, "from": {"module": 2, "port": "Env"}, "via": None,
                               "to": {"unit": "snd.fx2", "param": "Cutoff"}, "amount": 61.035,
                               "offset": -2.5, "polarity": "bi", "curve": "exp", "voice": False, "lock": 0}]}
    head["view"] = {"mode": "home", "sound": 1, "page": 2}
    return head


def chain_fx(names):
    rnd = random.Random(12)
    lfo = names.kinds["lfo"]
    doc = {"lunar": "1.0", "kind": "fx", "made": {"by": "desktop", "version": "0.1.0", "commit": "1757499"},
           "name": "FOUR WAY", "title": "Four-way chain", "about": "An echo, a gap, a comb and a limiter.",
           "author": "Lunar Modulator", "licence": "MIT",
           "chain": [unit(rnd, names, ls.MASTER, "echo"), None, unit(rnd, names, ls.MASTER, "comb"),
                     unit(rnd, names, ls.MASTER, "limit")],
           "mod": {"rack": [{"pos": 3, "kind": "lfo",
                             "params": {p.name: value(rnd, p) for p in sorted(lfo.params, key=lambda p: p.uid)},
                             "data": {"version": 1, "hex": "00ff10a5"}}],
                   "cables": [
                       {"slot": 1, "on": True, "from": {"module": 3, "port": "Out"}, "via": {"source": "VEL"},
                        "to": {"unit": "fx3", "param": "Resonance"}, "amount": 12.5, "offset": 0,
                        "polarity": "uni", "curve": "s", "voice": False, "lock": 400},
                       {"slot": 2, "on": False, "from": {"source": "BEAT"}, "via": None,
                        "to": {"unit": "fx4", "param": "Drive"}, "amount": -100, "offset": 33.333,
                        "polarity": "inv", "curve": "cube", "voice": False, "lock": 0},
                       {"slot": 32, "on": True, "from": {"source": "RAND"}, "via": None,
                        "to": {"module": 5, "param": "Rate"}, "amount": 0.006, "offset": 0,
                        "polarity": "auto", "curve": "lin", "voice": False, "lock": 0}]},
           "view": {"mode": "chain", "pos": 3}}
    return doc


def run(*args, **kw):
    return subprocess.run([str(TOOL), *map(str, args)], check=True, capture_output=True, **kw).stdout


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--force", action="store_true", help="rewrite the level's files")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    names = ls.Names.from_build()
    docs = {p.name: p.read_text() for p in sorted(EXAMPLES.glob("*.lunar"))}
    docs["tin-kit.sound.lunar"] = canon.dumps(kit_sound(names))
    docs["four-way.fx.lunar"] = canon.dumps(chain_fx(names))
    for name, text in docs.items():
        path = OUT / name
        if path.exists() and not args.force:
            continue
        tmp = OUT / (name + ".in")
        tmp.write_text(text)
        canonical = run("canon", tmp)
        tmp.unlink()
        path.write_bytes(canonical)
        path.with_suffix(".lunarb").write_bytes(run("pack", path))
        path.with_suffix(".records").write_bytes(run("records", path))
        print("wrote", path.relative_to(ROOT), "and its twins")
    movy = OUT / "orbit.set.movy1"
    if not movy.exists() or args.force:
        movy.write_text(ORBIT_SET)
        b = OUT / "orbit.set.lunarb"
        b.write_bytes(run("from-movy1", movy))
        b.with_suffix(".records").write_bytes(run("records", b))
        print("wrote", movy.relative_to(ROOT), "and its twins")
    shutil.rmtree(OUT / "__pycache__", ignore_errors=True)


if __name__ == "__main__":
    main()
