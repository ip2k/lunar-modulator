"""Tests for the Schwung v2 compatibility shim (engines/schwung.md, docs/11 §3)
and the two Schwung modules built through it: Sophie (sw-sophie, a sound
generator) and PSX Verb (sw-psxverb, an audio effect).

Renders through engines/build/fm1-render, and runs
engines/build/fm1-schwung-selftest for what a render cannot show: arena bounds
and exhaustion, re-blocking, MIDI and parameter-string encoding, and the
modules' own parameter contracts.
"""
import hashlib
import json
import re
import shutil
import subprocess
import wave

import pytest

from tests.engine_helpers import (ENGINES, RATE, cents, pitch_hz,  # noqa: F401
                                  render, renderer, rms)

SELFTEST = ENGINES / "build" / "fm1-schwung-selftest"
VENDORED = [ENGINES / "third_party" / "schwung",
            ENGINES / "third_party" / "schwung-modules" / "sophie",
            ENGINES / "third_party" / "schwung-modules" / "psxverb"]
BLOCK = 64                      # module block = the host's 64 frames
KICK_HZ = 440.0 * 2 ** ((36 - 69) / 12)
PSX_HEADROOM = 2.0              # sw_psxverb.cc: the bus goes in 6 dB down
# Twelve voices at full velocity, in phase: the bus goes above full scale.
CHORD = [f"0:{k}:127:0.5" for k in (48, 52, 55, 59, 60, 64, 67, 71, 72, 76, 79, 83)]
# Module names longer than the 12 characters a TFT label allows, and the
# fm1 table's short form. Every other fm1 name is the module's own.
SHORTENED = {"Ring Feedback": "Ring Fdbk"}
C_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


@pytest.fixture(scope="session")
def selftest_lines(renderer):
    # `make` in the renderer fixture builds the selftest too.
    res = subprocess.run([str(SELFTEST)], capture_output=True, text=True)
    return res.returncode, [json.loads(line) for line in res.stdout.splitlines() if line]


def contract(engine):
    out = subprocess.run([str(SELFTEST), "--contract", engine], check=True,
                         capture_output=True, text=True).stdout
    return json.loads(out)


def render_raw(renderer, tmp_path, args, name):
    """Render with arbitrary renderer arguments; returns (summary, left)."""
    wav = tmp_path / f"{name}.wav"
    res = subprocess.run([str(renderer), *args, "--out", str(wav)], check=True,
                         capture_output=True, text=True)
    with wave.open(str(wav), "rb") as w:
        raw = w.readframes(w.getnframes())
    left = [int.from_bytes(raw[i:i + 2], "little", signed=True) / 32767.0
            for i in range(0, len(raw), 4)]
    return json.loads(res.stdout), left, wav


def first_nonzero(samples):
    return next(i for i, x in enumerate(samples) if x != 0.0)


def nm_globals(text):
    """(undefined, defined) global symbols in `nm -g` output, leading
    underscores removed. Names that are not C identifiers cannot come from
    module code: they are compiler helpers, such as the PC thunks
    (`__x86.get_pc_thunk.bx`) that i386 GCC emits as global symbols in every
    PIE object. Sanitizer runtime symbols are left out too."""
    undefined, defined = set(), set()
    for line in text.splitlines():
        parts = line.split()
        if len(parts) not in (2, 3) or not C_IDENTIFIER.fullmatch(parts[-1]):
            continue
        name = parts[-1].lstrip("_")
        if name.startswith(("asan", "ubsan", "sanitizer")):   # instrumented builds
            continue
        if len(parts) == 2 and parts[0] == "U":
            undefined.add(name)
        elif len(parts) == 3:
            defined.add(name)
    return undefined, defined


# ------------------------------------------------------------ registry ---

