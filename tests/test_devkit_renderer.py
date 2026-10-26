"""The hardware workload must exercise the actual shared renderer on desktop."""
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULES = "dx7,macro,drums,filter,drive,echo,comp,arp,lfo,env,chance"


def build_reference(modules):
    cc = os.environ.get("FM1_SIM_CC", "cc")
    cxx = os.environ.get("FM1_SIM_CXX", "c++")
    if not shutil.which("make") or not shutil.which(cxx):
        pytest.skip("native toolchain unavailable")
    extra = os.environ.get("FM1_SIM_EXTRA", "") + " -DFM1_APP_EXTERNAL_ARENAS=1"
    tag = hashlib.sha256((cc + cxx + extra + modules).encode()).hexdigest()[:12]
    build = ROOT / "sim/web/build" / f"devkit-renderer-{tag}"
    target = build / "fm1-devkit-renderer-ref"
    subprocess.run([
        "make", "-s", "-C", str(ROOT / "engines"), "-f", "Makefile", "-f",
        str(ROOT / "sim/web/mk/sim.mk"), "-f", str(ROOT / "tools/jieli/renderer.mk"),
        f"SIM={ROOT / 'sim/web'}", f"BUILD={build}", "FM1_GPL_MODS=0",
        f"FM1_MODULES={modules}", f"CC={cc}", f"CXX={cxx}", f"EXTRA={extra}",
        "-j4", str(target),
    ], check=True, stdout=subprocess.DEVNULL)
    return target


@pytest.mark.parametrize("vcf_unroll,vcf_profile,oscillator_slopes,outer_timing_only",
                         [(False, False, False, False), (True, False, False, False),
                          (True, True, False, False), (True, True, True, False),
                          (True, False, True, True)])
