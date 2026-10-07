"""The parameter metadata export's layout (engines/state/schema/
metadata.schema.json; notes/2026-10-06-state-files.md §7.7), built in Python
from `fm1-render --list` and `--list-mod`: an independent construction that
tests/test_engine_metadata.py holds the C export (`fm1-render --meta`,
engines/state/fm1_meta.c) to, less what only C can say (instance bytes per
engine, aliases, known ids). `subset` cuts an export down to a few engines
and kinds, as engines/state/examples/metadata.json is.

Levels 1.1 (stage ED0), 1.2 (the v1 completion: source groups, a refusal's fix, the marks) and 1.3 (the id layout) add members only C's tables can say (page names, an
effect's group, whether a module is GPL, a modulation kind's licence, the
refusals, the telemetry layout, the id): EDITOR_ONLY_* list them,
`without_editor` takes them out, and tests/test_engine_editor_meta.py checks them on
their own. Each parameter's `step` is built here from the detent rule
(detent()).
"""
import json
import os
import re
from pathlib import Path

from tests import state_canon as canon

# The GPL switch the build was made with (engines/Makefile; tests/engine_helpers.py).
GPL_MODS = os.environ.get("FM1_GPL_MODS", "1") != "0"

ROOT = Path(__file__).resolve().parents[1]
ENGINES = ROOT / "engines"

# The FM6 voice fields in VCED order (the DX7's documented single-voice
# parameter list), and their largest values: what the C export (stage E2)
# will give, and what common.schema.json's dx7Op and globals check.
DX7_OP = [("R1", 99), ("R2", 99), ("R3", 99), ("R4", 99), ("L1", 99), ("L2", 99), ("L3", 99),
          ("L4", 99), ("BP", 99), ("LD", 99), ("RD", 99), ("LC", 3), ("RC", 3), ("RS", 7),
          ("AMS", 3), ("KVS", 7), ("OL", 99), ("M", 1), ("FC", 31), ("FF", 99), ("DET", 14)]
DX7_VOICE = [("PR1", 99), ("PR2", 99), ("PR3", 99), ("PR4", 99), ("PL1", 99), ("PL2", 99),
             ("PL3", 99), ("PL4", 99), ("ALG", 31), ("FB", 7), ("OKS", 1), ("LFS", 99),
             ("LFD", 99), ("LPMD", 99), ("LAMD", 99), ("LKS", 1), ("LFW", 5), ("LPMS", 7),
             ("TRNSP", 48)]
# The reader's caps (the note's §16), as the export states them.
LIMITS = {"bytes": {"project": 262144, "sound": 32768, "fx": 32768, "mods": 65536, "clip": 32768,
                    "settings": 4096, "movy1": 65536, "syx": 65536},
          "depth": 8, "string_bytes": 16384, "key_bytes": 64, "number_chars": 32, "members": 64,
          "items": 8192}
FLAG_ORDER = ["latch", "smooth", "nolock", "mod", "input", "poly", "log", "keysrc", "focus",
              "per_focus"]
# Level 1.1's members that --list and --list-mod cannot say: per engine (an
# engine's licence was in 1.0, from --list), per modulation kind, and at the
# top.
EDITOR_ONLY_ENGINE = ("group", "gpl", "page_names")
EDITOR_ONLY_KIND = ("licence", "gpl", "page_names")
EDITOR_ONLY_TOP = ("effect_groups", "refusals", "marks", "telemetry", "meta_id")
# Level 1.2's: a source's group, the groups and the curves' points (in `mod`), and the marks
# at the top (above). Level 1.3's, in `mod`: how the ids of a cable are laid out and the shape
# of the chain.
EDITOR_ONLY_SOURCE = ("group",)
EDITOR_ONLY_MOD = ("source_groups", "curve_points", "source_base", "source_stride", "unit_base",
                   "sounds", "inserts", "masters")


def detent(p):
    """A knob detent, as the panel steps (include/fm1_engine_meta.h's
    fm1_param_detent; a LOG parameter moves 1/100 of its position), in
    float32 arithmetic, as the export writes it."""
    f32 = canon.f32
    if p["type"] == 1:
        return 1
    if "log" in p["flags"]:
        v = f32(0.01)
    else:
        lo, hi = f32(p["min"]), f32(p["max"])
        rng = f32(hi - lo)
        if rng >= 10 and lo == int(lo) and hi == int(hi):
            v = max(float(int(f32(f32(rng / 100.0) + 0.5))), 1.0)
        else:
            v = f32(rng / 100.0)
    return canon.loads(canon.number(v))


def without_editor(doc):
    """doc less level 1.1's members that only C's tables say."""
    out = {k: v for k, v in doc.items() if k not in EDITOR_ONLY_TOP}
    out["engines"] = [{k: v for k, v in e.items() if k not in EDITOR_ONLY_ENGINE} for e in doc["engines"]]
    out["mod"] = {k: v for k, v in doc["mod"].items() if k not in EDITOR_ONLY_MOD}
    out["mod"]["kinds"] = [{k: v for k, v in m.items() if k not in EDITOR_ONLY_KIND} for m in doc["mod"]["kinds"]]
    out["mod"]["sources"] = [{k: v for k, v in x.items() if k not in EDITOR_ONLY_SOURCE} for x in doc["mod"]["sources"]]
    return out


