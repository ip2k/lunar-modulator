#!/usr/bin/env python3
"""Writes the example files of Lunar Modulator's JSON file kinds
(engines/state/examples/) from the desktop build's registry, and measures
the guide-like project as JSON, deflated JSON and a binary prototype
(notes/2026-10-06-state-files.md §3.4).

    make -C engines
    python3 tools/state_examples.py --write      # rewrite the examples
    python3 tools/state_examples.py --measure    # print §3.4's numbers

The examples are hand-designed states written in the canonical layout
(tests/state_canon.py); tests/test_state_schema.py checks them. Nothing
here reads or loads a file: the loaders are stages E3 and P1. The binary
"prototype" packs §8's layout approximately, to size it, and is not E3's
codec. Our own DX7 voice values, not a factory voice.
"""
import argparse
import base64
import json
import random
import struct
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tests import state_canon as canon  # noqa: E402
from tests.state_meta import subset  # noqa: E402

BUILD = ROOT / "engines" / "build"
OUT = ROOT / "engines" / "state" / "examples"

# Our own FM6 voice: 21 values per operator in VCED order, OP6 first
# (R1-R4 L1-L4 BP LD RD LC RC RS AMS KVS OL M FC FF DET), then PR1-PR4 PL1-PL4
# ALG FB OKS LFS LFD LPMD LAMD LKS LFW LPMS TRNSP.
DX7_VOICE = {
    "slot": 1,
    "name": "LUNAR LEAD",
    "ops": [
        [95, 40, 30, 60, 99, 80, 70, 0, 39, 0, 10, 0, 3, 2, 0, 2, 72, 0, 3, 0, 7],
        [90, 50, 35, 55, 99, 85, 60, 0, 39, 0, 0, 0, 0, 1, 0, 3, 80, 0, 1, 0, 9],
        [80, 45, 40, 50, 99, 90, 75, 0, 41, 5, 0, 0, 0, 1, 0, 1, 78, 0, 2, 0, 5],
        [85, 30, 30, 60, 99, 92, 80, 0, 39, 0, 0, 0, 0, 2, 0, 2, 99, 0, 1, 0, 7],
        [75, 40, 25, 55, 99, 85, 70, 0, 39, 0, 12, 0, 3, 3, 0, 1, 85, 0, 1, 0, 8],
        [99, 35, 30, 65, 99, 90, 80, 0, 39, 0, 0, 0, 0, 2, 0, 2, 99, 0, 1, 0, 7],
    ],
    "globals": [99, 99, 99, 99, 50, 50, 50, 50, 21, 6, 1, 35, 0, 5, 0, 0, 0, 3, 24],
}

# The example project's set, before the core exports it.
SMALL_SET = """movy1
bpm 11600
swing 54
link 0
key 0 1
sg 0 0 1 1
tk 0 0 0
au 0 0 64 synth:Decay
rt 0 1 0
cl 0 0 16 0 0:12:36:110:0;96:12:38:100:4;192:12:36:110:8;288:12:38:100:12
cp 0 0 1 1 0 0
cl 0 1 16 0 0:12:36:110:0;96:12:38:100:4;192:12:36:110:8;216:12:36:90:9;288:12:38:100:12;336:6:42:80:14
cp 0 1 1 1 0 0
tk 1 0 0
au 1 0 40 synth:Timbre
rt 1 1 1
cl 1 0 16 0 0:40:36:100:0;48:40:36:100:2;96:40:43:100:4;144:40:36:100:6;192:40:39:100:8;240:40:36:100:10;288:40:43:100:12;336:40:46:100:14
cp 1 0 1 1 0 0
lk 1 0 0:0:40;0:4:64;0:8:90;0:12:64
cl 1 1 16 0 0:40:38:100:0;96:40:45:100:4;192:40:41:100:8;288:40:48:100:12
cp 1 1 1 1 0 0
tk 2 0 0
rt 2 1 2
cl 2 1 16 0 0:380:60:85:0;0:380:63:85:0;0:380:67:85:0
cp 2 1 1 1 0 0
"""


