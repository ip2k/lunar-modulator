"""Engine API v2's parameter fields (engines/include/fm1_engine.h,
engines/README.md, "Parameters"): every engine's and effect's uids and
flags against the pinned record in tests/fixtures/param-uids.json, the rules
the flags follow, the decision taken for every ENUM parameter, abbreviations
and units, and the Schwung adapters' uids derived from their keys.

The fixture is the contract: a reordered table keeps its uids and passes; a
changed, reused or dropped uid fails, so no lock or route can silently move.
"""
import json
import re
import subprocess
from pathlib import Path

import pytest

from tests.engine_helpers import ENGINES, renderer  # noqa: F401

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "param-uids.json"
SELFTEST = ENGINES / "build" / "fm1-schwung-selftest"
FLAG_BITS = [(0x01, "latch"), (0x02, "smooth"), (0x04, "nolock"), (0x08, "mod"), (0x10, "input"),
             (0x20, "poly")]
UNITS = ["none", "semi", "ms", "hz", "pct", "deg"]     # fm1_unit_t's order
UID_MAX = 0x0FFF

# The decision for every ENUM parameter (docs/15 S7a's table, O13, as
# checked against each engine's code in this stage). Six-Op's Patch and
# Sophie's pad parameters are read at note-on (LATCH), so they take
# modulation too; Macro's LPG is read every block and lockable, but a
# rounded route could end a note held under Off, so it takes none. Sophie's
# Pad, the edit focus, was NOLOCK until the owner made it lockable for the
# lock pages (2026-10-02, docs/15 S8); it takes no modulation. The
# rule for the effects' switches (owner, 2026-10-02): a switch-like control
# that changes cleanly (it crossfades, glides or hands over, so no change,
# however fast, steps the output) is lockable and modulatable, rounded when
# modulated; tests/test_engines_fx_switches.py turns each of them every
# third block to check it.
ENUM_FLAGS = {
    ("macro", "Model"): ["nolock"],             # rebuilds every voice
    ("macro", "LPG"): [],
    ("macro-heavy", "Model"): ["nolock"],       # as Macro's
    ("macro-heavy", "LPG"): [],
    ("shapes", "Shape"): ["nolock"],            # every voice's oscillator at once
    ("sixop", "Patch"): ["latch", "mod"],       # read per voice at note-on
    ("dx7", "Patch"): ["latch", "mod"],         # as Six-Op's: a voice's data at note-on
    ("sw-sophie", "Pad"): [],                   # the edit focus: lockable (owner, docs/15 S8)
    ("sw-sophie", "Model"): ["latch", "mod"],   # a voice keeps its pad's patch
    ("sw-sophie", "Filter Type"): ["latch", "mod"],
    ("sw-psxverb", "Model"): ["nolock"],        # clears the 128 KB work area
    ("filter", "Type"): ["mod"],                # warms the new type up, then crossfades
    ("drive", "Type"): ["mod"],                 # crossfades over 5 ms
    ("drive", "Auto"): ["mod"],                 # its gain glides
    ("comp", "Character"): ["mod"],             # hands the smoothing over, the detector
    ("comp", "Auto Rel"): ["mod"],              #   crossfades: no step in the reduction
    ("comp", "Auto Gain"): ["mod"],             # its makeup and its bound glide in
    ("limit", "Mode"): ["mod"],                 # glides the stage, frame by frame
    ("djfilter", "Slope"): ["mod"],             # crossfades over 5 ms: lockable, rounded
    ("tilt", "Curve"): ["mod"],                 # glides between its two curves
    ("sat", "Shape"): ["mod"],                  # crossfades over 5 ms
    ("isolator", "Kill"): ["mod"],              # the band gains glide: a clean change
}


