#!/usr/bin/env python3
"""Lunar Modulator's saved-state files in Python (stage P1;
notes/2026-10-06-state-files.md §6.1, §7, §8, §12.6; engines/state/README.md).

An independent reader and writer of both encodings, written from the note
and not from the C: the canonical JSON (people, links, git) and the binary
container (the device). Its records, printed one JSON object a line, equal
`fm1-state records` for every file, and both write the same bytes, which
tests/test_state_codec.py holds.

    python3 tools/lunar_state.py check FILE        # the schema, the build's names, canonical
    python3 tools/lunar_state.py canon FILE [-o OUT] [--compact]
    python3 tools/lunar_state.py pack FILE [-o OUT] [--store]
    python3 tools/lunar_state.py unpack FILE [-o OUT]
    python3 tools/lunar_state.py records FILE
    python3 tools/lunar_state.py url FILE           # the #lunar= fragment of a launch link (§12.4)

Names come from the build's parameter metadata export (`fm1-render --meta`,
engines/state/schema/metadata.schema.json: every engine's, effect's, MIDI
effect's and modulation kind's parameters, ranges, defaults, list entries,
pad roles and old names, and the ids a build knows but lacks), or from a
saved copy of it (`--meta FILE`), so P1 resolves a name exactly as the
build that wrote the export. It never changes app state; only the C loader
does. MIT licence, like the rest of the repository.
"""
import argparse
import base64
import json
import re
import struct
import subprocess
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tests import state_canon as canon  # noqa: E402  the canonical layout's reference

TOOL = ROOT / "engines" / "build" / "fm1-state"
RENDER = ROOT / "engines" / "build" / "fm1-render"
SCHEMA = ROOT / "engines" / "state" / "schema"

MAJOR, MINOR = 1, 0
KINDS = [None, "project", "sound", "fx", "mods", "clip", "settings", "set", "dx7bank"]
KIND_CAP = [0, 262144, 32768, 32768, 65536, 32768, 4096, 65536, 65536]
ROLES = ["none", "sound", "insert", "master", "mfx", "module"]
SOUND, INSERT, MASTER, MFX, MODULE = 1, 2, 3, 4, 5
INFO = [None, "by", "version", "commit", "name", "title", "about", "author", "licence"]
INFO_CAP = {4: 16, 5: 80, 6: 240, 7: 64, 8: 32}
SETTINGS = [None, "metronome", "count_in_click", "full_velocity", "midi_in_channel"]
MODES = ["home", "fx", "glo", "seq", "session", "song", "rack", "matrix", "chain"]
VKEYS = ["sound", "page", "unit", "track", "bar", "panel", "pos", "slot", "entry"]
PANELS = ["track", "set", "clip", "step"]
ROOTS = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
POLARITY = ["auto", "uni", "bi", "inv"]
CURVES = ["lin", "square", "cube", "root", "cbrt", "exp", "log", "s"]
OP_MAX = [99, 99, 99, 99, 99, 99, 99, 99, 99, 99, 99, 3, 3, 7, 3, 7, 99, 1, 31, 99, 14]
GLOB_MAX = [99, 99, 99, 99, 99, 99, 99, 99, 31, 7, 1, 99, 99, 99, 99, 1, 5, 7, 48]
NONE = 0xFF
CHAIN3, CHAIN4 = 42, 43
SLOT_ON, POL_SHIFT, GATE_DST, CURVE_SHIFT, VOICE = 0x01, 1, 0x08, 4, 0x80


# ---- Refusals and the report ---------------------------------------------------------
class Refused(Exception):
    def __init__(self, code, what, path=""):
        super().__init__(f"{code}: {what} {path}".strip())
        self.code, self.what, self.path = code, what, path


class Report:
    def __init__(self):
        self.code = "OK"
        self.what = self.path = self.name = self.known = self.first_skip = ""
        self.skipped = self.repaired = self.defaulted = self.unknown = 0

    def skip(self, what, path=""):
        if not self.skipped:
            self.first_skip = f"{path}: {what}"
        self.skipped += 1

    def unknown_name(self, name, known=""):
        """An engine or kind the build lacks; `known` is its known-ids reason
        (gpl, planned, retired), "" when no list names it."""
        if not self.unknown:
            self.name, self.known = name, known
        self.unknown += 1


# ---- Names --------------------------------------------------------------------------------
def ascii_lower(s):
    return "".join(chr(ord(c) + 32) if "A" <= c <= "Z" else c for c in s)


def _meta_num(x):
    """A metadata number (kept as its text) as the float32 it names, exactly."""
    return canon.f32_of(str(x))


class Param:
    def __init__(self, d, focus=0):
        self.uid, self.name, self.abbr = d["uid"], d["name"], d.get("abbr") or ""
        self.enum = d["type"] == "enum"
        self.min, self.max, self.default = (_meta_num(d[k]) for k in ("min", "max", "def"))
        self.entries = d.get("entries")
        self.focus = focus
        self.aliases = list(d.get("aliases", []))               # old names
        self.entry_aliases = dict(d.get("entry_aliases", {}))   # old entry names -> index

    def count(self):
        return int(self.max - self.min) + 1


def find_param(params, key):
    """fm1_state_param_find: #UID, the name exactly, without ASCII case, by
    abbreviation, then by an old name (the owner's aliases)."""
    if len(key) >= 2 and key[0] == "#":
        if key[1] == "0" or len(key) > 5 or not key[1:].isdigit() or not key[1:].isascii():
            return None
        uid = int(key[1:])
        return next((i for i, p in enumerate(params) if p.uid == uid), None)
    for test in (lambda p: p.name == key, lambda p: ascii_lower(p.name) == ascii_lower(key),
                 lambda p: p.abbr and ascii_lower(p.abbr) == ascii_lower(key),
                 lambda p: any(ascii_lower(a) == ascii_lower(key) for a in p.aliases)):
        for i, p in enumerate(params):
            if test(p):
                return i
    return None


def find_entry(p, s):
    """fm1_state_entry_find: exactly, without ASCII case, then an old name."""
    if not p.enum or not p.entries:
        return None
    for test in (lambda e: e == s, lambda e: ascii_lower(e) == ascii_lower(s)):
        for k, e in enumerate(p.entries):
            if test(e):
                return k
    for old, k in p.entry_aliases.items():
        if ascii_lower(old) == ascii_lower(s) and k < p.count():
            return k
    return None


def _params(ps, kit):
    """A table's parameters with their pad roles: FOCUS 1, PER_FOCUS 2 (only
    in a kit, an engine with a FOCUS parameter), else 0."""
    def role(p):
        f = p.get("flags", [])
        return 1 if "focus" in f else 2 if kit and "per_focus" in f else 0
    return [Param(p, role(p)) for p in ps]


class Engine:
    ROLE = {"sound": "sound", "audio_fx": "fx", "midi_fx": "mfx"}

    def __init__(self, d):
        self.id, self.role = d["id"], self.ROLE[d["kind"]]
        self.pads = d["pads"]["count"] if d.get("pads") else 0
        kit = any("focus" in p.get("flags", []) for p in d["params"])
        self.params = _params(d["params"], kit)
        self.retired = dict(d.get("retired", {}))      # removed parameters' last names -> uid


class Kind:
    def __init__(self, d):
        self.id = d["id"]
        self.params = _params(d["params"], False)
        self.outs = [p["name"] for p in d["outs"]]
        self.gates = [p["name"] for p in d["gates"]]


class Names:
    """The build's names, ranges and defaults: its metadata export."""

    def __init__(self, meta):
        if meta.get("kind") != "metadata":
            raise ValueError("not a parameter metadata export")
        mod = meta["mod"]
        self.engines = [Engine(e) for e in meta["engines"]]
        self.kinds = {k["id"]: Kind(k) for k in mod["kinds"]}
        self.sources = {s["id"]: s["name"] for s in mod["sources"]}
        self.source_id = {s["name"]: s["id"] for s in mod["sources"]}
        self.host = _params(mod["host"], False)
        self.known = {k["id"]: k["reason"] for k in meta["known_ids"]}

    @staticmethod
    def parse(text):
        """The export's text, numbers kept exact (as their text)."""
        return json.loads(text, parse_float=str)

    @classmethod
    def from_build(cls, render=RENDER):
        return cls(cls.parse(subprocess.run([str(render), "--meta"], check=True, capture_output=True,
                                            text=True).stdout))

    @classmethod
    def from_file(cls, path):
        return cls(cls.parse(Path(path).read_text(encoding="utf-8")))

    def engine(self, role, eid):
        """fm1_state_engine: sounds for SOUND, audio effects for INSERT and
        MASTER, MIDI effects for MFX."""
        want = {SOUND: "sound", INSERT: "fx", MASTER: "fx", MFX: "mfx"}.get(role)
        pool = [e for e in self.engines if (e.role == "mfx") == (role == MFX)]
        e = next((e for e in pool if e.id == eid), None)
        return e if e and e.role == want else None


# ---- Numbers ---------------------------------------------------------------------------------
def f32_bits(x):
    return struct.unpack("<I", struct.pack("<f", x))[0]


def bits_f32(b):
    return struct.unpack("<f", struct.pack("<I", b))[0]


class Num(str):
    """A JSON number's text, kept exact."""


INT_RE = re.compile(r"-?(0|[1-9][0-9]*)$")
INT64 = 2 ** 63 - 1


# ---- Units' codes and names ------------------------------------------------------------------
def unit_code(kind, s):
    if s == "host":
        return 3
    if kind == "sound":
        return {"snd": 0, "snd.fx1": 20, "snd.fx2": 21}.get(s)
    if kind == "fx":
        return {"fx1": 1, "fx2": 2, "fx3": CHAIN3, "fx4": CHAIN4}.get(s)
    if s in ("fx1", "fx2"):
        return 1 if s == "fx1" else 2
    m = re.fullmatch(r"snd([1-4])(\.fx([12]))?", s)
    if not m:
        return None
    k = int(m.group(1)) - 1
    if m.group(3):
        return 20 + 4 * k + int(m.group(3)) - 1
    return 16 + k if k else 0


def code_name(kind, code):
    if code == 3:
        return "host"
    if kind == "sound":
        return {0: "snd", 20: "snd.fx1", 21: "snd.fx2"}.get(code)
    if kind == "fx":
        return {1: "fx1", 2: "fx2", CHAIN3: "fx3", CHAIN4: "fx4"}.get(code)
    if code in (1, 2):
        return f"fx{code}"
    if code == 0 or 17 <= code <= 19:
        return f"snd{code - 16 + 1 if code else 1}"
    if 20 <= code < 36 and (code - 20) % 4 < 2:
        return f"snd{(code - 20) // 4 + 1}.fx{(code - 20) % 4 + 1}"
    return None


