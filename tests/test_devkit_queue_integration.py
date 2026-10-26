"""Exact shared-app replay for the explicitly prepared whole-engine queue."""
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("queue_profile", [False, True, "detail", "micro", "mod_micro"])
@pytest.mark.parametrize("worker_drums", [False, True])
def test_whole_engine_queue_prepared_pcm(tmp_path, monkeypatch, worker_drums, queue_profile):
    renderer = load("queue_renderer_reference", ROOT / "tests/test_devkit_renderer.py")
    prepare = load("queue_preparer", ROOT / "tools/jieli/prepare-renderer-devkit.py")
    # Compare queue scheduling with the same arithmetic policy on both builds.
    # Apple Silicon otherwise contracts the baseline while the queue does not.
    monkeypatch.setenv("FM1_SIM_EXTRA", os.environ.get("FM1_SIM_EXTRA", "") +
                       " -ffp-contract=off")
    baseline = renderer.build_reference(renderer.MODULES)
    expected = tmp_path / "baseline.pcm"
    subprocess.run([str(baseline), str(expected)], check=True, capture_output=True)
    shadow = tmp_path / "source"
    (shadow / "sim/web/src").mkdir(parents=True)
    (shadow / "tools/jieli").mkdir(parents=True)
    if queue_profile == "mod_micro":
        # Copy only the two changed files; never modify symlinked real sources.
        (shadow / "engines/mod").mkdir(parents=True)
        for path in (ROOT / "engines").iterdir():
            if path.name != "mod":
                (shadow / "engines" / path.name).symlink_to(path, target_is_directory=path.is_dir())
        for path in (ROOT / "engines/mod").iterdir():
            destination = shadow / "engines/mod" / path.name
            if path.name in ("mod_core.c", "mod_glue.c"):
                unit = "core" if path.name == "mod_core.c" else "glue"
                destination.write_text(prepare.queue_modulation_micro(path.read_text(), unit))
            else:
                destination.symlink_to(path, target_is_directory=path.is_dir())
    else:
        (shadow / "engines").symlink_to(ROOT / "engines", target_is_directory=True)
    shutil.copytree(ROOT / "firmware/devkit", shadow / "firmware/devkit")
    (shadow / "sim/web/mk").symlink_to(ROOT / "sim/web/mk", target_is_directory=True)
    for path in (ROOT / "sim/web/src").iterdir():
        destination = shadow / "sim/web/src" / path.name
        if path.name == "fm1_app.c":
            text = prepare.queue_engine_callbacks(path.read_text())
            destination.write_text(prepare.queue_micro_callbacks(text, queue_profile == "mod_micro")
                                   if queue_profile in ("micro", "mod_micro") else text)
        else:
            destination.symlink_to(path, target_is_directory=path.is_dir())
    mk = (ROOT / "tools/jieli/renderer.mk").read_text()
    mk = mk.replace("$(BUILD)/devkit/arithmetic_probe.o",
                    "$(BUILD)/devkit/arithmetic_probe.o $(BUILD)/devkit/queue_host_support.o", 1)
    (shadow / "tools/jieli/renderer.mk").write_text(mk)
    # Host-only startup/join; actual target construction/task startup are explicit.
    (shadow / "firmware/devkit/queue_host_support.cc").write_text(r'''
#include "renderer_queue_bridge.h"
#include <atomic>
#include <chrono>
#include <thread>
#include <cassert>
#include <cstdlib>
static bool fault;
static uint32_t fault_ticks;
static uint32_t now() {
 if(fault) return fault_ticks+=2000000u;
 std::this_thread::yield();
 return (uint32_t)std::chrono::duration_cast<std::chrono::microseconds>(
  std::chrono::steady_clock::now().time_since_epoch()).count();
}
struct Host {
 std::atomic<bool> stop;
 std::thread worker;
 Host():stop(false) {
  fault=getenv("LUNAR_QUEUE_INJECT_TIMEOUT")!=0;
  assert(lunar_renderer_queue_init(now,2000000));
  if(fault) return;
  worker=std::thread([this]{while(!stop.load()) {
   lunar_renderer_queue_worker_step(); std::this_thread::yield();
  }});
 }
 ~Host() {
  stop=true;
  if(fault) {
   assert(!worker.joinable() && lunar_renderer_queue_error());
   assert(lunar_renderer_queue_completed()==0);
   assert(lunar_renderer_queue_worker_step()==1); // Original app buffers still alive.
   assert(lunar_renderer_queue_worker_step()==0 && !lunar_renderer_queue_begin());
   return;
  }
  worker.join();
  assert(!lunar_renderer_queue_error());
  assert(lunar_renderer_queue_completed()==44104);
  const unsigned peaks[]={3,6,3,3};
  for(unsigned s=0;s<4;++s) assert(lunar_renderer_queue_peak(s)==peaks[s]);
 }
};
static Host host;
''')
    if queue_profile in ("detail", "micro", "mod_micro"):
        reference = shadow / "firmware/devkit/renderer_reference.c"
        text = reference.read_text().replace('#include "renderer_live.h"',
                    '#include "renderer_live.h"\n#include "renderer_queue_bridge.h"\n#include <assert.h>')
        old = "        lunar_devkit_renderer_render(output.samples);"
        assert text.count(old) == 1
        text = text.replace(old, old + """
        uint32_t detail[LUNAR_QUEUE_DETAILS];
        assert(lunar_renderer_queue_detail_read(detail));
        assert(!lunar_renderer_queue_detail_read(detail));
""")
        if queue_profile in ("micro", "mod_micro"):
            text = text.replace("        assert(!lunar_renderer_queue_detail_read(detail));", """
        assert(!lunar_renderer_queue_detail_read(detail));
        uint32_t micro[LUNAR_QUEUE_MICROS], calls[LUNAR_QUEUE_MICROS];
        assert(lunar_renderer_queue_micro_read(micro, calls));
        assert(calls[LUNAR_QUEUE_RENDER] >= 4);
        unsigned effects = 0;
        for (unsigned i = 6; i < 20; ++i) effects += calls[i];
        assert(effects >= 4);
        assert(LUNAR_QUEUE_MICROS == 26);
        MICRO_CONTROL_COUNTS
        assert(!lunar_renderer_queue_micro_read(micro, calls));
""")
        if queue_profile in ("micro", "mod_micro"):
            counts = ("for(unsigned i=20;i<26;++i) assert(calls[i] >= 1 && calls[i] == calls[20]);"
                      if queue_profile == "mod_micro" else
                      "assert(calls[20] == 1 && calls[23] >= 1); assert(calls[22] == 0 && calls[24] == 0);")
            text = text.replace("MICRO_CONTROL_COUNTS", counts)
        reference.write_text(text)
    renderer.ROOT = shadow
    monkeypatch.setenv("FM1_SIM_EXTRA", os.environ.get("FM1_SIM_EXTRA", "") +
                       " -DLUNAR_DEVKIT_ENGINE_QUEUE=1 -DLUNAR_QUEUE_HOST_TEST=1"
                       " -pthread -I" + str(shadow / "firmware/devkit"))
    if worker_drums:
        monkeypatch.setenv("FM1_SIM_EXTRA", os.environ["FM1_SIM_EXTRA"] +
                           " -DLUNAR_QUEUE_WORKER_DRUMS=1")
    if queue_profile:
        monkeypatch.setenv("FM1_SIM_EXTRA", os.environ["FM1_SIM_EXTRA"] +
                           " -DLUNAR_QUEUE_PROFILE=1")
    if queue_profile in ("detail", "micro", "mod_micro"):
        monkeypatch.setenv("FM1_SIM_EXTRA", os.environ["FM1_SIM_EXTRA"] +
                           " -DLUNAR_QUEUE_DETAIL=1")
    if queue_profile in ("micro", "mod_micro"):
        monkeypatch.setenv("FM1_SIM_EXTRA", os.environ["FM1_SIM_EXTRA"] +
                           " -DLUNAR_QUEUE_MICRO=1")
    target = renderer.build_reference(renderer.MODULES)
    actual = tmp_path / "queue.pcm"
    subprocess.run([str(target), str(actual)], check=True, capture_output=True, timeout=120)
    assert len(expected.read_bytes()) == 11290624
    assert actual.read_bytes() == expected.read_bytes()

    harness = tmp_path / "fault.cc"
    harness.write_text(r'''
extern "C" {
#include "renderer_timing.h"
}
#include "renderer_queue_bridge.h"
#include <cassert>
#include <cstring>
static unsigned emitted;
static uint32_t ticks;
static uint32_t now() { return ++ticks; }
static void yield() {}
static void emit(const lunar_renderer_timing *) { ++emitted; }
int main() {
 assert(!lunar_devkit_renderer_timing(now,yield,emit));
 assert(!emitted && lunar_renderer_queue_error());
 lunar_renderer_status state;
 lunar_devkit_renderer_status(&state);
 assert(!state.blocks && !state.completed_cases && !state.init_error);
 int16_t output[256], expected[256];
 memset(output,0x4a,sizeof output); memcpy(expected,output,sizeof output);
 lunar_devkit_renderer_render(output); // Permanent refusal before any next writes.
 assert(!memcmp(output,expected,sizeof output));
}
''')
    objects = sorted(str(p) for p in target.parent.rglob("*.o")
                     if p.name != "renderer_reference.o")
    fault_exe = tmp_path / "fault"
    subprocess.run([os.environ.get("FM1_SIM_CXX", "c++"), "-std=c++11", "-pthread",
                    "-I" + str(shadow / "firmware/devkit"), "-I" + str(ROOT / "engines/include"),
                    str(harness), *objects, "-lm", "-o", str(fault_exe)], check=True)
    subprocess.run([str(fault_exe)], check=True,
                   env=dict(os.environ, LUNAR_QUEUE_INJECT_TIMEOUT="1"), timeout=30)