def test_schwung_engines_are_registered(renderer):
    out = subprocess.run([str(renderer), "--list"], check=True,
                         capture_output=True, text=True).stdout
    engines = {e["id"]: e for e in json.loads(out)}
    sophie, psx = engines["sw-sophie"], engines["sw-psxverb"]
    assert (sophie["kind"], sophie["max_voices"]) == ("sound", 12)
    assert (psx["kind"], psx["max_voices"]) == ("audio_fx", 0)
    assert "Matt Estela" in sophie["credits"] and "MIT" in sophie["credits"]
    assert "Charles Vestal" in psx["credits"] and "MIT" in psx["credits"]
    for e in (sophie, psx):
        text = e["id"] + e["name"]
        for name in ("Plaits", "Braids", "Rings", "Clouds", "Elements", "Mutable"):
            assert name not in text
        assert all(len(p["name"]) <= 12 for p in e["params"])
        pages = [p["page"] for p in e["params"]]
        assert pages == sorted(pages)
        assert all(pages.count(page) <= 4 for page in set(pages))


# ------------------------------------------------------------ selftest ---

def test_selftest_passes(selftest_lines):
    code, lines = selftest_lines
    failed = [line for line in lines if line.get("ok") is False]
    assert code == 0 and not failed, failed
    assert lines[-1]["summary"]["failed"] == 0
    assert lines[-1]["summary"]["passed"] >= 24
    ran = {line["check"] for line in lines if "check" in line}
    assert {"module_init_once", "host_api_written_once", "other_rate_refused",
            "later_host_keeps_the_block", "fx_headroom_passes_overs",
            "number_parser_matches_libc"} <= ran


def test_modules_are_initialised_once(selftest_lines):
    # Module init functions rewrite their own static tables (PSX Verb memsets
    # the one every instance calls through), so a second create must not call
    # init again while the first instance may be rendering.
    _, lines = selftest_lines
    line = next(line for line in lines if line.get("check") == "module_init_once")
    assert line["ok"] and set(line["inits"].values()) == {1}
    assert {"sophie", "psxverb"} <= set(line["inits"])


def test_module_number_parser_matches_the_c_library(selftest_lines):
    # atof/strtod/strtof in module sources go to the shim's heap-free parser.
    _, lines = selftest_lines
    line = next(line for line in lines if line.get("check") == "number_parser_matches_libc")
    assert line["ok"] and line["worst_ulps"] <= 1 and line["end_mismatches"] == 0
    assert line["exact"] / line["strings"] > 0.95


def test_arenas_are_bounded_and_measured(selftest_lines):
    _, lines = selftest_lines
    arenas = {line["engine"]: line for line in lines if line.get("check") == "arena_bounds"}
    for engine in ("sw-sophie", "sw-psxverb"):
        a = arenas[engine]
        assert 0 < a["arena_used"] <= a["arena_capacity"]
        # The capacity constant tracks what the module allocates.
        assert a["arena_capacity"] - a["arena_used"] <= 2048
        assert a["block"] == BLOCK
    assert arenas["sw-sophie"]["allocations"] == 1
    assert arenas["sw-psxverb"]["allocations"] == 2
    refused = {line["engine"] for line in lines
               if line.get("check") == "arena_exhaustion_refused" and line["ok"]}
    assert refused == {"sw-sophie", "sw-psxverb"}


def test_module_code_uses_the_arena_not_the_heap(renderer):
    nm = shutil.which("nm")
    if not nm:
        pytest.skip("no nm")
    # The heap, files, threads, and the C library's float parsers, which can
    # allocate (newlib's strtod) and are mapped to fm1_sw_strtof.
    forbidden = {"malloc", "calloc", "realloc", "free", "posix_memalign", "aligned_alloc",
                 "fopen", "open", "opendir", "stat", "mmap", "pthread_create", "dlopen",
                 "atof", "strtod", "strtof", "strtold"}
    objects = sorted((ENGINES / "build" / "sw").glob("*/*.o"))
    objects += [ENGINES / "build" / "our" / "src" / f
                for f in ("schwung_shim.o", "sw_sophie.o", "sw_psxverb.o")]
    assert len(objects) == 5
    for obj in objects:
        undefined, defined = nm_globals(subprocess.run(
            [nm, "-g", str(obj)], check=True, capture_output=True, text=True).stdout)
        assert not undefined & forbidden, (obj.name, undefined & forbidden)
        if obj.parent.parent.name == "sw":          # a vendored module
            # Only the renamed entry point is global, so modules cannot collide.
            assert defined == {f"fm1_sw_{obj.parent.name}_init"}, (obj.name, defined)
            if obj.parent.name in ("sophie", "psxverb"):   # both parse set_param values
                assert "fm1_sw_strtof" in undefined, obj.name