class Registry:
    def __init__(self):
        render = BUILD / "fm1-render"
        self.listed = json.loads(subprocess.check_output([str(render), "--list"]))
        self.mod = json.loads(subprocess.check_output([str(render), "--list-mod"]))
        # The metadata export, as C writes it (fm1-render --meta).
        self.meta_text = subprocess.check_output([str(render), "--meta"]).decode()
        self.meta = canon.loads(self.meta_text)
        self.eng = {e["id"]: e for e in self.listed}
        self.kinds = {k["id"]: k for k in self.mod["kinds"]}


def value(p, v):
    """A value as a file writes it: an entry's name, or a float32."""
    if p["type"] == 1:
        return p["names"][int(v)]
    v = canon.f32(v)
    return int(v) if v == int(v) else v


def params(table, over=None, only=None, skip=()):
    """Every parameter in uid order, at its default unless `over` sets it."""
    over = over or {}
    out = {}
    for p in sorted(table, key=lambda p: p["uid"]):
        if (only is not None and p["name"] not in only) or p["name"] in skip:
            continue
        v = over.get(p["name"], p["def"])
        out[p["name"]] = v if isinstance(v, str) else value(p, v)
    return out


def core_export(text, tracks=8):
    """A set as the sequencer core exports it, as its lines."""
    with tempfile.TemporaryDirectory() as d:
        src, dst = Path(d) / "in.movy1", Path(d) / "out.movy1"
        src.write_text(text)
        subprocess.run([str(BUILD / "fm1-seq"), "--tracks", str(tracks), "--seq", str(src),
                        "--export", str(dst), "--end", "64"], check=True, stdout=subprocess.DEVNULL)
        return dst.read_text().split("\n")[:-1]


def guide_like_set():
    """§3.1's set: 6 tracks, 7 scenes, 40 clips, 1,444 notes, 160 locks, the
    song note's 4-minute song list; repetitive, as real music is."""
    rnd = random.Random(7)
    lines = ["movy1", "bpm 11600", "swing 54", "link 0", "sg 0 0 1 1 2 2 3 3 4 4 2 1 3 3 5 5 6 6 6 6"]
    lines += [f"tk {t} 0 0" for t in range(6)]
    for t in range(6):
        lines += [f"au {t} 0 64 synth:Timbre", f"au {t} 1 40 synth:Decay"]
    lens = [4, 4, 8, 8, 4, 8, 4]
    for t in range(6):
        for sc in range(7):
            if t == 5 and sc in (0, 1):
                continue
            bars = lens[sc]
            steps = bars * 16
            n = []
            for b in range(bars):
                if t == 0:
                    n += [(b * 16 + q * 4, 12, 36, 110) for q in range(4)]
                    n += [(b * 16 + q * 4, 12, 38, 100) for q in (1, 3)]
                    n += [(b * 16 + e * 2, 6, 42, 80 if e % 2 else 95) for e in range(8)]
                elif t == 1:
                    riff = [36, 36, 43, 36, 39, 36, 43, 46]
                    n += [(b * 16 + e * 2, 40, p + sc % 3, 100) for e, p in enumerate(riff)]
                elif t in (2, 3):
                    n += [(b * 16, 380, p + (b % 4) * 2, 85) for p in (60, 63, 67)]
                elif b % 2 == 0:
                    phrase = [(0, 72), (3, 74), (6, 75), (8, 77), (12, 74), (16, 72), (20, 70), (24, 67),
                              (28, 70)]
                    n += [(b * 16 + s, 60, p, 96) for s, p in phrase]
            n.sort()
            lines.append(f"cl {t} {sc} {steps} 0 " +
                         ";".join(f"{s * 24}:{g}:{p}:{v}:{s}" for s, g, p, v in n))
            lines.append(f"cp {t} {sc} 1 1 0 0")
            if t in (1, 4) and sc in (2, 3, 6):
                lines.append(f"lk {t} {sc} " +
                             ";".join(f"0:{s}:{rnd.randint(30, 100)}" for s in range(0, steps, 4)))
    return core_export("\n".join(lines) + "\n")


