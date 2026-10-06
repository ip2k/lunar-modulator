"""The JSON file kinds' schemas and example files (engines/state/schema/,
engines/state/examples/; notes/2026-10-06-state-files.md §7).

Nothing reads or writes these files yet (stages E2, E3 and P1). These tests
hold the design steady until then: every schema is a valid draft 2020-12
schema; every example validates and is in the canonical layout and member
order (tests/state_canon.py); every name in an example resolves in today's
build and every value of every unit is written; the sets and clips are the
sequencer core's own export, byte for byte; and the build's own parameter
metadata, turned into the export's layout, fits metadata.schema.json, so an
engine added later with a name the format cannot carry fails here.
"""
import json
import subprocess

import pytest

from tests import state_canon as canon
from tests.state_meta import subset
from tests.engine_helpers import ENGINES, GPL_MODS, renderer  # noqa: F401

jsonschema = pytest.importorskip("jsonschema")
referencing = pytest.importorskip("referencing")

SCHEMA = ENGINES / "state" / "schema"
EXAMPLES = ENGINES / "state" / "examples"
BASE = "https://ip2k.github.io/lunar-modulator/schema/1/"
SEQ = ENGINES / "build" / "fm1-seq"
KINDS = ["project", "sound", "fx", "mods", "clip", "settings", "metadata"]


def schemas():
    return {k: json.loads((SCHEMA / f"{k}.schema.json").read_text()) for k in KINDS + ["common"]}


def registry():
    res = [(s["$id"], referencing.Resource.from_contents(s)) for s in schemas().values()]
    return referencing.Registry().with_resources(res)


def validator(kind):
    return jsonschema.Draft202012Validator(schemas()[kind], registry=registry())


def examples():
    return sorted(EXAMPLES.glob("*.lunar")) + [EXAMPLES / "metadata.json"]


@pytest.fixture(scope="module")
def build(renderer):
    listed = json.loads(subprocess.run([str(renderer), "--list"], check=True,
                                       capture_output=True, text=True).stdout)
    mod = json.loads(subprocess.run([str(renderer), "--list-mod"], check=True,
                                    capture_output=True, text=True).stdout)
    return listed, mod


@pytest.fixture(scope="module")
def meta(renderer):
    """The build's metadata export, as C writes it (fm1-render --meta)."""
    return canon.loads(subprocess.run([str(renderer), "--meta"], check=True,
                                      capture_output=True, text=True).stdout)


# ---- member order --------------------------------------------------------------------
def _props(schema, *path):
    node = schema
    for p in path:
        node = node[p]
    return list(node["properties"])


def _check_order(obj, order, where):
    keys = list(obj)
    assert all(k in order for k in keys), (where, [k for k in keys if k not in order])
    assert keys == sorted(keys, key=order.index), (where, keys)


def check_order(doc):
    """Every object's members in the order its schema lists them."""
    s = schemas()
    d = s["common"]["$defs"]
    top = _props(d["head"]) + [k for k in _props(s[doc["kind"]]) if k != "kind"]
    _check_order(doc, top, "top")

    def unit(u, where, kind):
        if u is not None:
            _check_order(u, list(d[kind]["properties"]), where)

    def ref(r, where):
        if r is not None:
            _check_order(r, ["source"] if "source" in r else ["module", "port"], where)

    def target(t, where):
        variants = [list(v["properties"]) for v in d["target"]["oneOf"]]
        assert any(set(t) <= set(v) and list(t) == [k for k in v if k in t] for v in variants), where

    for i, snd in enumerate(doc.get("sounds", []) + ([doc["sound"]] if "sound" in doc else [])):
        if snd is None:
            continue
        unit(snd, f"sound {i + 1}", "sound")
        for j, u in enumerate(snd.get("inserts", [])):
            unit(u, f"sound {i + 1} insert {j + 1}", "effect")
        for j, u in enumerate(snd.get("midi_fx", [])):
            unit(u, f"sound {i + 1} mfx {j + 1}", "midiEffect")
    for j, u in enumerate(doc.get("master", []) + doc.get("chain", [])):
        unit(u, f"chain {j + 1}", "effect")
    for v in doc.get("dx7", []):
        _check_order(v, list(d["dx7Voice"]["properties"]), "dx7")
    if "session" in doc:
        _check_order(doc["session"], list(d["session"]["properties"]), "session")
        if "key" in doc["session"]:
            _check_order(doc["session"]["key"], list(d["key"]["properties"]), "key")
    if "made" in doc:
        _check_order(doc["made"], list(d["made"]["properties"]), "made")
    if "view" in doc:
        _check_order(doc["view"], list(d["view"]["properties"]), "view")
    if "mod" in doc:
        m = doc["mod"]
        _check_order(m, list(d["mod"]["properties"]), "mod")
        for x in m.get("rack", []):
            _check_order(x, list(d["module"]["properties"]), f"module {x['pos']}")
        for c in m.get("cables", []):
            _check_order(c, list(d["cable"]["properties"]), f"cable {c['slot']}")
            ref(c["from"], f"cable {c['slot']} from")
            ref(c.get("via"), f"cable {c['slot']} via")
            target(c["to"], f"cable {c['slot']} to")
    if "settings" in doc:
        _check_order(doc["settings"], _props(s["settings"], "properties", "settings"), "settings")