def test_nm_filter_keeps_module_globals_and_drops_compiler_helpers():
    # `nm -g` of an i386 GCC PIE object, as CI's -m32 job builds them: the PC
    # thunks are global T symbols, not weak ones.
    i386 = ("00000000 T fm1_sw_psxverb_init\n"
            "         U _GLOBAL_OFFSET_TABLE_\n"
            "00000000 T __x86.get_pc_thunk.ax\n"
            "00000000 T __x86.get_pc_thunk.bx\n"
            "         U fm1_sw_calloc\n"
            "         U strcmp\n")
    undefined, defined = nm_globals(i386)
    assert defined == {"fm1_sw_psxverb_init"}
    assert undefined == {"GLOBAL_OFFSET_TABLE_", "fm1_sw_calloc", "strcmp"}
    _, defined = nm_globals(i386 + "00000040 T helper\n00000000 D table\n00000004 W weak\n")
    assert defined == {"fm1_sw_psxverb_init", "helper", "table", "weak"}
    undefined, defined = nm_globals("build/sw/sophie/sophie.o:\n"
                                    "0000000000000000 T _fm1_sw_sophie_init\n"
                                    "                 U _strtof\n")          # macOS
    assert defined == {"fm1_sw_sophie_init"} and undefined == {"strtof"}


# ----------------------------------------------------------- contracts ---

def _fm1_name(module_name):
    """The label the fm1 table should show for a module parameter name:
    Sophie's per-pad "Pad 1 " prefix dropped, and shortened only where the
    module's own name does not fit 12 characters."""
    name = re.sub(r"^Pad \d+ ", "", module_name)
    return SHORTENED.get(name, name)


def _check_against_chain_params(params, chain, key_of):
    for p in params:
        c = chain[key_of(p["key"])]
        if "name" in c:                            # module.json entries have none
            assert p["name"] == _fm1_name(c["name"]), (p["key"], p["name"], c["name"])
        if c["type"] == "enum":
            assert p["type"] == 1 and p["format"] == "index" and p["offset"] == 0
            assert p["enum_names"] == c["options"]
            default = c["default"]
            if isinstance(default, str):
                default = c["options"].index(default)
            assert p["def"] == default
        elif c["type"] == "int":                   # a 1-based selector
            assert p["type"] == 1 and p["format"] == "index"
            assert p["min"] + p["offset"] == c["min"] and p["max"] + p["offset"] == c["max"]
            assert len(p["enum_names"]) == c["max"] - c["min"] + 1
        else:
            assert c["type"] == "float" and p["type"] == 0 and p["format"] == "float"
            assert p["min"] == pytest.approx(c["min"]) and p["max"] == pytest.approx(c["max"])
            assert p["def"] == pytest.approx(c["default"], abs=1e-3)


def test_sophie_table_matches_its_chain_params(renderer):
    d = contract("sw-sophie")
    chain = {c["key"]: c for c in d["chain_params"]}
    # Knobs edit the focused pad; its defaults are pad 1's (the Kick).
    _check_against_chain_params(
        d["params"], chain, lambda k: k if k == "focused_pad" else "p01_" + k)
    levels = d["ui_pages"]["levels"]
    assert [p["key"] for p in d["params"]] == (
        [levels["root"]["child_index_param"]] + levels["root"]["knobs"] + levels["ring"]["knobs"])
    assert d["params"][0]["enum_names"] == levels["root"]["child_labels"]
    assert d["exposed"] == 8 and {p["page"] for p in d["params"][:8]} == {0, 1}
    # Shortened only where the module's own name is too long for the TFT.
    assert all(len(full) > 12 >= len(short) for full, short in SHORTENED.items())
    assert set(SHORTENED) <= {re.sub(r"^Pad \d+ ", "", c["name"]) for c in chain.values()}


def test_parameter_names_are_checked(renderer):
    # Two parameters of the same range and default swapping names must fail
    # the contract check (PSX Verb's Level and Input both mute the wet signal
    # at 0, so no render tells them apart).
    d = contract("sw-psxverb")
    chain = {c["key"]: c for c in d["chain_params"]}
    params = [dict(p) for p in d["params"]]
    level = next(p for p in params if p["key"] == "reverb_level")
    gain = next(p for p in params if p["key"] == "input_gain")
    level["name"], gain["name"] = gain["name"], level["name"]
    with pytest.raises(AssertionError):
        _check_against_chain_params(params, chain, lambda k: k)


