// SPDX-License-Identifier: MIT. FM6 kernel adapter differential/fault test.
#include "fm1_engine.h"
#include "fm1_dx7_kernel.h"
#include <atomic>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <thread>
extern "C" const fm1_engine_t fm1_engine_dx7;
struct Backend {
  int mode, calls;
  fm1_dx7_kernel_job_t late;
  std::atomic<bool> release;
  std::thread worker;
  Backend(int m): mode(m), calls(0), release(false) {}
};
static int Pair(void *ptr, fm1_dx7_kernel_job_t jobs[2]) {
  Backend &b = *static_cast<Backend *>(ptr); ++b.calls;
  if (b.mode == 0) {
    std::thread worker([&] { fm1_dx7_compute_kernel(&jobs[1]); });
    fm1_dx7_compute_kernel(&jobs[0]); worker.join(); return 1;
  }
  if (b.mode == 2 && b.calls == 1) {
    // A deliberately stalled job contains no pointer into the engine/call.
    b.late = jobs[1];
    b.worker = std::thread([&] {
      while (!b.release.load()) std::this_thread::yield();
      fm1_dx7_compute_kernel(&b.late);
    });
  }
  // Reject even after partial computation/corruption: engine must discard it.
  fm1_dx7_compute_kernel(&jobs[0]);
  std::memset(jobs, 0xa5, sizeof(*jobs) * 2); return 0;
}
int main(int argc, char **argv) {
  if (argc != 3) return 2;
  const float rate = std::atof(argv[1]); Backend backend(std::atoi(argv[2]));
  const fm1_engine_t &e = fm1_engine_dx7;
  fm1_host_t host = { FM1_ENGINE_API_VERSION, rate, 129 };
  const size_t size = (e.instance_size(&host) + 15) & ~size_t(15);
  void *memory[2] = {std::malloc(size + 15), std::malloc(size + 15)};
  if (!memory[0] || !memory[1]) return 3;
  void *instance[2];
  for (int i = 0; i < 2; ++i) {
    void *aligned = reinterpret_cast<void *>(
        (reinterpret_cast<uintptr_t>(memory[i]) + 15) & ~uintptr_t(15));
    instance[i] = e.create(aligned, &host);
  }
  if (!instance[0] || !instance[1]) return 3;
  fm1_dx7_kernel_adapter_t adapter = {Pair, &backend};
  fm1_dx7_set_kernel_adapter(instance[1], &adapter);
  float output[2][258]; const unsigned frames[] = {1, 7, 64, 129};
  for (unsigned call = 0; call < 768; ++call) {
    for (int which = 0; which < 2; ++which) {
      void *s = instance[which];
      if (call < 512) {
        if (!(call % 9)) {
          e.set_param(s, 0, (call / 9) % 32);
          e.note_on(s, 36 + (call / 9) % 35, 32 + call % 96);
        }
        if (!(call % 13)) e.note_off(s, 36 + (call / 13) % 35);
        if (!(call % 17)) e.set_param(s, 1, (call % 101) / 100.0f);
        if (!(call % 19)) e.set_param(s, 2, (call % 97) / 96.0f);
        if (!(call % 23)) e.set_param(s, 3, int(call % 15) - 7);
        if (!(call % 29)) e.pitch_bend(s, int(call % 13) - 6);
        if (!(call % 31)) e.set_param_note(s, 36 + (call / 9) % 35, 4, -0.2f);
      }
      if (call == 512) for (int key = 0; key < 128; ++key) e.note_off(s, key);
      // Detaching a backend does not wait for, or expose the engine to, late jobs.
      if (call == 640) fm1_dx7_set_kernel_adapter(s, NULL);
      e.render(s, output[which], frames[call % 4]);
    }
    if (std::memcmp(output[0], output[1], frames[call % 4] * 2 * sizeof(float))) {
      std::fprintf(stderr, "PCM mismatch call=%u rate=%g mode=%d\n", call, rate, backend.mode); return 4;
    }
  }
  if (!backend.calls) return 5;
  for (int i = 0; i < 2; ++i) { e.destroy(instance[i]); std::free(memory[i]); }
  if (backend.worker.joinable()) { backend.release.store(true); backend.worker.join(); }
  fm1_dx7_kernel_job_t invalid = {}; invalid.algorithm = 32;
  fm1_dx7_kernel_job_t before = invalid;
  if (fm1_dx7_compute_kernel(&invalid) || std::memcmp(&before, &invalid, sizeof invalid) ||
      fm1_dx7_compute_kernel(NULL)) return 6;
  std::printf("PASS exact PCM, retirement tails, detach/destruction, %d pair calls\n", backend.calls);
}