# ---- the tests ------------------------------------------------------------------------
def test_schemas_are_valid_and_named_for_their_place():
    for name, s in schemas().items():
        jsonschema.Draft202012Validator.check_schema(s)
        assert s["$schema"] == "https://json-schema.org/draft/2020-12/schema", name
        assert s["$id"] == BASE + f"{name}.schema.json", name


@pytest.mark.parametrize("path", examples(), ids=lambda p: p.name)
def test_example_validates_and_is_canonical(path):
    raw = path.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf") and b"\r" not in raw
    text = raw.decode("utf-8")
    doc = canon.loads(text)
    assert list(doc)[:2] == ["lunar", "kind"]
    if path.suffix == ".lunar":
        kind = doc["kind"]
        assert kind != "metadata"
        middle = path.name.split(".")[-2]
        assert middle == {"project": "first-orbit", "settings": "settings"}.get(kind, kind)
    else:
        assert doc["kind"] == "metadata"
    errors = sorted(validator(doc["kind"]).iter_errors(doc), key=lambda e: list(e.path))
    assert not errors, "\n".join(f"{list(e.path)}: {e.message}" for e in errors[:5])
    assert canon.dumps(doc) == text
    if doc["kind"] != "metadata":
        check_order(doc)


def test_the_schemas_refuse_what_they_should():
    good = canon.loads((EXAMPLES / "deep-bass.sound.lunar").read_text())
    v = validator("sound")
    assert v.is_valid(good)

    def bad(change):
        doc = json.loads(json.dumps(good))
        change(doc)
        return not v.is_valid(doc)

    assert bad(lambda d: d.update(lunar="2.0"))
    assert bad(lambda d: d.update(kind="project"))
    assert bad(lambda d: d.update(name="A NAME LONGER THAN 16"))
    assert bad(lambda d: d.update(title="bidi ‮ override"))
    assert bad(lambda d: d.update(extra=1))
    assert bad(lambda d: d["sound"].update(engine="Shapes"))
    assert bad(lambda d: d["sound"]["params"].update({"#0": 1}))
    assert bad(lambda d: d["sound"]["params"].update({"#4096x": 1}))
    assert bad(lambda d: d["sound"].update(level=101))
    assert bad(lambda d: d["sound"]["inserts"].append(None))
    assert bad(lambda d: d["mod"]["cables"][0].update(amount=100.5))
    assert bad(lambda d: d["mod"]["cables"][0].update(to={"unit": "snd5", "param": "Cutoff"}))
    assert bad(lambda d: d["mod"]["cables"][0].update(to={"module": 1, "param": "Rate", "gate": 1}))
    assert bad(lambda d: d["mod"]["cables"][0].update(curve="sine"))
    assert bad(lambda d: d["mod"]["rack"][0].update(pos=9))
    assert bad(lambda d: d["mod"]["rack"][0].update(data={"version": 1, "hex": "ABC"}))
    # The params `#UID` fallback and an ENUM by index are fine.
    doc = json.loads(json.dumps(good))
    doc["sound"]["params"]["#77"] = 0.5
    doc["sound"]["params"]["Shape"] = 6
    assert v.is_valid(doc)


