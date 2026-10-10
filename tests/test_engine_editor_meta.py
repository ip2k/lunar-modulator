"""What the metadata export says for the advanced editor (levels 1.1 to 1.3, stage
ED0; notes/2026-10-06-web-editor.md §6, decisions ED4, ED11 and ED16):

- every engine, audio effect, MIDI effect and modulation kind of the build is
  in it, each with its licence, whether that is GPL, its page names and (an
  audio effect) its group, and every parameter with its knob detent;
- page names are the panel's: the arpeggiator's PLAY ... SEED, and a null for
  every page the panel shows by number, one per page the panel pages
  (tests/test_sim_editor_meta.py checks them against the screen);
- the effect groups are the project page's, every audio effect in one;
- the refusal codes are the loader's and the planner's, with the screen's
  words, and memory only as a percentage of the FM-1's budget;
- the telemetry layout adds up, with the runtime's counts;
- `meta_id` is CRC-32 of the export less `made` and itself, the same every
  run;
- ids, codes, groups and sections stay put: tests/fixtures/editor-meta.json
  pins them, and only additions are allowed;
- licences follow the licence table and the GPL switch, on and off.

tests/test_engine_metadata.py checks the rest of the export, and
tests/test_state_schema.py validates it.
"""
import json
import re
import subprocess
import zlib

import pytest

from tests import state_canon as canon
from tests.engine_helpers import ENGINES, ROOT, renderer  # noqa: F401
from tests.state_meta import EDITOR_ONLY_ENGINE, EDITOR_ONLY_MOD, EDITOR_ONLY_SOURCE, EDITOR_ONLY_TOP

FIXTURE = ROOT / "tests" / "fixtures" / "editor-meta.json"
REFUSAL_TEST = ENGINES / "build" / "fm1-mod-refusal-test"


def _run(tool, *args):
    return subprocess.run([str(tool), *args], check=True, capture_output=True, text=True).stdout


@pytest.fixture(scope="module")
def text(renderer):
    return _run(renderer, "--meta")


@pytest.fixture(scope="module")
def meta(text):
    return canon.loads(text)


@pytest.fixture(scope="module")
def listed(renderer):
    return json.loads(_run(renderer, "--list"))


@pytest.fixture(scope="module")
def listed_mod(renderer):
    return json.loads(_run(renderer, "--list-mod"))


def _define(path, name):
    m = re.search(r"#define %s\s+([0-9]+)u?\b" % name, path.read_text())
    return int(m.group(1))


def _modules(meta):
    return meta["engines"] + meta["mod"]["kinds"]


def test_level_1_2_carries_every_editor_member(meta):
    assert meta["lunar"] == "1.3"
    assert list(meta)[-len(EDITOR_ONLY_TOP):] == list(EDITOR_ONLY_TOP)
    for e in meta["engines"]:
        want = {"licence", *EDITOR_ONLY_ENGINE} - (set() if e["kind"] == "audio_fx" else {"group"})
        assert want <= set(e), e["id"]
        assert ("group" in e) == (e["kind"] == "audio_fx"), e["id"]
    for k in meta["mod"]["kinds"]:
        assert {"licence", "gpl", "page_names"} <= set(k) and "group" not in k, k["id"]
    for m in _modules(meta) + [{"id": "host", "params": meta["mod"]["host"]}]:
        for p in m["params"]:
            assert p["step"] > 0, (m["id"], p["name"])
    assert set(EDITOR_ONLY_MOD) <= set(meta["mod"])
    assert all(set(EDITOR_ONLY_SOURCE) <= set(x) for x in meta["mod"]["sources"])


def test_source_groups_are_the_patch_bays(meta):
    """Level 1.2: a source's group is from its id (the ranges fm1_mod.h gives),
    so the editor holds no source name; the names of the groups are C's."""
    groups = meta["mod"]["source_groups"]
    ids = [g["id"] for g in groups]
    assert ids == ["notes", "sound", "lanes", "lane_values"]
    assert [g["name"] for g in groups] == ["Notes, clock and chance", "Sound {sound}'s notes",
                                           "Sequencer lanes", "Lane values"]
    header = (ENGINES / "include" / "fm1_mod.h").read_text()
    seq_gate, seq_vel, s_note = (int(re.search(r"%s = ([0-9]+)" % n, header).group(1)) for n in
                                 ("FM1_MOD_SRC_SEQ_GATE", "FM1_MOD_SRC_SEQ_VEL", "FM1_MOD_SRC_S_NOTE"))
    for x in meta["mod"]["sources"]:
        want = ("sound" if x["id"] >= s_note else "lane_values" if seq_vel <= x["id"] < seq_vel + 8
                else "lanes" if seq_gate <= x["id"] < seq_gate + 8 else "notes")
        assert x["group"] == want, x["name"]
        assert x["group"] in ids
        assert ("sound" in x) == (x["group"] == "sound"), x["name"]
        # The lanes' names are what the old name pattern said, so the Map's groups did not move.
        if x["group"] == "lanes":
            assert re.fullmatch(r"SEQ[1-8]", x["name"])
        if x["group"] == "lane_values":
            assert re.fullmatch(r"SQV[1-8]", x["name"])
    assert {x["group"] for x in meta["mod"]["sources"]} == set(ids)


