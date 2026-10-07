"""The virtual FM-1's side of the editor's metadata (stage ED0;
notes/2026-10-06-web-editor.md §6, decision ED4):

- the panel's pages are the export's: every module's page count, and the
  bottom bar names a page exactly where `page_names` does, with the same
  word (the arpeggiator's PLAY ... SEED, Acid Gen's LINE ... SEED);
- the page's static www/meta.json is the simulator's export: canonical, a
  1.2 export that validates, `made.by` "simulator", and its `meta_id` is its
  own CRC-32 less `made` and itself;
- the module wrote it (fm1w_meta_read, with the 32-bit module's instance
  bytes) and the build record (www/fm1.wasm.json) says its fm1w_meta_id was
  the file's id when build.sh checked them (test/meta.mjs);
- it is what fm1-sim-render --meta writes from these sources but for the
  instance bytes, a 64-bit build's here; a warning when the engines have
  moved on since, as for the module itself.
"""
import json
import subprocess
import warnings
import zlib

import pytest

from tests import state_canon as canon
from tests.test_sim_web import SIM, tools  # noqa: F401

WWW = SIM / "www"


def _call(tool, *args):
    return subprocess.run([str(tool), *args], check=True, capture_output=True, text=True).stdout


@pytest.fixture(scope="module")
def build_meta(tools, tmp_path_factory):
    """The export as the harness writes it for the page (--meta)."""
    path = tmp_path_factory.mktemp("meta") / "meta.json"
    _call(tools["sim"], "--meta", str(path))
    return path.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def labels(tools):
    return json.loads(_call(tools["sim"], "--page-labels"))


def test_the_panels_pages_are_the_exports(build_meta, labels):
    meta = canon.loads(build_meta)
    modules = meta["engines"] + meta["mod"]["kinds"]
    assert set(labels) == {m["id"] for m in modules}
    for m in modules:
        names, shown = m["page_names"], labels[m["id"]]
        assert len(shown) == len(names), (m["id"], shown, names)
        for k, (label, name) in enumerate(zip(shown, names)):
            head, _, word = label.partition(" ")
            assert head == f"{k + 1}/{len(names)}", (m["id"], label)
            if name is not None:
                assert word == name, (m["id"], label, name)
            else:                                  # numbered only: the unit's own word
                assert word in ("Sound", "M1", "Mod1", m["name"]), (m["id"], label)
    named = {m["id"] for m in modules if any(n is not None for n in m["page_names"])}
    assert "arp" in named and all(None not in next(x["page_names"] for x in modules if x["id"] == i)
                                  for i in named)


def test_meta_json_is_the_simulators_export():
    path = WWW / "meta.json"
    text = path.read_text(encoding="utf-8")
    meta = canon.loads(text)
    assert canon.dumps(meta) == text
    assert meta["kind"] == "metadata" and meta["lunar"] == "1.2"
    assert meta["made"] == {"by": "simulator", "version": "0.0.0", "commit": "0000000"}
    doc = dict(meta)
    mid = doc.pop("meta_id")
    doc.pop("made")
    assert mid == "%08x" % zlib.crc32(canon.dumps(doc).encode())


def test_meta_json_validates():
    jsonschema = pytest.importorskip("jsonschema")
    pytest.importorskip("referencing")
    from tests.test_state_schema import validator
    meta = json.loads((WWW / "meta.json").read_text(encoding="utf-8"))
    errors = list(validator("metadata").iter_errors(meta))
    assert not errors, "\n".join(f"{list(e.path)}: {e.message}" for e in errors[:5])
    assert jsonschema


def test_the_module_and_meta_json_were_checked_together():
    """build.sh writes www/meta.json beside www/fm1.wasm and records what
    test/meta.mjs found: the module's fm1w_meta_id is the file's id."""
    record = json.loads((WWW / "fm1.wasm.json").read_text(encoding="utf-8"))
    meta = json.loads((WWW / "meta.json").read_text(encoding="utf-8"))
    check = record["meta"]
    assert check["passed"] and check["meta_id"] == check["module_meta_id"] == meta["meta_id"]
    assert check["lunar"] == meta["lunar"]
    assert check["bytes"] == len((WWW / "meta.json").read_bytes())
    assert record["gpl_mods"] == int(meta["build"]["gpl"])


def _without_bytes(doc):
    """doc less what differs between a 32-bit module and a 64-bit desktop
    build of one registry: the instance bytes, and so the id; and `made`."""
    d = json.loads(json.dumps(doc))
    d.pop("made"), d.pop("meta_id")
    for m in d["engines"] + d["mod"]["kinds"]:
        m.pop("ram")
    return d


def test_meta_json_is_current(build_meta):
    """meta.json is what these sources write, but for the instance bytes,
    which are the 32-bit module's. When it is not, the engines or the export
    have moved on since the module was built: a warning, as for the module
    itself (tests/test_sim_web.py fails in CI when sim/web's own inputs,
    the export's writer and tables among them, changed)."""
    built = canon.loads(build_meta)
    meta = canon.loads((WWW / "meta.json").read_text(encoding="utf-8"))
    if built["build"]["gpl"] != meta["build"]["gpl"]:
        pytest.skip("this harness was built with the other GPL switch than the page's module")
    if _without_bytes(built) != _without_bytes(meta):
        warnings.warn("sim/web/www/meta.json is not what these sources write; rebuild with "
                      "sim/web/build-on-aeon.sh")
