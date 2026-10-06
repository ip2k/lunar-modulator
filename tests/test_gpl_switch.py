"""The GPL switch (FM1_GPL_MODS, engines/Makefile; CLAUDE.md, "The GPL
switch"; docs/12 §6).

GPL modules sit in their own engines/third_party/<name>/, with their licence
and an UPSTREAM.md, behind one build switch that is on by default in every
build while we test. With it off, the build is MIT/BSD only and stays
shareable. This file builds both, each in a directory of its own
(sim/web/build/native and native-mit, as tests/test_sim_web.py's harness does,
so neither build is turned back and forth), and checks:

- the switch is 0 or 1 and each build says which it was built with;
- the build with the switch off compiles no GPL source and no GPL header
  (every object's dependency list), links no symbol a GPL object defines, and
  lists no GPL module, in fm1-render --list or in the virtual FM-1's
  catalogue;
- every module the switch-off build lacks is labelled GPL in the licence
  table, and every module so labelled is missing there: the registry gate and
  the table agree;
- every GPL directory carries its licence and an UPSTREAM.md, and every row
  of the licence table names a module and the directory its code comes from;
- the page can name the GPL modules and offer the module under the GPL: the
  notice's place, the licence text beside the page, and the build record's
  list of licences, which matches the build it was made from;
- a parity scenario that plays a GPL module says so, so it skips where the
  switch is off.
"""
import hashlib
import json
import os
import re
import subprocess
import warnings
from pathlib import Path

import pytest

from tests.engine_helpers import ENGINES, GPL_MODS, ROOT

SIM = ROOT / "sim" / "web"
THIRD_PARTY = ENGINES / "third_party"
GNU_TEXT = re.compile(rb"GNU (?:LESSER |AFFERO )?GENERAL PUBLIC LICENSE")
SPDX_GPL = re.compile(rb"SPDX-License-Identifier:[^\n]*\b(?:L|A)?GPL")
# The GNU GPL version 3 as the FSF publishes it (gnu.org/licenses/gpl-3.0.txt).
GPL3_SHA256 = "3972dc9744f6499f0f9b2dbf76696f2ae7ad8af9b23dde66d6af86c9dfb36986"


def is_gpl(spdx):
    return "GPL" in spdx


def gpl_dirs():
    """engines/third_party/<name>/ directories whose licence file is a GNU
    licence: everything in them is GPL code."""
    out = []
    for d in sorted(p for p in THIRD_PARTY.iterdir() if p.is_dir()):
        if any(GNU_TEXT.search(f.read_bytes()[:2000]) for f in d.glob("LICEN[CS]E*")):
            out.append(d)
    return out


def is_gpl_file(path):
    """A file of GPL code: under a GPL directory, or with a GPL SPDX line."""
    path = path.resolve()
    if any(d in path.parents for d in gpl_dirs()):
        return True
    try:
        with open(path, "rb") as f:
            return bool(SPDX_GPL.search(f.read(4096)))
    except OSError:
        return False


def build(name, gpl):
    """fm1-render and the virtual FM-1's harness, with the switch at `gpl`,
    in sim/web/build/<name> (the directories tests/test_sim_web.py uses)."""
    out = SIM / "build" / name
    targets = [out / "fm1-render", out / "fm1-sim-render"]
    env = dict(os.environ, FM1_GPL_MODS=str(gpl))
    subprocess.run(["make", "-C", str(ENGINES), "-f", "Makefile", "-f", str(SIM / "mk" / "sim.mk"),
                    f"SIM={SIM}", f"BUILD={out}", f"FM1_GPL_MODS={gpl}", "-j4",
                    *map(str, targets)], check=True, env=env, stdout=subprocess.DEVNULL)
    return {"dir": out, "render": targets[0], "sim": targets[1]}


def call(tool, *args):
    return subprocess.run([str(tool), *args], check=True, capture_output=True, text=True).stdout


@pytest.fixture(scope="module")
def on():
    return build("native", 1)


@pytest.fixture(scope="module")
def off():
    return build("native-mit", 0)


def listing(b):
    return {e["id"]: e for e in json.loads(call(b["render"], "--list"))}