def code_index(code):
    """A cable unit code to the unit places of sounds 0-3, inserts 4-11 and
    master or chain 12-15 (as the C reader's code_index)."""
    if code == 0:
        return 0
    if 17 <= code <= 19:
        return code - 16
    if 20 <= code < 36 and (code - 20) % 4 < 2:
        return 4 + 2 * ((code - 20) // 4) + (code - 20) % 4
    return {1: 12, 2: 13, CHAIN3: 14, CHAIN4: 15}.get(code)


def unit_index(role, sound, slot):
    if role == SOUND:
        return sound
    if role == INSERT:
        return 4 + 2 * sound + slot
    if role == MASTER:
        return 12 + slot
    return None


# ---- Reading JSON --------------------------------------------------------------------------------
class Obj(list):
    """A JSON object as its (key, value) pairs, in order."""


MEMBERS = {
    "doc": ["$schema", "lunar", "kind", "made", "name", "title", "about", "author", "licence", "session",
            "sounds", "sound", "master", "chain", "dx7", "mod", "set", "clip", "settings", "view"],
    "made": ["by", "version", "commit"],
    "session": ["current", "octave", "transpose", "key"],
    "key": ["root", "scale"],
    "unit": ["engine", "on", "params", "pads", "level", "inserts", "midi_fx"],
    "dx7": ["slot", "name", "ops", "globals"],
    "mod": ["seed", "rack", "cables"],
    "module": ["pos", "kind", "params", "data"],
    "data": ["version", "hex"],
    "cable": ["slot", "on", "from", "via", "to", "amount", "offset", "polarity", "curve", "voice", "lock"],
    "ref": ["source", "module", "port"],
    "target": ["unit", "module", "param", "gate"],
    "view": ["mode", "sound", "page", "unit", "track", "bar", "panel", "pos", "slot", "entry"],
    "settings": ["metronome", "count_in_click", "full_velocity", "midi_in_channel"],
}
DOC_KINDS = {"session": {"project"}, "sounds": {"project"}, "master": {"project"}, "set": {"project"},
             "sound": {"sound"}, "chain": {"fx"}, "dx7": {"project", "sound"},
             "mod": {"project", "sound", "fx", "mods"}, "clip": {"clip"}, "settings": {"settings"},
             "view": {"project", "sound", "fx", "mods", "clip"}}
NEEDS = {"project": "sounds", "sound": "sound", "fx": "chain", "mods": "mod", "clip": "clip",
         "settings": "settings"}


def _parse(data):
    """JSON to a tree of Obj, list, str, Num, bool and None, refusing what the
    C tokenizer refuses (byte-order mark, bad UTF-8, U+0000, surrogate
    halves, NaN and the like) and its caps."""
    if data[:1] == b"\xef":
        raise Refused("NOT_LUNAR", "a byte-order mark")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as e:
        raise Refused("NOT_LUNAR" if e.start == 0 else "BAD", "bad UTF-8") from None

    def pairs(items):
        return Obj(items)

    def const(name):
        raise ValueError(name)
    try:
        tree = json.loads(text, object_pairs_hook=pairs, parse_float=Num, parse_int=Num,
                          parse_constant=const)
    except (ValueError, RecursionError) as e:
        if not text.strip() or text.lstrip()[:1] not in "{[" or getattr(e, "pos", 1) == 0:
            raise Refused("NOT_LUNAR", "an empty file, or no JSON object") from None
        raise Refused("BAD", "not well-formed JSON") from None

    def walk(v, depth):
        if isinstance(v, (Obj, list)):
            if depth >= 8:
                raise Refused("TOO_BIG", "nested too deep")
            if len(v) > (64 if isinstance(v, Obj) else 8192):
                raise Refused("TOO_BIG", "too many members or items")
            if isinstance(v, Obj) and len({k for k, _ in v}) != len(v):
                raise Refused("BAD", "duplicate key")
            for x in v:
                if isinstance(v, Obj):
                    k, x = x
                    if len(k.encode("utf-8", "surrogatepass")) > 64:
                        raise Refused("TOO_BIG", "a key past 64 bytes")
                    text_ok(k)
                walk(x, depth + 1)
        elif isinstance(v, Num):
            if len(v) > 32:
                raise Refused("TOO_BIG", "a number past 32 characters")
        elif isinstance(v, str):
            if len(v.encode("utf-8", "surrogatepass")) > 16384:
                raise Refused("TOO_BIG", "a string past 16 KiB")
            text_ok(v)

    def text_ok(s):
        if "\0" in s or any(0xD800 <= ord(c) <= 0xDFFF for c in s):
            raise Refused("BAD", "U+0000 or a surrogate half")
    walk(tree, 0)
    return tree


def _utf8(s):
    return s.encode("utf-8")


class JsonReader:
    """The tree to records, as state_json_read.c gives them."""

    def __init__(self, names):
        self.nm = names
        self.rep = Report()
        self.out = []
        self.kind = None
        self.unit_e = [None] * 16
        self.rack = [None] * 8
        self.rack_pos = 0
        self.cable_slots = 0
        self.dx7_slots = 0
        self.data_total = 0
        self.path = []

    # ---- helpers
    def where(self):
        return "/" + "/".join(str(p) for p in self.path) if self.path else "/"

    def bad(self, what, code="BAD"):
        raise Refused(code, what, self.where())

    def skip(self, what):
        self.rep.skip(what, self.where())

    def emit(self, rec):
        self.out.append(rec)

    def int_value(self, v, lo, hi):
        if not isinstance(v, Num):
            self.bad("an integer was expected")
        if not INT_RE.match(v):
            self.bad("a fraction or an exponent where an integer belongs")
        x = int(v)
        if not -INT64 <= x <= INT64:
            self.rep.repaired += 1
            return lo if v.startswith("-") else hi
        if x < lo:
            self.rep.repaired += 1
            return lo
        if x > hi:
            self.rep.repaired += 1
            return hi
        return x

    def float_value(self, v):
        if not isinstance(v, Num):
            self.bad("a number was expected")
        f = canon.f32_of(v)
        if f is None:
            self.bad("a number beyond a float32")
        return 0.0 if f == 0 else f

    def bool_value(self, v):
        if v is True or v is False:
            return v
        self.bad("true or false was expected")

    def members(self, obj, ctx, dup_ok=False):
        """(index, key, value, known) in order, refusing duplicates."""
        known = MEMBERS[ctx]
        seen = set()
        unknown = set()
        for k, v in obj:
            if k in known:
                if k in seen:
                    self.path.append(k)
                    self.bad("duplicate key")
                seen.add(k)
                yield k, v, True
            else:
                if k in unknown:
                    self.path.append(k)
                    self.bad("duplicate key")
                unknown.add(k)
                yield k, v, False

    # ---- text
    def text(self, key, v):
        if not isinstance(v, str) or isinstance(v, Num):
            self.bad("text was expected")
        cap = INFO_CAP.get(key, 64)
        out, n, over = [], 0, False
        for ch in v:
            cp = ord(ch)
            if cp < 0x20 or cp == 0x7F or 0x202A <= cp <= 0x202E or 0x2066 <= cp <= 0x2069:
                keep = False
            elif key in (1, 2, 3, 4):
                keep = cp < 0x7F
            elif key == 8:
                keep = ch.isascii() and (ch.isalnum() or ch in ".+-")
            else:
                keep = True
            if keep and n >= cap:
                keep = False
                if not over:
                    over = True
                    self.rep.repaired += 1
            elif not keep:
                self.rep.repaired += 1
            if keep:
                out.append(ch)
                n += 1
        self.emit({"rec": "info", "key": INFO[key], "text": "".join(out)})

    # ---- the document
    def read(self, tree):
        if not isinstance(tree, Obj):
            raise Refused("NOT_LUNAR", "not a JSON object")
        top = 0
        seen = set()
        for k, v, known in self.members(tree, "doc"):
            self.path = [k]
            if top < 2:
                if not known:
                    raise Refused("NOT_LUNAR" if top == 0 else "BAD",
                                  "a Lunar Modulator file opens with lunar" if top == 0 else
                                  "context first: kind follows lunar", self.where())
                if top == 0 and k not in ("lunar", "$schema"):
                    raise Refused("NOT_LUNAR", "a Lunar Modulator file opens with lunar", self.where())
                if k == "$schema" and top != 0:
                    self.bad("context first: $schema comes before lunar")
                if top == 1 and k != "kind":
                    self.bad("context first: kind follows lunar")
            elif k == "$schema":
                self.bad("context first: $schema comes before lunar")
            if not known:
                self.skip("a member this build does not know")
                continue
            if top >= 2 and k in DOC_KINDS and self.kind not in DOC_KINDS[k]:
                self.bad("not a member of this kind of file")
            if k in ("sounds", "master", "sound", "chain") and "mod" in seen:
                self.bad("context first: mod comes after the units its cables name")
            seen.add(k)
            if k == "$schema":
                if not isinstance(v, str) or isinstance(v, Num):
                    self.bad("$schema is a string")
            elif k == "lunar":
                if not isinstance(v, str) or isinstance(v, Num):
                    raise Refused("NOT_LUNAR", "lunar is the format level, \"1.0\"", self.where())
                m = re.fullmatch(r"([0-9]{1,3})\.([0-9]{1,3})", v)
                if not m:
                    raise Refused("NOT_LUNAR", "lunar is the format level, \"1.0\"", self.where())
                self.major, self.minor = int(m.group(1)), int(m.group(2))
                if self.major != MAJOR or self.minor > MINOR:
                    raise Refused("TOO_NEW", "made with a newer Lunar Modulator", self.where())
                top = 1
            elif k == "kind":
                if not isinstance(v, str) or isinstance(v, Num):
                    self.bad("kind is a string")
                if v == "metadata":
                    self.bad("the metadata export is not a state to load")
                if v not in NEEDS:
                    self.bad("not a kind of file this build knows")
                self.kind = v
                top = 2
                self.emit({"rec": "head", "kind": v, "major": MAJOR, "minor": self.minor})
            elif k == "made":
                self.want(v, Obj)
                for mk, mv, mknown in self.members(v, "made"):
                    self.path = ["made", mk]
                    if not mknown:
                        self.skip("a member this build does not know")
                        continue
                    self.text({"by": 1, "version": 2, "commit": 3}[mk], mv)
            elif k in ("name", "title", "about", "author", "licence"):
                self.text({"name": 4, "title": 5, "about": 6, "author": 7, "licence": 8}[k], v)
            elif k == "session":
                self.session(v)
            elif k == "sounds":
                self.want(v, list)
                for i, s in enumerate(v):
                    self.path = ["sounds", i]
                    if i >= 4:
                        self.bad("a project has four sound units")
                    self.unit_item(s, SOUND, i, 0)
            elif k == "sound":
                self.want(v, Obj)
                self.unit(v, SOUND, 0, 0)
            elif k in ("master", "chain"):
                self.want(v, list)
                for i, u in enumerate(v):
                    self.path = [k, i]
                    if i >= (2 if k == "master" else 4):
                        self.bad("a project has two master slots" if k == "master" else
                                 "a chain has at most four effects")
                    self.unit_item(u, MASTER, 0, i)
            elif k == "dx7":
                self.dx7(v)
            elif k == "mod":
                self.mod(v)
            elif k in ("set", "clip"):
                self.lines(v, k)
            elif k == "settings":
                self.settings(v)
            elif k == "view":
                self.view(v)
        self.path = []
        if top < 2:
            raise Refused("NOT_LUNAR", "a Lunar Modulator file opens with lunar and kind", "/")
        if NEEDS[self.kind] not in seen:
            raise Refused("BAD", "a member this kind of file needs is missing", "/")
        self.emit({"rec": "end"})
        return self.out

    def want(self, v, t):
        if t is Obj and not isinstance(v, Obj):
            self.bad("an object was expected")
        if t is list and (not isinstance(v, list) or isinstance(v, Obj)):
            self.bad("an array was expected")

    def session(self, v):
        self.want(v, Obj)
        rec = {"rec": "session", "current": 0, "octave": 0, "transpose": 0}
        key = {}
        for k, x, known in self.members(v, "session"):
            self.path = ["session", k]
            if not known:
                self.skip("a member this build does not know")
                continue
            if k == "current":
                rec["current"] = self.int_value(x, 1, 4) - 1
            elif k == "octave":
                rec["octave"] = self.int_value(x, -3, 3)
            elif k == "transpose":
                rec["transpose"] = self.int_value(x, -12, 12)
            else:
                self.want(x, Obj)
                for kk, kv, kknown in self.members(x, "key"):
                    self.path = ["session", "key", kk]
                    if not kknown:
                        self.skip("a member this build does not know")
                        continue
                    if not isinstance(kv, str) or isinstance(kv, Num):
                        self.bad("a name was expected")
                    if kk == "root":
                        if kv in ROOTS:
                            key["root"] = ROOTS.index(kv)
                        else:
                            self.skip("not a key root")
                    elif re.fullmatch(r"[a-z][a-z0-9-]{0,23}", kv):
                        key["scale"] = kv
                    else:
                        self.skip("not a scale id")
                if len(key) == 2:
                    rec["root"], rec["scale"] = key["root"], key["scale"]
                elif key:
                    self.skip("a key needs its root and its scale")
        self.emit(rec)

    def unit_item(self, v, role, sound, slot):
        if isinstance(v, Obj):
            return self.unit(v, role, sound, slot)
        if v is not None:
            self.bad("a unit (an object) or null was expected")
        if role == SOUND and sound == 0 and self.kind == "project":
            self.bad("Sound 1 is never empty")
        self.emit({"rec": "unit", "role": ROLES[role], "sound": sound, "slot": slot, "engine": ""})

    def unit(self, obj, role, sound, slot):
        base = list(self.path)
        e = None
        has_engine = False
        for k, v, known in self.members(obj, "unit"):
            self.path = base + [k]
            if known and ((k == "on" and role != MFX) or
                          (k in ("pads", "level", "inserts", "midi_fx") and role != SOUND)):
                known = False
            if known and k in ("params", "pads") and not has_engine:
                self.bad("context first: a unit's engine comes before its params and pads")
            if not known:
                self.skip("not a member of this unit" if k in MEMBERS["unit"] else
                          "a member this build does not know")
                continue
            if k == "engine":
                if not isinstance(v, str) or isinstance(v, Num):
                    self.bad("engine is an id")
                if len(_utf8(v)) > 63 or not re.fullmatch(r"[a-z][a-z0-9-]{0,14}", v):
                    self.bad("engine is an id of a-z, 0-9 and -")
                e = self.nm.engine(role, v)
                if not e:
                    self.rep.unknown_name(v, self.nm.known.get(v, ""))
                has_engine = True
                ix = unit_index(role, sound, slot)
                if ix is not None:
                    self.unit_e[ix] = e
                self.emit({"rec": "unit", "role": ROLES[role], "sound": sound, "slot": slot, "engine": v})
            elif k == "on":
                self.emit({"rec": "on", "role": ROLES[role], "sound": sound, "slot": slot,
                           "on": self.bool_value(v)})
            elif k == "params":
                self.want(v, Obj)
                self.params(v, e.params if e else None, role, sound, slot, None, e)
            elif k == "pads":
                self.want(v, list)
                if e and not e.pads:
                    self.skip("pads of an engine that is not a pad kit")
                    continue
                for i, pad in enumerate(v):
                    self.path = base + ["pads", i]
                    if i >= 32 or (e and i >= e.pads):
                        self.bad("more pads than the kit has")
                    self.want(pad, Obj)
                    self.params(pad, e.params if e else None, role, sound, slot, i, e)
            elif k == "level":
                f = self.float_value(v)
                if not f >= 0:
                    f = 0.0
                    self.rep.repaired += 1
                if f > 100:
                    f = 100.0
                    self.rep.repaired += 1
                self.emit({"rec": "level", "sound": sound, "f32": "%08x" % f32_bits(f)})
            elif k in ("inserts", "midi_fx"):
                self.want(v, list)
                for i, u in enumerate(v):
                    self.path = base + [k, i]
                    if k == "inserts" and i >= 2:
                        self.bad("a sound has two inserts")
                    if k == "midi_fx" and i >= 4:
                        self.bad("a sound has at most four MIDI effects")
                    self.unit_item(u, INSERT if k == "inserts" else MFX, sound, i)
        self.path = base
        if not has_engine:
            self.bad("a unit needs its engine")

    def params(self, obj, table, role, sound, slot, focus, e, module=False):
        base = list(self.path)
        seen, unknown = set(), set()
        for k, v in obj:
            self.path = base + [k]
            i = find_param(table, k) if table else None
            if i is not None:
                fk = 0 if module else table[i].focus
                if i in seen:
                    self.bad("duplicate key: two keys name one parameter")
                seen.add(i)
                if focus is None and fk == 2:
                    self.skip("a per-pad value outside pads")
                    continue
                if focus is not None and fk != 2:
                    self.skip("not a per-pad value")
                    continue
                p, uid = table[i], table[i].uid
            else:
                if k in unknown:
                    self.bad("duplicate key")
                unknown.add(k)
                retired = (next((u for n, u in e.retired.items() if ascii_lower(n) == ascii_lower(k)), None)
                           if table and e is not None and not module else None)
                if retired:      # a removed parameter's last name: by its retired uid, as #UID
                    p, uid = None, retired
                elif (len(k) >= 2 and k[0] == "#" and k[1] != "0" and len(k) <= 5 and
                        k[1:].isdigit() and k[1:].isascii() and 1 <= int(k[1:]) <= 4095):
                    p, uid = None, int(k[1:])
                else:
                    self.skip("a name this build does not resolve" if table else
                              "a name for an engine this build lacks")
                    continue
            rec = {"rec": "param", "role": "module" if module else ROLES[role], "sound": sound,
                   "slot": slot, "uid": uid, "focus": focus}
            if p is None:
                if not isinstance(v, Num):
                    if isinstance(v, (Obj, list)) or v is None or isinstance(v, bool):
                        self.bad("a number was expected")
                    self.skip("a value by name for a parameter this build cannot name")
                    continue
                rec["f32"] = "%08x" % f32_bits(self.float_value(v))
            elif p.enum:
                if isinstance(v, str) and not isinstance(v, Num):
                    k2 = find_entry(p, v) if len(_utf8(v)) <= 63 else None
                    if k2 is None:
                        self.skip("not an entry of the list")
                        continue
                    rec["index"] = k2
                else:
                    rec["index"] = self.int_value(v, 0, p.count() - 1)
            else:
                f = self.float_value(v)
                c = p.min if f < p.min else (p.max if f > p.max else f)
                if f32_bits(c) != f32_bits(f):
                    self.rep.repaired += 1
                rec["f32"] = "%08x" % f32_bits(0.0 if c == 0 else c)
            self.emit(rec)
        self.path = base

    def dx7(self, v):
        self.want(v, list)
        for i, voice in enumerate(v):
            self.path = ["dx7", i]
            if i >= 32:
                self.bad("at most 32 FM6 voices")
            self.want(voice, Obj)
            vced = [0] * 145 + [0x20] * 10
            slot, ops_n, glob_n = None, 0, 0
            for k, x, known in self.members(voice, "dx7"):
                self.path = ["dx7", i, k]
                if not known:
                    self.skip("a member this build does not know")
                    continue
                if k == "slot":
                    slot = self.int_value(x, 1, 32) - 1
                elif k == "name":
                    if not isinstance(x, str) or isinstance(x, Num):
                        self.bad("a voice's name is text")
                    raw = _utf8(x)
                    for j in range(10):
                        c = raw[j] if j < len(raw) and j < 63 else 0x20
                        if c < 0x20 or c > 0x7E:
                            c = 0x20
                            self.rep.repaired += 1
                        vced[145 + j] = c
                    if len(raw) > 10:
                        self.rep.repaired += 1
                elif k == "ops":
                    self.want(x, list)
                    ops_n = 0
                    for o, row in enumerate(x):
                        self.path = ["dx7", i, "ops", o]
                        if o >= 6:
                            self.bad("a voice has six operators")
                        self.want(row, list)
                        for j, val in enumerate(row):
                            if j >= 21:
                                self.bad("an operator has 21 values")
                            vced[o * 21 + j] = self.int_value(val, 0, OP_MAX[j])
                            ops_n += 1
                        if len(row) != 21:
                            self.bad("an operator has 21 values")
                    if len(x) != 6:
                        self.bad("a voice has six operators")
                else:
                    self.want(x, list)
                    glob_n = 0
                    for j, val in enumerate(x):
                        if j >= 19:
                            self.bad("a voice has 19 global values")
                        vced[126 + j] = self.int_value(val, 0, GLOB_MAX[j])
                        glob_n += 1
                    if len(x) != 19:
                        self.bad("a voice has 19 global values")
            self.path = ["dx7", i]
            if slot is None or ops_n != 126 or glob_n != 19:
                self.bad("a voice needs its slot, six operators and 19 globals")
            if (self.dx7_slots >> slot) & 1:
                self.bad("two voices in one FM6 slot")
            self.dx7_slots |= 1 << slot
            self.emit({"rec": "dx7", "slot": slot, "vced": bytes(vced).hex()})

    def mod(self, v):
        self.want(v, Obj)
        self.emit({"rec": "mod"})
        has_seed = False
        seen_cables = False
        for k, x, known in self.members(v, "mod"):
            self.path = ["mod", k]
            if not known:
                self.skip("a member this build does not know")
                continue
            if k == "seed":
                self.emit({"rec": "seed", "seed": self.int_value(x, 0, 4294967295)})
                has_seed = True
            elif k == "rack":
                if seen_cables:
                    self.bad("context first: rack comes before cables")
                self.want(x, list)
                for i, m in enumerate(x):
                    self.path = ["mod", "rack", i]
                    if i >= 8:
                        self.bad("a rack has eight positions")
                    self.want(m, Obj)
                    self.module(m, i)
            else:
                seen_cables = True
                self.want(x, list)
                for i, c in enumerate(x):
                    self.path = ["mod", "cables", i]
                    if i >= 32:
                        self.bad("a matrix has 32 slots")
                    self.want(c, Obj)
                    self.cable(c)
        self.path = ["mod"]
        if not has_seed and self.kind in ("project", "mods"):
            self.bad("a project's or a mod rack's mod needs its seed")

    def module(self, obj, i):
        base = list(self.path)
        pos = kind_id = None
        k_obj = None
        emitted = False
        for k, v, known in self.members(obj, "module"):
            self.path = base + [k]
            if not known:
                self.skip("a member this build does not know")
                continue
            if k in ("params", "data") and (pos is None or kind_id is None):
                self.bad("context first: a module's pos and kind come before its params and data")
            if k == "pos":
                p = self.int_value(v, 1, 8) - 1
                if (self.rack_pos >> p) & 1:
                    self.bad("two modules at one rack position")
                self.rack_pos |= 1 << p
                pos = p
            elif k == "kind":
                if not isinstance(v, str) or isinstance(v, Num):
                    self.bad("kind is an id")
                if len(_utf8(v)) > 63 or not re.fullmatch(r"[a-z][a-z0-9-]{0,14}", v):
                    self.bad("kind is an id of a-z, 0-9 and -")
                k_obj = self.nm.kinds.get(v)
                if not k_obj:
                    self.rep.unknown_name(v, self.nm.known.get(v, ""))
                kind_id = v
            elif k == "params":
                self.want(v, Obj)
                self.params(v, k_obj.params if k_obj else None, MODULE, 0, pos, None, None, module=True)
            elif k == "data":
                self.want(v, Obj)
                self.data(v, pos)
            if pos is not None and kind_id is not None and not emitted:
                emitted = True
                self.rack[pos] = k_obj
                self.emit({"rec": "module", "pos": pos, "kind": kind_id})
        self.path = base
        if pos is None or kind_id is None:
            self.bad("a module needs its pos and kind")

    def data(self, obj, pos):
        base = list(self.path)
        version = None
        hexed = None
        for k, v, known in self.members(obj, "data"):
            self.path = base + [k]
            if not known:
                self.skip("a member this build does not know")
                continue
            if k == "version":
                version = self.int_value(v, 0, 255)
            else:
                if version is None:
                    self.bad("context first: pattern data's version comes before its hex")
                if not isinstance(v, str) or isinstance(v, Num):
                    self.bad("pattern data is hex text")
                if not re.fullmatch(r"[0-9a-f]*", v):
                    self.bad("pattern data is lower-case hex")
                n = len(v) // 2
                if n > 4096 or self.data_total + n > 8192:
                    self.bad("too much pattern data", "TOO_BIG")
                if len(v) % 2:
                    self.bad("pattern data has an odd number of hex digits")
                self.data_total += n
                hexed = v
                self.emit({"rec": "data", "pos": pos, "version": version, "hex": v})
        self.path = base
        if version is None or hexed is None:
            self.bad("pattern data needs its version and hex")

    def ref(self, obj):
        base = list(self.path)
        has, source, module, port = set(), None, None, None
        for k, v, known in self.members(obj, "ref"):
            self.path = base + [k]
            if not known:
                self.skip("a member this build does not know")
                continue
            has.add(k)
            if k == "source":
                if not isinstance(v, str) or isinstance(v, Num):
                    self.bad("a source's name was expected")
                source = self.nm.source_id.get(v) if len(_utf8(v)) <= 63 else None
                if source is None:
                    self.skip("not a source this build has")
                    self.cable_bad = True
            elif k == "module":
                module = self.int_value(v, 1, 8) - 1
            else:
                if isinstance(v, Num):
                    port = self.int_value(v, 1, 8)
                elif isinstance(v, str):
                    if len(_utf8(v)) >= 16:
                        self.skip("not a port")
                        self.cable_bad = True
                        port = ""
                    else:
                        port = v
                else:
                    self.bad("a port's name or number was expected")
        self.path = base
        if has == {"source"}:
            return source if source is not None else NONE
        if "module" in has and "source" not in has:
            k = self.rack[module]
            if "port" in has:
                if isinstance(port, int):
                    pidx = port - 1
                else:
                    pidx = self.port_find(k.outs if k else None, port)
            else:
                pidx = 0
            if pidx is None or not 0 <= pidx <= 7:
                self.skip("not an output of that module")
                self.cable_bad = True
                return NONE
            return 64 + 8 * module + pidx
        self.bad("a cable's end is a source, or a module and its port")

    @staticmethod
    def port_find(ports, s):
        if ports is None:
            return None
        if len(s) == 1 and "1" <= s <= "8":
            k = int(s) - 1
            return k if k < len(ports) else None
        for test in (lambda p: p == s, lambda p: ascii_lower(p) == ascii_lower(s)):
            for i, p in enumerate(ports):
                if test(p):
                    return i
        return None

    def target(self, obj, rec):
        base = list(self.path)
        has, unit, module, param, gate = set(), None, None, None, None
        for k, v, known in self.members(obj, "target"):
            self.path = base + [k]
            if not known:
                self.skip("a member this build does not know")
                continue
            has.add(k)
            if k == "unit":
                if not isinstance(v, str) or isinstance(v, Num):
                    self.bad("a unit's name was expected")
                unit = unit_code(self.kind, v) if len(_utf8(v)) <= 63 else None
                if unit is None:
                    self.bad("not a unit of this kind of file")
            elif k == "module":
                module = self.int_value(v, 1, 8) - 1
            elif k == "param":
                if not isinstance(v, str) or isinstance(v, Num):
                    self.bad("a parameter's name was expected")
                if not re.fullmatch(r"[ -~]{1,24}", v):
                    self.bad("a parameter's name has 1-24 printable ASCII characters")
                param = v
            else:
                if isinstance(v, Num):
                    gate = self.int_value(v, 1, 8)
                elif isinstance(v, str):
                    if len(_utf8(v)) >= 16:
                        self.skip("not a gate")
                        self.cable_bad = True
                        gate = ""
                    else:
                        gate = v
                else:
                    self.bad("a gate's name or number was expected")
        self.path = base
        rec["name"] = ""
        if has == {"unit", "param"}:
            rec["unit"] = unit
            if unit == 3:
                table = self.nm.host
            else:
                ix = code_index(unit)
                e = self.unit_e[ix] if ix is not None else None
                table = e.params if e else None
            i = find_param(table, param) if table else None
            if i is not None:
                rec["dst"] = table[i].uid
            elif len(param) >= 2 and param[0] == "#" and param[1] != "0" and len(param) <= 5:
                if not (param[1:].isdigit() and param[1:].isascii() and 1 <= int(param[1:]) <= 4095):
                    self.bad("not a #UID")
                rec["dst"] = int(param[1:])
            elif table is not None:
                self.skip("not a host parameter" if unit == 3 else "not a parameter of that unit")
                self.cable_bad = True
            else:
                rec["dst"] = 0
                rec["name"] = param
            return
        if has == {"module", "param"}:
            k = self.rack[module]
            rec["unit"] = 8 + module
            i = find_param(k.params, param) if k else None
            if i is not None:
                rec["dst"] = k.params[i].uid
            elif len(param) >= 2 and param[0] == "#" and param[1] != "0" and len(param) <= 5:
                # A #UID the kind lacks, or of a kind the build lacks: kept, as a unit's is.
                if not (param[1:].isdigit() and param[1:].isascii() and 1 <= int(param[1:]) <= 4095):
                    self.bad("not a #UID")
                rec["dst"] = int(param[1:])
            elif k:
                self.skip("not a parameter of that module")
                self.cable_bad = True
            else:
                rec["dst"] = 0
                rec["name"] = param
            return
        if has == {"module", "gate"}:
            k = self.rack[module]
            rec["unit"] = 8 + module
            rec["flags"] |= GATE_DST
            if isinstance(gate, int):
                g = gate - 1
            else:
                g = self.port_find(k.gates if k else None, gate)
            if g is None or g < 0:
                self.skip("not a gate of that module")
                self.cable_bad = True
            else:
                rec["dst"] = g
            return
        self.bad("a cable goes to a unit's parameter, or a module's parameter or gate")

    def cable(self, obj):
        base = list(self.path)
        rec = {"rec": "cable", "slot": None, "src": NONE, "via": NONE, "unit": 0, "flags": SLOT_ON,
               "dst": 0, "amount": 0, "offset": 0, "lock": 0, "name": ""}
        self.cable_bad = False
        has = set()
        for k, v, known in self.members(obj, "cable"):
            self.path = base + [k]
            if not known:
                self.skip("a member this build does not know")
                continue
            if k == "slot":
                s = self.int_value(v, 1, 32) - 1
                if (self.cable_slots >> s) & 1:
                    self.bad("two cables in one matrix slot")
                self.cable_slots |= 1 << s
                rec["slot"] = s
                has.add(k)
            elif k == "on":
                rec["flags"] = rec["flags"] | SLOT_ON if self.bool_value(v) else rec["flags"] & ~SLOT_ON
            elif k in ("from", "via"):
                if k == "via" and v is None:
                    rec["via"] = NONE
                    continue
                self.want(v, Obj)
                if k == "from":
                    has.add(k)
                rec["src" if k == "from" else "via"] = self.ref(v)
            elif k == "to":
                self.want(v, Obj)
                has.add(k)
                self.target(v, rec)
            elif k in ("amount", "offset"):
                if not isinstance(v, Num):
                    self.bad("a percent was expected")
                q = canon.q14(v)
                if abs(canon.bounded(v, 3, -12)) > 100:
                    self.rep.repaired += 1
                rec[k] = q
                if k == "amount":
                    has.add(k)
            elif k in ("polarity", "curve"):
                if not isinstance(v, str) or isinstance(v, Num):
                    self.bad("a name was expected")
                names = POLARITY if k == "polarity" else CURVES
                if v not in names:
                    self.skip(f"not a {k}")
                    continue
                if k == "polarity":
                    rec["flags"] = (rec["flags"] & ~0x06) | (names.index(v) << POL_SHIFT)
                else:
                    rec["flags"] = (rec["flags"] & ~0x70) | (names.index(v) << CURVE_SHIFT)
            elif k == "voice":
                rec["flags"] = rec["flags"] | VOICE if self.bool_value(v) else rec["flags"] & ~VOICE
            elif k == "lock":
                rec["lock"] = self.int_value(v, 0, 4095)
        self.path = base
        if has != {"slot", "from", "to", "amount"}:
            self.bad("a cable needs its slot, from, to and amount")
        if not self.cable_bad:
            self.emit(rec)

    def lines(self, v, which):
        self.want(v, list)
        n = 0
        for i, line in enumerate(v):
            self.path = [which, i]
            if not isinstance(line, str) or isinstance(line, Num):
                self.bad("a movy1 line (a string) was expected")
            if which == "clip" and n >= 12:
                self.bad("a clip has at most 12 lines")
            if any(ord(c) < 0x20 or ord(c) == 0x7F for c in line):
                self.bad("a control character in a movy1 line")
            self.emit({"rec": "line", "which": which, "text": line})
            if which == "set" and n == 0 and line != "movy1":
                self.bad("a set's first line is movy1")
            if which == "clip" and not re.match(r"(au 0 [0-7] |cl 0 0 |cp 0 0 |lk 0 0 |tg 0 0 )",
                                                line[:7].ljust(7, "\0")):
                self.bad("a clip line is au, cl, cp, lk or tg at track 0 and slot 0")
            n += 1
        self.path = [which]
        if which == "set" and n == 0:
            self.bad("a set opens with movy1")
        if which == "clip" and n < 2:
            self.bad("a clip has its cl and cp lines")

    def settings(self, v):
        self.want(v, Obj)
        for k, x, known in self.members(v, "settings"):
            self.path = ["settings", k]
            if not known:
                self.skip("a member this build does not know")
                continue
            if k == "midi_in_channel":
                self.emit({"rec": "setting", "key": k, "int": self.int_value(x, 0, 16)})
            else:
                self.emit({"rec": "setting", "key": k, "bool": self.bool_value(x)})

    def view(self, v):
        self.want(v, Obj)
        rec = {"rec": "view", "mode": None}
        keys = {}
        ranges = {"sound": (1, 4), "page": (1, 16), "track": (1, 16), "bar": (1, 64), "pos": (1, 8),
                  "slot": (1, 32), "entry": (1, 64)}
        for k, x, known in self.members(v, "view"):
            self.path = ["view", k]
            if not known:
                self.skip("a member this build does not know")
                continue
            if k in ("mode", "panel", "unit"):
                if not isinstance(x, str) or isinstance(x, Num):
                    self.bad("a name was expected")
                if k == "mode":
                    if x not in MODES:
                        self.bad("not a view mode")
                    rec["mode"] = MODES.index(x)
                elif k == "panel":
                    if x in PANELS:
                        keys["panel"] = PANELS.index(x)
                    else:
                        self.skip("not a panel")
                else:
                    c = unit_code("project", x) if len(_utf8(x)) <= 63 else None
                    if c is None:
                        self.skip("not a unit")
                    else:
                        keys["unit"] = c
            else:
                keys[k] = self.int_value(x, *ranges[k])
        self.path = ["view"]
        if rec["mode"] is None:
            self.bad("a view needs its mode")
        for k in VKEYS:
            if k in keys:
                rec[k] = keys[k]
        self.emit(rec)


def read_json(data, names):
    """Records of a JSON state file; raises Refused. The report rides along
    on the exception's absence: (records, report)."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    r = JsonReader(names)
    tree = _parse(data)
    return r.read(tree), r.rep


# ---- Writing canonical JSON ------------------------------------------------------------------------
class _Doc:
    def __init__(self):
        self.head = None
        self.info = {}
        self.session = None
        self.units = {}      # (role, sound, slot) -> engine id ("" for null)
        self.on = {}
        self.params = {}     # (role, sound, slot) -> {(uid, focus): ("index"|"f32", value)}
        self.level = {}
        self.dx7 = {}
        self.mod = False
        self.seed = None
        self.modules = {}
        self.data = {}
        self.cables = {}
        self.lines = []
        self.view = None
        self.settings = {}


def _collect(records):
    d = _Doc()
    for r in records:
        t = r["rec"]
        if t == "head":
            d.head = r
        elif t == "info":
            d.info[r["key"]] = r["text"]
        elif t == "session":
            d.session = r
        elif t == "unit":
            d.units[(ROLES.index(r["role"]), r["sound"], r["slot"])] = r["engine"]
        elif t == "on":
            d.on[(ROLES.index(r["role"]), r["sound"], r["slot"])] = r["on"]
        elif t == "param":
            key = (ROLES.index(r["role"]), r["sound"], r["slot"])
            val = ("index", r["index"]) if "index" in r else ("f32", int(r["f32"], 16))
            d.params.setdefault(key, {})[(r["uid"], r["focus"])] = val
        elif t == "level":
            d.level[r["sound"]] = int(r["f32"], 16)
        elif t == "dx7":
            d.dx7[r["slot"]] = bytes.fromhex(r["vced"])
        elif t == "mod":
            d.mod = True
        elif t == "seed":
            d.mod = True
            d.seed = r["seed"]
        elif t == "module":
            d.modules[r["pos"]] = r["kind"]
        elif t == "data":
            d.data[r["pos"]] = (r["version"], r["hex"])
        elif t == "cable":
            d.cables[r["slot"]] = r
        elif t == "line":
            d.lines.append(r["text"])
        elif t == "view":
            d.view = r
        elif t == "setting":
            d.settings[r["key"]] = r.get("bool", r.get("int"))
    return d


class JsonWriter:
    def __init__(self, names):
        self.nm = names
        self.rep = Report()

    def value(self, p, val):
        """As its parameter takes it (state_json_write.c's param_val): a
        list entry in range, a float clamped; as it came without a table."""
        kind, v = val
        if p and p.enum:
            if kind == "index":
                k = min(v, 255)
            else:
                f = bits_f32(v)
                k = (int(canon.f32(f + 0.5)) if f < 255 else 255) if f >= 0 else 0
                self.rep.repaired += 1
            if k > p.count() - 1:
                k = p.count() - 1
                self.rep.repaired += 1
            return p.entries[k] if p.entries else k
        if p:
            f = float(v) if kind == "index" else bits_f32(v)
            c = p.min if f < p.min else (p.max if f > p.max else f)
            c = canon.f32(c)
            if c == 0:
                c = 0.0
            if kind == "index" or f32_bits(c) != v:
                self.rep.repaired += 1
            return c
        if kind == "index":
            return v
        return bits_f32(v)

    def default(self, p):
        self.rep.defaulted += 1
        if p.enum:
            return self.value(p, ("index", int(p.default)))
        return p.default

    def params_obj(self, key, table, focus, pad_side, module=False):
        recs = self.d.params.get(key, {})
        uids = {p.uid for p in table if (p.focus == 2) == pad_side and not module} if table else set()
        if table and module:
            uids = {p.uid for p in table}
        uids |= {u for (u, f) in recs if f == focus}
        by_uid = {p.uid: p for p in table} if table else {}
        out = {}
        for uid in sorted(uids):
            p = by_uid.get(uid)
            r = recs.get((uid, focus))
            if p and not module and (p.focus == 2) != pad_side:
                self.rep.skip("a value on the wrong side of the pad split")
                continue
            name = p.name if p else "#%d" % uid
            out[name] = self.value(p, r) if r else self.default(p)
        return out

    def unit(self, role, sound, slot):
        eid = self.d.units.get((role, sound, slot))
        if not eid:
            return None
        e = self.nm.engine(role, eid)
        table = e.params if e else None
        key = (role, sound, slot)
        u = {"engine": eid}
        if role == MFX:
            if key not in self.d.on:
                self.rep.defaulted += 1
            u["on"] = bool(self.d.on.get(key, False))
        u["params"] = self.params_obj(key, table, None, False)
        if role == SOUND:
            npads = min(e.pads, 32) if e else 0
            if not e:
                for (uid, f) in self.d.params.get(key, {}):
                    if f is not None:
                        npads = max(npads, f + 1)
            if npads:
                u["pads"] = [self.params_obj(key, table, j, True) for j in range(npads)]
            if sound in self.d.level:
                u["level"] = bits_f32(self.d.level[sound])
            else:
                self.rep.defaulted += 1
                u["level"] = 100
            u["inserts"] = [self.unit(INSERT, sound, j) for j in range(2)]
            top = max([j for j in range(4) if (MFX, sound, j) in self.d.units], default=-1)
            u["midi_fx"] = [self.unit(MFX, sound, j) for j in range(top + 1)]
        return u

    def ref(self, src):
        if src < 64:
            return {"source": self.nm.sources[src]}
        pos, port = (src - 64) // 8, (src - 64) % 8
        k = self.nm.kinds.get(self.d.modules.get(pos, ""))
        return {"module": pos + 1, "port": k.outs[port] if k and port < len(k.outs) else port + 1}

    def target_table(self, u):
        if 8 <= u < 16:
            k = self.nm.kinds.get(self.d.modules.get(u - 8, ""))
            return k.params if k else None
        if u == 3:
            return self.nm.host
        ix = code_index(u)
        if ix is None:
            return None
        role, sound, slot = ((SOUND, ix, 0) if ix < 4 else (INSERT, (ix - 4) // 2, (ix - 4) % 2)
                             if ix < 12 else (MASTER, 0, ix - 12))
        e = self.nm.engine(role, self.d.units.get((role, sound, slot), ""))
        return e.params if e else None

    def cable_ok(self, c):
        def ref_ok(s):
            return s in self.nm.sources if s < 64 else s < 128
        if not ref_ok(c["src"]) or (c["via"] != NONE and not ref_ok(c["via"])):
            return False
        if 8 <= c["unit"] < 16:
            if c["flags"] & GATE_DST:
                return True
        elif c["flags"] & GATE_DST or code_name(self.kind, c["unit"]) is None:
            return False
        table = self.target_table(c["unit"])
        if not c["dst"] and c["name"] and table is not None:
            return find_param(table, c["name"]) is not None
        return True

    def target(self, c):
        u = c["unit"]
        if 8 <= u < 16:
            k = self.nm.kinds.get(self.d.modules.get(u - 8, ""))
            if c["flags"] & GATE_DST:
                return {"module": u - 7, "gate": k.gates[c["dst"]] if k and c["dst"] < len(k.gates) else
                        c["dst"] + 1}
            table = k.params if k else None
            out = {"module": u - 7}
        else:
            out = {"unit": code_name(self.kind, u)}
            if u == 3:
                table = self.nm.host
            else:
                ix = code_index(u)
                role, sound, slot = ((SOUND, ix, 0) if ix < 4 else (INSERT, (ix - 4) // 2, (ix - 4) % 2)
                                     if ix < 12 else (MASTER, 0, ix - 12))
                e = self.nm.engine(role, self.d.units.get((role, sound, slot), ""))
                table = e.params if e else None
        if not c["dst"] and c["name"]:
            out["param"] = c["name"]
        else:
            p = next((p for p in table or [] if p.uid == c["dst"]), None)
            out["param"] = p.name if p else "#%d" % c["dst"]
        return out

    def mod(self):
        m = {}
        if self.d.seed is not None:
            m["seed"] = self.d.seed
        rack = []
        for pos in sorted(self.d.modules):
            kid = self.d.modules[pos]
            k = self.nm.kinds.get(kid)
            x = {"pos": pos + 1, "kind": kid,
                 "params": self.params_obj((MODULE, 0, pos), k.params if k else None, None, False,
                                           module=True)}
            if pos in self.d.data:
                x["data"] = {"version": self.d.data[pos][0], "hex": self.d.data[pos][1]}
            rack.append(x)
        m["rack"] = rack
        cables = []
        for slot in sorted(self.d.cables):
            c = self.d.cables[slot]
            if not self.cable_ok(c):
                self.rep.skip("a cable this kind of file or build cannot name")
                continue
            f = c["flags"]
            cables.append({"slot": slot + 1, "on": bool(f & SLOT_ON), "from": self.ref(c["src"]),
                           "via": None if c["via"] == NONE else self.ref(c["via"]), "to": self.target(c),
                           "amount": canon.percent(c["amount"]), "offset": canon.percent(c["offset"]),
                           "polarity": POLARITY[(f >> 1) & 3], "curve": CURVES[(f >> 4) & 7],
                           "voice": bool(f & VOICE), "lock": c["lock"]})
        m["cables"] = cables
        return m

    def doc(self, records):
        d = self.d = _collect(records)
        if not d.head:
            raise Refused("BAD", "no head record")
        kind = self.kind = d.head["kind"]
        if kind in ("set", "dx7bank"):
            raise Refused("BAD", "this kind has no JSON form")
        out = {"lunar": "%d.%d" % (MAJOR, d.head["minor"]), "kind": kind}
        made = {k: d.info[k] for k in ("by", "version", "commit") if k in d.info}
        if made:
            out["made"] = made
        for k in ("name", "title", "about", "author", "licence"):
            if k in d.info:
                out[k] = d.info[k]
        if kind == "project":
            if not d.units.get((SOUND, 0, 0)):
                raise Refused("BAD", "Sound 1 is never empty")
            if d.session:
                s = d.session
                out["session"] = {"current": s["current"] + 1, "octave": s["octave"],
                                  "transpose": s["transpose"]}
                if "root" in s:
                    out["session"]["key"] = {"root": ROOTS[s["root"] % 12], "scale": s["scale"]}
            out["sounds"] = [self.unit(SOUND, k, 0) for k in range(4)]
            out["master"] = [self.unit(MASTER, 0, j) for j in range(2)]
        elif kind == "sound":
            if (SOUND, 0, 0) not in d.units:
                raise Refused("BAD", "a sound file needs its sound")
            out["sound"] = self.unit(SOUND, 0, 0) or {"engine": ""}
        elif kind == "fx":
            top = max([j for j in range(4) if (MASTER, 0, j) in d.units], default=-1)
            out["chain"] = [self.unit(MASTER, 0, j) for j in range(top + 1)]
        if kind in ("project", "sound") and d.dx7:
            out["dx7"] = []
            for slot in sorted(d.dx7):
                v = d.dx7[slot]
                out["dx7"].append({"slot": slot + 1, "name": v[145:155].decode("ascii").rstrip(" "),
                                   "ops": [list(v[o * 21:o * 21 + 21]) for o in range(6)],
                                   "globals": list(v[126:145])})
        if (d.mod or kind == "mods") and kind in ("project", "sound", "fx", "mods"):
            out["mod"] = self.mod()
        if (kind == "project" and d.lines) or kind == "clip":
            out["clip" if kind == "clip" else "set"] = list(d.lines)
        if kind == "settings":
            out["settings"] = {k: d.settings[k] for k in SETTINGS[1:] if k in d.settings}
        if d.view and kind != "settings":
            v = {"mode": MODES[d.view["mode"] % 9]}
            for k in VKEYS:
                if k in d.view:
                    x = d.view[k]
                    v[k] = (code_name("project", x) or "host") if k == "unit" else \
                        (PANELS[x & 3] if k == "panel" else x)
            out["view"] = v
        return out


def write_json(records, names, compact=False):
    w = JsonWriter(names)
    doc = w.doc(records)
    return (canon.compact(doc) if compact else canon.dumps(doc)), w.rep


# ---- The binary container -----------------------------------------------------------------------
MAGIC = b"\x89Lunar\r\n"
TAGS = {b"info": 1, b"PROJ": 2, b"UNIT": 3, b"DX7V": 4, b"MODR": 5, b"SEQS": 6, b"CLIP": 7, b"view": 8,
        b"SETG": 9}
TAG_NAMES = {v: k for k, v in TAGS.items()}
CAP = {1: 2048, 2: 2048, 3: 6144, 4: 5200, 5: 12288, 6: 49152, 7: 16384, 8: 2048, 9: 2048}
CHUNK_KINDS = {1: set(KINDS[1:8]), 2: {"project"}, 3: {"project", "sound", "fx"}, 4: {"project", "sound"},
               5: {"project", "sound", "fx", "mods"}, 6: {"project", "set"}, 7: {"clip"},
               8: {"project", "sound", "fx", "mods", "clip"}, 9: {"settings"}}
KV_U32, KV_I32, KV_F32, KV_STR, KV_BYTES, KV_BOOL = 1, 2, 3, 4, 5, 6
CHUNKS_MAX, BIN_MAX = 64, 98304


def crc32(b):
    return zlib.crc32(b) & 0xFFFFFFFF


# ---- deflate: the same greedy fixed-Huffman stream as engines/state/fm1_deflate.c
_LEN_BASE = [3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 15, 17, 19, 23, 27, 31, 35, 43, 51, 59, 67, 83, 99, 115,
             131, 163, 195, 227, 258]
_LEN_EXTRA = [0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5, 0]
_DIST_BASE = [1, 2, 3, 4, 5, 7, 9, 13, 17, 25, 33, 49, 65, 97, 129, 193, 257, 385, 513, 769, 1025, 1537,
              2049, 3073, 4097, 6145, 8193, 12289, 16385, 24577]
_DIST_EXTRA = [0, 0, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8, 9, 9, 10, 10, 11, 11, 12, 12,
               13, 13]


def deflate(data):
    out = bytearray()
    acc = [0, 0]   # bit buffer, bit count

    def bits(v, n):
        acc[0] |= v << acc[1]
        acc[1] += n
        while acc[1] >= 8:
            out.append(acc[0] & 0xFF)
            acc[0] >>= 8
            acc[1] -= 8

    def code(c, n):
        bits(int(format(c, "0%db" % n)[::-1], 2), n)

    def lit(c):
        if c < 144:
            code(0x30 + c, 8)
        elif c < 256:
            code(0x190 + c - 144, 9)
        elif c < 280:
            code(c - 256, 7)
        else:
            code(0xC0 + c - 280, 8)

    def h3(i):
        return ((data[i] << 8) ^ (data[i + 1] << 4) ^ data[i + 2]) & 4095

    head, prev = [-1] * 4096, [-1] * 4096
    n = len(data)
    bits(1, 1)
    bits(1, 2)
    i = 0
    while i < n:
        best = dist = 0
        if i + 3 <= n:
            j, steps = head[h3(i)], 0
            while j >= 0 and i - j <= 4096 and steps < 128:
                lim = min(n - i, 258)
                ln = 0
                while ln < lim and data[j + ln] == data[i + ln]:
                    ln += 1
                if ln > best:
                    best, dist = ln, i - j
                    if ln == 258:
                        break
                j = prev[j & 4095]
                steps += 1
        if best >= 3:
            s = max(k for k in range(29) if _LEN_BASE[k] <= best)
            lit(257 + s)
            if _LEN_EXTRA[s]:
                bits(best - _LEN_BASE[s], _LEN_EXTRA[s])
            s = max(k for k in range(30) if _DIST_BASE[k] <= dist)
            code(s, 5)
            if _DIST_EXTRA[s]:
                bits(dist - _DIST_BASE[s], _DIST_EXTRA[s])
            for k in range(best):
                if i + k + 3 <= n:
                    h = h3(i + k)
                    prev[(i + k) & 4095] = head[h]
                    head[h] = i + k
            i += best
        else:
            lit(data[i])
            if i + 3 <= n:
                h = h3(i)
                prev[i & 4095] = head[h]
                head[h] = i
            i += 1
    lit(256)
    if acc[1]:
        bits(0, 8 - acc[1])
    return bytes(out)


def inflate(data, out_len):
    """Raw deflate to exactly out_len bytes, reaching back at most 4 KiB.
    zlib with a 4 KiB window checks a distance against the window only for
    output it has already handed back, so it is handed back a byte at a
    time: then every reach is checked."""
    try:
        d = zlib.decompressobj(-12)
        out = bytearray()
        buf = data
        while len(out) <= out_len:
            piece = d.decompress(buf, 1)
            buf = d.unconsumed_tail
            if not piece:
                break
            out += piece
        if len(out) != out_len or not d.eof:
            raise ValueError
    except (zlib.error, ValueError):
        raise Refused("BAD", "a deflated chunk that cannot be read") from None
    return bytes(out)


# ---- movy1 lines as items (engines/state/state_movy1.c)
def _num(t, mx):
    if not t or len(t) > 10 or (len(t) > 1 and t[0] == "0") or not t.isdigit() or not t.isascii():
        return None
    v = int(t)
    return v if v <= mx else None


def _snum(t, lo, hi):
    if t.startswith("-"):
        v = _num(t[1:], -lo)
        return None if v is None or v == 0 else -v
    return _num(t, hi)


def _typed(line):
    if line == "movy1":
        return b"\x02"
    t = line.split(" ")
    k = t[0]

    def u8(x):
        return _num(x, 255)
    try:
        if k == "bpm" and len(t) == 2 and _num(t[1], 0xFFFFFFFF) is not None:
            return b"\x03" + struct.pack("<I", _num(t[1], 0xFFFFFFFF))
        if k == "swing" and len(t) == 2 and _num(t[1], 0xFFFFFFFF) is not None:
            return b"\x04" + struct.pack("<I", _num(t[1], 0xFFFFFFFF))
        if k == "link" and len(t) == 2 and u8(t[1]) is not None:
            return bytes([5, u8(t[1])])
        if k == "sg" and len(t) >= 2:
            v = [u8(x) for x in t[1:]]
            return None if None in v else b"\x06" + struct.pack("<H", len(v)) + bytes(v)
        if k == "tk" and len(t) == 4 and None not in [u8(x) for x in t[1:]]:
            return bytes([7] + [u8(x) for x in t[1:]])
        if k in ("pm", "ps") and len(t) == 3 and None not in [u8(x) for x in t[1:]]:
            return bytes([8 if k == "pm" else 9] + [u8(x) for x in t[1:]])
        if k == "au" and len(t) >= 5 and None not in [u8(x) for x in t[1:4]]:
            label = line.split(" ", 4)[4].encode("utf-8")
            if len(t) > 5 or len(label) > 255:
                return None
            return bytes([0x0A] + [u8(x) for x in t[1:4]] + [len(label)]) + label
        if k == "rt" and len(t) == 4 and None not in [u8(x) for x in t[1:]]:
            return bytes([0x0B] + [u8(x) for x in t[1:]])
        if k in ("dq", "se") and len(t) == 2 and u8(t[1]) is not None:
            return bytes([0x10 if k == "dq" else 0x11, u8(t[1])])
        if k == "key" and len(t) == 3 and None not in (u8(t[1]), u8(t[2])):
            return bytes([0x13, u8(t[1]), u8(t[2])])
        if k == "sn" and len(t) == 3 and u8(t[1]) is not None:
            name = t[2].encode("utf-8")
            if not 1 <= len(name) <= 255:
                return None
            return bytes([0x12, u8(t[1]), len(name)]) + name
        if k == "cp" and len(t) == 7:
            a = [u8(x) for x in t[1:5]] + [_snum(t[5], -128, 127), u8(t[6])]
            if None in a:
                return None
            return bytes([0x0D] + a[:4] + [a[4] & 0xFF, a[5]])
        if k == "cl" and len(t) == 6:
            a = [u8(t[1]), u8(t[2]), _num(t[3], 65535), _num(t[4], 65535)]
            if None in a:
                return None
            out = bytearray([0x0C, a[0], a[1]]) + struct.pack("<HH", a[2], a[3])
            notes = t[5].split(";") if t[5] else []
            out += struct.pack("<H", len(notes))
            for note in notes:
                f = note.split(":")
                if len(f) != 5:
                    return None
                v = [_num(f[0], 65535), _num(f[1], 65535), _num(f[2], 255), _num(f[3], 255), _num(f[4], 65535)]
                if None in v:
                    return None
                out += struct.pack("<HHBBH", *v)
            return bytes(out) if len(notes) <= 65535 else None
        if k in ("lk", "tg") and len(t) == 4 and u8(t[1]) is not None and u8(t[2]) is not None and t[3]:
            items = t[3].split(";")
            out = bytearray([0x0E if k == "lk" else 0x0F, u8(t[1]), u8(t[2])]) + struct.pack("<H", len(items))
            for it in items:
                f = it.split(":")
                if k == "lk":
                    v = [u8(x) for x in f] if len(f) == 3 else [None]
                    if None in v:
                        return None
                    out += bytes(v)
                else:
                    if len(f) != 6:
                        return None
                    v = [u8(f[0]), _snum(f[1], -128, 127)] + [u8(x) for x in f[2:]]
                    if None in v:
                        return None
                    out += bytes([v[0], v[1] & 0xFF] + v[2:])
            return bytes(out)
    except (ValueError, IndexError):
        return None
    return None


def _item_text(b, i):
    """The text of the item at b[i:]; returns (text, next i)."""
    tag = b[i]
    i += 1

    def u8():
        nonlocal i
        i += 1
        return b[i - 1]

    def u16():
        nonlocal i
        i += 2
        return struct.unpack_from("<H", b, i - 2)[0]

    def u32():
        nonlocal i
        i += 4
        return struct.unpack_from("<I", b, i - 4)[0]
    if tag == 1:
        n = u16()
        s = b[i:i + n]
        if len(s) != n:
            raise IndexError
        return s.decode("utf-8"), i + n
    if tag == 2:
        return "movy1", i
    if tag in (3, 4):
        return ("bpm " if tag == 3 else "swing ") + str(u32()), i
    if tag == 5:
        return "link %d" % u8(), i
    if tag == 6:
        n = u16()
        return "sg" + "".join(" %d" % u8() for _ in range(n)), i
    if tag == 7:
        return "tk %d %d %d" % (u8(), u8(), u8()), i
    if tag in (8, 9):
        return ("pm" if tag == 8 else "ps") + " %d %d" % (u8(), u8()), i
    if tag == 0x0A:
        a, ln, base, n = u8(), u8(), u8(), u8()
        s = b[i:i + n]
        if len(s) != n:
            raise IndexError
        return "au %d %d %d " % (a, ln, base) + s.decode("utf-8"), i + n
    if tag == 0x0B:
        return "rt %d %d %d" % (u8(), u8(), u8()), i
    if tag in (0x10, 0x11):
        return ("dq " if tag == 0x10 else "se ") + str(u8()), i
    if tag == 0x13:
        root = u8()
        return "key %d %d" % (root, u8()), i
    if tag == 0x12:
        scene, n = u8(), u8()
        s = b[i:i + n]
        if len(s) != n:
            raise IndexError
        return "sn %d " % scene + s.decode("utf-8"), i + n
    if tag == 0x0C:
        t, s, ln, ls, n = u8(), u8(), u16(), u16(), u16()
        notes = []
        for _ in range(n):
            tick, gate, p, v, st = struct.unpack_from("<HHBBH", b, i)
            i += 8
            notes.append("%d:%d:%d:%d:%d" % (tick, gate, p, v, st))
        return "cl %d %d %d %d " % (t, s, ln, ls) + ";".join(notes), i
    if tag == 0x0D:
        t, s, num, den, tr, q = u8(), u8(), u8(), u8(), u8(), u8()
        return "cp %d %d %d %d %d %d" % (t, s, num, den, tr - 256 if tr > 127 else tr, q), i
    if tag in (0x0E, 0x0F):
        t, s, n = u8(), u8(), u16()
        items = []
        for _ in range(n):
            if tag == 0x0E:
                items.append("%d:%d:%d" % (u8(), u8(), u8()))
            else:
                st, ln, p, a, bb, inv = u8(), u8(), u8(), u8(), u8(), u8()
                items.append("%d:%d:%d:%d:%d:%d" % (st, ln - 256 if ln > 127 else ln, p, a, bb, inv))
        return ("lk" if tag == 0x0E else "tg") + " %d %d " % (t, s) + ";".join(items), i
    raise ValueError("an unknown item")


def encode_line(line):
    item = _typed(line)
    if item is not None:
        try:
            text, end = _item_text(item, 0)
            if end == len(item) and text == line:
                return item
        except (IndexError, ValueError, struct.error):
            pass
    raw = line.encode("utf-8")
    return b"\x01" + struct.pack("<H", len(raw)) + raw


# ---- the writer
def _kv(entries):
    out = struct.pack("<H", len(entries))
    for key, typ, val in entries:
        out += struct.pack("<HBBH", key, typ, 0, len(val)) + val
    return out


def write_bin(records, deflate_chunks=True, writer=3, version=(0, 1, 0)):
    """Records in canonical order to a binary file (engines/state/state_bin.c's
    layout and choices, byte for byte)."""
    chunks = []
    head = None
    cur = None   # [tag, bytearray, extra]

    def close():
        nonlocal cur
        if cur is None:
            return
        tag, body = cur[0], cur[1]
        if tag == 3:
            body += struct.pack("<H", 1 if cur[2].get("level") is not None else 0)
            if cur[2].get("level") is not None:
                body += struct.pack("<HBBHI", 1, KV_F32, 0, 4, cur[2]["level"])
        elif tag in (1, 2, 8, 9):
            body = bytearray(_kv(cur[2]["kv"]))
        elif tag == 4:
            body[0] = cur[2]["count"]
        if len(body) > CAP[tag]:
            raise Refused("TOO_BIG", "a chunk past its cap")
        chunks.append((tag, bytes(body)))
        cur = None

    def open_(tag, keep=False):
        nonlocal cur
        if cur is not None and cur[0] == tag and keep:
            return
        close()
        if head["kind"] not in CHUNK_KINDS[tag]:
            raise Refused("BAD", "a record this kind of file does not hold")
        cur = [tag, bytearray(), {"kv": [], "count": 0}]
        if tag == 4:
            cur[1].append(0)
    for r in records:
        t = r["rec"]
        if head is None and t != "head":
            raise Refused("BAD", "the head record comes first")
        if t == "head":
            head = r
        elif t == "info":
            open_(1, keep=True)
            cur[2]["kv"].append((INFO.index(r["key"]), KV_STR, r["text"].encode("utf-8")))
        elif t == "session":
            open_(2)
            kv = [(1, KV_I32, struct.pack("<i", r["current"])), (2, KV_I32, struct.pack("<i", r["octave"])),
                  (3, KV_I32, struct.pack("<i", r["transpose"]))]
            if "root" in r:
                kv += [(4, KV_U32, struct.pack("<I", r["root"])), (5, KV_STR, r["scale"].encode())]
            cur[2]["kv"] = kv
            close()
        elif t == "unit":
            close()
            open_(3)
            eid = r["engine"].encode()
            cur[1] += bytes([ROLES.index(r["role"]), r["sound"], r["slot"], 0, len(eid)]) + eid
            cur[2].update(unit=(r["role"], r["sound"], r["slot"]), count_at=len(cur[1]), count=0, level=None)
            cur[1] += b"\0\0"
        elif t == "on":
            if cur is None or cur[0] != 3 or cur[2]["unit"] != (r["role"], r["sound"], r["slot"]):
                raise Refused("BAD", "records out of canonical order")
            cur[1][3] = 2 | (1 if r["on"] else 0)
        elif t == "param":
            val = (1, r["index"]) if "index" in r else (0, int(r["f32"], 16))
            if r["role"] == "module":
                if cur is None or cur[0] != 5:
                    raise Refused("BAD", "records out of canonical order")
                cur[1] += struct.pack("<BBHBI", 2, r["slot"], r["uid"], val[0], val[1])
            else:
                if cur is None or cur[0] != 3 or cur[2]["unit"] != (r["role"], r["sound"], r["slot"]):
                    raise Refused("BAD", "records out of canonical order")
                cur[1] += struct.pack("<HBBI", r["uid"], NONE if r["focus"] is None else r["focus"],
                                      val[0], val[1])
                cur[2]["count"] += 1
                if cur[2]["count"] > 512:
                    raise Refused("TOO_BIG", "more than 512 records in a unit")
                struct.pack_into("<H", cur[1], cur[2]["count_at"], cur[2]["count"])
        elif t == "level":
            if cur is None or cur[0] != 3 or cur[2]["unit"][0] != "sound" or cur[2]["unit"][1] != r["sound"]:
                raise Refused("BAD", "records out of canonical order")
            cur[2]["level"] = int(r["f32"], 16)
        elif t == "dx7":
            open_(4, keep=True)
            cur[2]["count"] += 1
            cur[1] += bytes([r["slot"], 1]) + bytes.fromhex(r["vced"]) + b"\0\0\0"
        elif t == "mod":
            close()
            open_(5)
            cur[1] += b"\0" * 8
        elif t == "seed":
            if cur is None or cur[0] != 5:
                raise Refused("BAD", "records out of canonical order")
            cur[1][0] = 1
            struct.pack_into("<I", cur[1], 4, r["seed"])
        elif t == "module":
            if cur is None or cur[0] != 5:
                raise Refused("BAD", "records out of canonical order")
            k = r["kind"].encode()
            cur[1] += bytes([1, r["pos"], len(k)]) + k
        elif t == "data":
            if cur is None or cur[0] != 5:
                raise Refused("BAD", "records out of canonical order")
            b = bytes.fromhex(r["hex"])
            cur[1] += bytes([3, r["pos"], r["version"]]) + struct.pack("<H", len(b)) + b
        elif t == "cable":
            if cur is None or cur[0] != 5:
                raise Refused("BAD", "records out of canonical order")
            name = r["name"].encode()[:24]
            cur[1] += struct.pack("<BBBBBBHhhHB", 4, r["slot"], r["src"], r["via"], r["unit"], r["flags"],
                                  r["dst"], r["amount"], r["offset"], r["lock"], len(name)) + name
        elif t == "line":
            open_(7 if r["which"] == "clip" else 6, keep=True)
            cur[1] += encode_line(r["text"])
        elif t == "view":
            open_(8)
            kv = [(1, KV_U32, struct.pack("<I", r["mode"]))]
            for i, k in enumerate(VKEYS):
                if k in r:
                    kv.append((2 + i, KV_U32, struct.pack("<I", r[k])))
            cur[2]["kv"] = kv
            close()
        elif t == "setting":
            open_(9, keep=True)
            key = SETTINGS.index(r["key"])
            if "bool" in r:
                cur[2]["kv"].append((key, KV_BOOL, struct.pack("<I", 1 if r["bool"] else 0)))
            else:
                cur[2]["kv"].append((key, KV_I32, struct.pack("<i", r["int"])))
        elif t == "end":
            close()
    if not chunks:
        chunks.append((1, _kv([])))      # a file has a chunk: an empty info
    if len(chunks) > CHUNKS_MAX:
        raise Refused("TOO_BIG", "too many chunks")
    stored = []
    for tag, body in chunks:
        flags = 0
        if deflate_chunks and len(body) >= 16:
            z = deflate(body)
            if (len(z) + 4) * 4 <= len(body) * 3:
                body, flags = struct.pack("<I", len(body)) + z, 1
        stored.append((tag, flags, body))
    dir_end = 32 + 20 * len(stored) + 4
    base = (dir_end + 3) & ~3
    off, entries, data = base, b"", b""
    for tag, flags, body in stored:
        pad = (-len(data)) % 4
        data += b"\0" * pad
        off = base + len(data)
        entries += TAG_NAMES[tag] + struct.pack("<HHIII", 1, flags, off, len(body), crc32(body))
        data += body
    total = base + len(data)
    if total > BIN_MAX:
        raise Refused("TOO_BIG", "past 96 KiB")
    hdr = MAGIC + bytes([MAJOR, head["minor"], KINDS.index(head["kind"]), 0]) + \
        struct.pack("<HHHHI", 32, len(stored), 20, 0, total) + bytes([writer, *version])
    hdr += struct.pack("<I", crc32(hdr))
    return hdr + entries + struct.pack("<I", crc32(entries)) + b"\0" * (base - dir_end) + data


# ---- the reader
class _Chunk:
    def __init__(self, b):
        self.b, self.i = b, 0

    def take(self, n):
        if self.i + n > len(self.b):
            raise Refused("BAD", "a chunk ends early")
        self.i += n
        return self.b[self.i - n:self.i]

    def u8(self):
        return self.take(1)[0]

    def u16(self):
        return struct.unpack("<H", self.take(2))[0]

    def u32(self):
        return struct.unpack("<I", self.take(4))[0]

    def left(self):
        return len(self.b) - self.i

    def kv(self):
        n = self.u16()
        if n > 64:
            raise Refused("TOO_BIG", "more than 64 entries")
        for _ in range(n):
            key, typ, flags, ln = struct.unpack("<HBBH", self.take(6))
            if flags:
                raise Refused("BAD", "unknown entry flags")
            yield key, typ, self.take(ln)


def _clean_text(b, key):
    try:
        s = b.decode("utf-8")
    except UnicodeDecodeError:
        raise Refused("BAD", "text that is not clean UTF-8") from None
    for ch in s:
        cp = ord(ch)
        if cp < 0x20 or cp == 0x7F or 0x202A <= cp <= 0x202E or 0x2066 <= cp <= 0x2069:
            raise Refused("BAD", "text that is not clean UTF-8")
        if key in (1, 2, 3, 4) and cp >= 0x7F:
            raise Refused("BAD", "this text is printable ASCII")
        if key == 8 and not (ch.isascii() and (ch.isalnum() or ch in ".+-")):
            raise Refused("BAD", "not a licence id")
    if len(s) > INFO_CAP.get(key, 64):
        raise Refused("BAD", "text past its length")
    return s


def _id_ok(s):
    return s == "" or re.fullmatch(r"[a-z][a-z0-9-]{0,14}", s)


def _value(vtype, bits, rec):
    if vtype == 1:
        if bits >= 256:
            raise Refused("BAD", "a value that cannot be read")
        rec["index"] = bits
    elif vtype == 0:
        if (bits & 0x7F800000) == 0x7F800000 or bits == 0x80000000:
            raise Refused("BAD", "a value that cannot be read")
        rec["f32"] = "%08x" % bits
    else:
        raise Refused("BAD", "a value that cannot be read")


def _unit_place(kind, role, sound, slot):
    if kind == "project":
        if role == SOUND and sound < 4 and slot == 0:
            return sound
        if role == INSERT and sound < 4 and slot < 2:
            return 4 + 2 * sound + slot
        if role == MFX and sound < 4 and slot < 4:
            return 12 + 4 * sound + slot
        if role == MASTER and sound == 0 and slot < 2:
            return 28 + slot
    elif kind == "sound":
        if role == SOUND and sound == 0 and slot == 0:
            return 0
        if role == INSERT and sound == 0 and slot < 2:
            return 4 + slot
        if role == MFX and sound == 0 and slot < 4:
            return 12 + slot
    elif kind == "fx" and role == MASTER and sound == 0 and slot < 4:
        return 28 + slot
    return None


def _code_ok(kind, code):
    if 8 <= code < 16 or code == 3:
        return True
    if kind == "sound":
        return code in (0, 20, 21)
    if kind == "fx":
        return code in (1, 2, CHAIN3, CHAIN4)
    return code in (0, 1, 2, 17, 18, 19) or (20 <= code < 36 and (code - 20) % 4 < 2)


def read_bin(data):
    """Records of a binary state file; raises Refused."""
    rep = Report()
    if len(data) < 32 or data[:8] != MAGIC:
        raise Refused("NOT_LUNAR", "not a Lunar Modulator file")
    if struct.unpack_from("<I", data, 28)[0] != crc32(data[:28]):
        raise Refused("BAD", "the header's CRC does not match")
    major, minor, kind = data[8], data[9], data[10]
    if major != MAJOR or minor > MINOR:
        raise Refused("TOO_NEW", "made with a newer Lunar Modulator")
    if kind == 0 or kind >= 9 or kind == 8:
        raise Refused("BAD", "not a kind this build knows")
    kname = KINDS[kind]
    hdr, count, esz, _, total = struct.unpack_from("<HHHHI", data, 12)
    if not (32 <= hdr <= 256 and 1 <= count <= CHUNKS_MAX and 20 <= esz <= 64):
        raise Refused("BAD", "a header out of range")
    if total != len(data):
        raise Refused("BAD", "the file's length is not its header's")
    if total > BIN_MAX:
        raise Refused("TOO_BIG", "past 96 KiB")
    dir_end = hdr + count * esz
    if dir_end + 4 > total:
        raise Refused("BAD", "a directory past the file")
    if struct.unpack_from("<I", data, dir_end)[0] != crc32(data[hdr:dir_end]):
        raise Refused("BAD", "the directory's CRC does not match")
    prev = (dir_end + 4 + 3) & ~3
    entries = []
    for i in range(count):
        e = data[hdr + i * esz:hdr + i * esz + 20]
        tag = TAGS.get(e[:4])
        version, flags, off, ln, crc = struct.unpack_from("<HHIII", e, 4)
        if not tag:
            if 0x41 <= e[0] <= 0x5A:
                raise Refused("TOO_NEW", "a critical chunk this build does not know")
        else:
            if kname not in CHUNK_KINDS[tag]:
                raise Refused("BAD", "a chunk this kind of file does not hold")
            if ln > CAP[tag] + 4:
                raise Refused("TOO_BIG", "a chunk past its cap")
        if flags & ~1:
            raise Refused("BAD", "unknown chunk flags")
        if version < 1:
            raise Refused("BAD", "a chunk version of 0")
        if off & 3 or off < prev or ln > total or off > total - ln:
            raise Refused("BAD", "a chunk out of place")
        if any(data[prev:off]):
            raise Refused("BAD", "padding that is not zero")
        prev = off + ln
        if crc32(data[off:off + ln]) != crc:
            raise Refused("BAD", "a chunk's CRC does not match")
        entries.append((tag, version, flags, off, ln))
    if prev != total:
        raise Refused("BAD", "the last chunk does not end the file")
    out = [{"rec": "head", "kind": kname, "major": MAJOR, "minor": minor}]
    units, dx7_seen, cable_seen, pos_seen, mod_seen, data_total = set(), 0, 0, 0, False, 0
    lines_seen = False
    for tag, version, flags, off, ln in entries:
        if not tag:
            rep.skipped += 1
            continue
        b = data[off:off + ln]
        if flags & 1:
            if ln < 4:
                raise Refused("BAD", "a deflated chunk without its length")
            unpacked = struct.unpack_from("<I", b)[0]
            if unpacked > CAP[tag]:
                raise Refused("TOO_BIG", "a chunk past its cap")
            b = inflate(b[4:], unpacked)
        elif ln > CAP[tag]:
            raise Refused("TOO_BIG", "a chunk past its cap")
        c = _Chunk(b)
        if tag == 1:
            for key, typ, val in c.kv():
                if not 1 <= key <= 8 or typ != KV_STR:
                    rep.skipped += 1
                    continue
                if len(val) > 1024:
                    raise Refused("BAD", "text past its length")
                out.append({"rec": "info", "key": INFO[key], "text": _clean_text(val, key)})
        elif tag == 2:
            rec = {"rec": "session", "current": 0, "octave": 0, "transpose": 0}
            key = {}
            for k, typ, val in c.kv():
                if 1 <= k <= 4 and typ == (KV_U32 if k == 4 else KV_I32) and len(val) == 4:
                    v = struct.unpack("<I" if k == 4 else "<i", val)[0]
                    lim = {1: (0, 3), 2: (-3, 3), 3: (-12, 12), 4: (0, 11)}[k]
                    if not lim[0] <= v <= lim[1]:
                        raise Refused("BAD", "a session out of range")
                    if k == 4:
                        key["root"] = v
                    else:
                        rec[["current", "octave", "transpose"][k - 1]] = v
                elif k == 5 and typ == KV_STR:
                    s = val.decode("ascii", "replace")
                    if not 1 <= len(val) <= 24 or not re.fullmatch(r"[a-z][a-z0-9-]*", s):
                        raise Refused("BAD", "not a scale id")
                    key["scale"] = s
                else:
                    rep.skipped += 1
            if len(key) == 2:
                rec["root"], rec["scale"] = key["root"], key["scale"]
            out.append(rec)
        elif tag == 3:
            role, sound, slot, uflags, idn = c.take(5)
            place = _unit_place(kname, role, sound, slot)
            if place is None:
                raise Refused("BAD", "a unit this kind of file does not hold")
            if place in units:
                raise Refused("BAD", "a unit given twice")
            units.add(place)
            if uflags & ~3:
                raise Refused("BAD", "unknown unit flags")
            if idn > 15:
                raise Refused("BAD", "an engine id past 15 characters")
            eid = c.take(idn).decode("ascii", "replace")
            if not _id_ok(eid):
                raise Refused("BAD", "not an engine id")
            if kname == "project" and place == 0 and not eid:
                raise Refused("BAD", "Sound 1 is never empty")
            if kname == "sound" and place == 0 and not eid:
                raise Refused("BAD", "a sound file's sound is never empty")
            ref = {"role": ROLES[role], "sound": sound, "slot": slot}
            out.append({"rec": "unit", **ref, "engine": eid})
            if uflags & 2:
                if role != MFX:
                    raise Refused("BAD", "on is a MIDI effect's")
                out.append({"rec": "on", **ref, "on": bool(uflags & 1)})
            elif uflags & 1:
                raise Refused("BAD", "unknown unit flags")
            n = c.u16()
            if n > 512:
                raise Refused("TOO_BIG", "more than 512 records in a unit")
            if n and not eid:
                raise Refused("BAD", "an empty unit with values")
            for _ in range(n):
                uid, focus, vtype, bits = struct.unpack("<HBBI", c.take(8))
                if not 1 <= uid <= 4095:
                    raise Refused("BAD", "a uid out of range")
                if focus != NONE and (focus >= 32 or role != SOUND):
                    raise Refused("BAD", "a pad out of range")
                rec = {"rec": "param", **ref, "uid": uid, "focus": None if focus == NONE else focus}
                _value(vtype, bits, rec)
                out.append(rec)
            level = None
            for k, typ, val in c.kv():
                if k != 1 or typ != KV_F32 or len(val) != 4:
                    rep.skipped += 1
                    continue
                v = struct.unpack("<I", val)[0]
                f = bits_f32(v)
                if not 0 <= f <= 100 or v == 0x80000000:
                    raise Refused("BAD", "a level out of range")
                level = v
            if level is not None:
                if role != SOUND or not eid:
                    raise Refused("BAD", "a level is a sound's")
                out.append({"rec": "level", "sound": sound, "f32": "%08x" % level})
        elif tag == 4:
            n = c.u8()
            if not 1 <= n <= 32:
                raise Refused("BAD", "an FM6 voice count out of range")
            for _ in range(n):
                v = c.take(160)
                if v[0] >= 32 or v[1] != 1:
                    raise Refused("BAD", "an FM6 voice out of range")
                if (dx7_seen >> v[0]) & 1:
                    raise Refused("BAD", "two voices in one FM6 slot")
                dx7_seen |= 1 << v[0]
                vced = v[2:157]
                if any(vced[k] > OP_MAX[k % 21] for k in range(126)) or \
                        any(vced[126 + k] > GLOB_MAX[k] for k in range(19)) or \
                        any(not 0x20 <= x <= 0x7E for x in vced[145:155]):
                    raise Refused("BAD", "an FM6 value out of range")
                out.append({"rec": "dx7", "slot": v[0], "vced": vced.hex()})
        elif tag == 5:
            if mod_seen:
                raise Refused("BAD", "two mod chunks")
            mod_seen = True
            h = c.take(8)
            if h[0] & ~1 or h[1] or h[2] or h[3]:
                raise Refused("BAD", "unknown mod flags")
            out.append({"rec": "mod"})
            if h[0] & 1:
                out.append({"rec": "seed", "seed": struct.unpack_from("<I", h, 4)[0]})
            elif kname in ("project", "mods"):
                raise Refused("BAD", "a project's or a mod rack's mod needs its seed")
            while c.left():
                item = c.u8()
                if item == 1:
                    pos, n = c.u8(), c.u8()
                    if pos >= 8 or not 1 <= n <= 15:
                        raise Refused("BAD", "a module out of range")
                    if (pos_seen >> pos) & 1:
                        raise Refused("BAD", "two modules at one rack position")
                    pos_seen |= 1 << pos
                    kid = c.take(n).decode("ascii", "replace")
                    if not _id_ok(kid):
                        raise Refused("BAD", "not a kind id")
                    out.append({"rec": "module", "pos": pos, "kind": kid})
                elif item == 2:
                    pos, uid, vtype, bits = struct.unpack("<BHBI", c.take(8))
                    if pos >= 8 or not (pos_seen >> pos) & 1:
                        raise Refused("BAD", "a parameter of no module")
                    if not 1 <= uid <= 4095:
                        raise Refused("BAD", "a uid out of range")
                    rec = {"rec": "param", "role": "module", "sound": 0, "slot": pos, "uid": uid,
                           "focus": None}
                    _value(vtype, bits, rec)
                    out.append(rec)
                elif item == 3:
                    pos, ver, n = struct.unpack("<BBH", c.take(4))
                    if pos >= 8 or not (pos_seen >> pos) & 1:
                        raise Refused("BAD", "pattern data of no module")
                    if n > 4096 or data_total + n > 8192:
                        raise Refused("TOO_BIG", "too much pattern data")
                    data_total += n
                    out.append({"rec": "data", "pos": pos, "version": ver, "hex": c.take(n).hex()})
                elif item == 4:
                    slot, src, via, unit, fl, dst, amt, ofs, lock, n = struct.unpack("<BBBBBHhhHB", c.take(14))
                    if slot >= 32:
                        raise Refused("BAD", "a matrix slot out of range")
                    if (cable_seen >> slot) & 1:
                        raise Refused("BAD", "two cables in one matrix slot")
                    cable_seen |= 1 << slot
                    if src >= 128 or (via != NONE and via >= 128) or not _code_ok(kname, unit) or \
                            not -16384 <= amt <= 16384 or not -16384 <= ofs <= 16384 or lock > 4095 or \
                            (dst >= 8 if fl & GATE_DST else dst > 4095) or \
                            (fl & GATE_DST and not 8 <= unit < 16):
                        raise Refused("BAD", "a cable out of range")
                    if n > 24:
                        raise Refused("BAD", "a parameter's name past 24 characters")
                    name = c.take(n)
                    if any(not 0x20 <= x <= 0x7E for x in name):
                        raise Refused("BAD", "a parameter's name out of range")
                    if n and dst:
                        raise Refused("BAD", "a cable with both a uid and a name")
                    if not n and not dst and not fl & GATE_DST:
                        raise Refused("BAD", "a cable to no parameter")
                    out.append({"rec": "cable", "slot": slot, "src": src, "via": via, "unit": unit,
                                "flags": fl, "dst": dst, "amount": amt, "offset": ofs, "lock": lock,
                                "name": name.decode("ascii")})
                else:
                    raise Refused("BAD", "an unknown mod item")
        elif tag in (6, 7):
            which = "clip" if tag == 7 else "set"
            n = 0
            while c.left():
                if n >= (12 if which == "clip" else 8192):
                    raise Refused("TOO_BIG", "too many lines")
                try:
                    text, c.i = _item_text(c.b, c.i)
                except (IndexError, ValueError, struct.error):   # UnicodeDecodeError is a ValueError
                    raise Refused("BAD", "a movy1 item that cannot be read") from None
                if c.i > len(c.b) or len(text.encode("utf-8")) > 16384:
                    raise Refused("BAD", "a movy1 item that cannot be read")
                if any(ord(ch) < 0x20 or ord(ch) == 0x7F for ch in text):
                    raise Refused("BAD", "a control character in a movy1 line")
                if which == "set" and n == 0 and text != "movy1":
                    raise Refused("BAD", "a set's first line is movy1")
                if which == "clip" and not re.match(r"(au 0 [0-7] |cl 0 0 |cp 0 0 |lk 0 0 |tg 0 0 )",
                                                    text[:7].ljust(7, "\0")):
                    raise Refused("BAD", "a clip line is au, cl, cp, lk or tg at track 0 and slot 0")
                out.append({"rec": "line", "which": which, "text": text})
                n += 1
            if not n:
                raise Refused("BAD", "an empty list of lines")
            if which == "clip" and n < 2:
                raise Refused("BAD", "a clip has its cl and cp lines")
            if lines_seen:
                raise Refused("BAD", "two lists of lines")
            lines_seen = True
        elif tag == 8:
            rec = {"rec": "view", "mode": None}
            keys = {}
            for k, typ, val in c.kv():
                if not 1 <= k <= 10 or typ != KV_U32 or len(val) != 4:
                    rep.skipped += 1
                    continue
                v = struct.unpack("<I", val)[0]
                if k == 1:
                    if v >= 9:
                        raise Refused("BAD", "not a view mode")
                    rec["mode"] = v
                else:
                    kmax = [4, 16, 43, 16, 64, 3, 8, 32, 64][k - 2]
                    if v > kmax or (VKEYS[k - 2] not in ("unit", "panel") and v < 1):
                        raise Refused("BAD", "a view key out of range")
                    keys[VKEYS[k - 2]] = v
            if rec["mode"] is None:
                raise Refused("BAD", "a view needs its mode")
            for k in VKEYS:
                if k in keys:
                    rec[k] = keys[k]
            out.append(rec)
        elif tag == 9:
            for k, typ, val in c.kv():
                if not 1 <= k <= 4 or typ not in (KV_BOOL, KV_I32) or len(val) != 4:
                    rep.skipped += 1
                    continue
                v = struct.unpack("<I", val)[0]
                if (typ == KV_BOOL and v > 1) or (typ == KV_I32 and (k != 4 or v > 16)):
                    raise Refused("BAD", "a setting out of range")
                if (typ == KV_BOOL) != (k != 4):
                    raise Refused("BAD", "a setting of the wrong type")
                out.append({"rec": "setting", "key": SETTINGS[k],
                            **({"bool": bool(v)} if typ == KV_BOOL else {"int": v})})
        if c.left():
            if version == 1:
                raise Refused("BAD", "a chunk longer than its contents")
    if kname in ("project", "sound") and 0 not in units:
        raise Refused("BAD", "a project needs its Sound 1" if kname == "project" else "a sound file needs its sound")
    if kname == "mods" and not mod_seen:
        raise Refused("BAD", "a mod rack needs its mod chunk")
    if kname in ("clip", "set") and not lines_seen:
        raise Refused("BAD", "a clip or a set needs its lines")
    out.append({"rec": "end"})
    return out, rep


# ---- Records as text (the same lines as fm1-state records) ---------------------------------------
def _js(s):
    out = []
    for ch in s:
        o = ord(ch)
        if ch == '"':
            out.append('\\"')
        elif ch == "\\":
            out.append("\\\\")
        elif o < 0x20:
            out.append("\\u%04x" % o)
        else:
            out.append(ch)
    return '"' + "".join(out) + '"'


def record_line(r):
    parts = []
    for k, v in r.items():
        if v is None:
            t = "null"
        elif v is True or v is False:
            t = "true" if v else "false"
        elif isinstance(v, int):
            t = str(v)
        else:
            t = _js(v)
        parts.append(_js(k) + ":" + t)
    return "{" + ",".join(parts) + "}"


def records_text(records):
    return "".join(record_line(r) + "\n" for r in records)


# ---- Schemas ------------------------------------------------------------------------------------
def validate(doc):
    """Schema errors of a document (empty when it validates), or None
    without the jsonschema package."""
    try:
        import jsonschema
        import referencing
    except ImportError:
        return None
    schemas = {p.name: json.loads(p.read_text()) for p in SCHEMA.glob("*.schema.json")}
    reg = referencing.Registry().with_resources(
        [(s["$id"], referencing.Resource.from_contents(s)) for s in schemas.values()])
    v = jsonschema.Draft202012Validator(schemas[f"{doc['kind']}.schema.json"], registry=reg)
    return [f"{list(e.path)}: {e.message}" for e in v.iter_errors(doc)]


# ---- Launch links ---------------------------------------------------------------------------------
LINK_CAP = 32768


def link_fragment(records, names):
    """`#lunar=` and the base64url (no padding) of the deflate-raw of the
    compact JSON (§12.4); refused past the 32 KiB cap."""
    text, _ = write_json(records, names, compact=True)
    c = zlib.compressobj(9, zlib.DEFLATED, -15)
    data = base64.urlsafe_b64encode(c.compress(text.encode()) + c.flush()).rstrip(b"=").decode()
    if len(data) > LINK_CAP:
        raise Refused("TOO_BIG", "past the 32 KiB a link carries")
    return "#lunar=" + data


def read_link(fragment, names):
    """A #lunar= fragment's records, its inflated text capped at the
    kind's cap (a decompression bomb stops there)."""
    data = fragment.split("#lunar=", 1)[-1]
    if len(data) > LINK_CAP:
        raise Refused("TOO_BIG", "past the 32 KiB a link carries")
    raw = base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))
    d = zlib.decompressobj(-15)
    text = d.decompress(raw, KIND_CAP[1] + 1)
    if len(text) > KIND_CAP[1]:
        raise Refused("TOO_BIG", "larger than any kind's cap")
    return read_json(text, names)


