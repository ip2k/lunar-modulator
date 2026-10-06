"""The simulator page's files (stage W1, notes/2026-10-06-state-files.md §12):
the static half. The page itself is checked in headless Chromium by
sim/web/test/files.mjs (build-on-aeon.sh); here, what can be read from the
tree: the example files the page offers by link, the schemas the site
publishes at their $id URLs, and the rule that the audio thread never
parses JSON."""

import json
import re
import sys

import pytest

from tests.engine_helpers import ROOT

WWW = ROOT / "sim" / "web" / "www"
EXAMPLES = ROOT / "engines" / "state" / "examples"


def test_the_page_examples_are_the_state_examples_and_mit():
    names = sorted(p.name for p in (WWW / "examples").glob("*.lunar"))
    assert "first-orbit.lunar" in names
    for name in names:
        page = (WWW / "examples" / name).read_bytes()
        assert page == (EXAMPLES / name).read_bytes(), f"{name} differs from engines/state/examples"
        assert json.loads(page)["licence"] == "MIT"
    # Every example files.js lists is there, under the ?load= allowlist's
    # pattern.
    listed = re.findall(r"path: '(examples/[^']+)'", (WWW / "files.js").read_text())
    assert sorted(p.split("/")[1] for p in listed) == names
    for p in listed:
        assert re.fullmatch(r"[a-z0-9][a-z0-9/_.-]*\.(lunar|movy1|syx)", p)


def test_the_site_publishes_the_schemas_at_their_ids(tmp_path):
    pytest.importorskip("markdown")       # tools/manual/build.py's own needs
    sys.path.insert(0, str(ROOT / "tools" / "manual"))
    try:
        import build
    finally:
        sys.path.pop(0)

    class B:
        repo = ROOT

    build.publish_schemas(B, tmp_path)
    src = sorted((ROOT / "engines" / "state" / "schema").glob("*.schema.json"))
    out = sorted((tmp_path / "schema" / "1").glob("*.schema.json"))
    assert [p.name for p in out] == [p.name for p in src] and len(out) >= 8
    for p in out:
        sid = json.loads(p.read_text())["$id"]
        assert sid == f"https://ip2k.github.io/lunar-modulator/schema/1/{p.name}"


def test_the_audio_thread_takes_binary_only():
    worklet = (WWW / "worklet.js").read_text()
    code = "\n".join(l for l in worklet.splitlines() if not l.lstrip().startswith("//"))
    # The one JSON.parse is the module's own catalogue, once, at start.
    parses = [l for l in code.splitlines() if "JSON.parse" in l]
    assert len(parses) == 1 and "fm1w_catalog()" in parses[0] and "TextDecoder" not in code
    # state-load refuses anything but the binary container (\x89Lunar).
    assert "b[0] === 0x89 && b[1] === 0x4c" in code
    files = (WWW / "files.js").read_text()
    assert "new Worker(new URL('shadow.worker.js', import.meta.url), { type: 'module' })" in files
    shadow = (WWW / "shadow.worker.js").read_text()
    assert "fm1w_state_check" in shadow and "fm1w_state_pack" in shadow


def test_links_and_embed_keep_to_the_rules():
    files = (WWW / "files.js").read_text()
    assert "const LOAD_PREFIXES = ['guide/', 'manual/', 'examples/'];" in files
    assert "credentials: 'omit', redirect: 'error'" in files
    assert "const LINK_CAP = 32768;" in files
    # Replies and events go to the parent's origin, never '*'; messages are
    # taken from the parent on this origin only, or, on a page served from
    # localhost, on any local origin (the localhost exception, owner,
    # 2026-10-06; its rules under Node in tests/test_sim_origins.py).
    assert "window.parent.postMessage({ lunar: 1, ...m }, parentOrigin)" in files
    assert "parentOrigin = location.origin" in files
    assert "e.source !== window.parent || !trustedOrigin(e.origin)" in files
    assert "return origin === self || (isLocalOrigin(self) && isLocalOrigin(origin));" in files
    assert "const LOCAL_HOSTS = ['localhost', '127.0.0.1', '[::1]'];" in files
    assert "postMessage(" in files and "'*'" not in files
    # Preferences only in localStorage.
    assert files.count("localStorage.") == 2