def test_engine_detail_with_unrolled_fir_preserves_pcm(tmp_path, monkeypatch, vcf_unroll, vcf_profile, oscillator_slopes, outer_timing_only):
    """Replay private-copy instrumentation with the optimized FIR, including wrap."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "renderer_prepare", ROOT / "tools/jieli/prepare-renderer-devkit.py")
    prepare = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(prepare)
    monkeypatch.setenv("FM1_SIM_EXTRA", os.environ.get("FM1_SIM_EXTRA", "") +
                      " -DLUNAR_ENGINE_DETAIL_REPLAY=1 -O3 -ffp-contract=off")
    baseline_pcm = tmp_path / "baseline.pcm"
    baseline = subprocess.run([str(build_reference(MODULES)), str(baseline_pcm)],
                              capture_output=True, text=True, check=True)
    hashes = re.findall(r"hash=([0-9a-fA-F]+)", baseline.stdout)[:4]
    assert len(hashes) == 4
    if sys.platform.startswith("linux"):
        assert [int(h, 16) for h in hashes] == [0x6bcab227, 0x46c02687, 0x1e2f305d, 0x5b7dbc03]
    # Only these private copies change. All other sources and build lists are
    # shared read-only; use a separate build directory to avoid stale objects.
    shadow = tmp_path / "source"
    engines = shadow / "engines"
    engines.mkdir(parents=True)
    for path in (ROOT / "engines").iterdir():
        if path.name in ("src", "include") or ((vcf_unroll or vcf_profile or oscillator_slopes) and path.name == "third_party"):
            shutil.copytree(path, engines / path.name)
        elif path.name != "build":
            (engines / path.name).symlink_to(path, target_is_directory=path.is_dir())
    for name in ("firmware", "tools"):
        (shadow / name).symlink_to(ROOT / name, target_is_directory=True)
    # Keep simulator sources read-only, with separate temporary build output.
    (shadow / "sim/web").mkdir(parents=True)
    for name in ("src", "mk"):
        (shadow / "sim/web" / name).symlink_to(ROOT / "sim/web" / name,
                                              target_is_directory=True)
    for engine, name in enumerate(("mi_macro.cc", "drums.cc")):
        path = engines / "src" / name
        if not outer_timing_only:
            path.write_text(prepare.instrument_engine_profile(path.read_text(), engine))
    if oscillator_slopes:
        path = engines / "third_party/mutable/plaits/dsp/oscillator/variable_shape_oscillator.h"
        path.write_text(prepare.reuse_oscillator_slopes(path.read_text()))
    if vcf_unroll:
        path = engines / "third_party/mutable/plaits/dsp/engine2/virtual_analog_vcf_engine.cc"
        path.write_text(prepare.unroll_vcf_samples(path.read_text()))
    if vcf_profile:
        path = engines / "third_party/mutable/plaits/dsp/engine2/virtual_analog_vcf_engine.cc"
        path.write_text(prepare.instrument_vcf_profile(path.read_text()))
    header = engines / "include/fm1_resampler.h"
    text = header.read_text()
    table = re.search(r"static const float fm1_resampler_kernel\[[^\]]+\] = \{.*?\n\};",
                      text, re.S)
    assert table
    text = text.replace(table[0], prepare.resampler_slope_definition(table[0]), 1)
    old = ("  const float *k = &fm1_resampler_kernel[t >> 16];\n"
           "  return k[0] + (float)(t & 0xFFFFu) * (1.0f / 65536.0f) * (k[1] - k[0]);")
    assert text.count(old) == 1
    text = text.replace(old,
                        "  const float *k = &fm1_resampler_kernel_pairs[(t >> 16) * 2];\n"
                        "  return k[0] + (float)(t & 0xFFFFu) * k[1];", 1)
    header.write_text(prepare.unroll_resampler_lowpass(text))
    monkeypatch.setattr(sys.modules[__name__], "ROOT", shadow)
    if not outer_timing_only:
        monkeypatch.setenv("FM1_SIM_EXTRA", os.environ.get("FM1_SIM_EXTRA", "") +
                          " -DLUNAR_RENDERER_PROFILE=1 -DFM1_APP_RENDER_PROFILE=1"
                          " -DLUNAR_RENDERER_ENGINE_PROFILE=1")
    if vcf_profile:
        monkeypatch.setenv("FM1_SIM_EXTRA", os.environ["FM1_SIM_EXTRA"] +
                          " -DLUNAR_RENDERER_VCF_PROFILE=1")
    target = build_reference(MODULES)
    modified_pcm = tmp_path / "modified.pcm"
    subprocess.run([str(target), str(modified_pcm)], check=True, capture_output=True)
    assert modified_pcm.read_bytes() == baseline_pcm.read_bytes()
    if outer_timing_only:
        return  # No observer API is compiled in this exact-PCM comparison.
    harness = tmp_path / "engine-profile.cc"
    harness.write_text(r'''
#include "renderer_live.h"
#include <assert.h>
#include <stdint.h>
static uint32_t tick = UINT32_MAX - 8u;
static uint32_t now(void) { tick += 17u; return tick; }
int main(void) {
    const uint32_t hashes[] = {HASHES};
    lunar_devkit_renderer_profile_clock(now);
    assert(lunar_devkit_renderer_init());
    int16_t pcm[256];
    for (unsigned c = 0; c < 4; ++c) {
        for (unsigned b = 0; b < 5513; ++b) lunar_devkit_renderer_render(pcm);
        struct lunar_renderer_status state;
        lunar_devkit_renderer_status(&state);
        assert(state.completed_hash == hashes[c] && !state.invalid && !state.clipped);
        uint64_t nested_ticks = 0;
#ifdef LUNAR_RENDERER_VCF_PROFILE
        struct lunar_renderer_profile osc, filter;
        lunar_devkit_renderer_engine_read(4, &osc);
        lunar_devkit_renderer_engine_read(5, &filter);
        assert(osc.calls && osc.calls == filter.calls && osc.frames == filter.frames);
        assert(osc.frames == 12u * osc.calls);
        assert(osc.ticks == 17ull * osc.calls && osc.max_ticks == 17u);
        assert(filter.ticks == 17ull * filter.calls && filter.max_ticks == 17u);
        nested_ticks = 68ull * osc.calls; /* Four nested clock reads per VCF call. */
#endif
        for (unsigned i = 0; i < 4; ++i) {
            struct lunar_renderer_profile p;
            lunar_devkit_renderer_engine_read(i, &p);
            assert(p.calls && p.ticks == 17ull * p.calls + (i == 0 ? nested_ticks : 0));
            assert(p.max_ticks >= 17u);
            if (i || !nested_ticks) assert(p.max_ticks == 17u);
            if (i & 1) assert(p.calls == 352832u && p.frames == 352832u);
            else assert(p.frames == 12u * p.calls && p.frames >= 352832u);
        }
        lunar_devkit_renderer_profile_reset();
        for (unsigned i = 0; i <= LUNAR_RENDERER_ENGINE_REGIONS; ++i) {
            struct lunar_renderer_profile p;
            lunar_devkit_renderer_engine_read(i, &p);
            assert(!p.calls && !p.frames && !p.ticks && !p.max_ticks);
        }
    }
}
'''.replace("HASHES", ", ".join("0x" + h + "u" for h in hashes)))
    objects = sorted(str(p) for p in target.parent.rglob("*.o")
                     if p.name != "renderer_reference.o")
    exe = tmp_path / "engine-profile"
    subprocess.run([os.environ.get("FM1_SIM_CXX", "c++"), "-std=c++11",
                    "-DLUNAR_RENDERER_PROFILE=1", "-DLUNAR_RENDERER_ENGINE_PROFILE=1",
                    *(["-DLUNAR_RENDERER_VCF_PROFILE=1"] if vcf_profile else []),
                    "-I" + str(ROOT / "firmware/devkit"), str(harness), *objects,
                    "-lm", "-o", str(exe)], check=True)
    subprocess.run([str(exe)], check=True)


@pytest.mark.parametrize("pool_bytes", [148 * 1024, 136 * 1024])
def test_shared_renderer_schedule_and_pcm(tmp_path, monkeypatch, pool_bytes):
    extra = os.environ.get("FM1_SIM_EXTRA", "")
    if pool_bytes == 136 * 1024:
        # This pool is a 32-bit target budget. The 64-bit echo/voice instances
        # are larger, so require a real 32-bit replay rather than weakening it.
        probe = subprocess.run([os.environ.get("FM1_SIM_CC", "cc"), "-m32", "-x", "c",
                                "-", "-o", str(tmp_path / "abi-probe")],
                               input="int main(void) { return sizeof(void*) != 4; }\n",
                               capture_output=True, text=True)
        if probe.returncode:
            pytest.skip("32-bit compiler/runtime unavailable for target pool replay")
        subprocess.run([str(tmp_path / "abi-probe")], check=True)
        extra += " -m32"
    monkeypatch.setenv("FM1_SIM_EXTRA", extra + f" -DLUNAR_RENDERER_POOL_BYTES={pool_bytes}")
    target = build_reference(MODULES)
    pcm = tmp_path / "reference.pcm"
    # glibc replay enables the same divide-by-zero trap that exposed a
    # speculative logarithmic division on the chip's linear modulation path.
    env = dict(os.environ, LUNAR_TRAP_DIVZERO="1")
    result = subprocess.run([str(target), str(pcm)], capture_output=True, text=True, check=True, env=env)
    rows = [dict(re.findall(r"(\w+)=(\w+)", line)) for line in result.stdout.splitlines()]
    assert len(rows) == 8
    for i, row in enumerate(rows):
        assert int(row["completed"]) == i + 1
        assert int(row["case"]) == i % 4
        assert int(row["blocks"]) == (i + 1) * 5513
        assert row["invalid"] == row["clipped"] == "0"
        assert 0 < int(row["arena"]) <= pool_bytes
    assert int(rows[-1]["controls"]) > 1000
    assert pcm.stat().st_size == 8 * 5513 * 64 * 4
    # The same source and schedule, fresh process: reproducible PCM receipts.
    again = tmp_path / "again.pcm"
    replay = subprocess.run([str(target), str(again)], capture_output=True, text=True, check=True)
    assert result.stdout == replay.stdout
    assert hashlib.sha256(pcm.read_bytes()).digest() == hashlib.sha256(again.read_bytes()).digest()


def test_missing_effect_refuses_whole_workload():
    target = build_reference(MODULES.replace(",comp", ""))
    result = subprocess.run([str(target)], capture_output=True, text=True)
    assert result.returncode == 1
    assert "initialization refused: stage 1" in result.stderr
    assert "LUNAR_RENDERER completed=" not in result.stdout


def test_mixed_renderer_without_attached_pixels_preserves_pcm(tmp_path, monkeypatch):
    """Reclaim idle pixels, not any engine/effect/modulation/control work."""
    extra = os.environ.get("FM1_SIM_EXTRA", "")
    results = []
    for external in (0, 1):
        monkeypatch.setenv("FM1_SIM_EXTRA", extra + f" -DFM1_TFT_EXTERNAL_PIXELS={external}")
        pcm = tmp_path / f"mixed-{external}.pcm"
        result = subprocess.run([str(build_reference(MODULES)), str(pcm)],
                                capture_output=True, check=True,
                                env=dict(os.environ, LUNAR_TRAP_DIVZERO="1"))
        results.append((result.stdout, hashlib.sha256(pcm.read_bytes()).hexdigest()))
    assert results[0] == results[1]


def test_keys_workload_replays_real_app_and_refuses_missing_master(tmp_path, monkeypatch):
    # This arrangement retains the real sequencer, two modulation routes,
    # filter insert and both masters. No Macro/drum implementation is needed.
    monkeypatch.setenv("FM1_SIM_EXTRA", os.environ.get("FM1_SIM_EXTRA", "") +
                      " -DLUNAR_RENDERER_WORKLOAD=1 -DLUNAR_RENDERER_POOL_BYTES=98304")
    modules = MODULES.replace(",macro,drums", "").replace(",drive", "")
    target = build_reference(modules)
    pcm = tmp_path / "keys.pcm"
    result = subprocess.run([str(target), str(pcm)], capture_output=True, text=True,
                            check=True, env=dict(os.environ, LUNAR_TRAP_DIVZERO="1"))
    rows = [dict(re.findall(r"(\w+)=(\w+)", line)) for line in result.stdout.splitlines()]
    assert len(rows) == 8
    assert all(row["workload"] == "keys" and row["invalid"] == row["clipped"] == "0"
               for row in rows)
    assert [int(row["case"]) for row in rows] == list(range(4)) * 2
    # Apple and Linux math/toolchain paths have distinct PCM fingerprints.
    # Pin each checked host exactly; Linux also matches the pi32v2 capture.
    expected = ["1e3b4d6a", "8d53e78f", "2894bb36", "2f409722"]
    if sys.platform == "darwin":
        expected[-1] = "2e91545b"
    assert [row["hash"] for row in rows[:4]] == expected
    assert all(0 < int(row["arena"]) <= 96 * 1024 for row in rows)
    assert [int(row["blocks"]) for row in rows] == [5513 * i for i in range(1, 9)]
    assert int(rows[-1]["controls"]) > 1000
    assert pcm.stat().st_size == 8 * 5513 * 64 * 4
    replay = subprocess.run([str(target)], capture_output=True, text=True, check=True)
    assert result.stdout == replay.stdout
    monkeypatch.setenv("FM1_SIM_EXTRA", os.environ["FM1_SIM_EXTRA"] +
                      " -DLUNAR_RENDERER_PROFILE=1 -DFM1_APP_RENDER_PROFILE=1")
    profiled = subprocess.run([str(build_reference(modules))], capture_output=True,
                              text=True, check=True)
    # The reference also checks complete active-unit coverage and zero counts
    # for the four unused workload rows, rather than duplicating sound zero.
    assert profiled.stdout == result.stdout
    missing = subprocess.run([str(build_reference(modules.replace(",comp", "")))],
                             capture_output=True, text=True)
    assert missing.returncode == 1 and "initialization refused: stage 1" in missing.stderr


def test_unknown_renderer_workload_refused_before_sdk_access(tmp_path):
    import importlib.util
    spec = importlib.util.spec_from_file_location("renderer_prepare", ROOT / "tools/jieli/prepare-renderer-devkit.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with pytest.raises(ValueError, match="Unknown renderer workload"):
        module.prepare_renderer(tmp_path / "absent-sdk", ROOT, tmp_path / "out", workload="typo")
    assert not (tmp_path / "out").exists()



@pytest.mark.parametrize("prep_profile", [False, True])
def test_profile_preserves_pcm_and_counts_all_unit_frames(tmp_path, monkeypatch, prep_profile):
    # Profiling must preserve PCM relative to the unprofiled build on this
    # same host/libm. Keep the target-compatible Linux fingerprints pinned too.
    baseline = subprocess.run([str(build_reference(MODULES))], capture_output=True,
                              text=True, check=True)
    hashes = [int(x, 16) for x in re.findall(r"hash=([0-9a-fA-F]+)", baseline.stdout)][:4]
    assert len(hashes) == 4
    if sys.platform.startswith("linux"):
        assert hashes == [0x6bcab227, 0x46c02687, 0x1e2f305d, 0x5b7dbc03]
    monkeypatch.setenv("FM1_SIM_EXTRA", os.environ.get("FM1_SIM_EXTRA", "") +
                      " -DLUNAR_RENDERER_PROFILE=1 -DFM1_APP_RENDER_PROFILE=1")
    if prep_profile:
        monkeypatch.setenv("FM1_SIM_EXTRA", os.environ["FM1_SIM_EXTRA"] + " -DLUNAR_RENDERER_PREP_PROFILE=1")
    target = build_reference(MODULES)
    harness = tmp_path / "profile.cc"
    harness.write_text(r'''
#include "renderer_live.h"
#include <assert.h>
#include <stdint.h>
static uint32_t tick = UINT32_MAX - 40u;
static uint32_t now(void) { tick += 17u; return tick; }
int main(void) {
    const uint32_t hashes[] = {0x6bcab227u, 0x46c02687u, 0x1e2f305du, 0x5b7dbc03u};
    lunar_devkit_renderer_profile_clock(now);
    assert(lunar_devkit_renderer_init());
    int16_t pcm[256];
    struct lunar_renderer_profile invalid_detail;
    for (unsigned c = 0; c < 4; ++c) {
        uint64_t previous[8] = {0};
        for (unsigned b = 0; b < 5513; ++b) {
            lunar_devkit_renderer_render(pcm);
            for (unsigned i = 0; i < 8; ++i) {
                struct lunar_renderer_profile p;
                lunar_devkit_renderer_profile_read(i, &p);
                /* Includes every split callback, and resets each block. */
                assert(lunar_devkit_renderer_unit_last(i) == p.ticks - previous[i]);
                previous[i] = p.ticks;
            }
        }
        struct lunar_renderer_status state;
        lunar_devkit_renderer_status(&state);
        assert(state.completed_hash == hashes[c] && !state.invalid && !state.clipped);
        for (unsigned i = 0; i < 8; ++i) {
            struct lunar_renderer_profile p;
            lunar_devkit_renderer_profile_read(i, &p);
            assert(p.calls && p.frames == 5513u * 64u);
            assert(p.ticks == 17ull * p.calls && p.max_ticks == 17u);
            assert(lunar_devkit_renderer_unit_last(i) >= 17u);
            assert(lunar_devkit_renderer_unit_last(i) % 17u == 0);
        }
        assert(!lunar_devkit_renderer_unit_last(8));
        assert(lunar_devkit_renderer_profile_stages() == 6);
        for (unsigned i = 0; i < 6; ++i) {
            struct lunar_renderer_profile p;
            lunar_devkit_renderer_stage_read(i, &p);
            assert(p.calls == 5513 && p.frames == 5513u * 64u);
            /* Sounds/masters include the nested unit clock reads. */
            assert(p.ticks >= 17ull * p.calls && p.max_ticks >= 17u);
            if (i >= 2) assert(p.ticks == 17ull * p.calls && p.max_ticks == 17u);
            assert(lunar_devkit_renderer_stage_last(i) >= 17u);
            if (i >= 2) assert(lunar_devkit_renderer_stage_last(i) == 17u);
        }
        assert(!lunar_devkit_renderer_stage_last(6));
        for (unsigned i = 0; i < LUNAR_RENDERER_DETAIL_REGIONS; ++i) {
            struct lunar_renderer_profile p;
            lunar_devkit_renderer_detail_read(i, &p);
            assert(p.calls == 5513 && p.frames == 5513u * 64u);
            assert(p.ticks >= 17ull * p.calls && p.max_ticks >= 17u);
            if (i == 2) assert(p.ticks == 17ull * p.calls && p.max_ticks == 17u);
#ifndef LUNAR_RENDERER_PREP_PROFILE
            if (i == 0) assert(p.ticks == 17ull * p.calls && p.max_ticks == 17u);
#endif
            assert(lunar_devkit_renderer_detail_last(i) >= 17u);
        }
        lunar_devkit_renderer_detail_read(LUNAR_RENDERER_DETAIL_REGIONS, &invalid_detail);
        assert(!invalid_detail.calls && !invalid_detail.frames && !invalid_detail.ticks);
        assert(!lunar_devkit_renderer_detail_last(LUNAR_RENDERER_DETAIL_REGIONS));
#ifdef LUNAR_RENDERER_PREP_PROFILE
        for (unsigned i = 0; i <= LUNAR_RENDERER_PREP_REGIONS; ++i) {
            struct lunar_renderer_profile p;
            lunar_devkit_renderer_prep_read(i, &p);
            unsigned calls = i < 2 ? 1u : i < 4 ? 87u : 0u;
            assert(p.calls == calls && p.frames == 0);
            assert(p.ticks == 17ull * calls && p.max_ticks == (calls ? 17u : 0u));
            /* Last controls run at5504; final5512 has no events. */
            assert(!lunar_devkit_renderer_prep_last(i));
        }
        lunar_devkit_prep_profile(0, 1); /* inactive outside render */
        lunar_devkit_prep_profile(0, 0);
#endif
        lunar_devkit_renderer_profile_reset();
#ifdef LUNAR_RENDERER_PREP_PROFILE
        for (unsigned i = 0; i <= LUNAR_RENDERER_PREP_REGIONS; ++i) {
            struct lunar_renderer_profile p;
            lunar_devkit_renderer_prep_read(i, &p);
            assert(!p.calls && !p.frames && !p.ticks && !p.max_ticks);
            assert(!lunar_devkit_renderer_prep_last(i));
        }
#endif
        for (unsigned i = 0; i <= LUNAR_RENDERER_DETAIL_REGIONS; ++i) {
            struct lunar_renderer_profile p;
            lunar_devkit_renderer_detail_read(i, &p);
            assert(!p.calls && !p.frames && !p.ticks && !p.max_ticks);
            assert(!lunar_devkit_renderer_detail_last(i));
        }
        for (unsigned i = 0; i <= 6; ++i) {
            struct lunar_renderer_profile p;
            lunar_devkit_renderer_stage_read(i, &p);
            assert(!p.calls && !p.frames && !p.ticks && !p.max_ticks);
            assert(!lunar_devkit_renderer_stage_last(i));
        }
        for (unsigned i = 0; i <= 8; ++i) {
            struct lunar_renderer_profile p;
            lunar_devkit_renderer_profile_read(i, &p);
            assert(!p.calls && !p.frames && !p.ticks && !p.max_ticks);
            assert(!lunar_devkit_renderer_unit_last(i));
        }
    }
}
''')
    harness.write_text(harness.read_text().replace(
        "0x6bcab227u, 0x46c02687u, 0x1e2f305du, 0x5b7dbc03u",
        ", ".join(f"0x{x:08x}u" for x in hashes)))
    objects = sorted(str(p) for p in target.parent.rglob("*.o") if p.name != "renderer_reference.o")
    exe = tmp_path / "profile"
    subprocess.run([os.environ.get("FM1_SIM_CXX", "c++"), "-std=c++11", "-DLUNAR_RENDERER_PROFILE=1",
                    *(["-DLUNAR_RENDERER_PREP_PROFILE=1"] if prep_profile else []),
                    "-I" + str(ROOT / "firmware/devkit"), str(harness), *objects,
                    "-lm", "-o", str(exe)], check=True)
    subprocess.run([str(exe)], check=True)


@pytest.mark.parametrize('options', [
    {'outer_timing_only': True},
    {'outer_timing_only': True, 'timing_only': True, 'profile': True},
    {'oscillator_slopes': True},
    {'oscillator_slopes': True, 'timing_only': True, 'profile': True, 'hot_ram': True},
    {'vcf_unroll': True},
    {'vcf_profile': True},
    {'vcf_profile': True, 'engine_profile': True},
    {'vcf_unroll': True, 'timing_only': True, 'profile': True, 'hot_ram': True},
    {'prep_profile': True},
    {'prep_profile': True, 'timing_only': True},
    {'scheduling_probe': True},
    {'scheduling_probe': True, 'timing_only': True, 'profile': True, 'hot_ram': True},
    {'fm6_pair': True},
    {'fm6_pair': True, 'timing_only': True},
    {'fm6_pair': True, 'timing_only': True, 'hot_ram': True},
    {'msfa_pure_unroll': True},
    {'msfa_pure_unroll': True, 'timing_only': True, 'hot_ram': True, 'msfa_narrow_adds': True},
    {'msfa_sine_pair': True},
    {'msfa_sine_pair': True, 'timing_only': True, 'hot_ram': True},
    {'msfa_sine32': True},
    {'msfa_sine32': True, 'timing_only': True, 'hot_ram': True},
    {'msfa_narrow_adds': True},
    {'msfa_narrow_adds': True, 'timing_only': True},
    {'resampler_schedule': True},
    {'resampler_schedule': True, 'timing_only': True},
    {'mixer_ram': True},
    {'mixer_ram': True, 'timing_only': True},
    {'renderer_o3': True},
    {'renderer_o3': True, 'timing_only': True},
    {'resampler_unroll': True},
    {'resampler_unroll': True, 'timing_only': True},
    {'engine_profile': True},
    {'engine_profile': True, 'timing_only': True},
    {'resampler_slopes': True},
    {'resampler_slopes': True, 'timing_only': True},
    {'plaits_cache': True},
    {'plaits_cache': True, 'timing_only': True},
    {'plan_ram': True},
    {'plan_ram': True, 'timing_only': True, 'profile': True, 'prep_profile': True},
    {'plan_ram': True, 'timing_only': True, 'profile': True, 'event_ram': True},
    {'event_ram': True},
    {'event_ram': True, 'timing_only': True, 'profile': True},
    {'event_ram': True, 'timing_only': True, 'profile': True, 'prep_profile': True},
    {'event_ram': True, 'timing_only': True, 'profile': True, 'kind_ram': True},
    {'kind_ram': True},
    {'kind_ram': True, 'timing_only': True},
    {'kind_ram': True, 'timing_only': True, 'profile': True},
    {'module_ram': True},
    {'module_ram': True, 'timing_only': True},
    {'module_ram': True, 'timing_only': True, 'profile': True},
    {'hook_ram': True},
    {'hook_ram': True, 'timing_only': True},
    {'hook_ram': True, 'timing_only': True, 'profile': True},
    {'ui_ram': True},
    {'ui_ram': True, 'timing_only': True},
    {'dispatch_ram': True},
    {'dispatch_ram': True, 'timing_only': True},
    {'metadata_ram': True},
    {'metadata_ram': True, 'timing_only': True},
    {'control_ram': True},
    {'control_ram': True, 'timing_only': True},
    {'filter_process_ram': True},
    {'filter_process_ram': True, 'timing_only': True},
    {'resampler_outline': True},
    {'resampler_outline': True, 'timing_only': True},
    {'fx_ram': True},
    {'fx_ram': True, 'timing_only': True},
    {'cache_tables': True},
    {'cache_tables': True, 'timing_only': True, 'hot_ram': True, 'sine_ram': True},
    {'external_pixels': True},
    {'profile': True}, {'hot_ram': True}, {'sine_ram': True},
    {'sine_ram': True, 'timing_only': True},
    {'resampler_ram': True},
    {'resampler_ram': True, 'timing_only': True, 'hot_ram': True},
])
def test_profile_rejects_dac_preparation_before_writing(tmp_path, options):
    import importlib.util
    spec = importlib.util.spec_from_file_location("renderer_prepare", ROOT / "tools/jieli/prepare-renderer-devkit.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    out = tmp_path / "out"
    with pytest.raises(ValueError, match="worker-only|timing-only"):
        module.prepare_renderer(tmp_path / "absent-sdk", ROOT, out, **options)
    assert not out.exists()

@pytest.mark.parametrize("profile", [False, True])
def test_worker_timing_wrap_and_yields(tmp_path, profile):
    # Test the timing controller independently of DSP cost: the injected clock
    # wraps and makes every render late. UART scheduling yields and reporting
    # must stay outside each measured region and cover every density case.
    harness = tmp_path / "timing.c"
    harness.write_text(r'''
#include "renderer_timing.h"
#include <assert.h>
#include <string.h>
static unsigned clock_calls, rendered, yielded, emitted, init_ok = 1;
static uint32_t tick = UINT32_MAX - 40000u;
int lunar_devkit_renderer_init(void) { return init_ok; }
void lunar_devkit_renderer_render(int16_t *p) { ++rendered; memset(p, 0, 512); }
void lunar_devkit_renderer_status(struct lunar_renderer_status *p) {
    memset(p, 0, sizeof *p); p->blocks = rendered;
}
static uint32_t now(void) {
    ++clock_calls;
    tick += (!(clock_calls & 1u) && rendered % 5513u == 18u) ? 45000u : 35000u;
    return tick;
}
#ifdef LUNAR_RENDERER_PROFILE
void lunar_devkit_renderer_profile_clock(uint32_t (*clock)(void)) { assert(clock == now); }
void lunar_devkit_renderer_profile_reset(void) { }
uint32_t lunar_devkit_renderer_stage_last(unsigned s) { return rendered * 10u + s; }
uint32_t lunar_devkit_renderer_unit_last(unsigned u) { return rendered * 1000u + u; }
uint32_t lunar_devkit_renderer_detail_last(unsigned s) { return rendered * 100u + s; }
#endif
static void yield(void) { assert(!(clock_calls & 1u)); ++yielded; }
static void emit(const struct lunar_renderer_timing *r) {
    assert(!(clock_calls & 1u)); assert(r->test_case == emitted++);
    assert(r->blocks == 5513 && r->over_budget == 5513);
    assert(r->min_ticks == 35000 && r->max_ticks == 45000);
    assert(r->ticks == 5513ull * 35000u + 10000u);
    assert(r->state.blocks == emitted * 5513u);
#ifdef LUNAR_RENDERER_PROFILE
    assert(r->worst_block == 17u);
    for (unsigned u = 0; u < 8; ++u)
        assert(r->worst_units[u] == (r->test_case * 5513u + 18u) * 1000u + u);
    for (unsigned s = 0; s < LUNAR_RENDERER_PROFILE_STAGES; ++s)
        assert(r->worst_stages[s] == (r->test_case * 5513u + 18u) * 10u + s);
    for (unsigned d = 0; d < LUNAR_RENDERER_DETAIL_REGIONS; ++d)
        assert(r->worst_details[d] == (r->test_case * 5513u + 18u) * 100u + d);
#endif
}
int main(void) {
    assert(!lunar_devkit_renderer_timing(0, yield, emit));
    assert(!lunar_devkit_renderer_timing(now, 0, emit));
    assert(!lunar_devkit_renderer_timing(now, yield, 0));
    init_ok = 0;
    assert(!lunar_devkit_renderer_timing(now, yield, emit));
    assert(!clock_calls && !rendered && !yielded && !emitted);
    init_ok = 1;
    assert(lunar_devkit_renderer_timing(now, yield, emit));
    assert(rendered == 4u * 5513u && clock_calls == 2u * rendered);
    assert(yielded == 4u * (345u + 1u) && emitted == 4);
    return 0;
}
''')
    exe = tmp_path / "timing"
    subprocess.run([os.environ.get("FM1_SIM_CC", "cc"), "-std=c99", "-Wall", "-Wextra", "-Werror",
                    *(["-DLUNAR_RENDERER_PROFILE=1"] if profile else []),
                    "-I" + str(ROOT / "firmware/devkit"), str(harness),
                    str(ROOT / "firmware/devkit/renderer_timing.c"), "-o", str(exe)], check=True)
    subprocess.run([str(exe)], check=True)


def test_worker_recovery_window_precedes_crashing_initialization(tmp_path):
    # Run the actual worker and parser with only SDK hardware/scheduling mocked.
    # First simulate an init crash, then a fresh boot receiving an acknowledged
    # three-command handshake during its recovery window. No physical I/O.
    for name in ('app_config.h', 'system/includes.h', 'os/os_api.h', 'asm/includes.h'):
        header = tmp_path / name
        header.parent.mkdir(parents=True, exist_ok=True)
        header.write_text('')
    (tmp_path / 'app_config.h').write_text(r'''
#include <stdint.h>
#include <stdio.h>
struct mock_timer { uint32_t CON, CNT, PRD; };
extern struct mock_timer timer;
#define JL_TIMER4 (&timer)
int clk_get(const char *);
void os_time_dly(unsigned);
unsigned uxTaskGetStackHighWaterMark(void *);
void malloc_stats(void);
''')
    harness = tmp_path / 'worker.c'
    harness.write_text(r'''
#include "app_config.h"
#include "renderer_timing.h"
#include "boot_command.h"
#include <assert.h>
#include <setjmp.h>
#include <string.h>
struct mock_timer timer;
static jmp_buf exit_worker;
static unsigned recovering, ready, ticks, init_calls, acknowledgments, probe_yields;
static struct lunar_boot_command parser;
void lunar_devkit_worker(void *);
int clk_get(const char *name) { assert(!strcmp(name, "sys")); return 320000000; }
unsigned uxTaskGetStackHighWaterMark(void *p) { (void)p; return 256; }
void malloc_stats(void) {}

static void command(const char *s, enum lunar_boot_action expected) {
    enum lunar_boot_action action = LUNAR_BOOT_NONE;
    while (*s) action = lunar_boot_command_feed(&parser, *s++, ticks * 10u);
    assert(action == expected);
    ++acknowledgments;
}
void os_time_dly(unsigned n) {
    if (ready) {
        /* Receiver was reserved by app_main; host exchanges fit in this
         * window before a fault in workload initialization. */
        if (n == 200 && recovering) {
            ticks += 10; command("LUNAR PING\n", LUNAR_BOOT_PONG);
            ticks += 10; command("LUNAR ARM UBOOT\n", LUNAR_BOOT_ARMED);
            ticks += 10; command("LUNAR ENTER UBOOT\n", LUNAR_BOOT_ENTER);
            longjmp(exit_worker, 2);
        }
    }
    if (n == 1) { assert(!init_calls && ticks >= 310); ++probe_yields; }
    ticks += n; timer.CNT += n * 240000u;
}
int lunar_devkit_renderer_timing(uint32_t (*now)(void), void (*yield)(void),
    void (*emit)(const struct lunar_renderer_timing *)) {
    assert(now && yield && emit && ready && ticks >= 310 && probe_yields == 32);
    ++init_calls;
    longjmp(exit_worker, 1); /* workload initialization faults */
}
int main(void) {
    switch (setjmp(exit_worker)) {
    case 0: ready = 1; lunar_devkit_worker(0); assert(0); break;
    case 1: assert(init_calls == 1); break;
    default: assert(0);
    }
    recovering = 1; ready = ticks = init_calls = probe_yields = 0;
    memset(&timer, 0, sizeof timer); memset(&parser, 0, sizeof parser);
    switch (setjmp(exit_worker)) {
    case 0: ready = 1; lunar_devkit_worker(0); assert(0); break;
    case 2: assert(acknowledgments == 3); break;
    default: assert(0);
    }
    assert(!init_calls && !probe_yields); /* Recovery completes before the faulty workload runs. */
    return 0;
}
''')
    # Keep the compiler barrier, replacing only the pi32v2 hardware opcode.
    worker = tmp_path / 'sdk_worker.c'
    source = (ROOT / 'firmware/devkit/sdk_worker.c').read_text()
    barrier = '__asm__ volatile("csync;" ::: "memory");'
    assert source.count(barrier) == 1
    worker.write_text(source.replace(barrier, '__asm__ volatile("" ::: "memory");'))
    exe = tmp_path / 'worker'
    subprocess.run([os.environ.get('FM1_SIM_CC', 'cc'), '-std=c99', '-O2',
                    '-DLUNAR_DEVKIT_RENDERER_TIMING=1', '-DLUNAR_DEVKIT_BOOT_CONTROL=1',
                    '-I' + str(tmp_path), '-I' + str(ROOT / 'firmware/devkit'),
                    str(harness), str(worker),
                    str(ROOT / 'firmware/devkit/boot_command.c'),
                    str(ROOT / 'firmware/devkit/arithmetic_probe.c'), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True, capture_output=True)


@pytest.mark.parametrize("priority", [8, 18])
def test_recovery_is_reserved_before_workload_and_fails_closed(tmp_path, priority):
    # Execute actual receiver startup against allocation/UART fault injection.
    # The prepared app_main contract only allocates work on a zero result.
    for name in ('app_config.h', 'system/includes.h', 'device/includes.h',
                 'device/uart.h', 'asm/includes.h'):
        header = tmp_path / name
        header.parent.mkdir(parents=True, exist_ok=True)
        header.write_text('')
    (tmp_path / 'app_config.h').write_text(r"""
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef uintptr_t u32;
#define CPU_CRITICAL_ENTER() ((void)0)
#define UART_SET_CIRCULAR_BUFF_ADDR 1
#define UART_SET_CIRCULAR_BUFF_LENTH 2
#define UART_SET_RECV_BLOCK 3
#define UART_START 4
#define UART_FLUSH 5
void *dev_open(const char *, void *);
int dev_ioctl(void *, int, u32);
int dev_close(void *);
int dev_read(void *, void *, unsigned);
int os_task_create(void (*)(void *), void *, int, unsigned, int, const char *);
void os_time_dly(unsigned);
uint32_t sys_timer_get_ms(void);
""")
    harness = tmp_path / 'startup.c'
    harness.write_text(r"""