def test_the_id_layout_and_the_chain_shape_are_the_headers(meta):
    """Level 1.3: the editor reads how a cable's ids are laid out (a module's
    outputs are source_base + source_stride x position + port; its parameters
    and gate inputs unit_base + position) and the chain's shape from the
    export, and holds none of it. They are fm1_mod.h's, and a saved record
    carries them, so they are pinned."""
    header = (ENGINES / "include" / "fm1_mod.h").read_text()
    enum = lambda n: int(re.search(r"%s = ([0-9]+)" % n, header).group(1))   # noqa: E731
    mod = meta["mod"]
    assert mod["source_base"] == enum("FM1_MOD_SRC_MODULE") == enum("FM1_MOD_SRC_SYSTEM")
    assert mod["unit_base"] == enum("FM1_MOD_MODULE")
    assert mod["source_stride"] == _define(ENGINES / "include" / "fm1_mod.h", "FM1_MOD_MAX_OUTS")
    assert mod["sounds"] == _define(ENGINES / "include" / "fm1_mod.h", "FM1_MOD_SOUNDS")
    assert mod["inserts"] == _define(ENGINES / "include" / "fm1_mod.h", "FM1_MOD_INSERTS")
    assert mod["masters"] == _define(ENGINES / "include" / "fm1_mod.h", "FM1_MOD_MASTERS")
    # The telemetry block counts the same chain, and the sinks of `units` are its shape.
    tele = ENGINES / "include" / "fm1_tele.h"
    assert (mod["sounds"], mod["inserts"], mod["masters"]) == tuple(
        _define(tele, n) for n in ("FM1_TELE_SOUNDS", "FM1_TELE_INSERTS", "FM1_TELE_MASTERS"))
    assert mod["positions"] <= 8 and mod["source_stride"] >= max(len(k["outs"]) for k in mod["kinds"])
    names = {u["name"] for u in mod["units"]}
    assert {f"snd{k + 1}.fx{j + 1}" for k in range(mod["sounds"]) for j in range(mod["inserts"])} <= names
    # The id of the last module output stays below 256 (a record keeps it in a byte).
    assert mod["source_base"] + mod["source_stride"] * mod["positions"] <= 256
    assert mod["unit_base"] + mod["positions"] <= 16          # below the first sound unit (16)


def test_curve_points_are_the_runtimes(meta):
    """Level 1.2: each curve sampled in 33 steps; the lin curve is the identity, every
    curve is sign-preserving and passes through 0 and the ends."""
    pts = meta["mod"]["curve_points"]
    names = meta["mod"]["curves"]
    assert len(pts) == len(names) and all(len(c) == 33 for c in pts)
    lin = pts[names.index("lin")]
    assert all(abs(lin[k] - (-1 + k / 16)) < 1e-6 for k in range(33))
    for n, c in zip(names, pts):
        assert c[16] == 0 and c[0] == -1 and c[32] == 1, n
        assert all(c[k] <= c[k + 1] + 1e-6 for k in range(32)), n


def test_marks_are_the_panels(meta):
    """Level 1.2: the matrix marks, with the characters the panel's MATRIX page
    writes (fm1_mod_ui.c), and a repair only where one exists."""
    marks = meta["marks"]
    assert [m["mark"] for m in marks] == [">", "v", "~", "!", "-"]
    assert [m["name"] for m in marks] == ["runs", "voice", "late", "refused", "off"]
    ui = (ROOT / "sim" / "web" / "src" / "fm1_mod_ui.c").read_text()
    for c in "-!v":
        assert "mk[0] = '%s'" % c in ui, c
    assert "'~' : '>'" in ui
    late = marks[2]
    assert late["words"] == "a tick late" and late["fills"] == ["loop"]
    assert all(m["detail"] is None or m["fills"] == list(dict.fromkeys(re.findall(r"\{(\w+)\}", m["detail"])))
               for m in marks)