# ---- Files and the command line ------------------------------------------------------------------
KNOWN_TEXT = {"gpl": "in the GPL build only", "planned": "not built yet", "retired": "retired"}


def note_unknown(recs, rep, names):
    """fm1_state_note_unknown: the engines and kinds a binary file names that
    the build lacks, counted as the JSON reader counts them (the binary
    reader resolves no names)."""
    for r in recs:
        if r["rec"] == "unit" and r["engine"]:
            role = ROLES.index(r["role"])
            if not names.engine(role, r["engine"]):
                rep.unknown_name(r["engine"], names.known.get(r["engine"], ""))
        elif r["rec"] == "module" and r["kind"] not in names.kinds:
            rep.unknown_name(r["kind"], names.known.get(r["kind"], ""))


def read_any(data, names):
    """Records of a state file in either encoding."""
    if data[:8] == MAGIC:
        recs, rep = read_bin(data)
        note_unknown(recs, rep, names)
        return recs, rep
    return read_json(data, names)


SCALE_IDS = ["major", "minor", "chromatic", "dorian", "phrygian", "lydian", "mixolydian", "locrian"]


def key_problems(doc):
    """The project key has one home, the set's `key` line (stage A1; C major
    when the set has none): a project's session.key is written from it, and
    a load never applies it, so one that disagrees is a problem."""
    key = (doc.get("session") or {}).get("key")
    if doc.get("kind") != "project" or key is None or not doc.get("set"):
        return []
    root, scale = 0, 0
    for line in doc["set"]:
        w = line.split()
        if len(w) == 3 and w[0] == "key" and w[1].isdigit() and w[2].isdigit():
            root, scale = int(w[1]), int(w[2])
    want = {"root": ROOTS[root % 12], "scale": SCALE_IDS[scale] if scale < len(SCALE_IDS) else str(scale)}
    if key == want:
        return []
    return [f"session.key is {key['root']} {key['scale']} but the set's key is {want['root']} {want['scale']} "
            "(the set's `key` line is the project key; session.key is written from it)"]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("command", choices=["check", "canon", "pack", "unpack", "records", "url"])
    ap.add_argument("file")
    ap.add_argument("-o", "--out")
    ap.add_argument("--compact", action="store_true")
    ap.add_argument("--store", action="store_true", help="pack without deflate")
    ap.add_argument("--meta", help="a saved metadata export (fm1-render --meta) instead of the build's")
    args = ap.parse_args(argv)
    data = sys.stdin.buffer.read() if args.file == "-" else Path(args.file).read_bytes()
    names = Names.from_file(args.meta) if args.meta else Names.from_build()
    try:
        recs, rep = read_any(data, names)
        if args.command == "records":
            out = records_text(recs).encode()
        elif args.command == "url":
            out = (link_fragment(recs, names) + "\n").encode()
        elif args.command in ("canon", "unpack"):
            text, _ = write_json(recs, names, compact=args.compact)
            out = text.encode()
        elif args.command == "pack":
            text, _ = write_json(recs, names)
            recs, _ = read_json(text.encode(), names)
            out = write_bin(recs, deflate_chunks=not args.store)
        else:
            text, wrep = write_json(recs, names)
            doc = canon.loads(text)
            errors = validate(doc)
            problems = list(errors or [])
            if data[:8] != MAGIC and text.encode() != data:
                problems.append("not canonical (lunar_state.py canon writes it)")
            if rep.unknown:
                why = f": {KNOWN_TEXT[rep.known]}" if rep.known in KNOWN_TEXT else ""
                problems.append(f"uses {rep.name}, which this build does not have{why}")
            if rep.skipped:
                problems.append(f"{rep.skipped} skipped: {rep.first_skip}")
            problems += key_problems(doc)
            print(json.dumps({"kind": doc["kind"], "schema": "unchecked" if errors is None else
                              ("ok" if not errors else "errors"), "problems": problems}))
            return 1 if problems else 0
    except Refused as e:
        print(json.dumps({"code": e.code, "what": e.what, "path": e.path}), file=sys.stderr)
        return 1
    if args.out:
        Path(args.out).write_bytes(out)
    else:
        sys.stdout.buffer.write(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