def test_psxverb_table_matches_its_chain_params_and_module_json(renderer):
    d = contract("sw-psxverb")
    chain = {c["key"]: c for c in d["chain_params"]}
    _check_against_chain_params(d["params"], chain, lambda k: k)
    module_json = json.loads((VENDORED[2] / "module.json").read_text())
    root = module_json["capabilities"]["ui_hierarchy"]["levels"]["root"]
    declared = {p["key"]: p for p in root["params"]}
    _check_against_chain_params(d["params"], declared, lambda k: k)
    keys = [p["key"] for p in d["params"]]
    assert keys == root["knobs"] + [k for k in declared if k not in root["knobs"]]
    assert d["exposed"] == len(d["params"]) == 5


# ------------------------------------------------------------- Sophie ---

@pytest.mark.parametrize("note", range(36, 52))
def test_every_sophie_pad_sounds_cleanly(renderer, tmp_path, note):
    summary, left, _ = render(renderer, tmp_path, "sw-sophie", notes=[f"0.02:{note}:100:0.3"],
                              seconds=0.5)
    assert summary["nonfinite"] == 0 and summary["raw_clipped"] == 0
    assert 0.01 < summary["raw_peak"] < 0.95
    assert rms(left, 0.02, 0.1) > 1e-3


@pytest.mark.parametrize("note", [35, 52, 60])
def test_sophie_plays_only_its_sixteen_pads(renderer, tmp_path, note):
    summary, _, _ = render(renderer, tmp_path, "sw-sophie", notes=[f"0:{note}:100:0.3"],
                           seconds=0.3)
    assert summary["raw_peak"] == 0.0


@pytest.mark.parametrize("tune", [0, 12])
def test_sophie_is_in_tune_at_the_host_rate(renderer, tmp_path, tune):
    # The kick's body is a sine; with sweep, colour and metal at zero it is
    # almost pure. Sophie reads the host's rate (44,118) from host_api_v1_t.
    _, left, _ = render(renderer, tmp_path, "sw-sophie",
                        params=["Pad=0", f"Tune={tune}", "Decay=4", "Sweep=0", "Color=0",
                                "Metal=0"],
                        notes=["0:36:100:1.5"], seconds=1.0)
    assert abs(cents(pitch_hz(left, 0.4, 0.5), KICK_HZ * 2 ** (tune / 12))) < 1.0


@pytest.mark.parametrize("param", ["Model=1", "Metal=100", "Color=90", "Feedback=80",
                                   "Sweep=-60", "Tune=7"])
def test_sophie_parameters_change_the_output(renderer, tmp_path, param):
    # Pad 3 (Snare) factory patch: Shard model, colour 52, metal 76, feedback 18,
    # sweep 28, tune 0; every value below differs from it.
    _, base, _ = render(renderer, tmp_path, "sw-sophie", notes=["0:38:100:0.2"],
                        seconds=0.3, name="base")
    _, moved, _ = render(renderer, tmp_path, "sw-sophie", params=["Pad=2", param],
                         notes=["0:38:100:0.2"], seconds=0.3, name="moved")
    diff = [a - b for a, b in zip(base, moved)]
    assert rms(diff, 0.0, 0.2) > 5e-3


def test_sophie_decay_sets_the_ring_time(renderer, tmp_path):
    _, short, _ = render(renderer, tmp_path, "sw-sophie", params=["Decay=0.1"],
                         notes=["0:36:100:0.1"], seconds=1.0, name="short")
    _, long, _ = render(renderer, tmp_path, "sw-sophie", params=["Decay=2"],
                        notes=["0:36:100:0.1"], seconds=1.0, name="long")
    assert rms(short, 0.3, 0.9) == 0.0
    assert rms(long, 0.3, 0.9) > 1e-2


