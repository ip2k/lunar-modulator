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
const float kRates[] = {44118.0f, 47872.34f};
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
    {0, 1, 48, 64}, {160, 1, 49, 65}, {320, 1, 50, 66},
    {480, 1, 51, 67}, {640, 1, 52, 68}, {800, 1, 53, 69},
    {960, 1, 54, 70}, {1120, 1, 55, 71}, {1280, 1, 56, 72},
    {1600, 1, 48, 32}, {3200, 0, 48, 0}, {3360, 0, 49, 0},
    {3520, 0, 50, 0}, {3680, 0, 51, 0}, {3840, 0, 52, 0},
    {4000, 0, 53, 0}, {4160, 0, 54, 0}, {4320, 0, 55, 0},
    {4480, 0, 56, 0},
    {6400, 1, 60, 96}, {9600, 1, 64, 127}, {11200, 0, 60, 0},
    {12800, 1, 64, 32}, {14400, 1, 67, 110}, {16000, 0, 64, 0},
    {17600, 1, 72, 1}, {19200, 0, 67, 0}, {20800, 1, 60, 127},
    {21600, 0, 72, 0}, {22400, 0, 60, 0},
};

bool Render(const fm1_engine_t *engine, unsigned char *memory, float *audio,
            float rate, uint8_t voice_mode) {
  fm1_host_t host = {FM1_ENGINE_API_VERSION, rate, 16};
  if (engine->instance_size(&host) > 65536) return false;
  memset(memory, 0xA5, 65536);
  void *state = engine->create(memory, &host);
  if (!state) return false;
  uint16_t voice_mode_param = 0xFFFF;
  for (uint16_t i = 0; i < engine->n_params; ++i) {
    if (strcmp(engine->params[i].name, "Voice Mode") == 0) voice_mode_param = i;
  }
  if (voice_mode_param == 0xFFFF) return false;
  engine->set_param(state, voice_mode_param, voice_mode);
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
  const char *const modes[] = {"Poly", "Mono", "Legato"};
  uint32_t scenarios = 0;
  for (size_t r = 0; r < sizeof(kRates) / sizeof(kRates[0]); ++r) {
    for (uint8_t mode = 0; mode < sizeof(modes) / sizeof(modes[0]); ++mode) {
      if (!Render(kReference, kRefMem, kRefAudio, kRates[r], mode) ||
          !Render(kCached, kCachedMem, kCachedAudio, kRates[r], mode)) {
        fprintf(stderr, "could not create Six-Op %s comparison at %.2f Hz\n",
                modes[mode], kRates[r]);
        return 1;
      }
      if (memcmp(kRefAudio, kCachedAudio, sizeof(kRefAudio)) != 0) {
        for (uint32_t i = 0; i < 2 * kFrames; ++i) {
          if (memcmp(&kRefAudio[i], &kCachedAudio[i], sizeof(float)) != 0) {
            fprintf(stderr,
                    "first %s mismatch at %.2f Hz, sample %u: %.9g != %.9g\n",
                    modes[mode], kRates[r], i, kRefAudio[i], kCachedAudio[i]);
            return 1;
          }
        }
        return 1;
      }
      ++scenarios;
    }
  }
  printf("Six-Op cached accent: %u mode/rate scenarios, %u stereo frames each, bitwise equal\n",
         scenarios, kFrames);
  return 0;
}