def test_refusal_fixes_are_few_and_closed(meta):
    fixes = {c["name"]: c["fix"] for c in meta["refusals"]["codes"] if "fix" in c}
    assert fixes == {"VOICE_TO_MONO": {"id": "global", "words": "Make it global"},
                     "VOICE_TO_EFFECT": {"id": "global", "words": "Make it global"}}


def test_every_module_of_the_build_is_there(meta, listed, listed_mod):
    """Every engine, effect and MIDI effect --list names, every kind
    --list-mod names, in registry order; each kind of module present."""
    assert [e["id"] for e in meta["engines"]] == [e["id"] for e in listed]
    assert [k["id"] for k in meta["mod"]["kinds"]] == [k["id"] for k in listed_mod["kinds"]]
    kinds = {e["kind"] for e in meta["engines"]}
    assert kinds == {"sound", "audio_fx", "midi_fx"} and meta["mod"]["kinds"]


def test_steps_are_the_knobs(meta):
    """A few detents by hand: the rule itself is held to an independent
    construction in tests/test_engine_metadata.py."""
    by = {e["id"]: {p["name"]: p for p in e["params"]} for e in meta["engines"]}
    assert by["filter"]["Cutoff"]["step"] == 0.01 and "log" in by["filter"]["Cutoff"]["flags"]
    assert by["filter"]["Type"]["step"] == 1
    assert by["arp"]["Seed"]["step"] == 655             # 0..65535: whole units, a hundredth
    lin = [p for e in meta["engines"] for p in e["params"]
           if p["type"] == "float" and "log" not in p["flags"] and (p["min"], p["max"]) == (0, 1)]
    assert lin and all(p["step"] == 0.01 for p in lin)


def test_page_names_are_one_per_panel_page(meta):
    for m in _modules(meta):
        pages = max([p["page"] for p in m["params"] if not p.get("hidden")] or [1])
        assert len(m["page_names"]) == pages, m["id"]
    arp = next(e for e in meta["engines"] if e["id"] == "arp")
    assert arp["page_names"] == ["PLAY", "RHYTHM", "CHANCE", "FEEL", "MORE", "KEYS", "SEED"]
    named = {m["id"]: m["page_names"] for m in _modules(meta)
             if any(n is not None for n in m["page_names"])}
    assert "arp" in named and set(named) <= {"arp", "acid-gen"}   # the MIDI effects' ARP pages
    assert all(None not in names for names in named.values())
    app = (ROOT / "sim" / "web" / "src" / "fm1_app.c").read_text()
    assert "kArpPages" not in app and "kMfxPages" not in app   # the panel reads fm1_page_name


def _readme_groups():
    """The project page's effect lists: {label: text} from README.md's
    "The effects:" list."""
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    block = text.split("The effects:\n", 1)[1].split("\n\n", 1)[0]
    groups = {}
    for item in re.split(r"\n- ", "\n" + block)[1:]:
        m = re.match(r"\*\*(.+?):\*\*(.*)", item.replace("\n", " "), re.S)
        groups[m.group(1)] = m.group(2)
    return groups


def test_effect_groups_are_the_pages(meta):
    groups = meta["effect_groups"]
    ids = [g["id"] for g in groups]
    assert len(set(ids)) == len(ids)
    effects = [e for e in meta["engines"] if e["kind"] == "audio_fx"]
    assert all(e["group"] in ids for e in effects), [e["id"] for e in effects if e["group"] not in ids]
    page = _readme_groups()
    names = {g["id"]: g["name"] for g in groups}
    assert [names[i] for i in ids if i != "test"] == list(page)
    # Each effect the page names sits in the group that names it (longest
    # names first, so "DJ Filter" is not read as "Filter").
    for label, words in page.items():
        rest = words
        for e in sorted(effects, key=lambda e: -len(e["name"])):
            if re.search(r"\b%s\b" % re.escape(e["name"]), rest):
                assert names[e["group"]] == label, (e["id"], label)
                rest = re.sub(r"\b%s\b" % re.escape(e["name"]), "", rest)
    on_page = {e["id"] for e in effects
               if any(re.search(r"\b%s\b" % re.escape(e["name"]), w) for w in page.values())}
    assert {e["id"] for e in effects if e["group"] != "test"} == on_page
    assert {e["id"] for e in effects if e["group"] == "test"} == {"test-gain", "test-ext"}


