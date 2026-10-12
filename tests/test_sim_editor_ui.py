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
    files = {p.name: p.read_text() for p in sorted(EDITOR.glob("*.js"))}
    # Telemetry field names are data keys, not module choices. A field can
    # share a name with an effect ("gate"); exempt only metadata-known names
    # in a fields.indexOf lookup, leaving every other quoted id checked.
    fields = {f for section in meta["telemetry"]["sections"] for f in section["fields"]}
    # The native note schema's gate field and render/automation's mix target
    # are protocol names, not hard-coded engine choices. Limit these
    # exemptions to the modules that implement those protocols.
    protocol_names = {
        "sequence-model.js": {"gate"},
        "sequencer.js": {"mix"},
        "sequencer-host.js": {"mix"},
        "audio-export.js": {"mix"},
        "render.worker.js": {"mix"},
    }
    found = []
    for fname, code in files.items():
        code = re.sub(r"\.fields\.indexOf\(([\"'])([a-z0-9_.-]+)\1\)",
                      lambda m: ".fields.indexOf('')" if m[2] in fields else m[0], code)
        code = re.sub(r"typeof\s+[\w.]+\s*(?:===|!==)\s*([\"'])function\1", "typeof value", code)
        quoted = set(re.findall(r"'([a-z0-9_.-]+)'", code)) | set(re.findall(r'"([a-z0-9_.-]+)"', code))
        found.extend(f"{fname}: {name}" for name in sorted((quoted & ids) - protocol_names.get(fname, set())))
    assert not found, f"editor/*.js names {found}"


def test_the_editor_holds_no_id_layout_or_chain_shape():
    """§17, extended after the v1 review: the editor's code holds no module
    source id layout (the base, the stride, the unit base) and no count of the
    chain (sounds, inserts, masters, rack positions, matrix slots); the
    metadata gives them (level 1.3, `mod.*`), model.js reads them in once
    (`setLayout`) and the rest of the code names them by those exports. The
    names test above greps names; these are the binary-record details that
    always passed the page tests."""
    meta = json.loads((WWW / "meta.json").read_text())
    mod = meta["mod"]
    assert meta["lunar"] >= "1.3"
    for key in ("source_base", "source_stride", "unit_base", "sounds", "inserts", "masters", "positions", "slots"):
        assert isinstance(mod[key], int) and mod[key] >= 0, key
    files = {p.name: p.read_text() for p in sorted(EDITOR.glob("*.js"))}
    model = files["model.js"]
    # The eight are read from the metadata: no number at their declarations.
    for name in ("SOUNDS", "INSERTS", "MASTERS", "POSITIONS", "SLOTS", "SRC_MODULE", "SRC_STRIDE", "UNIT_MODULE"):
        assert re.search(r"export let %s = 0;" % name, model), name
        assert not re.search(r"(const|let|var)\s+%s\s*=\s*[1-9]" % name, "\n".join(files.values())), name
    assert "setLayout(doc.mod)" in model
    # And the arithmetic and the counts are not written out anywhere: strides, source bases, the
    # bare 64, loops to a count, arrays of one, key patterns of 1-4 / 1-8.
    forbidden = {
        "a stride shift or mask": r">>\s*3\b|&\s*7\b",
        "the source base as a number": r"[<>]=?\s*64\b|[-+]\s*64\b",
        "a stride as a number": r"\b8\s*\*\s*(pos|from|to)\b|\b(pos|from|to)\s*\*\s*8\b",
        "a count of the chain": r"new Array\((2|4|8|32)\)|\[0,\s*1\]\.map|levels:\s*\[0,\s*0,\s*0,\s*0\]|slot\s*<\s*(8|32)\b",
        "a key pattern with its count": r"\^(s|p|m)\(\[1-[48]\]\)|\.in\(\[12\]\)|\^m\(\[12\]\)",
    }
    found = []
    for fname, code in files.items():
        # SMF uses controller 64 for sustain. The native Movy codec uses a
        # 64-entry song/gate bound. These are not modulation source IDs;
        # their format/capacity checks run in midi-import.mjs against Wasm.
        if fname in {"midi-import.js", "sequence-model.js"}:
            continue
        for line_no, line in enumerate(code.splitlines(), 1):
            text = re.sub(r"//.*$", "", line)
            # Song entry capacity is a sequencer limit, not a modulation ID.
            if fname == "sequencer.js":
                text = text.replace("state.model.song.length >= 64", "state.model.song.length >= SONG_CAP")
            for what, rx in forbidden.items():
                if re.search(rx, text) and "mfx" not in text:
                    found.append(f"{fname}:{line_no} {what}: {line.strip()[:90]}")
    assert not found, found


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
    editor_part = worklet[worklet.index("onEditor(m)"):worklet.index("  onMessage(m)")]
    assert "JSON" not in editor_part and "fm1w_ram_part" in editor_part


def test_the_editor_shows_memory_only_as_a_percentage():
    """§11, §19: a user sees memory only as a percentage of the budget."""
    # File-format diagnostics describe byte lengths and bounded input files,
    # not the FM-1's RAM meter. Keep the percentage rule on the editor UI.
    formats = {"midi-import.js", "sequence-model.js", "sequencer-host.js", "wav.js", "render.worker.js"}
    code = "\n".join(p.read_text() for p in sorted(EDITOR.glob("*.js")) if p.name not in formats)
    # The words a page can show (template expressions left out): no KB,
    # no bytes.
    texts = ["".join(t) for t in re.findall(r"'([^'\n]*)'|`([^`\n]*)`", code)]
    shown = [t for t in texts if re.search(r"\bKB\b|\bkB\b|\bKiB\b|\bbytes\b", re.sub(r"\$\{[^}]*\}", "", t))]
    assert not shown, shown


def test_the_map_is_the_tables_second_view():
    """Stage ED5b (§10, §13): the Map draws the matrix's slots and edits them
    only through chains.js's makeCable (one CABLE record, the table's own
    path); it holds no edit of its own, sends nothing to a device, and asks C
    for its verdicts (the shadow Worker's `preview`, which now takes `mod`)."""
    map_js = (EDITOR / "map.js").read_text()
    chains = (EDITOR / "chains.js").read_text()
    assert "import { makeMap } from './map.js'" in chains and "makeCable" in chains
    code = re.sub(r"//[^\n]*", "", map_js)          # the comments may name what the code must not do
    for forbidden in ("sendOps", "setValue", "postMessage", "requestMIDIAccess", "fetch(", "localStorage"):
        assert forbidden not in code, forbidden
    # The verdict is C's: the preview of the cable record, with the rack after it.
    assert "preview([rec], false, true)" in map_js and "decodeMod" in map_js
    worker = (WWW / "shadow.worker.js").read_text()
    assert "mod: m.mod ? modRecords() : undefined" in worker
    # Wired into the page tests, and the editor's four tests run in the three engines.
    assert "editor-map.mjs" in (SIM / "build-on-aeon.sh").read_text()
    launcher = (SIM / "test" / "launch.mjs").read_text()
    assert "process.env.BROWSER" in launcher and "firefox" in launcher and "webkit" in launcher
    for t in ("editor.mjs", "editor-ui.mjs", "editor-reach.mjs", "editor-map.mjs"):
        assert "launch.mjs" in (SIM / "test" / t).read_text(), t