def catalog(renderer):
    """{engine id: [parameter, ...]} with flags as names, every defined
    parameter (a Schwung adapter's hidden ones from its contract)."""
    listed = json.loads(subprocess.run([str(renderer), "--list"], check=True,
                                       capture_output=True, text=True).stdout)
    out = {}
    for e in listed:
        params = [dict(p, type="enum" if p["type"] == 1 else "float") for p in e["params"]]
        if e["id"].startswith("sw-"):
            c = json.loads(subprocess.run([str(SELFTEST), "--contract", e["id"]], check=True,
                                          capture_output=True, text=True).stdout)
            shown = {p["name"]: p for p in params}
            params = []
            for p in c["params"]:
                row = dict(p, type="enum" if p["type"] == 1 else "float",
                           flags=[n for b, n in FLAG_BITS if p["flags"] & b],
                           unit=UNITS[p["unit"]] if p["unit"] < len(UNITS) else p["unit"])
                if p["name"] in shown:
                    for field in ("uid", "flags", "unit", "abbr"):
                        assert shown[p["name"]][field] == row[field], (e["id"], p["name"], field)
                params.append(row)
        out[e["id"]] = params
    return out


@pytest.fixture(scope="module")
def built(renderer):
    return catalog(renderer)


def test_uids_and_flags_match_the_fixture(built):
    """Every parameter of every engine and effect has the uid, type and flags
    the fixture pins, and nothing is missing or extra on either side."""
    pinned = json.loads(FIXTURE.read_text())["engines"]
    assert set(built) == set(pinned), set(built) ^ set(pinned)
    for eid, params in built.items():
        have = {p["name"]: (p["uid"], p["type"], p["flags"]) for p in params}
        want = {p["name"]: (p["uid"], p["type"], p["flags"]) for p in pinned[eid]}
        assert have == want, eid


def test_uids_are_unique_nonzero_12_bit_and_never_reused(built):
    retired = json.loads(FIXTURE.read_text())["retired"]
    for eid, params in built.items():
        uids = [p["uid"] for p in params]
        assert all(0 < u <= UID_MAX for u in uids), eid
        assert len(set(uids)) == len(uids), eid
        assert not set(uids) & set(retired.get(eid, [])), eid


def test_flags_follow_the_rules(built):
    """NOLOCK never with MOD; every FLOAT takes modulation unless it is NOLOCK
    and is SMOOTH unless the engine reads it at note-on (LATCH); LATCH and
    SMOOTH never together; INPUT only on a FLOAT -1..1 with default 0; POLY
    only on a FLOAT that takes modulation, never an INPUT; no unknown bit."""
    for eid, params in built.items():
        for p in params:
            f = set(p["flags"])
            assert f <= {n for _, n in FLAG_BITS}, (eid, p["name"], f)
            assert not {"nolock", "mod"} <= f, (eid, p["name"])
            assert not {"latch", "smooth"} <= f, (eid, p["name"])
            if p["type"] == "float" and "nolock" not in f:
                assert "mod" in f and ("smooth" in f or "latch" in f), (eid, p["name"])
            if "input" in f:
                assert p["type"] == "float" and (p["min"], p["max"], p["def"]) == (-1, 1, 0)
            if "poly" in f:
                assert p["type"] == "float" and "mod" in f and "input" not in f, (eid, p["name"])


def test_per_note_engines_match_the_fixture(renderer, built):
    """set_param_note is there exactly on the engines the fixture names, and
    only those have POLY parameters (every one of them has some)."""
    pinned = json.loads(FIXTURE.read_text())["per_note"]
    listed = json.loads(subprocess.run([str(renderer), "--list"], check=True,
                                       capture_output=True, text=True).stdout)
    assert sorted(e["id"] for e in listed if e["per_note"]) == sorted(pinned)
    with_poly = {eid for eid, params in built.items()
                 if any("poly" in p["flags"] for p in params)}
    assert with_poly == set(pinned)


def test_every_enum_has_its_decided_flags(built):
    enums = {(eid, p["name"]): p["flags"] for eid, params in built.items()
             for p in params if p["type"] == "enum"}
    assert enums == ENUM_FLAGS


