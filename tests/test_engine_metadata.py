"""The parameter metadata export, written by C (fm1-render --meta,
engines/state/fm1_meta.c; notes/2026-10-06-state-files.md §7.7), which an
editor builds its controls from:

- it is canonical JSON (tests/state_canon.py's layout, byte for byte) and the
  same bytes every run;
- it agrees with an independent construction from fm1-render --list and
  --list-mod (tests/state_meta.py) in everything both can say;
- what only C says is right: each engine's instance bytes at the FM-1's rate
  (fm1-render's own figure), FM6's VCED fields (the schema's ranges), the
  API versions, the RAM budget (the simulator's), the caps
  (include/fm1_state_caps.h), the project keys.

tests/test_state_schema.py validates it against metadata.schema.json and
holds engines/state/examples/metadata.json to it; tests/test_engine_names.py
checks its list entries, aliases and known ids.
"""
import json
import re
import subprocess

import pytest

from tests import state_canon as canon
from tests.state_meta import LIMITS, metadata_from_build
from tests.engine_helpers import ENGINES, renderer  # noqa: F401

ROOT = ENGINES.parent


def _define(path, name):
    m = re.search(r"#define %s\s+([0-9]+)u?\b" % name, path.read_text())
    return int(m.group(1))


@pytest.fixture(scope="module")
def text(renderer):
    return subprocess.run([str(renderer), "--meta"], check=True, capture_output=True,
                          text=True).stdout


@pytest.fixture(scope="module")
def meta(text):
    return canon.loads(text)


def _run(renderer, *args):
    return json.loads(subprocess.run([str(renderer), *args], check=True, capture_output=True,
                                     text=True).stdout)


def test_the_export_is_canonical_and_steady(renderer, text, meta):
    assert canon.dumps(meta) == text
    again = subprocess.run([str(renderer), "--meta"], check=True, capture_output=True,
                           text=True).stdout
    assert again == text
    assert list(meta)[:3] == ["lunar", "kind", "made"] and meta["kind"] == "metadata"


def test_it_agrees_with_the_list_tools(renderer, meta):
    """Everything --list and --list-mod say, the export says the same way;
    only the instance bytes per engine and the known ids are its own."""
    ref = metadata_from_build(_run(renderer, "--list"), _run(renderer, "--list-mod"))
    mine = json.loads(json.dumps(meta))
    for e in mine["engines"]:
        e.pop("ram")
    mine.pop("known_ids"), ref.pop("known_ids")
    assert mine == ref


def test_instance_bytes_are_the_renderers(renderer, meta, tmp_path):
    """An engine's `ram` is its instance at 44,118 Hz, as fm1-render reports
    it for a render at that rate."""
    ram = {e["id"]: e["ram"] for e in meta["engines"]}
    for eid in ("shapes", "drums", "dx7", "sw-sophie", "macro"):
        out = subprocess.run([str(renderer), "--engine", eid, "--note", "0:60:100:0.01",
                              "--seconds", "0.02", "--out", str(tmp_path / "x.wav")],
                             check=True, capture_output=True, text=True).stdout
        assert json.loads(out)["instance_bytes"] == ram[eid], eid
    assert all(isinstance(v, int) and v > 0 for v in ram.values())


def test_the_build_block(meta):
    b = meta["build"]
    assert b["engine_api"] == _define(ENGINES / "include" / "fm1_engine.h", "FM1_ENGINE_API_VERSION") == 4
    assert b["mod_api"] == _define(ENGINES / "include" / "fm1_mod.h", "FM1_MOD_API_VERSION") == 2
    assert b["rate"] == 44118
    assert b["ram_budget"] == _define(ROOT / "sim" / "web" / "src" / "fm1_app.h", "FM1_APP_RAM_BUDGET")
    assert b["gpl"] is False                      # no GPL module in this tree yet


def test_fm6_fields_are_the_formats(meta):
    """The VCED values by name, with the ranges a file's `ops` and `globals`
    take (common.schema.json) and a load clamps to."""
    common = json.loads((ENGINES / "state" / "schema" / "common.schema.json").read_text())["$defs"]

    def maxima(items):                       # a $ref to u99 is 0-99
        return [i.get("maximum", 99) for i in items]
    d = meta["dx7"]
    assert (d["user_slots"], d["name_chars"]) == (32, 10)
    assert [f["max"] for f in d["op_fields"]] == maxima(common["dx7Op"]["prefixItems"])
    assert [f["max"] for f in d["voice_fields"]] == maxima(common["dx7Voice"]["properties"]["globals"]["prefixItems"])
    assert [f["name"] for f in d["op_fields"]][:4] == ["R1", "R2", "R3", "R4"]
    assert d["op_fields"][-1]["name"] == "DET" and d["voice_fields"][-1]["name"] == "TRNSP"


def test_the_caps_are_the_readers(meta):
    caps = ENGINES / "include" / "fm1_state_caps.h"
    lim = meta["limits"]
    assert lim == LIMITS
    for kind, n in lim["bytes"].items():
        assert n == _define(caps, f"FM1_STATE_CAP_{kind.upper()}"), kind
    assert lim["depth"] == _define(caps, "FM1_STATE_CAP_DEPTH")
    assert lim["string_bytes"] == _define(caps, "FM1_STATE_CAP_STRING")
    assert lim["items"] == _define(caps, "FM1_STATE_CAP_ITEMS")


def test_keys_and_the_cable_vocabulary(meta):
    assert len(meta["keys"]["roots"]) == 12 and meta["keys"]["roots"][0] == "C"
    assert [s["id"] for s in meta["keys"]["scales"]] == ["major", "minor", "chromatic"]  # FM1_KEY_*
    mod = meta["mod"]
    assert mod["polarities"] == ["auto", "uni", "bi", "inv"]
    assert len(mod["curves"]) == 8
    assert [u["name"] for u in mod["units"]][:4] == ["snd1", "fx1", "fx2", "host"]
    assert all(p.get("hidden") for p in mod["host"])
    reg = next(k for k in mod["kinds"] if k["id"] == "register")
    assert reg["data"] == {"bytes": 5, "version": 1}


def test_floats_are_written_as_the_layout_says(renderer):
    """The export's float writer gives what tests/state_canon.py's number()
    gives (the shortest decimal that reads back to the float32, in
    ECMAScript's format) for every exponent's edges, values a knob reaches
    and random float32 bit patterns."""
    import struct
    out = subprocess.run([str(ENGINES / "build" / "fm1-meta-number-test"), "20000"], check=True,
                         capture_output=True, text=True).stdout.splitlines()
    assert len(out) > 20000
    for line in out:
        bits, got = line.split()
        v = struct.unpack("<f", bytes.fromhex(bits)[::-1])[0]
        assert got == canon.number(v), (bits, got)