class Examples:
    def __init__(self, reg):
        self.r = reg

    def unit(self, eid, over=None):
        return {"engine": eid, "params": params(self.r.eng[eid]["params"], over)}

    def per_pad(self, eid):
        """A pad kit's per-pad parameters: its PER_FOCUS ones (engine API v4)."""
        return [p["name"] for p in self.r.eng[eid]["params"] if "per_focus" in p["flags"]]

    def sound(self, eid, over=None, level=100, inserts=(None, None), mfx=(), pads=None):
        pp = self.per_pad(eid)
        s = {"engine": eid, "params": params(self.r.eng[eid]["params"], over, skip=pp or ())}
        if pp:
            s["pads"] = pads
        s.update(level=level, inserts=list(inserts), midi_fx=list(mfx))
        return s

    def drum_pads(self):
        rnd = random.Random(3)
        out = []
        for k in range(16):
            over = {"Tune": [0, -2, 3, 0, 5, -5, 7, -7, 0, -3, 2, 0, 2, 0, 4, 0][k],
                    "Decay": round(rnd.uniform(0.2, 0.8), 2), "Level": [0.9, 0.6, 0.8, 0.7][k % 4],
                    "Tone": round(rnd.uniform(0.3, 0.7), 2)}
            out.append(params(self.r.eng["drums"]["params"], over, only=self.per_pad("drums")))
        return out

    def arp(self, on, over=None):
        return {"engine": "arp", "on": on, "params": params(self.r.eng["arp"]["params"], over)}

    def module(self, pos, kind, over=None):
        return {"pos": pos, "kind": kind, "params": params(self.r.kinds[kind]["params"], over)}

    @staticmethod
    def cable(slot, frm, to, amount, via=None, pol="auto", curve="lin", voice=False, on=True):
        return {"slot": slot, "on": on, "from": frm, "via": via, "to": to, "amount": amount,
                "offset": 0, "polarity": pol, "curve": curve, "voice": voice, "lock": 0}

    @staticmethod
    def head(kind, name, title, about):
        return {"lunar": "1.0", "kind": kind,
                "made": {"by": "hand"},
                "name": name, "title": title, "about": about, "licence": "MIT"}

    def project(self, set_lines):
        c = self.cable
        doc = self.head("project", "FIRST ORBIT", "First orbit",
                        "The guide's first song: drums, a bass, chords through the arpeggiator "
                        "and an FM lead.")
        doc["session"] = {"current": 2, "octave": 0, "transpose": 0,
                          "key": {"root": "C", "scale": "minor"}}
        doc["sounds"] = [
            self.sound("drums", {"Pad": "1 Kick", "Kit": "Punch", "Accent": 0.6}, level=90,
                       pads=self.drum_pads()),
            # Macro, not Shapes: the project fits the FM-1's RAM (77% with the
            # app's own share; stage A1). The key is the set's `key` line.
            self.sound("macro", {"Model": "VA+Filter", "Harmonics": 0.3, "Timbre": 0.41, "Decay": 0.3},
                       level=80,
                       inserts=[self.unit("filter", {"Type": "Ladder", "Cutoff": 420, "Resonance": 0.3}),
                                self.unit("drive", {"Type": "Tube", "Drive": 6})]),
            self.sound("macro", {"Model": "VA Pair", "Harmonics": 0.35, "Decay": 0.7}, level=70,
                       mfx=[self.arp(True, {"Mode": "Up-Down", "Rate": "1/16", "Octaves": "2"})]),
            self.sound("dx7", {"Patch": "User 1", "Brightness": 0.6}, level=75,
                       inserts=[self.unit("echo", {"Time": 375, "Feedback": 0.45, "Mix": 0.25}), None]),
        ]
        doc["master"] = [self.unit("hall", {"Decay": 0.6, "Mix": 0.2}), self.unit("limit")]
        doc["dx7"] = [DX7_VOICE]
        doc["mod"] = {
            "seed": 1,
            "rack": [self.module(1, "lfo", {"Rate": 0.25, "Shape": "Triangle"}), self.module(2, "lfo"),
                     self.module(3, "env", {"Attack": 0.05, "Decay": 0.4, "Sustain": 0.3}),
                     self.module(4, "env"), self.module(5, "chance")],
            "cables": [
                c(1, {"module": 1, "port": "Out"}, {"unit": "snd2.fx1", "param": "Cutoff"}, 35),
                c(2, {"module": 3, "port": "Env"}, {"unit": "snd3", "param": "Timbre"}, 40, voice=True),
                c(3, {"source": "S3RTRG"}, {"module": 3, "gate": "Gate"}, 100, voice=True),
                c(4, {"module": 2, "port": "Out"}, {"unit": "host", "param": "Amp"}, -12.5,
                  via={"source": "VEL"}, pol="uni", curve="square", on=False),
            ],
        }
        doc["set"] = set_lines
        doc["view"] = {"mode": "home", "sound": 2, "page": 1}
        return doc

    def sound_file(self):
        doc = self.head("sound", "DEEP BASS", "Deep space bass",
                        "Mission 2.3: open the filter with KNOB2 until the bass growls.")
        doc["sound"] = self.sound(
            "shapes", {"Shape": "Saw Sub", "Timbre": 0.41, "Release": 0.2}, level=80,
            inserts=[self.unit("filter", {"Type": "Ladder", "Cutoff": 420, "Resonance": 0.3}), None])
        doc["mod"] = {"rack": [self.module(1, "lfo", {"Rate": 0.25, "Shape": "Triangle"})],
                      "cables": [self.cable(1, {"module": 1, "port": "Out"},
                                            {"unit": "snd.fx1", "param": "Cutoff"}, 35)]}
        doc["view"] = {"mode": "home", "sound": 1, "page": 1}
        return doc

    def fx_file(self):
        doc = self.head("fx", "SPACE VERBS", "Space verbs",
                        "An echo into a hall, with the hall's size breathing.")
        doc["chain"] = [self.unit("echo", {"Time": 375, "Feedback": 0.5, "Mix": 0.3}),
                        self.unit("hall", {"Decay": 0.75, "Size": 0.9, "Mix": 0.35})]
        doc["mod"] = {"rack": [self.module(1, "lfo", {"Rate": 0.1, "Shape": "Sine"})],
                      "cables": [self.cable(1, {"module": 1, "port": "Out"},
                                            {"unit": "fx2", "param": "Size"}, 20)]}
        return doc

    def mods_file(self):
        c = self.cable
        doc = self.head("mods", "WOBBLE", "Wobble",
                        "An LFO on Sound 1's filter, its rate from an envelope.")
        doc["mod"] = {
            "seed": 7,
            "rack": [self.module(1, "lfo", {"Rate": 0.6, "Shape": "Sine", "Sync": "1/8"}),
                     self.module(2, "env", {"Attack": 0.2, "Decay": 0.6})],
            "cables": [
                c(1, {"module": 1, "port": "Out"}, {"unit": "snd1.fx1", "param": "Cutoff"}, 50),
                c(2, {"module": 2, "port": "Env"}, {"module": 1, "param": "Rate"}, 30),
                c(3, {"source": "KEY"}, {"module": 2, "gate": "Gate"}, 100),
            ],
        }
        return doc

    def clip_file(self, set_lines):
        doc = self.head("clip", "BASS A", "Bass riff A",
                        "The bass riff of the first song, with its Timbre locks.")
        keep = [ln for ln in set_lines if ln.startswith(("au 1 ", "cl 1 0 ", "cp 1 0 ", "lk 1 0 "))]
        doc["clip"] = [ln[:3] + "0" + ln[4:] for ln in keep]      # to track 0
        return doc

    @staticmethod
    def settings_file():
        return {"lunar": "1.0", "kind": "settings",
                "made": {"by": "hand"},
                "settings": {"metronome": False, "count_in_click": True, "full_velocity": False,
                             "midi_in_channel": 0}}

    def all(self):
        small = core_export(SMALL_SET)
        meta = subset(self.r.meta, engines={"shapes", "drums", "filter", "arp"}, kinds={"lfo", "env"})
        return {"first-orbit.lunar": self.project(small),
                "deep-bass.sound.lunar": self.sound_file(),
                "space-verbs.fx.lunar": self.fx_file(),
                "wobble.mods.lunar": self.mods_file(),
                "bass-a.clip.lunar": self.clip_file(small),
                "settings.lunar": self.settings_file(),
                "metadata.json": meta}


