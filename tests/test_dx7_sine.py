"""The DX7 sine switch, FM1_DX7_SINE=msfa|trunc12 (engines/Makefile;
engines/msfa.md, "The trunc12 sine").

msfa (the default) keeps msfa's interpolated 1,024-point sine. trunc12 reads
a 4,096-point Q15 table with the phase's top 12 bits and no interpolation,
like the DX7's own sine ROM, and is compiled in place of msfa's Sin::lookup
from a staged copy of msfa (mk/msfa.mk). These tests hold:

  - the generated table and header to tools/msfa_tables.py and the vendored
    sin.h;
  - the switch to building what it says, rebuilding when it turns, refusing
    other values, and refusing a mismatched sin.h at compile time;
  - trunc12's signal-to-error ratio to at least 50 dB against frequency
    modulation in doubles (fm1-dx7-sine-oracle) wherever the modulation
    index is one cycle or less, and in feedback; msfa's to at least 80 dB
    everywhere; heavier modulation is reported, not gated (engines/msfa.md);
  - trunc12 replays with no non-finite sample and nothing clipped, through
    the dev kit's renderer replay (with and without ASan/UBSan) and every
    built-in voice;
  - msfa's internal consistency checks (copied kernels, the voice budget,
    the paired kernels) pass with trunc12 too.

trunc12 builds go to engines/build/dx7-trunc12 and the replay's to
sim/web/build/, both ignored; the default build is not touched.
"""
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import wave
from pathlib import Path

import pytest

from tests.engine_helpers import ENGINES, GPL_MODS, RATE, ROOT, renderer  # noqa: F401

TOOLS = ROOT / "tools" / "msfa_tables.py"
TRUNC_BUILD = ENGINES / "build" / "dx7-trunc12"
MODULES = "dx7,macro,drums,filter,drive,echo,comp,arp,lfo,env,chance"


