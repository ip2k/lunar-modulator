"""The virtual FM-1 (sim/web): its app layer renders what fm1-render renders,
every screen passes the layout check, the panel follows the M-VAVE manual,
and the page is self-contained.

The WebAssembly side is built and compared on aeon by sim/web/build-on-aeon.sh
(test/parity.mjs); its results are recorded in sim/web/www/fm1.wasm.json,
which the last tests here read.

Set FM1_SIM_EXTRA (and FM1_SIM_CC / FM1_SIM_CXX / FM1_SIM_OPT) to build the
harness with other flags, e.g. the ASan + UBSan set from engines/README.md;
that build goes to its own directory.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import warnings
from urllib.parse import unquote

import pytest

from tests.engine_helpers import ROOT, pitch_hz

SIM = ROOT / "sim" / "web"
ENGINES = ROOT / "engines"
SCENARIOS = json.loads((SIM / "test" / "scenarios.json").read_text(encoding="utf-8"))["scenarios"]


@pytest.fixture(scope="session")
def tools():
    if not shutil.which("make") or not (shutil.which("c++") or shutil.which("g++")):
        pytest.skip("no make / C++ compiler")
    extra = os.environ.get("FM1_SIM_EXTRA", "")
    flags = {
        "EXTRA": extra,
        "OPT": os.environ.get("FM1_SIM_OPT", "-O2"),
        "CC": os.environ.get("FM1_SIM_CC", "cc"),
        "CXX": os.environ.get("FM1_SIM_CXX", "c++"),
    }
    tag = hashlib.sha256(json.dumps(flags, sort_keys=True).encode()).hexdigest()[:8]
    build = SIM / "build" / ("native" if not extra and flags["OPT"] == "-O2" else f"native-{tag}")
    targets = [build / "fm1-render", build / "fm1-sim-render"]
    subprocess.run(
        ["make", "-C", str(ENGINES), "-f", "Makefile", "-f", str(SIM / "mk" / "sim.mk"),
         f"SIM={SIM}", f"BUILD={build}", "-j4"]
        + [f"{k}={v}" for k, v in flags.items()] + [str(t) for t in targets],
        check=True, stdout=subprocess.DEVNULL)
    return {"render": targets[0], "sim": targets[1]}


def scenario_args(s):
    args = ["--seconds", str(s["seconds"]), "--rate", str(s.get("rate", 44118))]
    args += ["--engine", s["engine"]]
    for p in s.get("params", []):
        args += ["--param", p]
    for n in s.get("notes", []):
        args += ["--note", n]
    for b in s.get("bends", []):
        args += ["--bend", b]
    for p in s.get("param_at", []):
        args += ["--param-at", p]
    for fx_id, fx_params in s.get("fx", []):
        args += ["--fx", fx_id]
        for p in fx_params:
            args += ["--fx-param", p]
    return args


def run(tool, args):
    res = subprocess.run([str(tool), *args], check=True, capture_output=True, text=True)
    return json.loads(res.stdout.strip().splitlines()[-1])


def left_channel(wav_bytes):
    data = wav_bytes[44:]
    return [int.from_bytes(data[i:i + 2], "little", signed=True) / 32767.0
            for i in range(0, len(data), 4)]


@pytest.mark.parametrize("s", SCENARIOS, ids=[s["name"] for s in SCENARIOS])
def test_app_renders_what_fm1_render_renders(tools, tmp_path, s):
    """Same engines, same events at the same block boundaries, same bus
    limiter: with MASTER at full gain the app's WAV is fm1-render's, byte for
    byte. The browser runs this layer; parity.mjs checks the WebAssembly build
    of it against fm1-render on aeon."""
    ref, app = tmp_path / "ref.wav", tmp_path / "app.wav"
    run(tools["render"], scenario_args(s) + ["--out", str(ref)])
    summary = run(tools["sim"], scenario_args(s) + ["--out", str(app)])
    assert summary["engine"] == s["engine"]
    assert app.read_bytes() == ref.read_bytes()
    assert summary["peak"] > 0.01, "the scenario makes no sound"


def test_scenarios_cover_every_engine_effect_and_page(tools):
    """scenarios.json promises that every engine and effect appears at least
    once, so parity.mjs checks each in the browser's module. A sound engine's
    page past the first is covered when some scenario sets one of its
    parameters (Macro's page 3, the envelope and gate, needs a scenario that
    moves it)."""
    res = subprocess.run([str(tools["render"]), "--list"], check=True,
                         capture_output=True, text=True)
    catalog = json.loads(res.stdout)
    used = {s["engine"] for s in SCENARIOS} | {fx for s in SCENARIOS for fx, _ in s.get("fx", [])}
    missing = sorted(e["id"] for e in catalog if e["id"] not in used)
    assert not missing, f"no parity scenario uses {missing}"
    set_names = {}
    for s in SCENARIOS:
        names = set_names.setdefault(s["engine"], set())
        for p in s.get("params", []) + [p.split(":", 1)[1] for p in s.get("param_at", [])]:
            names.add(p.split("=", 1)[0])
    for e in catalog:
        if e["kind"] != "sound" or e["id"] not in ("macro", "macro-heavy"):
            continue
        last_page = max(p["page"] for p in e["params"])
        on_last = {p["name"] for p in e["params"] if p["page"] == last_page}
        assert on_last & set_names.get(e["id"], set()), \
            f"no scenario sets a parameter on {e['id']}'s page {last_page + 1}"


def test_every_screen_passes_the_layout_check(tools, tmp_path):
    """Every page of every engine and effect, at defaults, minima, maxima and
    each list entry, the global page and every popup (the refusals, SEL
    outside FX mode and an emptied slot included): no text off screen or cut
    short, and no two labels, or a label and a bar, closer than 4 px
    (FM1_APP_LAYOUT_GAP)."""
    res = subprocess.run([str(tools["sim"]), "--screens", str(tmp_path)],
                         capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    summary = json.loads(res.stdout)
    assert summary["faults"] == 0
    assert summary["screens"] >= 280
    assert (tmp_path / "home-macro-p1.ppm").stat().st_size == 15 + 240 * 240 * 3


def test_font_header_is_current():
    subprocess.run(["python3", str(SIM / "tools" / "gen_font.py"), "--check"], check=True)


@pytest.mark.parametrize("panel,note", [
    ([], 53),                                             # key 0 is F3 (manual p.10)
    (["--button", "0:OCT+"], 65),                         # one octave up
    (["--button", "0:OCT-", "--button", "0.05:OCT-"], 29),
    (["--button", "0:OCT+:0.2", "--turn", "0.1:ALGORITHM:3"], 68),   # OCT+ held: transpose
    (["--button", "0:OCT+", "--button", "0.05:OCT+:0.2", "--button", "0.1:OCT-"], 53),  # both: reset
])
def test_panel_keys_follow_the_manual(tools, tmp_path, panel, note):
    """note = key position + 53 + 12 x octave + transpose; OCT-/OCT+ shift an
    octave, ALGORITHM with an OCT button held transposes, both buttons reset."""
    wav = tmp_path / "k.wav"
    summary = run(tools["sim"], ["--engine", "test-sine", "--seconds", "1.0", "--out", str(wav),
                                 "--key", "0.3:0:100:0.6", *panel])
    expected = 440.0 * 2 ** ((note - 69) / 12)
    assert pitch_hz(left_channel(wav.read_bytes()), 0.5, 0.3) == pytest.approx(expected, rel=0.003)
    assert summary["sounding"] == 0


def test_buttons_and_encoders(tools, tmp_path):
    """PRESETS steps the sound, FX mode and ALGORITHM pick the effect in the
    selected slot, SELECT moves to slot 2, KNOB1 turns a parameter there."""
    s = run(tools["sim"], ["--engine", "macro", "--seconds", "0.2",
                           "--turn", "0:PRESETS:1",
                           "--button", "0:FX", "--turn", "0.01:ALGORITHM:1",
                           "--turn", "0.02:SELECT:1", "--turn", "0.03:ALGORITHM:2",
                           "--turn", "0.04:KNOB1:10"])
    assert s["engine"] == "shapes"
    assert s["mode"] == 1
    assert s["fx"] == ["plate", "ensemble"]
    assert s["values2"][0] == pytest.approx(0.6)          # Ensemble Mix 0.5 + 10 x 0.01
    assert s["leds"][27 + 2] == "1"                       # the FX LED
    g = run(tools["sim"], ["--engine", "macro", "--seconds", "0.2", "--button", "0:GLO",
                           "--turn", "0.01:ALGORITHM:3"])
    assert g["mode"] == 2 and g["values0"][0] == 3        # GLO page; ALGORITHM = Model


def test_emptying_a_slot_returns_to_its_one_page(tools):
    """The Effect 2 dropdown's "(none)" on PSX Verb's second page: the empty
    slot shows page 1 of 1, not "2/1" (the select path used to keep the page)."""
    s = run(tools["sim"], ["--engine", "macro", "--fx", "plate", "--fx", "sw-psxverb",
                           "--seconds", "0.1", "--button", "0:FX", "--turn", "0.01:SELECT:2",
                           "--select", "0.03:2:-"])
    assert s["fx"] == ["plate", ""]
    assert (s["fx_slot"], s["fx_page"]) == (1, 0)


def test_a_sound_that_refuses_the_rate_is_stepped_over(tools):
    """Above 47,872 Hz the Plaits-based sounds (Macro, Macro Heavy, Six-Op)
    refuse the host. PRESETS steps over them and says why; a refused load
    puts the previous sound back with its values instead of leaving silence."""
    up = run(tools["sim"], ["--engine", "shapes", "--rate", "48000", "--seconds", "0.1",
                            "--turn", "0:PRESETS:1"])
    assert up["engine"] == "sw-sophie"
    assert up["popup"] == ["Macro Heavy", "refuses 48000 Hz"]
    down = run(tools["sim"], ["--engine", "shapes", "--rate", "48000", "--seconds", "0.1",
                              "--turn", "0:PRESETS:-1"])
    assert down["engine"] == "test-sine"
    kept = run(tools["sim"], ["--engine", "shapes", "--param", "Timbre=0.8", "--rate", "48000",
                              "--seconds", "0.3", "--select", "0.1:0:macro",
                              "--key", "0.15:0:100:0.1"])
    assert kept["engine"] == "shapes"
    assert kept["values0"][1] == pytest.approx(0.8)
    assert kept["peak"] > 0.01
    at_plaits_rate = run(tools["sim"], ["--engine", "shapes", "--rate", "47872", "--seconds", "0.1",
                                        "--turn", "0:PRESETS:1"])
    assert at_plaits_rate["engine"] == "macro-heavy"


def test_page_is_self_contained():
    """No CDN, nothing fetched from another origin, every reference relative:
    the page works from a local static server and can be published as static
    files, at any path, over http://localhost or https. Its fonts are its own
    files (fonts/)."""
    www = SIM / "www"
    for f in www.iterdir():
        if f.suffix in (".html", ".js", ".mjs", ".css"):
            # The SVG namespace is an identifier, never fetched.
            text = f.read_text(encoding="utf-8").replace("http://www.w3.org/2000/svg", "")
            assert not re.search(r"(https?:)?//[a-z0-9.-]+\.[a-z]{2,}/", text, re.I), f.name
    html = (www / "index.html").read_text(encoding="utf-8")
    refs = re.findall(r'(?:src|href)="([^"#]+)"', html)
    css = (www / "style.css").read_text(encoding="utf-8")
    refs += re.findall(r'url\("?([^")]+)"?\)', css)
    for ref in refs:
        assert not ref.startswith("/"), f"{ref} is not relative"
        assert (www / unquote(ref)).is_file(), ref   # browsers percent-decode: Exo2%5Bwght%5D.ttf
    for name in ("worklet.js", "fm1-wasm.mjs", "fm1.wasm"):
        assert (www / name).exists(), name
    # The worklet and the module are found next to app.js, wherever it is.
    app = (www / "app.js").read_text(encoding="utf-8")
    assert "new URL(name, import.meta.url)" in app
    assert "addModule(asset('worklet.js'))" in app and "fetch(asset('fm1.wasm'))" in app


# Git blob hashes of google/fonts' ofl/audiowide files (main, 2026-10-01):
# the font must stay unmodified, since a subset or any other change is a
# Modified Version that the SIL OFL's Reserved Font Name clause forbids
# calling "Audiowide".
FONTS = {
    "audiowide/Audiowide-Regular.ttf": "8b50bedc0f99bcfcb5686a3dbeb5b51d1c0190d5",
    "audiowide/OFL.txt": "19bb4adffab57778a892f98e9552441208896226",
    "exo2/Exo2[wght].ttf": "9cb20188a07687580312d2099e6c79ca8ecb7b58",
    "exo2/OFL.txt": "5bec9840d2e0df42d80d6fac55279d1d5e5b9199",
}


def test_fonts_are_unmodified_and_licensed():
    fonts = SIM / "www" / "fonts"
    for rel, blob in FONTS.items():
        data = (fonts / rel).read_bytes()
        assert hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest() == blob, rel
    for font in fonts.rglob("*.ttf"):
        assert (font.parent / "OFL.txt").is_file(), font
        assert str(font.relative_to(fonts)) in FONTS, f"{font} has no recorded hash"


def test_wasm_exports_match_the_web_layer():
    exported = set(re.findall(r"^\S.*?\b(fm1w_\w+)\(", (SIM / "src" / "fm1_web.c").read_text(encoding="utf-8"), re.M))
    mk = (SIM / "mk" / "sim.mk").read_text(encoding="utf-8")
    listed = set(re.findall(r"\bfm1w_\w+", mk.split("WASM_EXPORTS :=")[1].split("comma")[0]))
    assert exported == listed


def test_committed_wasm_matches_its_build_record():
    """build-on-aeon.sh writes fm1.wasm.json next to the module: its hash, the
    hashes of the sources it was built from, and the parity results.

    When sim/web's own inputs (src/, mk/, build.sh, the parity test) have
    changed since, the module is stale: a warning locally, a failure in CI
    (CI=true), so a pull request that changes the simulator carries its
    rebuilt module. When only engines/ has changed, CI warns too: engine
    work elsewhere should not need aeon, but rebuild before the module is
    published."""
    record = json.loads((SIM / "www" / "fm1.wasm.json").read_text(encoding="utf-8"))
    wasm = (SIM / "www" / "fm1.wasm").read_bytes()
    assert hashlib.sha256(wasm).hexdigest() == record["wasm_sha256"]
    parity = record["parity"]
    assert parity["failed"] == 0 and parity["passed"] >= len(SCENARIOS)
    assert record["imports"] == []
    assert all("@sha256:" in i for i in record["images"]) and len(record["images"]) >= 2
    current = source_hashes()
    stale = [k for k in ("engines", "sim") if current[k] != record["sources_sha256"].get(k)]
    if "sim" in stale and os.environ.get("CI") == "true":
        pytest.fail("sim/web changed since www/fm1.wasm was built; rebuild it with "
                    "sim/web/build-on-aeon.sh and commit www/fm1.wasm and fm1.wasm.json")
    if stale:
        warnings.warn(f"sim/web/www/fm1.wasm was built from other {' and '.join(stale)} "
                      "sources than these; rebuild with sim/web/build-on-aeon.sh")


def source_hashes():
    """The hashes build-on-aeon.sh records (sim/web/tools/source_hash.py)."""
    res = subprocess.run(["python3", str(SIM / "tools" / "source_hash.py"), str(ROOT)],
                         check=True, capture_output=True, text=True)
    return json.loads(res.stdout)
