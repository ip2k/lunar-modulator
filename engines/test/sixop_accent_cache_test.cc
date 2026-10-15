// Compare complete Six-Op renders against the pre-cache per-block accent
// calculation, including retriggers with changed velocity, releases and voice
// allocation pressure. This is a host equivalence test, not a timing test.

#define sixop sixop_reference
#define fm1_engine_sixop fm1_engine_sixop_reference
#define FM1_SIXOP_TEST_REFERENCE_ACCENT
#include "../src/mi_sixop.cc"
#undef FM1_SIXOP_TEST_REFERENCE_ACCENT
#undef fm1_engine_sixop
#undef sixop

#include "../src/mi_sixop.cc"

#include <stdint.h>
#include <stdio.h>
#include <string.h>

namespace {

const fm1_engine_t *kReference = &fm1_engine_sixop_reference;
const fm1_engine_t *kCached = &fm1_engine_sixop;
const float kRate = 47872.34f;
const uint32_t kFrames = 24000;
alignas(16) unsigned char kRefMem[65536];
alignas(16) unsigned char kCachedMem[65536];
float kRefAudio[2 * kFrames];
float kCachedAudio[2 * kFrames];

struct Event {
  uint32_t frame;
  uint8_t on;
  uint8_t key;
  uint8_t velocity;
};

const Event kEvents[] = {
    {0, 1, 60, 96}, {3200, 1, 64, 127}, {6400, 0, 60, 0},
    {8000, 1, 64, 32}, {11200, 1, 67, 110}, {12800, 0, 64, 0},
    {16000, 1, 72, 1}, {17600, 0, 67, 0}, {19200, 1, 60, 127},
    {20800, 0, 72, 0}, {22400, 0, 60, 0},
};

bool Render(const fm1_engine_t *engine, unsigned char *memory, float *audio) {
  fm1_host_t host = {FM1_ENGINE_API_VERSION, kRate, 16};
  if (engine->instance_size(&host) > 65536) return false;
  memset(memory, 0xA5, 65536);
  void *state = engine->create(memory, &host);
  if (!state) return false;
  for (uint32_t frame = 0, event = 0; frame < kFrames; frame += 16) {
    while (event < sizeof(kEvents) / sizeof(kEvents[0]) &&
           kEvents[event].frame == frame) {
      const Event &e = kEvents[event++];
      if (e.on) engine->note_on(state, e.key, e.velocity);
      else engine->note_off(state, e.key);
    }
    engine->render(state, audio + 2 * frame, 16);
  }
  engine->destroy(state);
  return true;
}

}  // namespace

int main() {
  if (!Render(kReference, kRefMem, kRefAudio) ||
      !Render(kCached, kCachedMem, kCachedAudio)) {
    fprintf(stderr, "could not create Six-Op comparison instances\n");
    return 1;
  }
  if (memcmp(kRefAudio, kCachedAudio, sizeof(kRefAudio)) != 0) {
    for (uint32_t i = 0; i < 2 * kFrames; ++i) {
      if (memcmp(&kRefAudio[i], &kCachedAudio[i], sizeof(float)) != 0) {
        fprintf(stderr, "first output mismatch at sample %u: %.9g != %.9g\n",
                i, kRefAudio[i], kCachedAudio[i]);
        return 1;
      }
    }
    return 1;
  }
  printf("Six-Op cached accent: %u stereo frames bitwise equal across retriggers/releases\n",
         kFrames);
  return 0;
}
