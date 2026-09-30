// schwung_race.cc -- fm1-schwung-race: a data-race probe for the Schwung shim,
// meaningful only under ThreadSanitizer (engines/schwung.md, "Threads").
//
// One sw-sophie and one sw-psxverb render on an "audio" thread while the main
// thread creates and destroys further instances of both, as a UI task would
// while sound plays. A create that rewrote anything a running instance reads
// (the module's API table, the shared host_api_v1_t) shows up as a race.
//
//   make -C engines clean
//   make -C engines EXTRA="-fsanitize=thread -g" OPT=-O1 build/fm1-schwung-race
//   engines/build/fm1-schwung-race     # exit 0 and no report = no race seen
//   make -C engines clean
//
// Not part of `all`, and not run by the tests: it needs a TSan build. A desktop
// tool: it allocates and starts a thread; the engines do neither. MIT licence.

#include "fm1_engine.h"

#include <atomic>
#include <cstdio>
#include <cstdlib>
#include <thread>
#include <vector>

extern "C" {
extern const fm1_engine_t fm1_engine_sw_sophie;
extern const fm1_engine_t fm1_engine_sw_psxverb;
}

namespace {

const fm1_host_t kHost = { FM1_ENGINE_API_VERSION, 44118.0f, 64 };

void *Make(const fm1_engine_t &e, std::vector<void *> *mems) {
  void *m = NULL;
  if (posix_memalign(&m, 16, e.instance_size(&kHost)) != 0) abort();
  mems->push_back(m);
  return e.create(m, &kHost);
}

}  // namespace

int main() {
  const fm1_engine_t &snd = fm1_engine_sw_sophie;
  const fm1_engine_t &fx = fm1_engine_sw_psxverb;
  std::vector<void *> mems;
  void *s = Make(snd, &mems);
  void *f = Make(fx, &mems);
  if (!s || !f) {
    fprintf(stderr, "create failed\n");
    return 1;
  }
  std::atomic<bool> stop(false);
  std::thread audio([&] {
    float buf[2 * 64];
    for (uint32_t n = 0; !stop.load(std::memory_order_relaxed); ++n) {
      if (n % 64 == 0) snd.note_on(s, static_cast<uint8_t>(36 + n / 64 % 16), 100);
      snd.render(s, buf, 64);
      fx.render(f, buf, 64);
    }
  });
  for (int i = 0; i < 50; ++i) {
    std::vector<void *> more;
    void *a = Make(fx, &more);
    void *b = Make(snd, &more);
    if (a) fx.destroy(a);
    if (b) snd.destroy(b);
    for (void *m : more) free(m);
  }
  stop = true;
  audio.join();
  snd.destroy(s);
  fx.destroy(f);
  for (void *m : mems) free(m);
  printf("{\"creates\":100,\"ok\":true}\n");
  return 0;
}