# ---- a binary prototype of §8's layout, to size it ---------------------------------
def _kv(items):
    out = struct.pack("<H", len(items))
    for k, v in items:
        if isinstance(v, str):
            b = v.encode()
            out += struct.pack("<HBB", k, 3, len(b)) + b
        elif isinstance(v, float):
            out += struct.pack("<HBBf", k, 2, 4, v)
        else:
            out += struct.pack("<HBBi", k, 1, 4, v)
    return out


def _unit_bytes(reg, u, role, snd, slot, level=None):
    table = {p["name"]: p for p in reg.eng[u["engine"]]["params"]}

    def rec(name, v, focus):
        p = table[name]
        b = struct.pack("<I", p["names"].index(v)) if p["type"] == 1 else struct.pack("<f", v)
        return struct.pack("<HBB", p["uid"], focus, p["type"]) + b
    recs = [rec(n, v, 0xFF) for n, v in u["params"].items()]
    for k, pad in enumerate(u.get("pads") or []):
        recs += [rec(n, v, k) for n, v in pad.items()]
    idb = u["engine"].encode()
    head = struct.pack("<BBBBB", role, snd, slot, 1 if u.get("on", True) else 0, len(idb)) + idb
    return head + struct.pack("<H", len(recs)) + b"".join(recs) + \
        _kv([(1, float(level))] if level is not None else [])