def test_refusals_are_the_loaders_and_the_planners(meta):
    codes = meta["refusals"]["codes"]
    by_name = {c["name"]: c for c in codes}
    assert len(by_name) == len(codes) and len({c["code"] for c in codes}) == len(codes)
    # The loader's, in FM1_STATE_* order (engines/state/state_names.c).
    names = re.search(r'"OK", ([^}]*)\}', (ENGINES / "state" / "state_names.c").read_text()).group(1)
    loader = re.findall(r'"([A-Z_]+)"', names)
    assert [by_name[n]["code"] for n in loader] == list(range(1, len(loader) + 1))
    # The planner's: the C test reaches each reason it can and agrees with
    # the plan on every slot of its fuzz.
    out = json.loads(_run(REFUSAL_TEST, "1000"))
    assert out["failed"] == 0 and out["cases"] >= 30 and out["fuzz_slots"] == 32000
    # The loop each late slot closes (fm1_mod_slot_loop, stage ED1): checked
    # on every delayed slot of the fuzz, and there are some.
    assert out["late_loops"] > 0
    cable = {c["name"] for c in codes if "cable" in c["of"] and c["code"] >= 32}
    assert set(out["reasons"]) <= cable
    assert {"NO_SOURCE", "NO_DEST", "NOLOCK", "ENUM_NO_MOD", "VOICE_TO_MONO", "VOICE_TO_EFFECT",
            "UNIT_RESERVED"} <= set(out["reasons"])
    header = (ENGINES / "include" / "fm1_refusal.h").read_text()
    for c in codes:
        assert re.search(r"FM1_REFUSE_%s = %d\b" % (c["name"], c["code"]), header), c["name"]
        assert c["fills"] == list(dict.fromkeys(re.findall(r"\{(\w+)\}", c["detail"] or "")))
    assert [k["reason"] for k in meta["refusals"]["known"]] == ["gpl", "planned", "retired", "list"]


def test_refusal_words_say_memory_in_percent(meta):
    """Owner, 2026-10-06: a user sees memory only as a percentage of the
    FM-1's budget, refusal messages included; the screen's own words."""
    for c in meta["refusals"]["codes"]:
        for text in (c["words"], c["detail"] or ""):
            assert not re.search(r"\d\s*K\b|\bKB\b|\bkB\b|\bbytes?\b|\bKiB\b", text), (c["name"], text)
    ram = next(c for c in meta["refusals"]["codes"] if c["name"] == "RAM")
    assert ram["fills"] == ["pct"] and "{pct}%" in ram["detail"]
    app = (ROOT / "sim" / "web" / "src" / "fm1_app.c").read_text()
    assert '"does not fit"' in app and ram["words"].lower() == "does not fit"
    assert '"needs %u%% of RAM"' in app and ram["detail"] == "needs {pct}% of RAM"
    rate = next(c for c in meta["refusals"]["codes"] if c["name"] == "RATE")
    assert '"refuses %.0f Hz"' in app and rate["detail"] == "refuses {rate} Hz"


def test_the_telemetry_layout_adds_up(meta):
    t = meta["telemetry"]
    mod_h = ENGINES / "include" / "fm1_mod.h"
    positions, slots, voices, outs = (_define(mod_h, n) for n in (
        "FM1_MOD_POSITIONS", "FM1_MOD_SLOTS", "FM1_MOD_VOICES", "FM1_MOD_MAX_OUTS"))
    rows = {s["name"]: s for s in t["sections"]}
    assert list(rows) == ["meters", "reduction", "voices", "outs", "voice_outs", "dests", "voice_dests"]
    assert len(rows["meters"]["rows"]) == 4 * 3 + 4 and rows["meters"]["fields"] == ["peak", "rms"]
    assert rows["meters"]["rows"][:3] == ["snd1", "snd1.fx1", "snd1.fx2"]
    assert rows["meters"]["rows"][-4:] == ["mix", "fx1", "fx2", "out"]
    assert rows["reduction"]["rows"][-3:] == ["fx1", "fx2", "limiter"]
    assert t["version"] == 2 and rows["reduction"]["fields"] == ["db", "gate"]
    assert len(rows["voices"]["rows"]) == voices
    assert len(rows["outs"]["rows"]) == positions and len(rows["outs"]["items"]) == outs
    assert len(rows["voice_outs"]["fields"]) == voices
    assert len(rows["dests"]["rows"]) == slots and len(rows["voice_dests"]["rows"]) == slots
    offset = mask = 0
    for s in t["sections"]:
        assert (s["offset"], s["mask"]) == (offset, mask), s["name"]
        assert len(set(s["rows"])) == len(s["rows"]) and len(set(s["fields"])) == len(s["fields"])
        offset += len(s["rows"]) * max(1, len(s["items"])) * len(s["fields"])
        mask += len(s["rows"])
    assert t["floats"] == offset and mask <= 32 * t["mask_words"]
    assert t["hz"] == 30                        # ED11: at most 30 blocks a second