def test_sophie_knobs_edit_the_focused_pad(renderer, tmp_path):
    _, _, default = render(renderer, tmp_path, "sw-sophie", notes=["0:36:100:0.3"],
                           seconds=0.6, name="default")
    _, _, other = render(renderer, tmp_path, "sw-sophie", params=["Pad=1", "Decay=3"],
                         notes=["0:36:100:0.3"], seconds=0.6, name="other")
    _, rim, _ = render(renderer, tmp_path, "sw-sophie", params=["Pad=1", "Decay=3"],
                       notes=["0:37:100:0.3"], seconds=0.6, name="rim")
    assert default.read_bytes() == other.read_bytes()   # pad 1 untouched
    assert rms(rim, 0.4, 0.6) > 1e-3                     # pad 2 now rings


def test_sophie_whole_kit_at_once(renderer, tmp_path):
    # 16 hits on 12 voices: the oldest are stolen. At full velocity the sum
    # reaches Sophie's own output clamp (30000/32768), which is not a clip here.
    summary, left, _ = render(renderer, tmp_path, "sw-sophie",
                              notes=[f"0:{n}:127:0.2" for n in range(36, 52)], seconds=0.5)
    assert summary["nonfinite"] == 0 and summary["raw_clipped"] == 0
    assert summary["peak"] <= 0.98 + 1e-6 and rms(left, 0.0, 0.2) > 1e-2


# ----------------------------------------------------------- PSX Verb ---

def test_psxverb_processes_noise(renderer, tmp_path):
    summary, left, _ = render(renderer, tmp_path, input="noise", seconds=1.0,
                              fx=[("sw-psxverb", [])])
    assert summary["fx"] == ["sw-psxverb"] and summary["input"] == "noise"
    # Dry noise plus its reverb may pass full scale; the module's own clamp is
    # at the headroom, and the host's limiter takes the rest.
    assert summary["nonfinite"] == 0 and summary["clipped"] == 0
    assert summary["raw_peak"] <= PSX_HEADROOM
    assert rms(left, 0.1, 1.0) > 0.05


def test_psxverb_impulse_has_a_tail(renderer, tmp_path):
    _, wet, _ = render(renderer, tmp_path, input="impulse", seconds=1.0,
                       fx=[("sw-psxverb", [])], name="wet")
    _, dry, _ = render(renderer, tmp_path, input="impulse", seconds=1.0,
                       fx=[("sw-psxverb", ["Mix=0"])], name="dry")
    assert first_nonzero(wet) == first_nonzero(dry) == BLOCK   # one-block FIFO
    assert rms(wet, 0.05, 0.3) > 1e-4
    assert rms(dry, 0.01, 1.0) == 0.0


def test_psxverb_dry_path_is_the_input_one_block_late(renderer, tmp_path):
    _, ref, _ = render(renderer, tmp_path, input="sine", seconds=0.3,
                       fx=[("test-gain", ["Gain=1"])], name="ref")
    _, out, _ = render(renderer, tmp_path, input="sine", seconds=0.3,
                       fx=[("sw-psxverb", ["Mix=0"])], name="out")
    assert all(x == 0.0 for x in out[:BLOCK])
    worst = max(abs(out[n + BLOCK] - ref[n]) for n in range(len(ref) - BLOCK))
    # Within two of the module's 16-bit steps (2/32768 each at 2x headroom:
    # the input's rounding, PSX Verb's own 32767/32768 gain and truncation),
    # plus the WAV file's rounding of each render.
    assert worst < (2 * PSX_HEADROOM + 1) / 32767


def test_psxverb_passes_overs_on_to_the_limiter(renderer, tmp_path):
    # Twelve voices in phase put the bus above full scale, which the host's
    # limiter is there for. Through PSX Verb with Mix at 0 the overs must reach
    # it intact, not hard-clipped at the int16 conversion.
    dry, _, _ = render(renderer, tmp_path, "shapes", notes=CHORD, seconds=0.6, name="dry")
    wet, _, _ = render(renderer, tmp_path, "shapes", notes=CHORD, seconds=0.6, name="wet",
                       fx=[("sw-psxverb", ["Mix=0"])])
    assert dry["raw_peak"] > 1.05 and dry["raw_clipped"] > 0
    # Within three of the module's steps (rounding in, gain and truncation out).
    assert wet["raw_peak"] == pytest.approx(dry["raw_peak"], abs=3 * PSX_HEADROOM / 32768)
    assert wet["raw_clipped"] > 0 and wet["clipped"] == 0 and wet["nonfinite"] == 0