@pytest.mark.parametrize("options", [
    {"engine_queue_mod_micro": True},
    {"engine_queue": True, "engine_queue_detail": True, "engine_queue_mod_micro": True},
    {"engine_queue_micro": True},
    {"engine_queue": True, "engine_queue_profile": True, "engine_queue_micro": True},
    {"engine_queue_detail": True},
    {"engine_queue": True, "engine_queue_detail": True},
    {"engine_queue_profile": True},
    {"engine_queue": True, "engine_queue_profile": True},
    {"engine_queue_drums": True},
    {"engine_queue": True, "engine_queue_drums": True},
    {"engine_queue": True},
    {"engine_queue": True, "timing_only": True, "hot_ram": True, "renderer_o3": True},
    {"engine_queue": True, "timing_only": True, "hot_ram": True, "renderer_o3": True,
     "outer_timing_only": True, "profile": True, "workload": "keys"},
    {"engine_queue": True, "fm6_pair": True},
    {"engine_queue": True, "scheduling_probe": True},
])
def test_queue_preparation_refuses_unsupported_combinations(tmp_path, options):
    prepare = load("queue_guard_preparer", ROOT / "tools/jieli/prepare-renderer-devkit.py")
    out = tmp_path / "out"
    with pytest.raises(ValueError):
        prepare.prepare_renderer(tmp_path / "absent-sdk", ROOT, out, **options)
    assert not out.exists()