def catalogue(b):
    return {e["id"]: e for e in json.loads(call(b["sim"], "--list"))}


def deps(d):
    """Every file the objects under d were compiled from: their .d files
    (-MMD -MP), resolved from engines/, where make runs."""
    files = set()
    for dep in d.rglob("*.d"):
        text = dep.read_text().replace("\\\n", " ")
        for line in text.splitlines():
            if ":" not in line:
                continue
            for tok in line.split(":", 1)[1].split():
                p = Path(tok) if os.path.isabs(tok) else ENGINES / tok
                files.add(p.resolve())
    return files


def defined_symbols(paths):
    out = set()
    for p in paths:
        res = subprocess.run(["nm", "-g", "--defined-only", str(p)], capture_output=True, text=True)
        if res.returncode:      # Apple's nm takes -U for "defined only"
            res = subprocess.run(["nm", "-g", "-U", str(p)], check=True, capture_output=True, text=True)
        out |= {line.split()[-1] for line in res.stdout.splitlines() if len(line.split()) >= 3}
    return out


# ---- The switch itself ---------------------------------------------------------------------

def test_the_switch_is_zero_or_one():
    res = subprocess.run(["make", "-C", str(ENGINES), "FM1_GPL_MODS=2", "-n"],
                         capture_output=True, text=True)
    assert res.returncode != 0 and "FM1_GPL_MODS is 0 or 1" in res.stderr


def test_each_build_says_how_it_was_built(on, off):
    for b, gpl in ((on, 1), (off, 0)):
        info = json.loads(call(b["render"], "--build-info"))
        assert info["gpl_mods"] == gpl and info["engine_api"] == 3
        header = (b["dir"] / "gen" / "fm1_gpl_mods.h").read_text()
        assert header.startswith(f"#define FM1_GPL_MODS {gpl} ")
    assert json.loads(call(off["render"], "--build-info"))["gpl_modules"] == 0


# ---- The MIT/BSD build has nothing GPL in it ---------------------------------------------

def test_the_mit_build_compiles_no_gpl_file(off):
    gpl = sorted(str(p.relative_to(ROOT)) for p in deps(off["dir"]) if is_gpl_file(p))
    assert not gpl, f"GPL code in the build with the switch off: {gpl}"


def test_the_mit_build_links_no_gpl_symbol(on, off):
    """No symbol that an object of GPL code defines (in the build with the
    switch on) is in the switch-off programs."""
    gpl_objs = []
    for dep in on["dir"].rglob("*.d"):
        obj = dep.with_suffix(".o")
        text = dep.read_text().replace("\\\n", " ")
        first = text.split(":", 1)[1].split() if ":" in text else []
        srcs = [(ENGINES / t).resolve() if not os.path.isabs(t) else None for t in first]
        if obj.is_file() and any(s is not None and is_gpl_file(s) for s in srcs):
            gpl_objs.append(obj)
    symbols = defined_symbols(gpl_objs)
    if GPL_MODS and gpl_dirs():
        assert symbols, "GPL directories exist, but no object of the switch-on build is from one"
    leaked = symbols & defined_symbols([off["render"], off["sim"]])
    assert not leaked, sorted(leaked)[:20]


def test_the_mit_build_lists_no_gpl_module(off):
    for name, entries in (("fm1-render --list", listing(off)), ("the catalogue", catalogue(off))):
        gpl = [i for i, e in entries.items() if is_gpl(e["licence"])]
        assert not gpl, f"{name} of the switch-off build lists {gpl}"
    assert not any(e["gpl"] for e in catalogue(off).values())


def test_the_gate_and_the_licence_table_agree(on, off):
    """What the switch leaves out is exactly what the table calls GPL; the
    rest is the same in both builds, licences included."""
    a, b = listing(on), listing(off)
    assert set(b) <= set(a)
    assert {i for i in a if i not in b} == {i for i, e in a.items() if is_gpl(e["licence"])}
    for i, e in b.items():
        assert (e["licence"], e["source"]) == (a[i]["licence"], a[i]["source"]), i
    cat = catalogue(on)
    assert set(cat) == set(a)
    for i, e in cat.items():
        assert (e["licence"], e["source"], e["gpl"]) == (a[i]["licence"], a[i]["source"],
                                                         is_gpl(a[i]["licence"])), i