def _seqs(lines):
    out = bytearray()
    for ln in lines:
        w = ln.split(" ")
        if w[0] == "cl":
            notes = w[5].split(";") if len(w) > 5 and w[5] else []
            out += struct.pack("<BBHBBBBbBH", *map(int, w[1:5]), 1, 1, 0, 0, 0, len(notes))
            for n in notes:
                out += struct.pack("<HHBBH", *map(int, n.split(":")))
        elif w[0] == "lk":
            items = w[3].split(";")
            out += struct.pack("<BBH", int(w[1]), int(w[2]), len(items))
            for it in items:
                out += struct.pack("<BBB", *map(int, it.split(":")))
        elif w[0] != "cp":
            out += ln.encode() + b"\n"
    return bytes(out)


def binary_prototype(reg, doc):
    chunks = [_kv([(1, doc["name"]), (2, doc["title"]), (3, doc["about"]), (4, doc["licence"])]),
              _kv([(1, doc["session"]["current"]), (2, 0), (3, 0), (4, 0), (5, 1)])]
    for k, s in enumerate(doc["sounds"]):
        if s:
            chunks.append(_unit_bytes(reg, s, 0, k, 0, s["level"]))
            chunks += [_unit_bytes(reg, u, 1, k, j) for j, u in enumerate(s["inserts"]) if u]
            chunks += [_unit_bytes(reg, u, 4, k, j) for j, u in enumerate(s["midi_fx"]) if u]
    chunks += [_unit_bytes(reg, u, 2, 0, j) for j, u in enumerate(doc["master"]) if u]
    for v in doc["dx7"]:
        vced = bytes(sum(v["ops"], []) + v["globals"]) + v["name"].ljust(10).encode()
        chunks.append(struct.pack("<BB", v["slot"], 1) + vced + b"\0\0\0")
    m = doc["mod"]
    mb = struct.pack("<I", m["seed"])
    for x in m["rack"]:
        kd = reg.kinds[x["kind"]]
        mb += kd["guid"].encode() + struct.pack("<BB", x["pos"], len(x["params"]))
        for n, v in x["params"].items():
            p = next(p for p in kd["params"] if p["name"] == n)
            mb += struct.pack("<Hf", p["uid"], float(p["names"].index(v)) if p["type"] == 1 else float(v))
        mb += struct.pack("<BH", 0, 0)
    chunks.append(mb + bytes(12 * 32))
    chunks.append(_seqs(doc["set"]))
    chunks.append(_kv([(1, 0), (2, 2), (3, 1)]))
    body = b"".join(c + bytes((-len(c)) % 4) for c in chunks)
    return bytes(32) + bytes(20 * len(chunks) + 4) + body


