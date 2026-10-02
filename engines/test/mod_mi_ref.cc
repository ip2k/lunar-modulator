// mod_mi_ref.cc -- fm1-mod-mi-ref: the C ports in engines/mod/mod_mi.c
// against the Mutable Instruments originals they were ported from, compiled
// from the vendored, unmodified files (engines/third_party/mutable, eurorack
// 08460a6): Peaks' BouncingBall, PulseShaper and PulseRandomizer and Braids'
// Quantizer (Emilie Gillet, MIT), docs/16 MG2.
//
//   - the tables: Peaks' lut_delay_times and lut_gravity and Braids' 49
//     scales, element by element;
//   - each port call by call (sample by sample for the ball) over random
//     knob settings, reconfigured as it runs, and random triggers: every
//     output must be identical. The randomizer runs on stmlib::Random
//     seeded with the port's state;
//   - Bounce and Burst as kinds, through the modulation runtime at host
//     blocks of 64 with notes at random frames: Bounce's OUT at every tick is
//     the original ball's output after the last 48 kHz sample before the
//     tick, and Burst's OUT edges sit where the original shaper's output
//     changes, its calls at 12 kHz (docs/16 §2.6's accumulator).
//
// Prints one JSON line of counts; exits 1 after reporting the first
// mismatch. Desktop test code, MIT licence; the vendored files keep theirs.
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <vector>

#include "peaks/modulations/bouncing_ball.h"
#include "peaks/pulse_processor/pulse_randomizer.h"
#include "peaks/pulse_processor/pulse_shaper.h"
#include "peaks/resources.h"
#include "braids/quantizer.h"
#include "braids/quantizer_scales.h"
#include "stmlib/utils/random.h"

#include "fm1_mod.h"
#include "../mod/mod_mi.h"