@pytest.mark.parametrize("params,window,low,high", [
    (["Decay=0"], (1.0, 2.0), None, 1e-6),
    (["Decay=1"], (1.0, 2.0), 1e-4, None),
    (["Model=0"], (0.3, 0.8), None, 1e-4),     # Room: gone by 0.3 s
    (["Model=5"], (0.3, 0.8), 1e-3, None),     # Space Echo: still ringing
    (["Level=0"], (0.05, 1.0), None, 0.0),     # no wet signal at all
])
def test_psxverb_parameters_shape_the_tail(renderer, tmp_path, params, window, low, high):
    _, left, _ = render(renderer, tmp_path, input="impulse", seconds=2.0,
                        fx=[("sw-psxverb", params)])
    level = rms(left, *window)
    if low is not None:
        assert level > low
    if high is not None:
        assert level <= high


# ------------------------------------------------------------- common ---

@pytest.mark.parametrize("args", [
    ["--engine", "sw-sophie", "--note", "0:36:100:0.5", "--note", "0.1:42:80:0.2"],
    ["--input", "noise", "--fx", "sw-psxverb", "--fx-param", "Model=5"],
])
def test_schwung_rendering_is_deterministic(renderer, tmp_path, args):
    _, _, a = render_raw(renderer, tmp_path, args + ["--seconds", "0.8"], "a")
    _, _, b = render_raw(renderer, tmp_path, args + ["--seconds", "0.8"], "b")
    assert a.read_bytes() == b.read_bytes()


def test_partial_host_blocks(renderer, tmp_path):
    # 37-frame host blocks: Sophie renders ahead in 36-frame module blocks and
    # comes out bit-identical; PSX Verb's FIFO latency becomes 36 frames.
    notes = ["--note", "0:36:100:0.3", "--note", "0:46:100:0.3"]
    _, _, full = render_raw(renderer, tmp_path,
                            ["--engine", "sw-sophie", *notes, "--seconds", "0.5"], "full")
    _, _, part = render_raw(renderer, tmp_path, ["--engine", "sw-sophie", *notes,
                                                 "--seconds", "0.5", "--frames", "37"], "part")
    assert full.read_bytes() == part.read_bytes()
    summary, left, _ = render_raw(renderer, tmp_path,
                                  ["--input", "impulse", "--fx", "sw-psxverb", "--seconds", "0.5",
                                   "--frames", "37"], "fx37")
    assert summary["block"] == 37 and first_nonzero(left) == 36
    assert summary["nonfinite"] == 0


def test_schwung_instance_sizes_are_reported(renderer, tmp_path, selftest_lines):
    sophie, _, _ = render(renderer, tmp_path, "sw-sophie", seconds=0.1, name="s")
    psx, _, _ = render(renderer, tmp_path, input="silence", seconds=0.1,
                       fx=[("sw-psxverb", [])], name="p")
    measured = {line["engine"]: line["instance_bytes"] for line in selftest_lines[1]
                if line.get("check") == "arena_bounds"}
    assert sophie["instance_bytes"] == measured["sw-sophie"]
    assert psx["fx_bytes"] == [measured["sw-psxverb"]]
    # 12 voices of 1,536-sample ring delays; the SPU work area is 128 KB.
    assert sophie["instance_bytes"] < 80_000
    assert psx["fx_bytes"][0] < 136_000


# ------------------------------------------------------------ vendoring ---

@pytest.mark.parametrize("directory", VENDORED, ids=lambda d: d.name)
def test_vendored_files_match_their_upstream_manifest(directory):
    manifest = (directory / "UPSTREAM.md").read_text()
    rows = re.findall(r"^\| `([^`]+)` \| `[^`]+` \| `([0-9a-f]{64})` \|$", manifest, re.M)
    listed = dict(rows)
    present = {p.name for p in directory.iterdir() if p.name != "UPSTREAM.md"}
    assert set(listed) == present
    for name, digest in listed.items():
        assert hashlib.sha256((directory / name).read_bytes()).hexdigest() == digest, name
    assert (directory / "LICENSE").read_text().startswith("MIT License")
    assert re.search(r"at `[0-9a-f]{40}`", manifest)             # pinned by commit
