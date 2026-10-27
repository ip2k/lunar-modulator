"""DX7 pristine reuse must not survive release or same-slot patch replacement.

The reference instance forces the original full Start initialization before each
NoteOn. Both instances use current DSP; compare every original Instance byte
(and an owned frequency table), then PCM. Only the appended reuse metadata and
test-only hit counter are excluded. No Git history or persistent traces needed.
"""
import os
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
ENGINES = ROOT / "engines"


def _once(source, old, new):
    assert source.count(old) == 1, old
    return source.replace(old, new)


@pytest.fixture(scope="module", params=[False, True], ids=["normal", "asan-ubsan"])
def lifecycle_binary(request, tmp_path_factory):
    compiler = shutil.which(os.environ.get("CXX", "clang++"))
    if not compiler:
        pytest.skip("C++ compiler unavailable")
    work = tmp_path_factory.mktemp("dx7-pristine")
    source = (ENGINES / "src/msfa_dx7.cc").read_text()
    source = _once(source, "  unsigned voice_limit_;", r'''
 public:
  void TestForceOriginalStart() { pristine_mask_ = 0; }
  unsigned TestReuseHits() const { return test_reuse_hits_; }
  bool TestPristine() const { return pristine_mask_ != 0; }
  bool TestOriginalStateEquals(const Instance &other) const {
    // All original fields precede and include own_lut_. Reuse metadata was
    // appended after it; neither instance has a kernel adapter bound.
    if (memcmp(this, &other, offsetof(Instance, own_lut_) + sizeof(own_lut_))) return false;
    if (own_lut_ && memcmp(reinterpret_cast<const unsigned char *>(this) + sizeof(Instance),
                          reinterpret_cast<const unsigned char *>(&other) + sizeof(Instance),
                          sizeof(int32_t) * fm1_msfa::kFreqLutSize)) return false;
    return true;
  }
 private:
  unsigned voice_limit_;''')
    source = _once(source, "  uint8_t init_velocity_[kNumVoices];",
                   "  uint8_t init_velocity_[kNumVoices];\n  unsigned test_reuse_hits_;")
    source = _once(source, "        return;  /* NoteOn still calls glide.Begin and glide.StartFor. */",
                   "        ++test_reuse_hits_;\n        return;  /* NoteOn still calls glide.Begin and glide.StartFor. */")
    (work / "engine.cc").write_text(source)
    harness = work / "lifecycle.cc"
    harness.write_text(r'''
#include <cassert>
#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <cstdio>
#include "engine.cc"

using fm1::dx7::Instance;
using namespace fm1::dx7;
struct Pair {
  void *ma, *mb;
  Instance *a, *b;
  unsigned snapshots;
  Pair(unsigned rate) : snapshots(0) {
    fm1_host_t h = {FM1_ENGINE_API_VERSION, static_cast<float>(rate), 129};
    const size_t bytes = InstanceSize(&h);
    ma = calloc(1, bytes); mb = calloc(1, bytes); assert(ma && mb);
    a = static_cast<Instance *>(Create(ma, &h));
    b = static_cast<Instance *>(Create(mb, &h)); assert(a && b);
    assert(a->SetVoiceLimit(1) && b->SetVoiceLimit(1));
    a->SetParam(P_PATCH, 32); b->SetParam(P_PATCH, 32);
    check();
  }
  ~Pair() { Destroy(a); Destroy(b); free(ma); free(mb); }
  void check() { assert(a->TestOriginalStateEquals(*b)); ++snapshots; }
  void store(const uint8_t *patch) {
    assert(a->SetUserVoice(0, patch)); assert(b->SetUserVoice(0, patch)); check();
  }
  void note(uint8_t key, bool hit) {
    const unsigned before = a->TestReuseHits();
    b->TestForceOriginalStart();
    a->NoteOn(key, 90); b->NoteOn(key, 90);
    assert(a->TestReuseHits() - before == static_cast<unsigned>(hit));
    check();
  }
  void off(uint8_t key) { a->NoteOff(key); b->NoteOff(key); check(); }
  void audio() {
    const unsigned sizes[] = {1, 7, 64, 129, 64};
    float x[258], y[258];
    for (unsigned n : sizes) {
      a->Render(x, n); b->Render(y, n);
      assert(!memcmp(x, y, n * 2 * sizeof(float))); check();
    }
  }
};
int main(int argc, char **argv) {
  assert(argc == 2); const unsigned rate = static_cast<unsigned>(atoi(argv[1]));
  uint8_t original[FM1_DX7_VCED_BYTES], changed[FM1_DX7_VCED_BYTES];
  memcpy(original, kInitVoice, sizeof original);
  for (unsigned op=0; op<6; ++op) {
    uint8_t *o=original+op*kOpBytes;
    o[OP_R1]=80; o[OP_R1+1]=60; o[OP_R1+2]=40; o[OP_R1+3]=30;
    o[OP_L1]=99; o[OP_L1+1]=85; o[OP_L1+2]=70; o[OP_L1+3]=0;
    o[OP_LD]=o[OP_RD]=0; o[OP_RS]=1; o[OP_OL]=80;
    o[OP_MODE]=op&1; o[OP_FC]=1;
  }
  original[V_ALG]=31; original[V_TRNSP]=24;
  memcpy(changed, original, sizeof changed);
  changed[OP_R1]=25; changed[OP_L1]=40; changed[OP_OL]=55;
  changed[V_PR1]=33; changed[V_PL1]=70;
  unsigned snapshots=0;
  {
    Pair p(rate); p.store(original);
    p.note(48,false); p.note(49,true); assert(p.a->TestPristine());
    // No render between release and retrigger: keydown(false) changed both
    // envelopes even though patch, velocity and key-rate group still match.
    p.off(49); p.note(50,false); p.note(51,true); p.audio();
    snapshots+=p.snapshots;
  }
  {
    Pair p(rate); p.store(original);
    p.note(48,false); p.note(49,true); assert(p.a->TestPristine());
    // Same slot/index, different envelope bytes; no intervening render.
    p.store(changed); p.note(50,false); p.note(51,true);
    // Restore the original slot while the changed initialization is pristine.
    p.store(original); p.note(52,false); p.note(53,true); p.audio();
    snapshots+=p.snapshots;
  }
  {
    Pair p(rate); p.store(original);
    p.note(48,false); p.note(49,true); assert(p.a->TestPristine());
    // A change-and-restore transaction cannot revive a stale validity bit.
    p.store(changed); p.store(original); p.note(50,false); p.audio();
    snapshots+=p.snapshots;
  }
  printf("PASS pristine release/store original-state+PCM snapshots=%u\n",snapshots);
}
''')
    flags = ["-std=c++11", "-O2", "-fno-exceptions", "-fno-rtti", "-DTEST",
             "-ffp-contract=off", "-fwrapv", "-I"+str(ENGINES/"include"),
             "-I"+str(ENGINES/"src"), "-isystem", str(ENGINES/"third_party/msfa")]
    if request.param:
        # Vendored msfa relies on signed fixed-point shifts; existing engine
        # sanitizer proofs exclude that legacy category, not memory errors.
        flags += ["-fsanitize=address,undefined", "-fno-sanitize=shift",
                  "-fno-omit-frame-pointer"]
    objects = []
    for unit in ["dx7note", "env", "fm_core", "fm_op_kernel", "freqlut", "lfo", "patch", "pitchenv"]:
        obj = work / (unit+".o")
        subprocess.run([compiler, *flags, '-DFM1_MSFA_UNIT="'+unit+'.cc"', "-c",
                        str(ENGINES/"src/msfa_unit.cc"), "-o", str(obj)], check=True, timeout=60)
        objects.append(str(obj))
    binary = work / "lifecycle"
    sources = [ENGINES/"src"/(unit+".cc") for unit in ["dx7_voice", "dx7_loop", "msfa_tables", "msfa_rom"]]
    subprocess.run([compiler, *flags, str(harness), *map(str, sources), *objects,
                    "-o", str(binary)], check=True, timeout=120)
    return binary


@pytest.mark.parametrize("rate", [44118, 96000], ids=["shared-lut", "owned-lut"])
def test_pristine_invalidated_before_next_note(lifecycle_binary, rate):
    result = subprocess.run([str(lifecycle_binary), str(rate)], check=True,
                            capture_output=True, text=True, timeout=10)
    assert result.stdout.startswith("PASS pristine release/store original-state+PCM"), result.stdout
