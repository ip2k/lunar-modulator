"""The names a saved file uses, held steady (notes/2026-10-06-state-files.md
§5.2, §9, ST4):

- list entries only grow at their end: every entry pinned in
  tests/fixtures/enum-names.json still names its index in the build, by its
  name or by an entry alias, and a list has exactly the pinned entries (a
  new one is appended to the fixture with it); entry names are distinct
  without case, so a file's name finds one index;
- aliases (engines/aliases.json) name a real parameter or entry and never
  shadow a current name;
- known ids (engines/known-ids.json) have a reason the format knows, are
  unique, and a planned one is not in the build;
- engines/state/fm1_known.c is what tools/gen_known.py writes from the two
  files.
"""
import json
import subprocess
import sys

import pytest

from tests.engine_helpers import ENGINES, renderer  # noqa: F401

ROOT = ENGINES.parent
PINNED = ROOT / "tests" / "fixtures" / "enum-names.json"
ALIASES = ENGINES / "aliases.json"
KNOWN = ENGINES / "known-ids.json"


@pytest.fixture(scope="module")
def meta(renderer):
    return json.loads(subprocess.run([str(renderer), "--meta"], check=True, capture_output=True,
                                     text=True).stdout)


def owners(meta):
    """{("engines" | "mod", id): [param, ...]} from the export."""
    out = {("engines", e["id"]): e["params"] for e in meta["engines"]}
    out.update({("mod", k["id"]): k["params"] for k in meta["mod"]["kinds"]})
    return out


def gpl_ids():
    """The ids known-ids.json gives as GPL modules: in a build only with the
    GPL switch on, so their pins stand aside when it is off."""
    return {r["id"] for r in json.loads(KNOWN.read_text())["ids"] if r["reason"] == "gpl"}


def test_list_entries_only_grow_at_their_end(meta):
    pinned = json.loads(PINNED.read_text())
    have = owners(meta)
    seen = set()
    gpl = gpl_ids()
    for section in ("engines", "mod"):
        for oid, lists in pinned[section].items():
            if (section, oid) not in have and oid in gpl and not meta["build"]["gpl"]:
                continue              # a GPL module, built without the switch
            assert (section, oid) in have, f"{oid} is pinned but not in the build: move it, never drop it"
            params = {str(p["uid"]): p for p in have[(section, oid)]}
            for uid, entries in lists.items():
                p = params.get(uid)
                assert p is not None and p["type"] == "enum", (oid, uid)
                now = p["entries"]
                aliases = p.get("entry_aliases", {})
                for i, name in enumerate(entries):
                    assert i < len(now) and (now[i] == name or aliases.get(name) == i), \
                        f"{oid} #{uid} entry {i} was {name!r}: append, or alias a rename"
                assert len(now) == len(entries), \
                    f"{oid} #{uid} ({p['name']}) has {len(now)} entries, {len(entries)} pinned: pin the new ones"
                seen.add((section, oid, uid))
    for (section, oid), params in have.items():
        for p in params:
            if p["type"] == "enum":
                assert (section, oid, str(p["uid"])) in seen, \
                    f"{oid} {p['name']} (#{p['uid']}) is a list with no pinned entries"


def test_entry_names_find_one_index(meta):
    for (_, oid), params in owners(meta).items():
        for p in params:
            if p["type"] != "enum":
                continue
            names = [n.lower() for n in p["entries"]] + [n.lower() for n in p.get("entry_aliases", {})]
            assert len(set(names)) == len(names), (oid, p["name"])
            assert not any(n.startswith("#") for n in names), (oid, p["name"])


def test_aliases_name_real_things_and_shadow_nothing(meta):
    data = json.loads(ALIASES.read_text())
    have = owners(meta)
    for row in data["params"] + data["entries"]:
        section = "engines" if "engine" in row else "mod"
        oid = row.get("engine", row.get("kind"))
        params = {p["uid"]: p for p in have[(section, oid)]}
        p = params[row["uid"]]
        if "index" in row:
            assert p["type"] == "enum" and 0 <= row["index"] < len(p["entries"]), row
            assert row["alias"].lower() not in [n.lower() for n in p["entries"]], row
        else:
            names = {q["name"].lower() for q in params.values()}
            names |= {q["abbr"].lower() for q in params.values()}
            assert row["alias"].lower() not in names, row
    # The export carries them where they belong.
    for (section, oid), params in have.items():
        for p in params:
            want = sorted(r["alias"] for r in data["params"]
                          if r.get("engine" if section == "engines" else "kind") == oid and r["uid"] == p["uid"])
            assert sorted(p.get("aliases", [])) == want, (oid, p["name"])


def test_known_ids(meta):
    rows = json.loads(KNOWN.read_text())["ids"]
    ids = [r["id"] for r in rows]
    assert len(set(ids)) == len(ids)
    built = {e["id"] for e in meta["engines"]} | {k["id"] for k in meta["mod"]["kinds"]}
    for r in rows:
        assert r["reason"] in ("gpl", "planned", "retired"), r
        assert r["what"] in ("sound", "audio_fx", "midi_fx", "mod"), r
        assert ("since" in r) == (r["reason"] == "retired"), r
        if r["reason"] != "gpl":
            assert r["id"] not in built, f"{r['id']} is built: it is no longer {r['reason']}"
        if r["reason"] == "gpl" and r["id"] in built:
            assert meta["build"]["gpl"], f"{r['id']} is GPL, built without the switch"
    # The export lists exactly the ones the build lacks, in the file's order.
    assert [k["id"] for k in meta["known_ids"]] == [i for i in ids if i not in built]


def test_the_c_tables_are_what_the_tool_writes():
    res = subprocess.run([sys.executable, str(ROOT / "tools" / "gen_known.py"), "--check"],
                         capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