# ---- The licence table and the vendored directories -----------------------------------------

def test_every_licence_row_names_a_module_and_its_code(on):
    entries = listing(on)
    ids = [e["id"] for e in json.loads(call(on["render"], "--list"))]
    assert len(ids) == len(set(ids)), "an engine and a MIDI effect share an id"
    for i, e in entries.items():
        assert e["licence"] and re.fullmatch(r"[A-Za-z0-9.+-]+(?: (?:AND|OR|WITH) [A-Za-z0-9.+-]+)*",
                                             e["licence"]), (i, e["licence"])
        if e["licence"] == "MIT":
            assert e["source"] is None, i
            continue
        assert e["source"] and (ROOT / e["source"]).is_dir(), (i, e["source"])
        if is_gpl(e["licence"]):
            assert (ROOT / e["source"]).resolve() in [d.resolve() for d in gpl_dirs()], i


def test_every_gpl_directory_has_its_licence_and_upstream():
    for d in gpl_dirs():
        assert (d / "UPSTREAM.md").is_file(), d
        upstream = (d / "UPSTREAM.md").read_text()
        assert re.search(r"\b[0-9a-f]{7,40}\b", upstream), f"{d}/UPSTREAM.md names no commit"
        assert "GPL" in upstream, f"{d}/UPSTREAM.md does not name its licence"


# ---- The page ---------------------------------------------------------------------------------

def test_the_page_can_offer_the_module_under_the_gpl():
    www = SIM / "www"
    html = (www / "index.html").read_text(encoding="utf-8")
    assert re.search(r'<p class="licence-note" id="licence-note" hidden></p>', html)
    app = (www / "app.js").read_text(encoding="utf-8")
    assert "licences/GPL-3.0.txt" in app and "fm1.wasm.json" in app and "source.json" in app
    source = json.loads((www / "source.json").read_text(encoding="utf-8"))
    assert source["repository"].startswith("https://github.com/") and source["commit"] is None
    text = (www / "licences" / "GPL-3.0.txt").read_bytes()
    assert hashlib.sha256(text).hexdigest() == GPL3_SHA256


def test_the_build_record_names_the_switch_and_the_licences(on):
    """sim/web/build.sh records the switch the module was built with and every
    module whose code is not all MIT. While the record's engine sources are
    this tree's, its list is this tree's switch-on build's."""
    record = json.loads((SIM / "www" / "fm1.wasm.json").read_text(encoding="utf-8"))
    assert record["gpl_mods"] == 1, "the published module is built with the switch on (owner, 2026-10-05)"
    want = [{"id": e["id"], "name": e["name"], "kind": e["kind"], "licence": e["licence"],
             "source": e["source"]} for e in json.loads(call(on["render"], "--list"))
            if e["licence"] != "MIT"]
    res = subprocess.run(["python3", str(SIM / "tools" / "source_hash.py"), str(ROOT)],
                         check=True, capture_output=True, text=True)
    if json.loads(res.stdout)["engines"] != record["sources_sha256"]["engines"]:
        warnings.warn("www/fm1.wasm was built from other engine sources; its licence list is not checked")
        return
    assert record["licences"] == want


def test_gpl_scenarios_say_so(on):
    """A parity scenario that plays a GPL module is marked "gpl", and only such
    a scenario, so the switch-off build skips exactly those."""
    entries = listing(on)
    gpl = {i for i, e in entries.items() if is_gpl(e["licence"])}
    scenarios = json.loads((SIM / "test" / "scenarios.json").read_text(encoding="utf-8"))["scenarios"]
    for s in scenarios:
        used = {s["engine"]} | {fx for fx, _ in s.get("fx", [])}
        used |= {m for _, m, _ in s.get("mfx", [])} | {i for _, i, _ in s.get("sounds", [])}
        used |= {i for _, i, _ in s.get("inserts", [])}
        assert bool(used & gpl) == bool(s.get("gpl")), s["name"]