def tables_module():
    spec = importlib.util.spec_from_file_location("msfa_tables", TOOLS)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def make_engines(build, sine, *targets):
    subprocess.run(["make", "-s", "-C", str(ENGINES), "-j4", f"BUILD={build}",
                    f"FM1_DX7_SINE={sine}", *targets],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


@pytest.fixture(scope="module")
def trunc12():
    if not shutil.which("make") or not (shutil.which("c++") or shutil.which("g++")):
        pytest.skip("no make / C++ compiler")
    make_engines(TRUNC_BUILD, "trunc12")
    return TRUNC_BUILD


def oracle(build):
    out = subprocess.run([str(build / "fm1-dx7-sine-oracle")], check=True,
                         capture_output=True, text=True, timeout=120).stdout
    return json.loads(out)


# ------------------------------------------------------------ the tables --

def test_generated_files_are_current():
    """msfa_rom.cc (both tables) and msfa_sin_trunc12.h are what the
    generator makes from the vendored sin.h."""
    r = subprocess.run([sys.executable, str(TOOLS), "--check"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_trunc12_header_keeps_the_vendored_head():
    """Everything before msfa's table declaration is the vendored text; only
    the notice is added and the tail replaced."""
    m = tables_module()
    vendored = m.SIN_H.read_text()
    header = m.OUT_SIN12.read_text()
    assert header.endswith(m.SIN12_TAIL)
    head = vendored[: vendored.index(m.SIN_H_TAIL)]
    assert header.replace(m.SIN12_NOTICE, "", 1) == head + m.SIN12_TAIL
    assert "Copyright 2012 Google Inc." in header and "Apache License" in header


def test_trunc12_table_shape():
    """4,096 Q15 points at the middles of their steps: odd about the half
    cycle, symmetric about each quarter, peak 32,767 and never past it."""
    t = tables_module().sin12_table()
    assert len(t) == 4096
    assert all(t[i] == -t[4095 - i] for i in range(4096))
    assert all(t[i] == t[2047 - i] for i in range(2048))
    assert max(t) == 32767 and min(t) == -32767
    assert t[0] == 25 and t[1023] == t[1024] == 32767
    src = (ENGINES / "src" / "msfa_rom.cc").read_text()
    body = src[src.index("kSinTab12[4096] = {"):]
    body = body[body.index("{") + 1: body.index("}")]
    assert [int(x) for x in re.findall(r"-?\d+", body)] == t


# ------------------------------------------------------------ the switch --

def test_build_info_names_the_sine(renderer, trunc12):  # noqa: F811
    info = json.loads(subprocess.run([str(renderer), "--build-info"], check=True,
                                     capture_output=True, text=True).stdout)
    assert info["dx7_sine"] == "msfa"
    info = json.loads(subprocess.run([str(trunc12 / "fm1-render"), "--build-info"], check=True,
                                     capture_output=True, text=True).stdout)
    assert info["dx7_sine"] == "trunc12" and info["gpl_mods"] == int(GPL_MODS)
    assert (trunc12 / "gen" / "msfa-trunc12" / "sin.h").read_text() == \
        (ENGINES / "src" / "msfa_sin_trunc12.h").read_text()


def test_only_one_sine_table_is_linked(renderer, trunc12):  # noqa: F811
    """The switch is flash-neutral in kind: each build links one table."""
    nm = shutil.which("nm")
    if not nm:
        pytest.skip("no nm")

    def syms(path):
        return subprocess.run([nm, "-C", str(path)], check=True, capture_output=True,
                              text=True).stdout
    msfa, t12 = syms(renderer), syms(trunc12 / "fm1-render")
    assert "kSinTab12" not in msfa and re.search(r"\bkSinTab\b", msfa)
    assert "kSinTab12" in t12 and not re.search(r"\bkSinTab\b(?!12)", t12)


def test_switch_turning_rebuilds(tmp_path):
    """One build directory, the switch turned twice: build-info follows."""
    if not shutil.which("make"):
        pytest.skip("no make")
    build = tmp_path / "flip"
    for sine in ("trunc12", "msfa", "trunc12"):
        make_engines(build, sine, str(build / "fm1-render"))
        info = json.loads(subprocess.run([str(build / "fm1-render"), "--build-info"], check=True,
                                         capture_output=True, text=True).stdout)
        assert info["dx7_sine"] == sine


def test_switch_refuses_other_values():
    r = subprocess.run(["make", "-s", "-C", str(ENGINES), "-n", "FM1_DX7_SINE=lerp"],
                       capture_output=True, text=True)
    assert r.returncode != 0 and "FM1_DX7_SINE is msfa or trunc12" in r.stderr


@pytest.mark.parametrize("define,msfa_dir,error", [
    ("-DFM1_DX7_SINE_TRUNC12=1", "vendored", "msfa's own sin.h was included"),
    ("", "staged", "the trunc12 sin.h was included"),
    ("", "vendored", None),
    ("-DFM1_DX7_SINE_TRUNC12=1", "staged", None),
])
def test_mismatched_sin_h_does_not_compile(tmp_path, trunc12, define, msfa_dir, error):
    """src/msfa.h stops a build whose switch and sin.h disagree."""
    cxx = shutil.which("c++") or shutil.which("g++")
    src = tmp_path / "probe.cc"
    src.write_text('#include "msfa.h"\n')
    d = ENGINES / "third_party" / "msfa" if msfa_dir == "vendored" else \
        trunc12 / "gen" / "msfa-trunc12"
    cmd = [cxx, "-std=c++11", "-fsyntax-only", f"-I{ENGINES / 'src'}", f"-I{ENGINES / 'include'}",
           "-isystem", str(d), str(src)] + ([define] if define else [])
    r = subprocess.run(cmd, capture_output=True, text=True)
    if error:
        assert r.returncode != 0 and error in r.stderr
    else:
        assert r.returncode == 0, r.stderr


# ------------------------------------------------------- signal to error --

INDEX_LE_1 = ("pure 110", "pure 440", "pure 1760.3", "pure 7040", "1:1 idx0.25 220",
              "tine 1:14 idx0.05 523", "1:3.5 idx0.5 110", "1:1 idx1 220",
              "3-op 1:2:3 330", "3-op 1:1:7 svar 196")
HEAVY = ("1:2 idx2 110", "1:1 idx4 55")


def test_msfa_sine_snr(renderer):  # noqa: F811
    r = oracle(ENGINES / "build")
    assert r["dx7_sine"] == "msfa"
    snr = {s["name"]: s["snr_db"] for s in r["stacks"]}
    assert set(snr) == set(INDEX_LE_1 + HEAVY)
    assert min(snr.values()) >= 80, snr
    assert min(f["snr_db"] for f in r["feedback"]) >= 95, r["feedback"]
    assert r["lookup"]["peak"] <= 1 << 24 and r["lookup"]["max_err_db"] <= -100


def test_trunc12_sine_snr(renderer, trunc12):  # noqa: F811
    """At least 50 dB wherever the modulation index is a cycle or less, and in
    feedback; the heavy cases are held only above 40 dB (their error grows
    about 6 dB per doubling of the index; engines/msfa.md). Every case falls
    well below msfa's, which shows the kernels really switched."""
    r, ref = oracle(trunc12), oracle(ENGINES / "build")
    assert r["dx7_sine"] == "trunc12"
    snr = {s["name"]: s["snr_db"] for s in r["stacks"]}
    msfa = {s["name"]: s["snr_db"] for s in ref["stacks"]}
    for name in INDEX_LE_1:
        assert snr[name] >= 50, (name, snr[name])
    for name in HEAVY:
        assert snr[name] >= 40, (name, snr[name])
    for name in snr:
        assert snr[name] <= msfa[name] - 20, (name, snr[name], msfa[name])
    assert all(f["snr_db"] >= 50 for f in r["feedback"]), r["feedback"]
    assert min(snr[n] for n in INDEX_LE_1 if n.startswith("pure")) >= 65
    assert r["lookup"]["peak"] <= 1 << 24 and r["lookup"]["max_err_db"] <= -60


# ------------------------------------------------------------- replays --

def test_msfa_consistency_checks_pass_with_trunc12(trunc12):
    """The copied kernels, the voice budget and the paired kernels compare
    the engine with itself: they must hold whichever sine it reads."""
    for rate in (16385, 44118, 96000):
        for mode in range(4):
            out = subprocess.run([str(trunc12 / "fm1-dx7-kernel-test"), str(rate), str(mode)],
                                 check=True, capture_output=True, text=True, timeout=60).stdout
            assert out.startswith("PASS exact PCM"), out
        out = subprocess.run([str(trunc12 / "fm1-dx7-budget-test"), str(rate)],
                             check=True, capture_output=True, text=True, timeout=30).stdout
        assert out.startswith("PASS default12 exact PCM"), out
    out = subprocess.run([str(trunc12 / "fm1-dx7-pair-test")], check=True,
                         capture_output=True, text=True, timeout=60).stdout
    assert out.startswith("PASS"), out
    r = subprocess.run([str(trunc12 / "fm1-dx7-oracle"), "--tables-vs-msfa"],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr


@pytest.mark.parametrize("patch", range(32))
def test_every_builtin_voice_with_trunc12(trunc12, tmp_path, patch):
    """A chord of each built-in voice at full velocity: finite, audible and
    under full scale before the limiter."""
    wav = tmp_path / "v.wav"
    out = subprocess.run([str(trunc12 / "fm1-render"), "--engine", "dx7", "--param",
                          f"Patch={patch}", "--note", "0:48:127:0.6", "--note", "0:55:127:0.6",
                          "--note", "0:64:127:0.6", "--seconds", "2.0", "--out", str(wav)],
                         check=True, capture_output=True, text=True).stdout
    s = json.loads(out)
    assert s["nonfinite"] == 0 and s["raw_clipped"] == 0, (patch, s)
    assert s["raw_peak"] > 0.01, (patch, s)
    with wave.open(str(wav), "rb") as w:
        assert w.getframerate() == RATE


@pytest.mark.parametrize("sanitize", [False, True], ids=["plain", "asan-ubsan"])
def test_devkit_renderer_replay_with_trunc12(tmp_path, sanitize):
    """The dev kit's renderer replay (firmware/devkit/renderer_reference.c),
    built with trunc12: eight runs of the four workloads, no non-finite
    sample (invalid) and nothing past int16 (clipped) in any; reproducible."""
    cc = os.environ.get("FM1_SIM_CC", "cc")
    cxx = os.environ.get("FM1_SIM_CXX", "c++")
    if not shutil.which("make") or not shutil.which(cxx):
        pytest.skip("native toolchain unavailable")
    extra = os.environ.get("FM1_SIM_EXTRA", "") + " -DFM1_APP_EXTERNAL_ARENAS=1"
    if sanitize:
        extra += " -fsanitize=address,undefined -fno-sanitize=shift -fno-omit-frame-pointer"
    tag = hashlib.sha256((cc + cxx + extra + MODULES + "trunc12").encode()).hexdigest()[:12]
    build = ROOT / "sim/web/build" / f"devkit-renderer-trunc12-{tag}"
    target = build / "fm1-devkit-renderer-ref"
    subprocess.run([
        "make", "-s", "-C", str(ENGINES), "-f", "Makefile", "-f",
        str(ROOT / "sim/web/mk/sim.mk"), "-f", str(ROOT / "tools/jieli/renderer.mk"),
        f"SIM={ROOT / 'sim/web'}", f"BUILD={build}", "FM1_GPL_MODS=0", "FM1_DX7_SINE=trunc12",
        f"FM1_MODULES={MODULES}", f"CC={cc}", f"CXX={cxx}", f"EXTRA={extra}",
        "-j4", str(target),
    ], check=True, stdout=subprocess.DEVNULL)
    assert (build / "gen" / "fm1_dx7_sine.h").read_text().startswith("#define FM1_DX7_SINE_TRUNC12 1")
    env = dict(os.environ, ASAN_OPTIONS="halt_on_error=1", UBSAN_OPTIONS="halt_on_error=1")
    pcm = tmp_path / "trunc12.pcm"
    result = subprocess.run([str(target), str(pcm)], capture_output=True, text=True,
                            check=True, env=env, timeout=300)
    rows = [dict(re.findall(r"(\w+)=(\w+)", line)) for line in result.stdout.splitlines()]
    assert len(rows) == 8
    for i, row in enumerate(rows):
        assert int(row["completed"]) == i + 1
        assert row["invalid"] == row["clipped"] == "0", row
    assert pcm.stat().st_size == 8 * 5513 * 64 * 4
    if not sanitize:
        again = tmp_path / "again.pcm"
        replay = subprocess.run([str(target), str(again)], capture_output=True, text=True,
                                check=True, env=env, timeout=300)
        assert replay.stdout == result.stdout
        assert pcm.read_bytes() == again.read_bytes()


# -------------------------------------------------- dev-kit preparation --

def load_pipeline_prepare():
    spec = importlib.util.spec_from_file_location(
        "pipeline_prepare", ROOT / "tools/jieli/prepare-pipeline-devkit.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("sine", ["msfa", "trunc12"])
def test_pipeline_preparation_carries_the_sine(tmp_path, monkeypatch, sine):
    """The dev kit's pipeline image (synthetic SDK, offline, never hardware)
    builds its renderer with the chosen sine: the fragment passes the
    switch, the receipt names it, the msfa-only sine patches stay off with
    trunc12, and the table the build reads is the one placed in RAM."""
    from tests.test_prepare_pipeline_devkit import sdk_fixture
    module = load_pipeline_prepare()
    sdk, correction = sdk_fixture(tmp_path)
    monkeypatch.setattr(module, "ORIGINAL_SYSTEM_SHA256", module.sha256(sdk / module.SYSTEM))
    monkeypatch.setattr(module, "PIPELINE_SYSTEM_SHA256", module.sha256(correction))
    out = tmp_path / "prepared"
    module.prepare_pipeline(sdk, ROOT, out, correction, dx7_sine=sine)
    fragment = (out / "apps/demo/demo_hello/board/wl82/lunar-renderer.mk").read_text()
    assert fragment.count("FM1_DX7_SINE=") == 1 and f"FM1_DX7_SINE={sine} " in fragment
    receipt = json.loads((out / "lunar-devkit-input.json").read_text())
    assert receipt["dx7_sine"] == sine
    assert receipt["msfa_sine32"] == receipt["msfa_sine_pair"] == (sine == "msfa")
    assert receipt["msfa_narrow_adds"]
    staged = out / "lunar-source/engines"
    sin_h = (staged / "third_party/msfa/sin.h").read_bytes()
    vendored = (ENGINES / "third_party/msfa/sin.h").read_bytes()
    assert (sin_h == vendored) == (sine == "trunc12")
    assert set(receipt["msfa_narrow_adds_original_sha256"]) == \
        ({"fm_op_kernel.cc"} if sine == "trunc12" else {"sin.h", "fm_op_kernel.cc"})
    rom = (staged / "src/msfa_rom.cc").read_text()
    placed = '__attribute__((section(".lunar_cache_tables"))) = {'
    assert ("kSinTab12[4096] " + placed in rom) == (sine == "trunc12")
    assert ("kSinTab[2048] " + placed in rom) == (sine == "msfa")


def test_renderer_preparation_refuses_msfa_sine_patches_with_trunc12(tmp_path):
    spec = importlib.util.spec_from_file_location(
        "renderer_prepare", ROOT / "tools/jieli/prepare-renderer-devkit.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with pytest.raises(ValueError, match="trunc12 has none"):
        module.prepare_renderer(tmp_path, ROOT, tmp_path / "out", timing_only=True, hot_ram=True,
                                msfa_narrow_adds=True, msfa_sine32=True, dx7_sine="trunc12")
    with pytest.raises(ValueError, match="Unknown DX7 sine"):
        module.prepare_renderer(tmp_path, ROOT, tmp_path / "out", dx7_sine="lerp")
    with pytest.raises(ValueError, match="Unknown DX7 sine"):
        load_pipeline_prepare().renderer_preset("lerp")


def test_browser_firmware_and_dev_kit_share_the_default():
    """The owner's rule (2026-10-28): the browser plays what the firmware
    plays. The Makefile's default, the dev kit fragment's value and the
    checked-in module's record agree (a record older than the switch was
    built with msfa's sine, the only one there was)."""
    default = re.search(r"^FM1_DX7_SINE \?= (\w+)$", (ENGINES / "Makefile").read_text(), re.M)
    assert default and default[1] == "msfa"
    fragment = (ROOT / "tools/jieli/devkit-renderer-sdk.mk").read_text()
    assert re.findall(r"FM1_DX7_SINE=(\w+)", fragment) == [default[1]]
    record = json.loads((ROOT / "sim/web/www/fm1.wasm.json").read_text())
    assert record.get("dx7_sine", "msfa") == default[1]