def test_micro_control_hook_transformation_is_exact_and_refuses_drift():
    prepare = load("queue_control_preparer", ROOT / "tools/jieli/prepare-renderer-devkit.py")
    original = prepare.queue_engine_callbacks((ROOT / "sim/web/src/fm1_app.c").read_text())
    transformed = prepare.queue_micro_callbacks(original)
    for region, name in enumerate(("begin", "event", "lock", "tick", "lock_slot", "note_on"), 20):
        assert transformed.count(f"QUEUE_MICRO({region}, 1);") == 1
        assert transformed.count(f"QUEUE_MICRO({region}, 0);") == 1
        assert f"lunar_micro_{name}" in transformed
    with pytest.raises(ValueError, match="hook table"):
        prepare.queue_micro_callbacks(original.replace("a, seq_auto_begin,", "a, changed_begin,", 1))


def test_modulation_micro_boundaries_refuse_drift_and_nested_hooks():
    prepare = load("queue_modulation_preparer", ROOT / "tools/jieli/prepare-renderer-devkit.py")
    app = prepare.queue_engine_callbacks((ROOT / "sim/web/src/fm1_app.c").read_text())
    app = prepare.queue_micro_callbacks(app, modulation=True)
    assert "lunar_micro_tick" not in app
    assert "QUEUE_MICRO(23, 1)" not in app
    for unit, name, regions in (("core", "mod_core.c", range(20, 24)),
                                ("glue", "mod_glue.c", range(24, 26))):
        original = (ROOT / "engines/mod" / name).read_text()
        transformed = prepare.queue_modulation_micro(original, unit)
        for region in regions:
            assert transformed.count(f"QUEUE_MOD_MICRO({region}, 1);") == 1
            assert transformed.count(f"QUEUE_MOD_MICRO({region}, 0);") == 1
        with pytest.raises(ValueError, match="boundary"):
            prepare.queue_modulation_micro(transformed, unit)
        old = "take_system(m);" if unit == "core" else "g->sound_writes += k;"
        with pytest.raises(ValueError, match="boundary"):
            prepare.queue_modulation_micro(original.replace(old, "changed_boundary();", 1), unit)
    with pytest.raises(ValueError, match="Unknown"):
        prepare.queue_modulation_micro("", "unknown")