def _resolve(table, params, where, pads=False):
    """Every key names a parameter, every ENUM string is an entry, every value
    is in range, and every parameter is written."""
    by_name = {p["name"]: p for p in table}
    for k, val in params.items():
        assert k in by_name, (where, k)
        p = by_name[k]
        if p["type"] == 1:
            if isinstance(val, str):
                assert val in p["names"], (where, k, val)
            else:
                assert isinstance(val, int) and p["min"] <= val <= p["max"], (where, k, val)
        else:
            assert isinstance(val, (int, float)) and p["min"] <= val <= p["max"], (where, k, val)
    uids = [by_name[k]["uid"] for k in params]
    assert uids == sorted(uids), (where, "uid order")
    return set(params)


def test_example_names_resolve_in_the_build(build):
    listed, mod = build
    eng = {e["id"]: e for e in listed}
    kinds = {k["id"]: k for k in mod["kinds"]}
    sources = {s["name"] for s in mod["sources"]}
    host = {p["name"] for p in mod["host"]}
    for path in sorted(EXAMPLES.glob("*.lunar")):
        doc = canon.loads(path.read_text())

        def unit(u, kind, where):
            e = eng[u["engine"]]
            assert e["kind"] == kind, (where, u["engine"])
            names = {p["name"] for p in e["params"]}
            # A pad kit's per-pad values are its PER_FOCUS ones (engine API v4).
            per_pad = {p["name"] for p in e["params"] if "per_focus" in p["flags"]}
            got = _resolve(e["params"], u["params"], where)
            if e["pads"]:
                assert len(u["pads"]) == e["pads"]["count"], where
                for k, pad in enumerate(u["pads"]):
                    assert _resolve(e["params"], pad, f"{where} pad {k + 1}") == per_pad
                assert got == names - per_pad, where
            else:
                assert "pads" not in u and got == names, where

        snds = doc.get("sounds", []) + ([doc["sound"]] if "sound" in doc else [])
        for i, s in enumerate(snds):
            if s is None:
                continue
            unit(s, "sound", f"{path.name} sound {i + 1}")
            for j, u in enumerate(s["inserts"]):
                if u:
                    unit(u, "audio_fx", f"{path.name} sound {i + 1} insert {j + 1}")
            for j, u in enumerate(s["midi_fx"]):
                if u:
                    unit(u, "midi_fx", f"{path.name} sound {i + 1} mfx {j + 1}")
        for j, u in enumerate(doc.get("master", []) + doc.get("chain", [])):
            if u:
                unit(u, "audio_fx", f"{path.name} chain {j + 1}")
        m = doc.get("mod")
        if not m:
            continue
        rack = {x["pos"]: kinds[x["kind"]] for x in m["rack"]}
        assert list(rack) == sorted(rack)
        for x in m["rack"]:
            k = kinds[x["kind"]]
            assert _resolve(k["params"], x["params"], f"{path.name} module {x['pos']}") == \
                {p["name"] for p in k["params"]}
        slots = [c["slot"] for c in m["cables"]]
        assert slots == sorted(set(slots)), path.name
        units = {"sound": {"snd", "snd.fx1", "snd.fx2", "host"}, "fx": {"fx1", "fx2", "fx3", "fx4"}}.get(
            doc["kind"], {"snd1", "snd2", "snd3", "snd4", "fx1", "fx2", "host"} |
            {f"snd{k}.fx{j}" for k in range(1, 5) for j in (1, 2)})
        for c in m["cables"]:
            where = f"{path.name} cable {c['slot']}"
            for r in (c["from"], c["via"]):
                if r and "source" in r:
                    assert r["source"] in sources, where
                elif r:
                    assert r["port"] in [o["name"] for o in rack[r["module"]]["outs"]], where
            t = c["to"]
            if "unit" in t:
                assert t["unit"] in units, where
                if t["unit"] == "host":
                    assert t["param"] in host, where
            elif "gate" in t:
                assert t["gate"] in [g["name"] for g in rack[t["module"]]["gates"]], where
            else:
                assert t["param"] in [p["name"] for p in rack[t["module"]]["params"]], where
            for f in ("amount", "offset"):
                assert c[f] == canon.percent(canon.q14(c[f])), (where, f, "not the shortest")


def _core_export(tmp_path, lines, tracks):
    src, dst = tmp_path / "in.movy1", tmp_path / "out.movy1"
    src.write_text("\n".join(lines) + "\n")
    subprocess.run([str(SEQ), "--tracks", str(tracks), "--seq", str(src), "--export", str(dst),
                    "--end", "64"], check=True, stdout=subprocess.DEVNULL)
    return dst.read_text()