namespace {

int failed = 0;

#define CHECK(c)                                                               \
  do {                                                                         \
    if (!(c) && !failed) {                                                     \
      fprintf(stderr, "%s:%d: check failed: %s\n", __FILE__, __LINE__, #c);   \
      failed = 1;                                                              \
    }                                                                          \
  } while (0)

uint32_t rnd_state = 0x1234567u;
uint32_t Rnd() {
  rnd_state ^= rnd_state << 13;
  rnd_state ^= rnd_state >> 17;
  rnd_state ^= rnd_state << 5;
  return rnd_state;
}

void RandomKnobs(uint16_t p[4]) {
  for (int i = 0; i < 4; ++i) {
    // Ends and the middle more often than a uniform draw gives them.
    const uint32_t r = Rnd() % 10;
    p[i] = r == 0 ? 0 : r == 1 ? 65535 : r == 2 ? 32768 : static_cast<uint16_t>(Rnd());
  }
}

unsigned Tables() {
  unsigned n = 0;
  for (int i = 0; i < MOD_MI_LUT_SIZE; ++i) {
    CHECK(mod_mi_lut_delay_times[i] == peaks::lut_delay_times[i]);
    CHECK(mod_mi_lut_gravity[i] == peaks::lut_gravity[i]);
    n += 2;
  }
  CHECK(sizeof(braids::scales) / sizeof(braids::scales[0]) == MOD_MI_SCALES);
  for (int s = 0; s < MOD_MI_SCALES; ++s) {
    CHECK(mod_mi_scales[s].span == braids::scales[s].span);
    CHECK(mod_mi_scales[s].num_notes == braids::scales[s].num_notes);
    for (size_t k = 0; k < braids::scales[s].num_notes; ++k) {
      CHECK(mod_mi_scales[s].notes[k] == braids::scales[s].notes[k]);
    }
    ++n;
  }
  for (int i = 0; i < 65536; i += 7) {
    CHECK(mod_mi_interpolate88(mod_mi_lut_delay_times, static_cast<uint16_t>(i)) ==
          stmlib::Interpolate88(peaks::lut_delay_times, static_cast<uint16_t>(i)));
    ++n;
  }
  return n;
}

unsigned Ball() {
  unsigned n = 0;
  for (int trial = 0; trial < 120; ++trial) {
    peaks::BouncingBall up;
    mod_mi_bounce_t me;
    uint16_t p[4];
    up.Init();
    mod_mi_bounce_init(&me);
    for (int s = 0; s < 24000; ++s) {
      if (s % 4000 == 0) {
        RandomKnobs(p);
        up.Configure(p, peaks::CONTROL_MODE_FULL);
        mod_mi_bounce_configure(&me, p);
      }
      // The first sample always drops the ball: Init leaves upstream's
      // position and velocity unset.
      const bool rising = s == 0 || Rnd() % 6000 == 0;
      const peaks::GateFlags flag = rising ? (peaks::GATE_FLAG_RISING | peaks::GATE_FLAG_HIGH)
                                           : peaks::GATE_FLAG_LOW;
      int16_t o = 0;
      int floor = 0;
      up.Process(&flag, &o, 1);
      const int16_t m = mod_mi_bounce_sample(&me, rising, &floor);
      CHECK(m == o);
      ++n;
    }
  }
  return n;
}

unsigned Shaper() {
  unsigned n = 0;
  for (int trial = 0; trial < 150; ++trial) {
    peaks::PulseShaper up;
    mod_mi_shaper_t me;
    uint16_t p[4];
    const uint32_t density = 1 + Rnd() % 400;   // calls per trigger, on average
    up.Init();
    mod_mi_shaper_init(&me);
    for (int c = 0; c < 30000; ++c) {
      if (c % 5000 == 0) {
        RandomKnobs(p);
        up.Configure(p, peaks::CONTROL_MODE_FULL);
        mod_mi_shaper_configure(&me, p);
      }
      const bool rising = Rnd() % density == 0;
      peaks::GateFlags flags[4] = { 0, 0, 0, 0 };
      int16_t out[4];
      if (rising) flags[Rnd() % 4] = peaks::GATE_FLAG_RISING | peaks::GATE_FLAG_HIGH;
      up.Process(flags, out, 4);
      CHECK(mod_mi_shaper_call(&me, rising) == out[0]);
      ++n;
    }
  }
  return n;
}

unsigned Randomizer() {
  unsigned n = 0;
  for (int trial = 0; trial < 150; ++trial) {
    peaks::PulseRandomizer up;
    mod_mi_randomizer_t me;
    uint16_t p[4];
    const uint32_t seed = Rnd();
    const uint32_t density = 1 + Rnd() % 400;
    up.Init();
    stmlib::Random::Seed(seed);
    mod_mi_randomizer_init(&me, seed);
    for (int c = 0; c < 30000; ++c) {
      if (c % 5000 == 0) {
        RandomKnobs(p);
        up.Configure(p, peaks::CONTROL_MODE_FULL);
        mod_mi_randomizer_configure(&me, p);
      }
      const bool rising = Rnd() % density == 0;
      peaks::GateFlags flags[4] = { 0, 0, 0, 0 };
      int16_t out[4];
      if (rising) flags[Rnd() % 4] = peaks::GATE_FLAG_RISING | peaks::GATE_FLAG_HIGH;
      up.Process(flags, out, 4);
      CHECK(mod_mi_randomizer_call(&me, rising) == out[0]);
      CHECK(me.rng == stmlib::Random::state());
      ++n;
    }
  }
  return n;
}

unsigned Quantizer() {
  unsigned n = 0;
  for (int trial = 0; trial < 300; ++trial) {
    braids::Quantizer up;
    mod_mi_quantizer_t me;
    int scale = static_cast<int>(Rnd() % MOD_MI_SCALES);
    int32_t pitch = static_cast<int32_t>(Rnd() % 16000) - 8000, root = 0;
    up.Init();
    up.Configure(braids::scales[scale]);
    mod_mi_quantizer_init(&me);
    mod_mi_quantizer_configure(&me, static_cast<unsigned>(scale));
    for (int c = 0; c < 4000; ++c) {
      if (Rnd() % 500 == 0) {   // a scale change: upstream starts afresh, as the port does
        scale = static_cast<int>(Rnd() % MOD_MI_SCALES);
        up.Init();
        up.Configure(braids::scales[scale]);
        mod_mi_quantizer_configure(&me, static_cast<unsigned>(scale));
      }
      if (Rnd() % 300 == 0) root = static_cast<int32_t>(Rnd() % 12) * 128;
      // A random walk with jumps: slow moves exercise the hysteresis.
      pitch += static_cast<int32_t>(Rnd() % 81) - 40;
      if (Rnd() % 50 == 0) pitch = static_cast<int32_t>(Rnd() % 16000) - 8000;
      if (pitch < -9000 || pitch > 9000) pitch = 0;
      CHECK(mod_mi_quantizer_process(&me, pitch, root) == up.Process(pitch, root));
      ++n;
    }
  }
  return n;
}

// ---- the kinds through the runtime ----------------------------------------------------------

const uint32_t kRate = 44118;
const uint32_t kTick = FM1_MOD_TICK;

uint16_t Knob(float k) {   // the kinds' mapping (kinds_int.h kind_u16)
  if (!(k >= 0.0f)) k = 0.0f;
  if (k > 1.0f) k = 1.0f;
  return static_cast<uint16_t>(k * 65535.0f + 0.5f);
}

struct Rt {
  std::vector<unsigned char> mem;
  fm1_mod_t *m;
  explicit Rt(uint32_t seed) : mem(fm1_mod_size() + 16) {
    const fm1_host_t host = { FM1_ENGINE_API_VERSION, static_cast<float>(kRate), 64 };
    unsigned char *p = mem.data() + (16 - reinterpret_cast<uintptr_t>(mem.data()) % 16) % 16;
    m = fm1_mod_create(p, &host, seed);
  }
};

// Runs `blocks` blocks of 64 with a note-on (and off) at each frame in
// `notes` (absolute, ascending, >= 64 apart); calls on_tick after each tick
// with its absolute frame.
template <typename F>
void Drive(fm1_mod_t *m, const std::vector<uint64_t> &notes, unsigned blocks, F on_tick) {
  size_t next = 0;
  uint64_t pos = 0;
  for (unsigned b = 0; b < blocks; ++b, pos += 64) {
    uint32_t tf = fm1_mod_begin(m, 64, 0);
    for (uint32_t f = 0; f < 64; ++f) {
      if (tf == f) {
        fm1_mod_tick(m, f, NULL);
        on_tick(pos + f);
        tf += kTick;
      }
      while (next < notes.size() && notes[next] == pos + f) {
        fm1_mod_note(m, f, 60, 100);
        fm1_mod_note(m, f, 60, 0);
        ++next;
      }
    }
  }
}

std::vector<uint64_t> RandomNotes(unsigned blocks, uint32_t gap) {
  std::vector<uint64_t> notes;
  uint64_t at = 100 + Rnd() % 1000;
  while (at < static_cast<uint64_t>(blocks) * 64 - 64) {
    notes.push_back(at);
    at += 64 + Rnd() % gap;
  }
  return notes;
}

unsigned BounceKind() {
  unsigned n = 0;
  const int kind = fm1_mod_kind_find("bounce");
  CHECK(kind >= 0);
  for (int trial = 0; trial < 12; ++trial) {
    Rt rt(static_cast<uint32_t>(trial));
    const float knob[4] = { (Rnd() % 1000) / 999.0f, (Rnd() % 1000) / 999.0f,
                            (Rnd() % 1000) / 999.0f, (Rnd() % 2000) / 999.5f - 1.0f };
    const unsigned blocks = 2000;
    const std::vector<uint64_t> notes = RandomNotes(blocks, 30000);
    fm1_mod_set_kind(rt.m, 0, kind);
    for (unsigned i = 0; i < 4; ++i) fm1_mod_set_param(rt.m, 0, i, knob[i]);
    // The original at 48 kHz over the same timeline.
    peaks::BouncingBall up;
    uint16_t p[4] = { Knob(1.0f - knob[0]), Knob(knob[1]), Knob(knob[2]), 0 };
    {
      float v = knob[3] * 32767.0f + 32768.0f;
      v = v < 0.0f ? 0.0f : v > 65535.0f ? 65535.0f : v;
      p[3] = static_cast<uint16_t>(v >= 0.0f ? static_cast<int32_t>(v + 0.5f) : 0);
    }
    up.Init();
    up.Configure(p, peaks::CONTROL_MODE_FULL);
    {
      // Before the first trigger upstream's ball is unset; the port's
      // starts at rest at 0. Drop both with a trigger at frame 0 instead.
      std::vector<uint64_t> all(1, 0);
      all.insert(all.end(), notes.begin(), notes.end());
      size_t next = 0;
      uint64_t sample = 0;
      int16_t o = 0;
      Drive(rt.m, all, blocks, [&](uint64_t t) {
        const uint64_t end = t * MOD_MI_BALL_RATE / kRate;   // samples before t(k)
        for (; sample < end; ++sample) {
          bool rising = false;
          while (next < all.size() && all[next] * MOD_MI_BALL_RATE / kRate <= sample) {
            rising = true;
            ++next;
          }
          const peaks::GateFlags f = rising ? (peaks::GATE_FLAG_RISING | peaks::GATE_FLAG_HIGH)
                                            : peaks::GATE_FLAG_LOW;
          up.Process(&f, &o, 1);
        }
        const float want = static_cast<float>(o) * (1.0f / 32767.0f);
        CHECK(fm1_mod_out(rt.m, 0, 0) == want);
        ++n;
      });
    }
  }
  return n;
}

unsigned BurstKind() {
  unsigned n = 0;
  const int kind = fm1_mod_kind_find("burst");
  CHECK(kind >= 0);
  for (int trial = 0; trial < 12; ++trial) {
    Rt rt(static_cast<uint32_t>(100 + trial));
    const unsigned blocks = 3000;
    const float count = static_cast<float>(1 + Rnd() % 8);
    const float spacing = (Rnd() % 1000) / 2000.0f, length = (Rnd() % 1000) / 3000.0f;
    const bool delay_mode = trial % 3 == 2;
    const float delay = (Rnd() % 1000) / 2500.0f;
    const std::vector<uint64_t> notes = RandomNotes(blocks, 40000);
    fm1_mod_set_kind(rt.m, 0, kind);
    fm1_mod_set_param(rt.m, 0, 0, delay_mode ? 1.0f : 0.0f);   // Mode
    fm1_mod_set_param(rt.m, 0, 1, count);
    fm1_mod_set_param(rt.m, 0, 2, spacing);
    fm1_mod_set_param(rt.m, 0, 3, length);
    fm1_mod_set_param(rt.m, 0, 4, delay);
    // The original shaper over the same timeline, at 12,000 calls a second;
    // the absolute frames where its output changes.
    peaks::PulseShaper up;
    uint16_t p[4] = { delay_mode ? Knob(delay) : uint16_t(0), Knob(length), Knob(spacing),
                      static_cast<uint16_t>((static_cast<unsigned>(count) - 1u) << 13) };
    up.Init();
    up.Configure(p, peaks::CONTROL_MODE_FULL);
    std::vector<std::pair<uint64_t, int> > want, got;
    {
      const uint64_t calls = static_cast<uint64_t>(blocks) * 64 * MOD_MI_PULSE_RATE / kRate;
      size_t next = 0;
      int level = 0;
      for (uint64_t c = 0; c < calls; ++c) {
        bool rising = false;
        peaks::GateFlags flags[4] = { 0, 0, 0, 0 };
        int16_t out[4];
        while (next < notes.size() && notes[next] * MOD_MI_PULSE_RATE / kRate <= c) {
          rising = true;
          ++next;
        }
        if (rising) flags[0] = peaks::GATE_FLAG_RISING | peaks::GATE_FLAG_HIGH;
        up.Process(flags, out, 4);
        if ((out[0] != 0) != (level != 0)) {
          level = out[0] != 0;
          // The boundary after call c.
          want.push_back(std::make_pair(((c + 1) * kRate + MOD_MI_PULSE_RATE - 1) / MOD_MI_PULSE_RATE,
                                        level));
        }
      }
    }
    Drive(rt.m, notes, blocks, [&](uint64_t t) {
      const fm1_mod_gate_t *g = fm1_mod_gate_out(rt.m, 0, 0);
      for (unsigned e = 0; e < g->n; ++e) {
        got.push_back(std::make_pair(t - kTick + g->ev[e].frame, static_cast<int>(g->ev[e].high)));
      }
    });
    while (!want.empty() && want.back().first >= static_cast<uint64_t>(blocks) * 64 - kTick) {
      want.pop_back();   // past the last tick the kind ran
    }
    CHECK(got == want);
    CHECK(want.size() > 4);
    n += static_cast<unsigned>(want.size());
    fm1_mod_stats_t st;
    fm1_mod_get_stats(rt.m, &st);
    CHECK(st.edges_dropped == 0);
  }
  return n;
}

}  // namespace

int main() {
  const unsigned tables = Tables();
  const unsigned ball = Ball();
  const unsigned shaper = Shaper();
  const unsigned randomizer = Randomizer();
  const unsigned quantizer = Quantizer();
  const unsigned bounce_ticks = BounceKind();
  const unsigned burst_edges = BurstKind();
  printf("{\"tables\":%u,\"ball_samples\":%u,\"shaper_calls\":%u,\"randomizer_calls\":%u,"
         "\"quantizer_calls\":%u,\"bounce_ticks\":%u,\"burst_edges\":%u,\"failed\":%d}\n",
         tables, ball, shaper, randomizer, quantizer, bounce_ticks, burst_edges, failed);
  return failed;
}
