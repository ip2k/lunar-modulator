// repeat_selftest.cc -- bounded state/timing regressions for Repeat.
#include "../src/fx_repeat.cc"

#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>

namespace {
using fm1::repeat::Instance;
const fm1_engine_t &E = fm1_engine_repeat;
int passed = 0, failed = 0;

void Check(const char *name, bool ok, const char *detail = NULL) {
  printf("{\"check\":\"%s\",\"ok\":%s", name, ok ? "true" : "false");
  if (detail) printf(",\"detail\":\"%s\"", detail);
  puts("}");
  if (ok) ++passed; else ++failed;
}

struct Unit {
  fm1_host_t host;
  std::vector<unsigned char> raw;
  void *self;
  Unit(float rate, uint32_t max_frames = 64)
      : host{ FM1_ENGINE_API_VERSION, rate, max_frames },
        raw(E.instance_size(&host) + 16u, 0xA5), self(NULL) {
    const uintptr_t p = reinterpret_cast<uintptr_t>(&raw[0]);
    void *mem = &raw[0] + ((16u - (p & 15u)) & 15u);
    self = E.create(mem, &host);
  }
  ~Unit() { if (self) E.destroy(self); }
  Instance *state() { return static_cast<Instance *>(self); }
  void Set(uint16_t i, float v) { E.set_param(self, i, v); }
  void Run(float *lr, uint32_t n, float bpm = 120.0f, bool running = false,
           uint8_t events = 0) {
    fm1_fx_ext_t ext = {};
    ext.bpm = bpm; ext.running = running; ext.events = events;
    fm1_engine_repeat.render_ext(self, lr, n, &ext);
  }
};

void Fill(Unit &u, uint32_t n, float bpm = 120.0f, bool running = false) {
  std::vector<float> b(2u * n);
  for (uint32_t i = 0; i < n; ++i) {
    b[2u * i] = static_cast<float>((i % 257u) + 1u) / 258.0f;
    b[2u * i + 1u] = -static_cast<float>((i % 193u) + 1u) / 194.0f;
  }
  u.Run(&b[0], n, bpm, running);
}

void TestMetadataAndBounds() {
  bool ok = E.kind == FM1_KIND_AUDIO_FX && strcmp(E.id, "repeat") == 0 &&
            E.n_params == 3 && E.render_ext &&
            E.fx_wants == (FM1_FX_WANT_TEMPO | FM1_FX_WANT_TRANSPORT);
  const float rates[] = { 8000.0f, 44118.0f, 96000.0f, 192000.0f };
  for (size_t i = 0; i < sizeof(rates) / sizeof(rates[0]); ++i) {
    Unit u(rates[i]);
    ok = ok && u.self != NULL && E.instance_size(&u.host) > 65536u &&
         (E.instance_size(&u.host) & 15u) == 0;
  }
  const float bad[] = { 0.0f, -1.0f, NAN, INFINITY, 7999.0f, 192001.0f };
  for (size_t i = 0; i < sizeof(bad) / sizeof(bad[0]); ++i) {
    Unit u(bad[i]);
    ok = ok && u.self == NULL;
  }
  Check("metadata_and_rate_bounds", ok);
}

void TestDivisionCaps() {
  struct Case { float rate, bpm; uint32_t requested, denominator, frames; } cases[] = {
    { 192000.0f, 20.0f, 8u, 256u, 9000u },
    { 96000.0f, 20.0f, 8u, 128u, 9000u },
    { 44118.0f, 120.0f, 16u, 16u, 5515u },
    { 8000.0f, 300.0f, 32u, 32u, 200u },
  };
  bool ok = true;
  for (size_t i = 0; i < sizeof(cases) / sizeof(cases[0]); ++i) {
    Unit u(cases[i].rate);
    u.Set(fm1::repeat::P_SLICE,
          cases[i].requested == 8u ? 0.0f : cases[i].requested == 16u ? 1.0f : 2.0f);
    u.Set(fm1::repeat::P_HOLD, 1.0f);
    Fill(u, fm1::repeat::kCapacity, cases[i].bpm, false);
    const Instance *s = u.state();
    ok = ok && s->held && s->loop_denominator == cases[i].denominator &&
         s->loop_frames == cases[i].frames && s->loop_frames <= fm1::repeat::kCapacity;
    printf("{\"diagnostic\":\"effective_slice\",\"rate\":%.0f,\"bpm\":%.0f,"
           "\"requested_denominator\":%u,\"effective_denominator\":%u,\"frames\":%u}\n",
           cases[i].rate, cases[i].bpm, cases[i].requested, s->loop_denominator, s->loop_frames);
  }
  Check("exact_subdivision_caps", ok);
}

void TestCompleteHistoryAndBeatCapture() {
  Unit stopped(44118.0f), running(44118.0f);
  float silence[2] = { 0.0f, 0.0f };
  running.Run(silence, 1, 120.0f, true);  // establish transport before arming
  stopped.Set(fm1::repeat::P_HOLD, 1.0f);
  running.Set(fm1::repeat::P_HOLD, 1.0f);
  Fill(stopped, fm1::repeat::kCapacity - 1u, 120.0f, false);
  Fill(running, fm1::repeat::kCapacity - 1u, 120.0f, true);
  bool ok = !stopped.state()->held && stopped.state()->ring_valid == fm1::repeat::kCapacity - 1u &&
            !running.state()->held && running.state()->armed &&
            running.state()->ring_valid == fm1::repeat::kCapacity;
  Fill(stopped, 1u, 120.0f, false);
  float one[2] = { 0.25f, -0.5f };
  running.Run(one, 1, 120.0f, true, FM1_FX_EV_BEAT);
  ok = ok && stopped.state()->held && running.state()->held;
  Check("full_history_before_latch_and_next_beat", ok);
}

void TestCapturesNewestSlice() {
  Unit u(44118.0f);
  float silence[2] = { 0.0f, 0.0f };
  u.Run(silence, 1, 120.0f, true);
  u.Set(fm1::repeat::P_HOLD, 1.0f);
  std::vector<float> source(2u * (fm1::repeat::kCapacity - 1u));
  for (uint32_t i = 0; i < fm1::repeat::kCapacity - 1u; ++i) {
    // A nonperiodic ramp makes the ring's newest region distinguishable from
    // its oldest sample; a repeating fixture could hide the wrong cursor.
    source[2u * i] = static_cast<float>((i * 73u + 19u) % 30001u) / 30001.0f;
    source[2u * i + 1u] = -static_cast<float>((i * 97u + 23u) % 29009u) / 29009.0f;
  }
  u.Run(&source[0], fm1::repeat::kCapacity - 1u, 120.0f, true);
  float beat[2] = { 0.0f, 0.0f };
  u.Run(beat, 1, 120.0f, true, FM1_FX_EV_BEAT);
  const Instance *s = u.state();
  const uint32_t newest = (s->ring_write - s->loop_frames) & fm1::repeat::kMask;
  const int16_t expected = s->ring[2u * newest];
  const int16_t oldest = s->ring[0];
  const float actual = s->ReadLoop(0, s->loop_frames, 0);
  const float expected_float = static_cast<float>(expected) * (1.0f / 32767.0f);
  const uint32_t tail = (s->ring_write - 1u) & fm1::repeat::kMask;
  const float raw_seam = fabsf(static_cast<float>(s->ring[2u * tail] - expected)) /
                         32767.0f;
  const float seam_delta = fabsf(s->ReadLoop(s->loop_frames - 1u, s->loop_frames, 0) - actual);
  if (!(raw_seam > 0.1f && seam_delta == 0.0f))
    printf("{\"diagnostic\":\"loop_seam\",\"raw_jump\":%.6f,\"smoothed_jump\":%.9f,\"length\":%u}\n",
           raw_seam, seam_delta, s->loop_frames);
  Check("held_slice_starts_at_capture_head", s->held && s->loop_frames != 0u &&
        actual == expected_float && expected != oldest && raw_seam > 0.1f && seam_delta == 0.0f);
}

void TestHoldFreezeTempoAndRetrigger() {
  Unit u(44118.0f);
  float silence[2] = { 0.0f, 0.0f };
  u.Run(silence, 1, 120.0f, true);  // Hold is set after transport is known
  u.Set(fm1::repeat::P_HOLD, 1.0f);
  Fill(u, fm1::repeat::kCapacity - 1u, 120.0f, true);
  float marker[2] = { 0.9f, -0.7f };
  u.Run(marker, 1, 120.0f, true, FM1_FX_EV_BEAT);
  const uint32_t frozen_write = u.state()->ring_write;
  std::vector<int16_t> frozen(u.state()->ring, u.state()->ring + 2u * fm1::repeat::kCapacity);
  Fill(u, 1024, 120.0f, true);
  bool ok = u.state()->held && u.state()->ring_write == frozen_write &&
            memcmp(&frozen[0], u.state()->ring, frozen.size() * sizeof(int16_t)) == 0;
  const uint32_t old = u.state()->loop_frames;
  Fill(u, 1, 300.0f, true);
  ok = ok && u.state()->loop_frames == old;
  float beat[2] = { 0.1f, 0.2f };
  u.Run(beat, 1, 300.0f, true, FM1_FX_EV_BEAT);
  ok = ok && u.state()->loop_frames != old && u.state()->fade_left + 1u == u.state()->ramp_frames;
  const bool tempo_ok = u.state()->loop_frames != old && u.state()->fade_left + 1u == u.state()->ramp_frames;
  u.Set(fm1::repeat::P_HOLD, 0.0f);
  Fill(u, u.state()->ramp_frames, 300.0f, true);
  ok = ok && !u.state()->held && !u.state()->release_pending;
  const bool release_ok = !u.state()->held && !u.state()->release_pending;
  u.Set(fm1::repeat::P_HOLD, 1.0f);
  float no_beat[2] = { 0.2f, -0.2f };
  u.Run(no_beat, 1, 300.0f, true);
  const bool rearm_ok = !u.state()->held && u.state()->armed;
  ok = ok && !u.state()->held && u.state()->armed;
  u.Run(no_beat, 1, 300.0f, true, FM1_FX_EV_BEAT);
  ok = ok && u.state()->held;
  if (!ok) printf("{\"diagnostic\":\"retrigger\",\"tempo\":%s,\"release\":%s,\"rearm\":%s,\"held\":%u,\"armed\":%u,\"loop\":%u}\n",
                  tempo_ok ? "true" : "false", release_ok ? "true" : "false",
                  rearm_ok ? "true" : "false", u.state()->held, u.state()->armed, u.state()->loop_frames);
  Check("frozen_ring_beat_tempo_and_retrigger", ok);
}

void TestTransportAndReset() {
  Unit u(44118.0f);
  float silence[2] = { 0.0f, 0.0f };
  u.Run(silence, 1, 120.0f, true);
  u.Set(fm1::repeat::P_HOLD, 1.0f);
  Fill(u, fm1::repeat::kCapacity - 1u, 120.0f, true);
  float one[2] = { 0.3f, 0.3f };
  u.Run(one, 1, 120.0f, true, FM1_FX_EV_BEAT);
  u.Run(one, 1, 120.0f, false, FM1_FX_EV_STOP);
  Fill(u, u.state()->ramp_frames + 2u, 120.0f, false);
  bool ok = !u.state()->held && !u.state()->armed && u.state()->ring_valid <= 3u;
  u.Run(one, 1, 120.0f, true, FM1_FX_EV_START);
  ok = ok && u.state()->ring_valid == 1 && u.state()->armed && u.state()->arm_on_beat;
  const bool start_ok = u.state()->ring_valid == 1 && u.state()->armed && u.state()->arm_on_beat;
  Fill(u, fm1::repeat::kCapacity, 120.0f, true);
  ok = ok && !u.state()->held;
  const bool waiting_ok = !u.state()->held && u.state()->armed;
  u.Run(one, 1, 120.0f, true, FM1_FX_EV_BEAT);
  ok = ok && u.state()->held;
  const bool latch_ok = u.state()->held;
  u.Run(one, 1, 120.0f, true, FM1_FX_EV_RESET);
  Fill(u, u.state()->ramp_frames + 2u, 120.0f, true);
  ok = ok && !u.state()->held && u.state()->ring_valid <= 3u;
  if (!ok) printf("{\"diagnostic\":\"transport\",\"held\":%u,\"armed\":%u,\"ring\":%u,\"release\":%u,\"wet\":%.4f}\n",
                  u.state()->held, u.state()->armed, u.state()->ring_valid,
                  u.state()->release_pending, u.state()->wet);
  if (!ok) printf("{\"diagnostic\":\"transport_stages\",\"start\":%s,\"waiting\":%s,\"latch\":%s}\n",
                  start_ok ? "true" : "false", waiting_ok ? "true" : "false", latch_ok ? "true" : "false");
  Check("stop_start_reset_clear_and_rearm", ok);
}

void TestZeroMixAndFiniteOutput() {
  Unit u(44118.0f);
  u.Set(fm1::repeat::P_MIX, 0.0f);
  std::vector<float> a(2u * 256u), original;
  for (size_t i = 0; i < a.size(); ++i) {
    const uint32_t bits = (i % 5u == 0u) ? 0x80000000u :
                          (i % 7u == 0u) ? 0x7fc01234u : 0x3e800000u + static_cast<uint32_t>(i);
    memcpy(&a[i], &bits, sizeof(bits));
  }
  original = a;
  u.Run(&a[0], 256u, 120.0f, false);
  bool exact = memcmp(&a[0], &original[0], a.size() * sizeof(float)) == 0;

  Unit wet(44118.0f);
  wet.Set(fm1::repeat::P_MIX, 1.0f);
  std::vector<float> bad(2u * 512u);
  for (size_t i = 0; i < bad.size(); ++i) bad[i] = (i % 11u == 0u) ? NAN : (i % 13u == 0u) ? INFINITY : 8.0f;
  wet.Run(&bad[0], 512u, 120.0f, false);
  bool finite = true;
  for (size_t i = 0; i < bad.size(); ++i) finite = finite && std::isfinite(bad[i]);
  Check("mix_zero_exact_dry_and_hostile_finite", exact && finite);
}

bool DryAfterAction(uint8_t event, bool running, bool change_hold) {
  Unit u(44118.0f);
  u.Set(fm1::repeat::P_MIX, 1.0f);
  if (change_hold) {
    u.Set(fm1::repeat::P_HOLD, 1.0f);
    u.Set(fm1::repeat::P_HOLD, 0.0f);
  }
  float sample[2] = { 0.25f, -0.375f };
  if (event == FM1_FX_EV_STOP) u.Run(sample, 1, 120.0f, true);
  u.Run(sample, 1, 120.0f, running, event);
  std::vector<float> dry(2u * (u.state()->ramp_frames + 1u));
  for (size_t i = 0; i < dry.size(); i += 2u) {
    dry[i] = 0.25f;
    dry[i + 1u] = -0.375f;
  }
  u.Run(&dry[0], static_cast<uint32_t>(dry.size() / 2u), 120.0f, running);
  bool exact = true;
  for (size_t i = 0; i < dry.size(); i += 2u)
    exact = exact && dry[i] == 0.25f && dry[i + 1u] == -0.375f;
  return exact && u.state()->wet == 0.0f && u.state()->wet_left == 0u && !u.state()->held;
}

void TestDryReleaseActionsStayDry() {
  const bool start = DryAfterAction(FM1_FX_EV_START, true, false);
  const bool stop = DryAfterAction(FM1_FX_EV_STOP, false, false);
  const bool reset = DryAfterAction(FM1_FX_EV_RESET, true, false);
  const bool hold_off = DryAfterAction(0, false, true);
  Check("dry_start_stop_reset_and_hold_off_stay_dry", start && stop && reset && hold_off);
}

void TestRepeatedMixTargetKeepsRampDeadline() {
  Unit once(44118.0f), repeated(44118.0f);
  float warm_a[2] = { 0.2f, -0.3f }, warm_b[2] = { 0.2f, -0.3f };
  once.Run(warm_a, 1);
  repeated.Run(warm_b, 1);
  once.Set(fm1::repeat::P_MIX, 1.0f);
  repeated.Set(fm1::repeat::P_MIX, 1.0f);
  std::vector<float> first_a(10u), first_b(10u);
  for (size_t i = 0; i < first_a.size(); i += 2u) {
    first_a[i] = first_b[i] = 0.25f;
    first_a[i + 1u] = first_b[i + 1u] = -0.375f;
  }
  once.Run(&first_a[0], 5);
  repeated.Run(&first_b[0], 5);
  repeated.Set(fm1::repeat::P_MIX, 1.0f);
  const uint32_t remaining_frames = once.state()->ramp_frames - 5u;
  std::vector<float> rest_a(2u * remaining_frames);
  std::vector<float> rest_b(rest_a.size());
  for (size_t i = 0; i < rest_a.size(); i += 2u) {
    rest_a[i] = rest_b[i] = 0.25f;
    rest_a[i + 1u] = rest_b[i + 1u] = -0.375f;
  }
  once.Run(&rest_a[0], remaining_frames);
  repeated.Run(&rest_b[0], remaining_frames);
  Check("same_mix_target_does_not_restart_ramp", once.state()->mix == 1.0f &&
        repeated.state()->mix == once.state()->mix && once.state()->mix_left == 0u &&
        repeated.state()->mix_left == 0u && rest_a == rest_b);
}

void TestQuickReholdRequiresFreshCapture() {
  Unit u(44118.0f);
  float sample[2] = { 0.3f, -0.2f };
  u.Run(sample, 1, 120.0f, true);
  u.Set(fm1::repeat::P_HOLD, 1.0f);
  Fill(u, fm1::repeat::kCapacity - 1u, 120.0f, true);
  u.Run(sample, 1, 120.0f, true, FM1_FX_EV_BEAT);
  const bool initially_held = u.state()->held;
  u.Set(fm1::repeat::P_HOLD, 0.0f);
  Fill(u, 5u, 120.0f, true);
  u.Set(fm1::repeat::P_HOLD, 1.0f);
  Fill(u, u.state()->ramp_frames - 5u, 120.0f, true);
  const bool cleared_and_armed = !u.state()->held && !u.state()->release_pending &&
                                 u.state()->ring_valid == 0u && u.state()->armed;
  u.Run(sample, 1, 120.0f, true, FM1_FX_EV_BEAT);
  const bool beat_cannot_restore_old_loop = !u.state()->held && u.state()->ring_valid == 1u;
  Fill(u, fm1::repeat::kCapacity - 1u, 120.0f, true);
  u.Run(sample, 1, 120.0f, true, FM1_FX_EV_BEAT);
  Check("quick_rehold_waits_for_fresh_ring_and_beat", initially_held && cleared_and_armed &&
        beat_cannot_restore_old_loop && u.state()->held);
}

void TestRepeatedHoldOffKeepsReleaseDeadline() {
  Unit once(44118.0f), repeated(44118.0f);
  float warm_a[2] = { 0.1f, -0.2f }, warm_b[2] = { 0.1f, -0.2f };
  once.Run(warm_a, 1, 120.0f, true);
  repeated.Run(warm_b, 1, 120.0f, true);
  once.Set(fm1::repeat::P_HOLD, 1.0f);
  repeated.Set(fm1::repeat::P_HOLD, 1.0f);
  Fill(once, fm1::repeat::kCapacity - 1u, 120.0f, true);
  Fill(repeated, fm1::repeat::kCapacity - 1u, 120.0f, true);
  once.Run(warm_a, 1, 120.0f, true, FM1_FX_EV_BEAT);
  repeated.Run(warm_b, 1, 120.0f, true, FM1_FX_EV_BEAT);
  once.Set(fm1::repeat::P_HOLD, 0.0f);
  repeated.Set(fm1::repeat::P_HOLD, 0.0f);
  Fill(once, 5u, 120.0f, true);
  Fill(repeated, 5u, 120.0f, true);
  repeated.Set(fm1::repeat::P_HOLD, 0.0f);
  const uint32_t remaining_frames = once.state()->ramp_frames - 5u;
  Fill(once, remaining_frames, 120.0f, true);
  Fill(repeated, remaining_frames, 120.0f, true);
  Check("same_hold_off_does_not_restart_release", once.state()->wet == 0.0f &&
        repeated.state()->wet == 0.0f && !once.state()->release_pending &&
        !repeated.state()->release_pending && !once.state()->held && !repeated.state()->held);
}

void TestExplicitHoldOnRearmsAfterStop() {
  Unit u(44118.0f);
  float sample[2] = { 0.1f, -0.2f };
  u.Run(sample, 1, 120.0f, true);
  u.Set(fm1::repeat::P_HOLD, 1.0f);
  Fill(u, fm1::repeat::kCapacity - 1u, 120.0f, true);
  u.Run(sample, 1, 120.0f, true, FM1_FX_EV_BEAT);
  u.Run(sample, 1, 120.0f, false, FM1_FX_EV_STOP);
  Fill(u, u.state()->ramp_frames, 120.0f, false);
  const bool stopped_cleared = !u.state()->held && !u.state()->armed &&
                               u.state()->ring_valid <= 1u && u.state()->hold == fm1::repeat::HOLD_ON;
  u.Set(fm1::repeat::P_HOLD, 1.0f);
  const bool rearmed = u.state()->armed && u.state()->latch_when_full;

  Unit off(44118.0f);
  float off_sample[2] = { 0.1f, -0.2f };
  off.Run(off_sample, 1, 120.0f, true);
  off.Set(fm1::repeat::P_HOLD, 1.0f);
  Fill(off, fm1::repeat::kCapacity - 1u, 120.0f, true);
  off.Run(off_sample, 1, 120.0f, true, FM1_FX_EV_BEAT);
  off.Run(off_sample, 1, 120.0f, false, FM1_FX_EV_STOP);
  off.Set(fm1::repeat::P_HOLD, 0.0f);
  off.Set(fm1::repeat::P_HOLD, 0.0f);
  Fill(off, off.state()->ramp_frames, 120.0f, false);
  const bool repeated_off_kept_stop_clear = !off.state()->release_pending &&
       !off.state()->held && !off.state()->armed && off.state()->ring_valid <= 1u;
  if (!(stopped_cleared && rearmed && repeated_off_kept_stop_clear))
    printf("{\"diagnostic\":\"hold_rearm\",\"clear\":%s,\"rearm\":%s,\"repeat_off_clear\":%s,\"armed\":%u,\"latch_full\":%u,\"ring\":%u}\n",
           stopped_cleared ? "true" : "false", rearmed ? "true" : "false",
           repeated_off_kept_stop_clear ? "true" : "false", u.state()->armed,
           u.state()->latch_when_full, off.state()->ring_valid);
  Check("explicit_unchanged_hold_on_rearms_after_stop", stopped_cleared && rearmed &&
        repeated_off_kept_stop_clear);
}

void TestChunkInvariant() {
  Unit a(44118.0f), b(44118.0f);
  a.Set(fm1::repeat::P_HOLD, 1.0f); b.Set(fm1::repeat::P_HOLD, 1.0f);
  std::vector<float> x(2u * (fm1::repeat::kCapacity + 2048u));
  for (size_t i = 0; i < x.size() / 2u; ++i) {
    x[2u * i] = static_cast<float>(i % 67u) / 67.0f;
    x[2u * i + 1u] = -static_cast<float>(i % 43u) / 43.0f;
  }
  std::vector<float> y = x;
  a.Run(&x[0], fm1::repeat::kCapacity, 120.0f, false);
  b.Run(&y[0], fm1::repeat::kCapacity / 2u, 120.0f, false);
  b.Run(&y[2u * (fm1::repeat::kCapacity / 2u)], fm1::repeat::kCapacity / 2u, 120.0f, false);
  a.Run(&x[2u * fm1::repeat::kCapacity], 1, 120.0f, true, FM1_FX_EV_BEAT);
  b.Run(&y[2u * fm1::repeat::kCapacity], 1, 120.0f, true, FM1_FX_EV_BEAT);
  a.Run(&x[2u * (fm1::repeat::kCapacity + 1u)], 2047u, 120.0f, true);
  for (uint32_t i = 1; i < 2048u; ++i)
    b.Run(&y[2u * (fm1::repeat::kCapacity + i)], 1u, 120.0f, true);
  bool same = true;
  for (size_t i = 0; i < x.size(); ++i) same = same && x[i] == y[i];
  Check("chunk_invariant_capture_and_playback", same);
}
}  // namespace

int main() {
  TestMetadataAndBounds();
  TestDivisionCaps();
  TestCompleteHistoryAndBeatCapture();
  TestCapturesNewestSlice();
  TestHoldFreezeTempoAndRetrigger();
  TestTransportAndReset();
  TestZeroMixAndFiniteOutput();
  TestDryReleaseActionsStayDry();
  TestRepeatedMixTargetKeepsRampDeadline();
  TestQuickReholdRequiresFreshCapture();
  TestRepeatedHoldOffKeepsReleaseDeadline();
  TestExplicitHoldOnRearmsAfterStop();
  TestChunkInvariant();
  printf("{\"summary\":\"repeat\",\"passed\":%d,\"failed\":%d}\n", passed, failed);
  return failed ? 1 : 0;
}