def test_example_sets_and_clips_are_the_cores_own_export(renderer, tmp_path):
    """A project's set is the core's export, byte for byte (so it is Movy's
    format); a clip's lines, put at track 0 of a set, come back unchanged."""
    proj = canon.loads((EXAMPLES / "first-orbit.lunar").read_text())
    text = "\n".join(proj["set"]) + "\n"
    assert _core_export(tmp_path, proj["set"], 8) == text
    clip = canon.loads((EXAMPLES / "bass-a.clip.lunar").read_text())["clip"]
    head = ["movy1", "bpm 12000", "swing 50", "link 0", "tk 0 0 0"]
    out = _core_export(tmp_path, head + clip, 1).split("\n")[:-1]
    assert out == head + clip


def test_the_builds_metadata_fits_the_schema(meta):
    """Today's every engine, effect, MIDI effect and modulation kind, in the
    build's export (fm1-render --meta), validates: a new one whose names,
    abbreviations or ranges the format cannot carry fails here."""
    doc = meta
    errors = list(validator("metadata").iter_errors(doc))
    assert not errors, "\n".join(f"{list(e.path)}: {e.message}" for e in errors[:5])
    for e in doc["engines"] + doc["mod"]["kinds"]:
        names = [p["name"].lower() for p in e["params"]]
        assert len(set(names)) == len(names), e["id"]          # names compare without case
        for p in e["params"]:
            if p["type"] == "enum":
                assert len(p["entries"]) == p["max"] - p["min"] + 1, (e["id"], p["name"])
            if "hidden" not in p:
                assert 1 <= p["knob"] <= 4, (e["id"], p["name"])


def test_the_metadata_example_is_the_builds(meta):
    """engines/state/examples/metadata.json is the build's export (fm1-render
    --meta) cut down to a few engines and kinds, byte for byte: the golden
    file an editor can be written against. It is the default build's, with
    the GPL switch on (its `build.gpl` and `known_ids` say so)."""
    if not GPL_MODS:
        pytest.skip("the example is the export of the default build, GPL switch on")
    ex = canon.loads((EXAMPLES / "metadata.json").read_text())
    want = subset(meta, engines={e["id"] for e in ex["engines"]},
                  kinds={k["id"] for k in ex["mod"]["kinds"]})
    assert canon.dumps(ex) == canon.dumps(want)


def test_numbers_are_written_as_the_layout_says():
    n = canon.number
    assert [n(0.41), n(420.0), n(18000.0), n(-0.0), n(1 / 3), n(0.1), n(-2.5)] == \
        ["0.41", "420", "18000", "0", "0.33333334", "0.1", "-2.5"]
    assert [n(1e-7), n(5e-7), n(0.000001), n(1.5e-6), n(1e21), n(123456789.0)] == \
        ["1e-7", "5e-7", "0.000001", "0.0000015", "1e+21", "123456790"]
    assert n(7) == "7" and n(4294967295) == "4294967295"
    for v in (0.41, 1 / 3, 20.0, 18000.0, 0.0001, 3.14159, 1e-9, 65535.0):
        s = n(v)
        assert canon.f32(float(s)) == canon.f32(v)
        assert len(s.replace("-", "").replace(".", "").lstrip("0")) <= 9 or "e" in s
    with pytest.raises(ValueError):
        n(float("nan"))


def test_every_q14_amount_has_one_shortest_decimal():
    """Writers give a cable's amount as the shortest percent (at most 3
    decimals) that reads back to the same Q1.14, by the exact rule and by
    the float rule the mod script uses today (fm1_mod_q14 of v / 100)."""
    def q14_float(d):
        x = canon.f32(d / 100.0)
        x = max(-1.0, min(1.0, x))
        x = canon.f32(x * 16384.0)
        return int(canon.f32(x + 0.5)) if x >= 0 else -int(canon.f32(0.5 - x))
    for q in range(-16384, 16385):
        p = canon.percent(q)
        assert canon.q14(p) == q and q14_float(float(p)) == q, q
        assert len(canon.number(p).split(".")[-1]) <= 3 or "." not in canon.number(p)
    assert canon.percent(5734) == 35 and canon.percent(16384) == 100 and canon.percent(0) == 0
