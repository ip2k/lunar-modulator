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


@pytest.mark.parametrize("queue_profile", [False, True])
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
    (shadow / "engines").symlink_to(ROOT / "engines", target_is_directory=True)
    shutil.copytree(ROOT / "firmware/devkit", shadow / "firmware/devkit")
    (shadow / "sim/web/mk").symlink_to(ROOT / "sim/web/mk", target_is_directory=True)
    for path in (ROOT / "sim/web/src").iterdir():
        destination = shadow / "sim/web/src" / path.name
        if path.name == "fm1_app.c":
            destination.write_text(prepare.queue_engine_callbacks(path.read_text()))
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
