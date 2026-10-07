"""The web editor's shell, flow and sound (stage ED2 of
notes/2026-10-06-web-editor.md): the static half. sim/web/test/editor-unit.mjs
runs the editor's data and history against the module when node is here;
the page itself (layouts, follow both ways, undo, PLAY and EDIT, every
module's inspector at desktop and tablet widths) is checked in headless
Chromium by sim/web/test/editor-ui.mjs (build-on-aeon.sh).
"""
import json
import re
import shutil
import subprocess

import pytest

from tests.engine_helpers import ROOT

SIM = ROOT / "sim" / "web"
WWW = SIM / "www"
EDITOR = WWW / "editor"


def test_the_editor_data_and_history_against_the_module():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    r = subprocess.run([node, str(SIM / "test" / "editor-unit.mjs"), str(WWW)],
                       capture_output=True, text=True, timeout=300)
    out = json.loads(r.stdout)
    assert r.returncode == 0 and out["failed"] == 0, (out["why"], r.stderr[-2000:])
    # Every control kind of §6's table is met by some parameter.
    assert set(out["kinds"]) == {"slider", "segments", "grid", "list", "search"}
    assert out["undo"]["back"] == out["undo"]["first"] and out["undo"]["steps"] >= 50


def test_the_editor_names_no_module():
    """§17: the editor's code holds no engine, effect, MIDI effect, kind or
    source id; everything comes from the metadata and C."""
    meta = json.loads((WWW / "meta.json").read_text())
    ids = {e["id"] for e in meta["engines"]}
    ids |= {k["id"] for k in meta["mod"]["kinds"]}
    ids |= {s["name"] for s in meta["mod"]["sources"] if len(s["name"]) > 3}
    code = "\n".join(p.read_text() for p in sorted(EDITOR.glob("*.js")))
    quoted = set(re.findall(r"'([a-z0-9_.-]+)'", code)) | set(re.findall(r'"([a-z0-9_.-]+)"', code))
    found = sorted(quoted & ids)
    assert not found, f"editor/*.js names {found}"


def test_the_editor_loads_on_first_use_and_keys_are_gated():
    html = (WWW / "index.html").read_text()
    app = (WWW / "app.js").read_text()
    # The layout switch is the page's; the editor is imported only when it
    # leaves Panel, never by a static import.
    assert 'id="layout-switch"' in html and 'id="editor-host"' in html
    assert "import('./editor/editor.js')" in app
    assert not re.search(r"^import .*editor/", app, re.M)
    # EDIT: no computer key reaches the FM-1 (§13).
    assert re.search(r"function keydown\(e\) \{.*?if \(sim\.keysToEditor\) return;", app, re.S)
    # The editor's port speaks binary only: no JSON on the audio thread.
    worklet = (WWW / "worklet.js").read_text()
    editor_part = worklet[worklet.index("onEditor(m)"):worklet.index("async onMessage(m)")]
    assert "JSON" not in editor_part and "fm1w_ram_part" in editor_part


def test_the_editor_shows_memory_only_as_a_percentage():
    """§11, §19: a user sees memory only as a percentage of the budget."""
    code = "\n".join(p.read_text() for p in sorted(EDITOR.glob("*.js")))
    # The words a page can show (template expressions left out): no KB,
    # no bytes.
    texts = ["".join(t) for t in re.findall(r"'([^'\n]*)'|`([^`\n]*)`", code)]
    shown = [t for t in texts if re.search(r"\bKB\b|\bkB\b|\bKiB\b|\bbytes\b", re.sub(r"\$\{[^}]*\}", "", t))]
    assert not shown, shown
