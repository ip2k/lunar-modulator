"""Exact shared-app replay for the explicitly prepared whole-engine queue."""
import importlib.util
import os
from pathlib import Path
import shutil
import shlex
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("queue_profile,worker_drums", [(p, d) for p in
    (False, True, "detail", "micro", "mod_micro", "module_micro") for d in (False, True)] +
    [("insert", False), ("insert_profile", False), ("caller_post", False), ("caller_post_ready", False)])
def test_whole_engine_queue_prepared_pcm(tmp_path, monkeypatch, worker_drums, queue_profile):
    drums_ready = queue_profile == "caller_post_ready"
    caller_post = drums_ready or queue_profile == "caller_post"
    insert = caller_post or queue_profile in ("insert", "insert_profile")
    profiling = bool(queue_profile) and queue_profile != "insert"
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
    if queue_profile in ("mod_micro", "module_micro"):
        # Copy only the two changed files; never modify symlinked real sources.
        (shadow / "engines/mod").mkdir(parents=True)
        for path in (ROOT / "engines").iterdir():
            if path.name != "mod":
                (shadow / "engines" / path.name).symlink_to(path, target_is_directory=path.is_dir())
        for path in (ROOT / "engines/mod").iterdir():
            destination = shadow / "engines/mod" / path.name
            if path.name in ("mod_core.c", "mod_glue.c"):
                unit = "core" if path.name == "mod_core.c" else "glue"
                destination.write_text(prepare.queue_modulation_micro(path.read_text(), unit, queue_profile == "module_micro"))
            else:
                destination.symlink_to(path, target_is_directory=path.is_dir())
    elif drums_ready:
        # Only the prepared header and Drums TU are writable; other sources stay read-only links.
        for directory in (ROOT / "engines").iterdir():
            destination = shadow / "engines" / directory.name
            if directory.name in ("include", "src"):
                destination.mkdir(parents=True)
                for item in directory.iterdir():
                    if item.name not in ("fm1_resampler.h", "drums.cc"):
                        (destination / item.name).symlink_to(item, target_is_directory=item.is_dir())
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.symlink_to(directory, target_is_directory=directory.is_dir())
        header = prepare.unroll_resampler_lowpass((ROOT / "engines/include/fm1_resampler.h").read_text())
        header, drums = prepare.drums_ready_conversion(header, (ROOT / "engines/src/drums.cc").read_text())
        (shadow / "engines/include/fm1_resampler.h").write_text(header)
        (shadow / "engines/src/drums.cc").write_text(drums)
    else:
        (shadow / "engines").symlink_to(ROOT / "engines", target_is_directory=True)
    shutil.copytree(ROOT / "firmware/devkit", shadow / "firmware/devkit")
    (shadow / "sim/web/mk").symlink_to(ROOT / "sim/web/mk", target_is_directory=True)
    for path in (ROOT / "sim/web/src").iterdir():
        destination = shadow / "sim/web/src" / path.name
        if path.name == "fm1_app.c":
            text = prepare.queue_engine_callbacks(path.read_text())
            if insert:
                text = prepare.queue_insert_callbacks(text, caller_post)
                text += "\nint lunar_test_post_layout(const fm1_app_t *a) { return lunar_post_layout_valid(a); }\nint lunar_test_post_begin(fm1_app_t *a) { return lunar_queue_begin(a); }\n"
            destination.write_text(prepare.queue_micro_callbacks(text, queue_profile in ("mod_micro", "module_micro"))
                                   if queue_profile in ("micro", "mod_micro", "module_micro") else text)
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
static bool fault, layout_only;
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
  layout_only=getenv("LUNAR_QUEUE_LAYOUT_ONLY")!=0;
  if(fault || layout_only) return;
  worker=std::thread([this]{while(!stop.load()) {
   lunar_renderer_queue_worker_step(); std::this_thread::yield();
  }});
 }
 ~Host() {
  stop=true;
  if(layout_only) { assert(!worker.joinable() && !lunar_renderer_queue_completed()); return; }
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
    if queue_profile in ("detail", "micro", "mod_micro", "module_micro"):
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
        if queue_profile in ("micro", "mod_micro", "module_micro"):
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
        if queue_profile in ("micro", "mod_micro", "module_micro"):
            counts = ("assert(calls[20] >= 1); for(unsigned i=21;i<26;++i) assert(calls[i] == 5*calls[20]);"
                      if queue_profile == "module_micro" else
                      "for(unsigned i=20;i<26;++i) assert(calls[i] >= 1 && calls[i] == calls[20]);"
                      if queue_profile == "mod_micro" else
                      "assert(calls[20] == 1 && calls[23] >= 1); assert(calls[22] == 0 && calls[24] == 0);")
            text = text.replace("MICRO_CONTROL_COUNTS", counts)
        reference.write_text(text)
    renderer.ROOT = shadow
    monkeypatch.setenv("FM1_SIM_EXTRA", os.environ.get("FM1_SIM_EXTRA", "") +
                       " -DLUNAR_DEVKIT_ENGINE_QUEUE=1 -DLUNAR_QUEUE_HOST_TEST=1"
                       " -pthread -I" + str(shadow / "firmware/devkit"))
    if insert:
        monkeypatch.setenv("FM1_SIM_EXTRA", os.environ["FM1_SIM_EXTRA"] + " -DLUNAR_QUEUE_POST=1")
    if caller_post:
        monkeypatch.setenv("FM1_SIM_EXTRA", os.environ["FM1_SIM_EXTRA"] + " -DLUNAR_QUEUE_CALLER_POST=1")
    if worker_drums:
        monkeypatch.setenv("FM1_SIM_EXTRA", os.environ["FM1_SIM_EXTRA"] +
                           " -DLUNAR_QUEUE_WORKER_DRUMS=1")
    if profiling:
        monkeypatch.setenv("FM1_SIM_EXTRA", os.environ["FM1_SIM_EXTRA"] +
                           " -DLUNAR_QUEUE_PROFILE=1")
    if queue_profile in ("detail", "micro", "mod_micro", "module_micro"):
        monkeypatch.setenv("FM1_SIM_EXTRA", os.environ["FM1_SIM_EXTRA"] +
                           " -DLUNAR_QUEUE_DETAIL=1")
    if queue_profile in ("micro", "mod_micro", "module_micro"):
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
    if insert:
        guard = tmp_path / "insert-guard.cc"
        guard.write_text(r'''
extern "C" {
#include "fm1_app.h"
int lunar_test_post_layout(const fm1_app_t *);
int lunar_test_post_begin(fm1_app_t *);
#include "renderer_queue_bridge.h"
}
#include <cassert>
#include <cstring>
static fm1_app_t a;
static unsigned char memory[FM1_APP_UNITS][128];
static void unit(int id, const fm1_engine_t *engine) {
 a.unit[id].e=engine; a.unit[id].self=a.unit[id].mem=memory[id];
 a.unit[id].bytes=64; a.unit[id].cap=128;
}
int main() {
 const int sound=fm1_app_sound_unit(1), fx=fm1_app_insert_unit(1,0), fx2=fm1_app_insert_unit(1,1);
 const fm1_engine_t *macro=fm1_engine_find("macro"), *drive=fm1_engine_find("drive");
 assert(macro && drive); unit(sound,macro); assert(lunar_test_post_layout(&a));
 unit(fx,drive); assert(lunar_test_post_layout(&a));
 unit(fx2,drive); assert(lunar_test_post_layout(&a));
 a.unit[sound].value[0]=1; assert(!lunar_test_post_layout(&a)); a.unit[sound].value[0]=0;
 a.unit[fx].e=fm1_engine_find("filter"); assert(!lunar_test_post_layout(&a)); a.unit[fx].e=drive;
 a.unit[fx].self=memory[sound]; assert(!lunar_test_post_layout(&a)); a.unit[fx].self=memory[fx];
 a.unit[fx].mem=memory[sound]+1; a.unit[fx].self=a.unit[fx].mem;
 assert(!lunar_test_post_layout(&a)); a.unit[fx].self=a.unit[fx].mem=memory[fx];
 a.unit[fx].bytes=129; assert(!lunar_test_post_layout(&a)); a.unit[fx].bytes=64;
 a.unit[fx].self=0; assert(!lunar_test_post_layout(&a)); a.unit[fx].self=memory[fx];
 unit(fm1_app_sound_unit(0),fm1_engine_find("dx7"));
 a.unit[fm1_app_sound_unit(0)].self=memory[fx]+1; assert(!lunar_test_post_layout(&a));
 a.unit[fm1_app_sound_unit(0)].self=memory[fm1_app_sound_unit(0)]; assert(lunar_test_post_layout(&a));
 a.unit[fx].e=fm1_engine_find("filter");
 assert(!lunar_test_post_begin(&a) && lunar_renderer_queue_error());
 assert(lunar_renderer_queue_worker_step()==0 && !lunar_renderer_queue_begin());
}
''')
        if caller_post:
            # Every moved sound/insert arena is validated, including unused tails.
            guard.write_text(guard.read_text().replace('#include <cstring>', '#include <cstring>\n#include <cstdlib>').replace(
                'assert(macro && drive); unit(sound,macro);',
                'assert(macro && drive); for(unsigned s=0;s<4;++s) unit(fm1_app_sound_unit(s),fm1_engine_find(s==1?"macro":s==2?"drums":"dx7")); unit(sound,macro);').replace(
                ' a.unit[fx].e=fm1_engine_find("filter");\n assert(!lunar_test_post_begin',
                r''' const int callerfx=fm1_app_insert_unit(0,0);
 unit(callerfx,fm1_engine_find("filter")); assert(lunar_test_post_layout(&a));
 for(unsigned s=0;s<4;++s) for(unsigned j=0;j<2;++j) {
   const int id=fm1_app_insert_unit(s,j); const fm1_app_unit_t saved=a.unit[id];
   unit(id,fm1_engine_find(s==0?"filter":"drive"));
   if(s<2) assert(lunar_test_post_layout(&a)); else assert(!lunar_test_post_layout(&a));
   a.unit[id]=saved;
 }
 const fm1_app_unit_t saved=a.unit[callerfx];
 a.unit[callerfx].e=fm1_engine_find("drive"); assert(!lunar_test_post_layout(&a)); a.unit[callerfx]=saved;
 a.unit[callerfx].self=a.unit[callerfx].mem=memory[sound]+80; assert(!lunar_test_post_layout(&a)); a.unit[callerfx]=saved;
 a.unit[callerfx].self=a.unit[callerfx].mem=(unsigned char*)(UINTPTR_MAX-32); assert(!lunar_test_post_layout(&a)); a.unit[callerfx]=saved;
 a.unit[callerfx].cap=63; assert(!lunar_test_post_layout(&a)); a.unit[callerfx]=saved;
 a.unit[callerfx].self=0; assert(!lunar_test_post_layout(&a)); a.unit[callerfx]=saved;
 // Cached approvals must notice changes to unselected live arenas as well.
 const int master=1;
 const fm1_app_unit_t master_saved=a.unit[master];
 unit(master,fm1_engine_find("echo")); assert(lunar_test_post_layout(&a));
 a.unit[master].self=a.unit[master].mem=memory[sound]+80;
 assert(!lunar_test_post_layout(&a));
 a.unit[master]=master_saved; assert(lunar_test_post_layout(&a));
 // Switching app identity must revalidate even after another app was sealed.
 static fm1_app_t other; other=a;
 assert(lunar_test_post_layout(&other));
 other.unit[callerfx].cap=63; assert(!lunar_test_post_layout(&other));
 assert(lunar_test_post_layout(&a));
 // Change only the unused tail of an arena: full-cap overlap is still illegal.
 const size_t oldcap=a.unit[sound].cap;
 a.unit[sound].cap=sizeof(memory); assert(!lunar_test_post_layout(&a));
 a.unit[sound].cap=oldcap; assert(lunar_test_post_layout(&a));
 const unsigned fault=(unsigned)atoi(getenv("LUNAR_LAYOUT_FAULT"));
 switch(fault) {
 case 0: a.unit[callerfx].e=fm1_engine_find("drive"); break;
 case 1: a.unit[callerfx].self=a.unit[callerfx].mem=memory[sound]+80; break;
 case 2: a.unit[callerfx].self=a.unit[callerfx].mem=(unsigned char*)(UINTPTR_MAX-32); break;
 case 3: a.unit[callerfx].cap=63; break;
 case 4: a.unit[callerfx].self=0; break;
 case 5: a.unit[fm1_app_sound_unit(3)].e=0; break;
 case 6: unit(fm1_app_insert_unit(2,1),drive); break;
 case 7: a.unit[callerfx].mem=memory[sound]; break;
 case 8: a.unit[callerfx].bytes=0; break;
 case 9: a.unit[sound].value[0]=1; break;
 }
 assert(!lunar_test_post_begin'''))
        guard_exe = tmp_path / "insert-guard"
        subprocess.run([os.environ.get("FM1_SIM_CXX", "c++"), "-std=c++11", "-pthread",
                        "-I" + str(shadow / "sim/web/src"), "-I" + str(ROOT / "engines/include"),
                        "-I" + str(ROOT / "engines/host"), str(guard), *objects,
                        *shlex.split(os.environ.get("FM1_SIM_EXTRA", "")), "-lm", "-o", str(guard_exe)], check=True)
        for fault in range(10 if caller_post else 1):
            subprocess.run([str(guard_exe)], check=True, timeout=30,
                           env=dict(os.environ, LUNAR_QUEUE_LAYOUT_ONLY="1", LUNAR_LAYOUT_FAULT=str(fault)))

    fault_exe = tmp_path / "fault"
    subprocess.run([os.environ.get("FM1_SIM_CXX", "c++"), "-std=c++11", "-pthread",
                    "-I" + str(shadow / "firmware/devkit"), "-I" + str(ROOT / "engines/include"),
                    str(harness), *objects, *shlex.split(os.environ.get("FM1_SIM_EXTRA", "")),
                    "-lm", "-o", str(fault_exe)], check=True)
    subprocess.run([str(fault_exe)], check=True,
                   env=dict(os.environ, LUNAR_QUEUE_INJECT_TIMEOUT="1"), timeout=30)


@pytest.mark.parametrize("options", [
    {"engine_queue_caller_post": True},
    {"engine_queue": True, "engine_queue_caller_post": True},
    {"engine_queue_insert": True},
    {"engine_queue": True, "engine_queue_insert": True, "engine_queue_drums": True},
    {"engine_queue": True, "engine_queue_insert": True, "engine_queue_detail": True},
    {"engine_queue_module_micro": True},
    {"engine_queue_micro": True, "engine_queue_module_micro": True},
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


def test_module_component_micro_refuses_drift_and_keeps_glue_unmarked():
    prepare = load("queue_module_preparer", ROOT / "tools/jieli/prepare-renderer-devkit.py")
    core = (ROOT / "engines/mod/mod_core.c").read_text()
    glue = (ROOT / "engines/mod/mod_glue.c").read_text()
    assert prepare.queue_modulation_micro(glue, "glue", modules=True) == glue
    transformed = prepare.queue_modulation_micro(core, "core", modules=True)
    for region in range(20, 26):
        assert transformed.count(f"QUEUE_MOD_MICRO({region}, 1);") == 1
        assert transformed.count(f"QUEUE_MOD_MICRO({region}, 0);") == 1
    assert "QUEUE_MOD_MICRO(21, 1);\n  for (i = 0; i < m->plan.n_order" not in transformed
    assert transformed.index("  if (!kd) return;", transformed.index("static void run_module")) < transformed.index("  QUEUE_MOD_MICRO(21, 1);")
    with pytest.raises(ValueError, match="boundary"):
        prepare.queue_modulation_micro(transformed, "core", modules=True)
    for old in ("  module_params(m, pos, kd, m->peff[pos]);",
                "  module_gates(m, pos, kd, gin, &m->gin_level[pos]);",
                "  kd->process(instance(m, pos), &io);",
                "  module_outputs(m, kd, out, gout, prev_end, NULL);"):
        with pytest.raises(ValueError, match="boundary"):
            prepare.queue_modulation_micro(core.replace(old, "changed_boundary();", 1), "core", modules=True)