def test_abbreviations_and_units(built):
    """abbr: 1-6 printable characters (never NULL), unique in the engine, and
    still unique cut to 5 (a matrix row with a unit prefix, docs/16 §5.3).
    unit: one of the six. Every defined parameter, the Schwung modules'
    hidden ones included (from their contract)."""
    for eid, params in built.items():
        abbrs = [p["abbr"] for p in params]
        assert all(isinstance(a, str) and re.fullmatch(r"[ -~]{1,6}", a) for a in abbrs), \
            (eid, abbrs)
        assert len(set(abbrs)) == len(abbrs), eid
        assert len({a[:5] for a in abbrs}) == len(abbrs), eid
        assert all(p["unit"] in UNITS for p in params), eid
    units = {(eid, p["name"]): p["unit"] for eid, params in built.items() for p in params
             if p["unit"] != "none"}
    assert units[("echo", "Time")] == "ms" and units[("sw-sophie", "Tune")] == "semi"
    assert units[("limit", "Release")] == units[("limit", "Lookahead")] == "ms"
    assert units[("sw-sophie", "Color")] == "pct"
    assert units[("sw-sophie", "Ring Time")] == "ms"     # hidden: from the contract


def test_names_are_unique_without_case(built):
    """A lane label names its parameter by name without ASCII case
    (fm1_seq_lane_param), and the bridge trusts a stored uid while its
    parameter's name matches the label (engines/seq.md, "Where locks
    resolve"): both need every name in an engine distinct without case."""
    for eid, params in built.items():
        names = [p["name"].lower() for p in params]
        assert len(set(names)) == len(names), eid


def fnv1a_uid(key):
    """schwung_shim.h's KeyUid, computed independently."""
    h = 2166136261
    for c in key.encode():
        h = ((h ^ c) * 16777619) & 0xFFFFFFFF
    return 0x800 | ((h ^ (h >> 11) ^ (h >> 22)) & 0x7FF)


@pytest.mark.parametrize("engine", ["sw-sophie", "sw-psxverb"])
def test_schwung_uids_derive_from_the_module_keys(renderer, engine):
    """A Schwung parameter's uid is 0x800 plus its key's FNV-1a hash folded
    to 11 bits, so a module that reorders its parameters keeps every uid;
    native engines number from 1, below 0x800."""
    c = json.loads(subprocess.run([str(SELFTEST), "--contract", engine], check=True,
                                  capture_output=True, text=True).stdout)
    assert [p["uid"] for p in c["params"]] == [fnv1a_uid(p["key"]) for p in c["params"]]


def test_the_shim_has_a_ramp_for_every_smooth_parameter(built):
    """The Schwung shim keeps eight SMOOTH ramps per instance (kMaxRamps in
    src/schwung_shim.cc, docs/15 S7b); a module with more SMOOTH parameters,
    hidden ones included, would leave the rest unramped."""
    for eid, params in built.items():
        if eid.startswith("sw-"):
            assert sum("smooth" in p["flags"] for p in params) <= 8, eid


def test_native_uids_stay_below_the_derived_range(built):
    for eid, params in built.items():
        if not eid.startswith("sw-"):
            assert all(p["uid"] < 0x800 for p in params), eid


def test_macro_heavy_shares_macros_uids(built):
    """The parameters both engines have keep one uid, so a lock survives a
    swap between them; Macro Heavy's own Word Speed takes the next one."""
    macro = {p["name"]: p["uid"] for p in built["macro"]}
    heavy = {p["name"]: p["uid"] for p in built["macro-heavy"]}
    assert {n: heavy[n] for n in macro} == macro
    assert heavy["Word Speed"] == max(macro.values()) + 1
    names = [p["name"] for p in built["macro-heavy"]]
    assert [heavy[n] for n in names] != list(range(1, len(names) + 1)), \
        "uid is not index + 1 here: the case that catches a host using one for the other"