#include "app_config.h"
#include "boot_command.h"
#include <assert.h>
static int fault, io, closed, recovery, work;
static unsigned char handle;
void *dev_open(const char *name, void *arg) {
    assert(!strcmp(name, "uart1") && !arg && !work);
    return fault == 1 ? NULL : &handle;
}
int dev_ioctl(void *p, int cmd, u32 value) {
    (void)value; assert(p == &handle && !work); ++io;
    return fault == cmd + 1 ? -1 : 0;
}
int dev_close(void *p) { assert(p == &handle); ++closed; return 0; }
int dev_read(void *p, void *b, unsigned n) { (void)p;(void)b;(void)n;return 0; }
int os_task_create(void (*fn)(void *), void *arg, int priority, unsigned stack,
                   int queue, const char *name) {
    assert(fn && arg == &handle && priority == EXPECTED_CONTROL_PRIORITY && stack == 1024 && !queue);
    assert(!strcmp(name, "lunar_control") && io == 4 && !work);
    if (fault == 6) return -6;
    recovery = 1; return 0;
}
void os_time_dly(unsigned n) { (void)n; }
uint32_t sys_timer_get_ms(void) { return 0; }
void nvram_set_boot_state(u32 state) { (void)state; assert(0); }
static void app_start(int worker_oom) {
    if (!lunar_devkit_boot_control_start()) {
        assert(recovery && io == 4);
        if (!worker_oom) work = 1;
    }
}
int main(void) {
    for (fault = 0; fault <= 6; ++fault) {
        io = closed = recovery = work = 0;
        app_start(0);
        assert(work == (fault == 0));
        assert(recovery == (fault == 0));
        assert(closed == (fault >= 2));
    }
    fault = io = closed = recovery = work = 0;
    app_start(1);
    assert(recovery && !work && !closed); // worker OOM leaves receiver allocated
    return 0;
}
""")
    # Keep the actual startup logic; only ELF placement is target-specific.
    control = tmp_path / 'boot_control.c'
    control.write_text((ROOT / 'firmware/devkit/boot_control.c').read_text().replace(
        'section(".volatile_ram_code"), noinline', 'noinline'))
    exe = tmp_path / 'startup'
    subprocess.run([os.environ.get('FM1_SIM_CC', 'cc'), '-std=c99', '-O2',
                    '-DEXPECTED_CONTROL_PRIORITY=' + str(priority),
                    *(['-DLUNAR_DEVKIT_SCHEDULING_PROBE=1'] if priority == 18 else []),
                    '-I' + str(tmp_path), '-I' + str(ROOT / 'firmware/devkit'),
                    str(harness), str(control),
                    str(ROOT / 'firmware/devkit/boot_command.c'), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True, capture_output=True)


@pytest.mark.parametrize('workload', ['mixed', 'keys'])
def test_copied_kernel_attachment_preserves_full_renderer_pcm(tmp_path, monkeypatch, workload):
    extra = os.environ.get('FM1_SIM_EXTRA', '') + (
        ' -DLUNAR_DEVKIT_FM6_PAIR=1 -DLUNAR_MAILBOX_HOST_TEST=1 -pthread')
    if workload == 'keys':
        extra += ' -DLUNAR_RENDERER_WORKLOAD=1 -DLUNAR_RENDERER_POOL_BYTES=98304'
    monkeypatch.setenv('FM1_SIM_EXTRA', extra)
    target = build_reference(MODULES)
    baseline = tmp_path / 'baseline.pcm'
    subprocess.run([str(target), str(baseline)], check=True, capture_output=True)
    expected = hashlib.sha256(baseline.read_bytes()[:4 * 5513 * 64 * 4]).hexdigest()
    source = tmp_path / 'attach.cc'
    source.write_text(r'''
#include "renderer_live.h"
#include "fm6_pair_bridge.h"
#include <atomic>
#include <cassert>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <thread>
static unsigned calls;
static uint32_t now() {
    std::this_thread::yield(); // host scheduling only, not target timing evidence
    return (uint32_t)std::chrono::duration_cast<std::chrono::microseconds>(
        std::chrono::steady_clock::now().time_since_epoch()).count();
}
static int serial(void *, fm1_dx7_kernel_job_t jobs[2]) {
    ++calls;
    return fm1_dx7_compute_kernel(&jobs[0]) && fm1_dx7_compute_kernel(&jobs[1]);
}
static int reject(void *, fm1_dx7_kernel_job_t jobs[2]) {
    ++calls;
    std::memset(jobs, 0xa5, 2 * sizeof *jobs);
    return 0; // mutated copies must be discarded without advancing envelopes twice
}
int main(int argc, char **argv) {
    assert(argc == 3);
    const int mode = std::atoi(argv[1]);
    fm1_dx7_kernel_adapter_t invalid = {0, 0};
    assert(!lunar_devkit_renderer_kernel_adapter(&invalid));
    assert(lunar_devkit_renderer_kernel_adapter(0));
    fm1_dx7_kernel_adapter_t synchronous = {mode == 1 ? serial : reject, 0};
    std::atomic<bool> run(true);
    std::thread worker;
    if (!mode) {
        assert(lunar_fm6_pair_init(now, 1000000u));
        worker = std::thread([&] { while (run.load()) lunar_fm6_pair_worker_step(); });
    }
    assert(lunar_devkit_renderer_kernel_adapter(mode ? &synchronous : lunar_fm6_pair_adapter()));
    assert(lunar_devkit_renderer_init());
    assert(!lunar_devkit_renderer_kernel_adapter(0)); // cannot detach during a live render
    FILE *out = std::fopen(argv[2], "wb"); assert(out);
    int16_t pcm[256];
    for (unsigned b = 0; b < 4 * 5513u; ++b) {
        lunar_devkit_renderer_render(pcm);
        for (unsigned i = 0; i < 64; ++i)
            assert(std::fwrite(pcm + 4 * i, 4, 1, out) == 1);
    }
    assert(!std::fclose(out));
    struct lunar_renderer_status status;
    lunar_devkit_renderer_status(&status);
    assert(status.completed_cases == 4 && !status.invalid && !status.clipped);
    run.store(false);
    if (worker.joinable()) worker.join();
    if (!mode) assert(lunar_fm6_pair_completed() > 100 && !lunar_fm6_pair_disabled());
    else assert(calls > 100);
}
''')
    objects = sorted(str(p) for p in target.parent.rglob('*.o') if p.name != 'renderer_reference.o')
    exe = tmp_path / 'attach'
    subprocess.run([os.environ.get('FM1_SIM_CXX', 'c++'), '-std=c++11', '-O2', '-pthread',
                    '-I' + str(ROOT / 'firmware/devkit'), '-I' + str(ROOT / 'engines/include'),
                    str(source), *objects, '-lm', '-o', str(exe)], check=True)
    for mode in (0, 1, 2):
        pcm = tmp_path / f'attach-{mode}.pcm'
        subprocess.run([str(exe), str(mode), str(pcm)], check=True, timeout=120)
        assert hashlib.sha256(pcm.read_bytes()).hexdigest() == expected


@pytest.mark.parametrize("planner", [False, True])
def test_prep_profile_preserves_original_calls_and_refuses_drift(planner):
    import importlib.util
    spec = importlib.util.spec_from_file_location("prep_profile", ROOT / "tools/jieli/prepare-renderer-devkit.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    path = "engines/mod/mod_plan.c" if planner else "sim/web/src/fm1_app.c"
    original = (ROOT / path).read_text()
    observed = module.instrument_prep_profile(original, planner)
    assert observed.startswith("extern void lunar_devkit_prep_profile(unsigned, int);\n")
    normalized = observed.split("\n", 1)[1]
    # Drop only the newly inserted observer lines; normalize whitespace, not code.
    normalized = re.sub(r"^ *lunar_devkit_prep_profile\(\d+, [01]\);\n", "", normalized, flags=re.M)
    assert re.sub(r"\s+", "", normalized) == re.sub(r"\s+", "", original)
    regions = (7,) if planner else (4, 5, 6, 8, 9, 10, 11)
    for region in regions:
        assert observed.count(f"lunar_devkit_prep_profile({region}, 1);") == 1
        assert observed.count(f"lunar_devkit_prep_profile({region}, 0);") == 1
    with pytest.raises(ValueError):
        module.instrument_prep_profile(original.replace("mod_plan_build(" if planner else "static void play_on(", "changed(", 1), planner)
    if planner:
        with pytest.raises(ValueError, match="early return"):
            module.instrument_prep_profile(original.replace("void mod_plan_build(fm1_mod_t *m) {", "void mod_plan_build(fm1_mod_t *m) { return;", 1), True)
    else:
        for anchor in ("seq_flush(a);", "a->seq_last_n = fm1_seq_host_advance(&a->seq_host, n);",
                       "fm1_seq_host_dispatch_slots_ticks(&a->seq_host, n, slot, FM1_APP_SOUNDS, &hook);",
                       "float *b = a->mix[k];"):
            with pytest.raises(ValueError):
                module.instrument_prep_profile(original.replace(anchor, "changed();", 1))
        with pytest.raises(ValueError, match="dispatch definition"):
            module.instrument_prep_profile(original.replace("static void render_sounds(fm1_app_t *a, uint32_t n, float *out) {",
                                                            "static void render_sounds(fm1_app_t *a, uint32_t n, float *out) { return;", 1))


def test_dispatch_profile_preserves_calls_and_refuses_drift():
    import importlib.util
    spec = importlib.util.spec_from_file_location("dispatch_profile", ROOT / "tools/jieli/prepare-renderer-devkit.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    regions = []
    for path, functions in module.DISPATCH_PROFILE_CALLS.items():
        original = (ROOT / path).read_text()
        observed = module.instrument_dispatch_profile(original, functions)
        normalized = observed.split("\n", 1)[1]
        normalized = re.sub(r"^ *lunar_devkit_prep_profile\(\d+, [01]\);\n", "", normalized, flags=re.M)
        assert re.sub(r"\s+", "", normalized) == re.sub(r"\s+", "", original)
        for signature, calls in functions:
            with pytest.raises(ValueError, match="dispatch definition"):
                module.instrument_dispatch_profile(original.replace(signature, "changed", 1), functions)
            with pytest.raises(ValueError, match="dispatch definition"):
                module.instrument_dispatch_profile(original + "\n" + original, functions)
            for region, call in calls:
                regions.append(region)
                assert observed.count(f"lunar_devkit_prep_profile({region}, 1);") == 1
                assert observed.count(f"lunar_devkit_prep_profile({region}, 0);") == 1
                with pytest.raises(ValueError, match="dispatch call"):
                    module.instrument_dispatch_profile(original.replace(call, "changed();", 1), functions)
    assert sorted(regions) == list(range(12, 24))


def test_preparation_profile_cli_registered_before_parsing(tmp_path):
    result = subprocess.run([sys.executable, str(ROOT / "tools/jieli/prepare-renderer-devkit.py"),
                             "--sdk", str(tmp_path / "absent"), "--source", str(ROOT),
                             "--out", str(tmp_path / "out"), "--prep-profile"],
                            capture_output=True, text=True)
    assert result.returncode != 0
    assert "Preparation profiling requires" in result.stderr
    assert "unrecognized arguments" not in result.stderr
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("selection", ["HOOK_RAM_FUNCTIONS", "MODULE_RAM_FUNCTIONS", "KIND_RAM_FUNCTIONS", "EVENT_RAM_FUNCTIONS", "PLAN_RAM_FUNCTIONS"])
def test_hook_ram_preserves_definitions_and_refuses_source_drift(selection):
    import importlib.util
    spec = importlib.util.spec_from_file_location("renderer_prepare", ROOT / "tools/jieli/prepare-renderer-devkit.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for name, signatures in getattr(module, selection).items():
        original = (ROOT / name).read_bytes()
        placed = module.place_hook_ram(original, signatures)
        assert placed.count(b'#pragma code_seg(".volatile_ram_code")') == len(signatures)
        assert placed.replace(b'#pragma code_seg(".volatile_ram_code")\n', b'').replace(b'\n#pragma code_seg()', b'') == original
        with pytest.raises(ValueError, match="Unexpected hook definition"):
            module.place_hook_ram(original + original, signatures)
        with pytest.raises(ValueError, match="Unexpected hook definition"):
            module.place_hook_ram(original.replace(signatures[0], b"missing_hook", 1), signatures)