def deflate(b, wbits=15):
    c = zlib.compressobj(9, zlib.DEFLATED, -wbits)
    return c.compress(b) + c.flush()


def link(b):
    return len(base64.urlsafe_b64encode(deflate(b)).rstrip(b"="))


def measure(reg, ex):
    big = guide_like_set()
    doc = ex.project(big)
    pretty = canon.dumps(doc).encode()
    comp = canon.compact(doc).encode()
    rest = canon.compact(dict(doc, set=[])).encode()
    binary = binary_prototype(reg, doc)
    notes = sum(len(ln.split(" ")[5].split(";")) for ln in big if ln.startswith("cl "))
    print(f"guide-like project: {sum(ln.startswith('cl ') for ln in big)} clips, {notes} notes, "
          f"set {len(chr(10).join(big)) + 1:,} B")
    nlines = pretty.count(b"\n")
    print(f"JSON canonical {len(pretty):,} B; deflate-raw 32 KiB {len(deflate(pretty)):,}, "
          f"4 KiB {len(deflate(pretty, 12)):,}, 1 KiB {len(deflate(pretty, 10)):,}; {nlines} lines")
    print(f"JSON compact {len(comp):,} B; deflate-raw 32 KiB {len(deflate(comp)):,}, "
          f"4 KiB {len(deflate(comp, 12)):,}; link {link(comp):,} characters")
    print(f"  the set's lines {len(canon.compact(big).encode()):,} B; everything else "
          f"{len(rest):,} B, deflated {len(deflate(rest)):,}")
    print(f"binary prototype {len(binary):,} B; deflate-raw 32 KiB {len(deflate(binary)):,}, "
          f"4 KiB {len(deflate(binary, 12)):,}; link {link(binary):,} characters")
    for name, d in ex.all().items():
        text = canon.dumps(d).encode()
        print(f"  {name:24} {len(text):7,} B, compact {len(canon.compact(d).encode()):7,} B, "
              f"link {link(canon.compact(d).encode()):6,} characters")
    full = reg.meta_text.encode()
    print(f"full metadata export {len(full):,} B, deflated {len(zlib.compress(full, 9)):,} B")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--write", action="store_true", help="rewrite engines/state/examples/")
    ap.add_argument("--measure", action="store_true", help="print the note's §3.4 numbers")
    args = ap.parse_args()
    if not (args.write or args.measure):
        ap.error("say --write, --measure or both")
    reg = Registry()
    ex = Examples(reg)
    if args.write:
        OUT.mkdir(parents=True, exist_ok=True)
        for name, doc in ex.all().items():
            (OUT / name).write_text(canon.dumps(doc))
            print("wrote", (OUT / name).relative_to(ROOT))
    if args.measure:
        measure(reg, ex)


if __name__ == "__main__":
    main()