def _define(path, name):
    m = re.search(r"#define %s\s+([0-9.]+)u?f?\b" % name, path.read_text())
    return float(m.group(1)) if "." in m.group(1) else int(m.group(1))


def meta_params(table, hidden=False):
    out, knobs = [], {}
    for p in table:
        row = {"uid": p["uid"], "name": p["name"], "abbr": p["abbr"],
               "type": "enum" if p["type"] == 1 else "float",
               "min": p["min"], "max": p["max"], "def": p["def"], "step": detent(p),
               "unit": p["unit"], "page": p["page"] + 1}
        if hidden or "input" in p["flags"]:
            row["hidden"] = True
        else:
            knobs[p["page"]] = knobs.get(p["page"], 0) + 1
            row["knob"] = knobs[p["page"]]
        row["flags"] = sorted(p["flags"], key=FLAG_ORDER.index)
        if p["type"] == 1:
            row["entries"] = list(p["names"])
        out.append(row)
    return out


def metadata_from_build(listed, mod, engines=None, kinds=None):
    """The export's layout, from fm1-render --list and --list-mod: what the C
    export (stage E2) must write, less what the build cannot say yet
    (instance bytes per engine, aliases, known ids)."""
    doc = {"lunar": "1.3", "kind": "metadata",
           "made": {"by": "desktop", "version": "0.0.0", "commit": "0000000"}}
    doc["build"] = {
        "engine_api": _define(ENGINES / "include" / "fm1_engine.h", "FM1_ENGINE_API_VERSION"),
        "mod_api": _define(ENGINES / "include" / "fm1_mod.h", "FM1_MOD_API_VERSION"),
        "rate": 44118,
        "ram_budget": _define(ROOT / "sim" / "web" / "src" / "fm1_app.h", "FM1_APP_RAM_BUDGET"),
        "gpl": GPL_MODS,
        "modules": "all"}        # the module list (FM1_MODULES): these tools build every module
    doc["engines"] = [
        {"id": e["id"], "name": e["name"], "kind": e["kind"], "credits": e["credits"],
         "licence": e["licence"], "max_voices": e["max_voices"], "per_note": e["per_note"], "pads": e["pads"],
         "fx_wants": e["fx_wants"], "params": meta_params(e["params"])}
        for e in listed if engines is None or e["id"] in engines]
    # Removed parameters' last names (engines/aliases.json, `retired`), as C's table has them.
    retired = json.loads((ENGINES / "aliases.json").read_text()).get("retired", [])
    for e in doc["engines"]:
        rows = {r["name"]: r["uid"] for r in retired if r.get("engine") == e["id"]}
        if rows:
            e["retired"] = rows
    sources = []
    for s in mod["sources"]:
        row = {"id": s["id"], "name": s["name"], "kind": s["kind"], "unit": s["unit"]}
        m = re.fullmatch(r"S([1-4])[A-Z]+", s["name"])
        if m:
            row["sound"] = int(m.group(1))
        sources.append(row)
    doc["mod"] = {
        "positions": mod["positions"], "slots": mod["slots"], "tick": mod["tick"],
        "kinds": [
            {"id": k["id"], "guid": k["guid"], "name": k["name"], "abbr": k["abbr"],
             "credits": k["credits"],
             "flags": (["transport"] if k["transport"] else []) + (["poly_ok"] if k["poly_ok"] else []),
             "ram": k["instance_bytes"], "data": k["data"], "params": meta_params(k["params"]),
             "gates": [{"name": g["name"], "kind": g["kind"], "unit": g["unit"],
                        "normal": g.get("normal")} for g in k["gates"]],
             "outs": [{"name": o["name"], "kind": o["kind"], "unit": o["unit"]} for o in k["outs"]]}
            for k in mod["kinds"] if kinds is None or k["id"] in kinds],
        "sources": sources,
        "units": [{"name": "snd1" if n == "snd" else n, "code": c} for c, n in mod["sinks"]],
        "host": meta_params(mod["host"], hidden=True),
        "polarities": ["auto", "uni", "bi", "inv"],
        "curves": ["lin", "square", "cube", "root", "cbrt", "exp", "log", "s"]}
    doc["dx7"] = {"user_slots": 32, "name_chars": 10,
                  "op_fields": [{"name": n, "max": m} for n, m in DX7_OP],
                  "voice_fields": [{"name": n, "max": m} for n, m in DX7_VOICE]}
    doc["keys"] = {"roots": ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"],
                   "scales": [{"id": n.lower(), "name": n} for n in
                              ("Major", "Minor", "Chromatic", "Dorian", "Phrygian", "Lydian",
                               "Mixolydian", "Locrian")]}
    doc["known_ids"] = []
    doc["limits"] = LIMITS
    return doc


def subset(doc, engines, kinds):
    """doc with only the engines and modulation kinds named, in its order."""
    out = dict(doc)
    out["engines"] = [e for e in doc["engines"] if e["id"] in engines]
    out["mod"] = dict(doc["mod"], kinds=[k for k in doc["mod"]["kinds"] if k["id"] in kinds])
    return out
