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

import pytest

from tests.engine_helpers import ROOT, pitch_hz

SIM = ROOT / "sim" / "web"
ENGINES = ROOT / "engines"
SCENARIOS = json.loads((SIM / "test" / "scenarios.json").read_text())["scenarios"]


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


def test_every_screen_passes_the_layout_check(tools, tmp_path):
    """Every page of every engine and effect, at defaults, minima, maxima and
    each list entry, the global page and every popup: no text off screen, and
    no two labels, or a label and a bar, closer than 2 px."""
    res = subprocess.run([str(tools["sim"]), "--screens", str(tmp_path)],
                         capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    summary = json.loads(res.stdout)
    assert summary["faults"] == 0
    assert summary["screens"] >= 200
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


def test_page_is_self_contained():
    """No CDN, no fonts, nothing fetched from another origin: the page works
    from a local static server and can be published as static files."""
    www = SIM / "www"
    for f in www.iterdir():
        if f.suffix in (".html", ".js", ".mjs", ".css"):
            # The SVG namespace is an identifier, never fetched.
            text = f.read_text().replace("http://www.w3.org/2000/svg", "")
            assert not re.search(r"(https?:)?//[a-z0-9.-]+\.[a-z]{2,}/", text, re.I), f.name
    html = (www / "index.html").read_text()
    for ref in re.findall(r'(?:src|href)="([^"#]+)"', html):
        assert (www / ref).exists(), ref
    for name in ("worklet.js", "fm1-wasm.mjs", "fm1.wasm"):
        assert (www / name).exists(), name


def test_wasm_exports_match_the_web_layer():
    exported = set(re.findall(r"^\S.*?\b(fm1w_\w+)\(", (SIM / "src" / "fm1_web.c").read_text(), re.M))
    mk = (SIM / "mk" / "sim.mk").read_text()
    listed = set(re.findall(r"\bfm1w_\w+", mk.split("WASM_EXPORTS :=")[1].split("comma")[0]))
    assert exported == listed


def test_committed_wasm_matches_its_build_record():
    """build-on-aeon.sh writes fm1.wasm.json next to the module: its hash, the
    hash of the sources it was built from, and the parity results."""
    record = json.loads((SIM / "www" / "fm1.wasm.json").read_text())
    wasm = (SIM / "www" / "fm1.wasm").read_bytes()
    assert hashlib.sha256(wasm).hexdigest() == record["wasm_sha256"]
    parity = record["parity"]
    assert parity["failed"] == 0 and parity["passed"] >= len(SCENARIOS)
    assert record["imports"] == []
    current = source_hash()
    if current != record["sources_sha256"]:
        warnings.warn("sim/web/www/fm1.wasm was built from other sources than these; "
                      "rebuild with sim/web/build-on-aeon.sh")


def source_hash():
    """The hash build-on-aeon.sh records (sim/web/tools/source_hash.py)."""
    res = subprocess.run(["python3", str(SIM / "tools" / "source_hash.py"), str(ROOT)],
                         check=True, capture_output=True, text=True)
    return res.stdout.strip()