def test_meta_id_is_the_exports_crc_less_made(renderer, text, meta):
    doc = dict(meta)
    mid = doc.pop("meta_id")
    doc.pop("made")
    assert mid == "%08x" % zlib.crc32(canon.dumps(doc).encode())
    assert _run(renderer, "--meta") == text     # the same every run


def test_pinned_ids_stay_put(meta):
    """Codes, groups, telemetry sections and the arp's page names never move
    or change; new ones are added (tests/fixtures/editor-meta.json)."""
    pin = json.loads(FIXTURE.read_text())
    codes = {c["code"]: c["name"] for c in meta["refusals"]["codes"]}
    assert all(codes.get(int(k)) == v for k, v in pin["refusal_codes"].items())
    groups = [g["id"] for g in meta["effect_groups"]]
    assert groups[:len(pin["effect_groups"])] == pin["effect_groups"]
    fx = {e["id"]: e.get("group") for e in meta["engines"]}
    assert all(fx[k] == v for k, v in pin["effect_group_of"].items() if k in fx)
    t = meta["telemetry"]
    assert t["version"] >= pin["telemetry"]["version"]
    for want, got in zip(pin["telemetry"]["sections"], t["sections"]):
        assert got["name"] == want["name"] and got["offset"] == want["offset"]
        assert got["rows"][:len(want["rows"])] == want["rows"]
    assert [m["mark"] for m in meta["marks"]][:len(pin["marks"])] == pin["marks"]
    assert [g["id"] for g in meta["mod"]["source_groups"]][:len(pin["source_groups"])] == pin["source_groups"]
    assert {k: meta["mod"][k] for k in pin["mod_layout"]} == pin["mod_layout"]
    fixes = {str(c["code"]): c["fix"]["id"] for c in meta["refusals"]["codes"] if "fix" in c}
    assert all(fixes.get(k) == v for k, v in pin["refusal_fix"].items())
    pages = {m["id"]: m["page_names"] for m in _modules(meta)}
    assert all(pages[k][:len(v)] == v for k, v in pin["page_names"].items() if k in pages)
    assert "arp" in pages


def test_licences_follow_the_table_and_the_switch(meta, listed):
    """Each module's licence is the licence table's (fm1-render --list, the
    GPL switch's table), GPL exactly when it names a GNU licence, and GPL
    modules only in a build with the switch on."""
    lic = {e["id"]: e.get("licence") for e in listed}
    if not any(lic.values()):
        pytest.skip("this build's --list names no licences (the GPL switch's table is not in it)")
    for e in meta["engines"]:
        assert e["licence"] == lic[e["id"]], e["id"]
        assert e["gpl"] == ("GPL" in e["licence"]), e["id"]
    for k in meta["mod"]["kinds"]:
        assert k["licence"] == "MIT" and k["gpl"] is False, k["id"]
    gpl = [e["id"] for e in meta["engines"] if e["gpl"]]
    assert bool(gpl) <= meta["build"]["gpl"]


def test_licences_with_the_switch_on_and_off():
    """Both builds of the switch (tests/test_gpl_switch.py's directories): on,
    the GPL modules are in the export marked GPL and the build says so; off,
    none is, each is a known id whose reason is `gpl`, and every module both
    builds have carries the same licence. The two exports differ in id."""
    from tests.test_gpl_switch import build
    on, off = (canon.loads(_run(build(name, gpl)["render"], "--meta"))
               for name, gpl in (("native", 1), ("native-mit", 0)))
    assert on["build"]["gpl"] is True and off["build"]["gpl"] is False
    gpl = {e["id"] for e in on["engines"] if e["gpl"]}
    assert gpl and all("GPL" in e["licence"] for e in on["engines"] if e["id"] in gpl)
    assert not any(e["gpl"] or "GPL" in e["licence"] for e in _modules(off))
    assert {e["id"] for e in on["engines"]} - {e["id"] for e in off["engines"]} == gpl
    known = {k["id"]: k["reason"] for k in off["known_ids"]}
    assert all(known.get(i) == "gpl" for i in gpl), {i: known.get(i) for i in gpl}
    shared = {e["id"]: (e["licence"], e["gpl"]) for e in off["engines"]}
    assert all(shared[e["id"]] == (e["licence"], e["gpl"]) for e in on["engines"] if e["id"] in shared)
    assert on["meta_id"] != off["meta_id"]
