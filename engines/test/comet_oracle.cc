// comet_oracle.cc -- fm1-comet-oracle: "Comet Kit" (src/comet_kit.cc) against
// fm1-x0x's 909 kit driven directly (tests/test_engine_comet_kit.py). Built
// only while the GPL switch is on (mk/fm1-x0x.mk).
//
//   fm1-comet-oracle --twin [--rate HZ] [--block N]
//       Plays a set of lines (every pad, accents and soft hits, the hats
//       choking each other, rolls inside a chunk, both kits, every drive
//       type, the knobs at their ends, the kit's Accent, Velocity and
//       Volume) through the engine in host blocks of N frames, split at
//       every event as a host splits them, and through a copy of its
//       vendored unit, taken after create, driven as fm1-x0x drives it:
//       drum909_set with 9W9's integer pots, written out here from 9W9's
//       panel defaults and the voicings the engine documents, before each
//       hit, drum909_trigger, and drum909_render in 16-sample chunks counted
//       from create, each event on the chunk after its frame. Prints one
//       JSON line per line played: samples, how many differ, the largest
//       difference, the peak, non-finite and subnormal output samples, and
//       the most subnormal floats seen in the engine's unit after a render
//       call. The two must be the same, bit for bit.
//   fm1-comet-oracle --fields [--rate HZ]
//       For a list of knob settings, each on a fresh instance with the pad
//       struck once, the unit's own values on that pad's voice (Hz, ms,
//       levels, depths, drive), as JSON lines, for the test to hold against
//       9W9's pot curves.
//   fm1-comet-oracle --state [--rate HZ]
//       Every pad struck at once, then the tails: after each chunk, which
//       floats of the unit's state are subnormal (names and the most at
//       once), and whether the output was ever subnormal.
//
// MIT licence (this file).

#include "fm1_engine.h"
#include "comet_kit.h"

#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <set>
#include <string>
#include <vector>

namespace {

using namespace fm1::comet_kit;

const fm1_engine_t *Engine() {
  const fm1_engine_t *e = fm1_engine_find("comet");
  if (!e) {
    fprintf(stderr, "comet is not in this build (FM1_GPL_MODS=0?)\n");
    exit(1);
  }
  return e;
}

int ParamIndex(const fm1_engine_t *e, const char *name) {
  for (uint16_t i = 0; i < e->n_params; ++i) {
    if (strcmp(e->params[i].name, name) == 0) return i;
  }
  fprintf(stderr, "no parameter %s\n", name);
  exit(1);
}

// ---- the subnormal floats of the unit's state ------------------------------------------

struct Scan {
  int count = 0;
  std::set<std::string> *names = nullptr;
  void F(float x, const std::string &n) {
    if (std::fpclassify(x) == FP_SUBNORMAL) {
      ++count;
      if (names) names->insert(n);
    }
  }
  void Env(const d9_env_t &e, const std::string &n) {
    F(e.v, n + ".v"); F(e.cur, n + ".cur"); F(e.r, n + ".r"); F(e.v0, n + ".v0");
    F(e.v1, n + ".v1"); F(e.l2r, n + ".l2r"); F(e.t1, n + ".t1");
  }
  void Bq(const d9_biquad_t &f, const std::string &n) {
    F(f.b0, n + ".b0"); F(f.b1, n + ".b1"); F(f.b2, n + ".b2"); F(f.a1, n + ".a1");
    F(f.a2, n + ".a2"); F(f.x1, n + ".x1"); F(f.x2, n + ".x2"); F(f.y1, n + ".y1");
    F(f.y2, n + ".y2");
  }
  void Shape(const d9_shape_t &s, const std::string &n) {
    F(s.k, n + ".k"); F(s.g, n + ".g"); F(s.c1, n + ".c1"); F(s.c2, n + ".c2");
  }
  void Unit(const drum909_t &u) {
    static const char *const kBt[5] = { "bd", "sd", "lt", "mt", "ht" };
    for (int i = 0; i < 5; ++i) {
      const d9_bt_t &b = u.bt[i];
      const std::string n = kBt[i];
      const float fl[] = { b.tune, b.sweep_depth, b.sweep_time, b.decay, b.attack, b.click_tone,
                           b.level, b.tune2, b.osc2_mix, b.snappy, b.noise_decay, b.noise_hp,
                           b.amp_hold, b.pitch_mod, b.drive, b.bd_df, b.bd_mult, b.bd_base,
                           b.out_gain, b.crush_st[0], b.crush_st[1] };
      static const char *const kFl[] = { "tune", "sweep_depth", "sweep_time", "decay", "attack",
                                         "click_tone", "level", "tune2", "osc2_mix", "snappy",
                                         "noise_decay", "noise_hp", "amp_hold", "pitch_mod",
                                         "drive", "bd_df", "bd_mult", "bd_base", "out_gain",
                                         "crush_st0", "crush_st1" };
      for (unsigned k = 0; k < sizeof(fl) / sizeof(fl[0]); ++k) F(fl[k], n + "." + kFl[k]);
      Shape(b.shape, n + ".shape");
      Env(b.pitch, n + ".pitch"); Env(b.amp, n + ".amp"); Env(b.click_env, n + ".click_env");
      Env(b.noise_env, n + ".noise_env");
      Bq(b.click_lp, n + ".click_lp"); Bq(b.noise_hpf, n + ".noise_hpf");
      Bq(b.noise_lpf, n + ".noise_lpf"); Bq(b.dc_block, n + ".dc_block");
    }
    for (int i = 0; i < 3; ++i) {
      const d9_tom_t &t = u.tom[i];
      const std::string n = std::string("tom") + char('0' + i);
      for (int j = 0; j < 3; ++j) Env(t.env[j], n + ".env" + char('0' + j));
      Env(t.pitch, n + ".pitch"); Env(t.noise_env, n + ".noise_env");
      Bq(t.noise_bp, n + ".noise_bp"); Bq(t.dc_block, n + ".dc_block");
      F(t.out_gain, n + ".out_gain"); F(t.noise_level, n + ".noise_level");
      F(t.crush_st[0], n + ".crush_st0"); F(t.crush_st[1], n + ".crush_st1");
    }
    const d9_rim_t &r = u.rim;
    F(r.tune, "rim.tune"); F(r.tune2, "rim.tune2"); F(r.res, "rim.res"); F(r.decay, "rim.decay");
    F(r.noise_mix, "rim.noise_mix"); F(r.drive, "rim.drive"); F(r.level, "rim.level");
    F(r.accent, "rim.accent"); F(r.crush_st[0], "rim.crush_st0"); F(r.crush_st[1], "rim.crush_st1");
    Shape(r.shape, "rim.shape"); Bq(r.bp1, "rim.bp1"); Bq(r.bp2, "rim.bp2"); Bq(r.hp, "rim.hp");
    Env(r.amp, "rim.amp");
    const d9_clap_t &c = u.clap;
    F(c.tune, "clap.tune"); F(c.res, "clap.res"); F(c.spread, "clap.spread");
    F(c.burst_decay, "clap.burst_decay"); F(c.tail_decay, "clap.tail_decay");
    F(c.tail_level, "clap.tail_level"); F(c.drive, "clap.drive"); F(c.level, "clap.level");
    F(c.accent, "clap.accent"); F(c.next_pulse, "clap.next_pulse");
    F(c.crush_st[0], "clap.crush_st0"); F(c.crush_st[1], "clap.crush_st1");
    Shape(c.shape, "clap.shape"); Bq(c.bp, "clap.bp"); Bq(c.hp, "clap.hp");
    Env(c.burst, "clap.burst"); Env(c.tail, "clap.tail");
    static const char *const kSmp[4] = { "ch", "oh", "cr", "rd" };
    for (int i = 0; i < 4; ++i) {
      const d9_smp_t &s = u.smp[i];
      const std::string n = kSmp[i];
      F(s.decay, n + ".decay"); F(s.volume, n + ".volume"); F(s.pitch, n + ".pitch");
      F(s.drive, n + ".drive"); F(s.crush_st[0], n + ".crush_st0");
      F(s.crush_st[1], n + ".crush_st1");
      Shape(s.shape, n + ".shape"); Env(s.out, n + ".out");
    }
    for (int i = 0; i < DR_NUM; ++i) {
      F(u.send_rev[i], "send_rev"); F(u.send_dly[i], "send_dly");
    }
    F(u.accent, "accent"); F(u.vel_depth, "vel_depth");
  }
};

int SubnormalState(const drum909_t &u, std::set<std::string> *names = nullptr) {
  Scan s;
  s.names = names;
  s.Unit(u);
  return s.count;
}

// ---- the voicings, written out from the engine's documentation --------------------------

// 9W9's pot names for each knob, as the engine maps them (engines/README.md,
// "Comet Kit").
int KnobOfPot(const char *name) {
  static const char *const kMap[][2] = {
    { "Tune", "Tune" }, { "Decay", "Decay" }, { "Tail", "Decay" }, { "Level", "Level" },
    { "Tone", "Tone" }, { "Pitch", "Tone" }, { "Attack", "Snap" }, { "Snappy", "Snap" },
    { "P.Dpth", "Sweep" }, { "Drive", "Drive" }, { "Dist", "Drive Type" },
  };
  static const char *const kKnobs[] = { "Tune", "Decay", "Level", "Tone", "Snap", "Sweep",
                                        "Drive", "Drive Type" };
  for (auto &m : kMap) {
    if (strcmp(m[0], name) == 0) {
      for (int k = 0; k < 8; ++k) {
        if (strcmp(kKnobs[k], m[1]) == 0) return k;
      }
    }
  }
  return -1;
}

// The pads' voicings where they differ from 9W9's panel: (kit, pad, knob, pot),
// kit -1 for both.
struct VoicingOverride { int kit, pad, knob, pot; };
const VoicingOverride kVoicings[] = {
  { -1, 4, 0, 80 }, { -1, 4, 3, 90 }, { -1, 4, 4, 96 },   // Snare 2: Tune, Tone, Snap
  { -1, 7, 0, 104 }, { -1, 8, 1, 100 }, { -1, 11, 0, 101 }, { -1, 12, 0, 19 },
  { 1, 0, 2, 61 }, { 1, 0, 1, 80 }, { 1, 0, 6, 30 }, { 1, 10, 2, 60 },   // Big Beat
};

int VoicingPot(int kit, int pad, int knob, int def) {
  for (const auto &o : kVoicings) {
    if ((o.kit < 0 || o.kit == kit) && o.pad == pad && o.knob == knob) return o.pot;
  }
  return def;
}

// The integer pot a knob at u (0, 0.5 or 1 in these lines) puts a pot at.
int KnobPot(int knob, float u, int at) {
  if (knob == 5 || knob == 6) return u == 0.0f ? at : 127;           // Sweep, Drive: added
  return u == 0.5f ? at : (u == 0.0f ? 0 : 127);                      // the others: about
}

// ---- lines ------------------------------------------------------------------------------

struct Ev {
  uint32_t frame;
  int pad;          // a hit on pad `pad` (0..15) at velocity `vel`; -1: a setting
  int vel;
  const char *param;
  float value;
};

struct Line {
  const char *name;
  std::vector<Ev> evs;
  uint32_t frames;
};

void Hit(Line *l, uint32_t frame, int pad, int vel) { l->evs.push_back({ frame, pad, vel, nullptr, 0.0f }); }
void Set(Line *l, const char *param, float v) { l->evs.push_back({ 0, -1, 0, param, v }); }
void SetPad(Line *l, int pad, const char *param, float v) {
  Set(l, "Pad", static_cast<float>(pad));
  Set(l, param, v);
}

// A pattern over all sixteen pads at 120 BPM (a 16th is rate / 8 frames),
// with accents, soft hits, the hats choking each other and a fill.
void Pattern(Line *l, float rate, int bars) {
  const uint32_t step = static_cast<uint32_t>(rate / 8.0f);
  for (int k = 0; k < 16 * bars; ++k) {
    const uint32_t f = 1 + k * step;   // off the chunk grid
    const int s = k % 16;
    if (s % 4 == 0) Hit(l, f, 0, s == 0 ? 127 : 100);
    if (s == 4 || s == 12) Hit(l, f, 2, 112);
    if (s == 13) Hit(l, f, 4, 70);
    if (s % 2 == 0) Hit(l, f, s % 8 == 6 ? 10 : 6, s % 4 == 2 ? 127 : 88);
    if (s == 7) Hit(l, f, 8, 90);
    if (s == 3 || s == 11) Hit(l, f, 1, 100);
    if (s == 12) Hit(l, f, 3, 120);
    if (k == 16 * bars - 4) Hit(l, f, 5, 127);
    if (k == 16 * bars - 3) Hit(l, f, 7, 127);
    if (k == 16 * bars - 2) Hit(l, f, 9, 127), Hit(l, f, 11, 110);
    if (k == 16 * bars - 1) Hit(l, f, 12, 127), Hit(l, f, 14, 127);
    if (k == 0) Hit(l, f, 13, 127);
    if (k == 8) Hit(l, f, 15, 100);
  }
  l->frames = 16 * bars * step + static_cast<uint32_t>(rate * 2.0f);   // and the tails
}

std::vector<Line> Lines(float rate) {
  std::vector<Line> lines;
  {
    Line l{ "defaults", {}, 0 };
    Pattern(&l, rate, 2);
    lines.push_back(l);
  }
  {
    Line l{ "big-beat", {}, 0 };
    Set(&l, "Kit", 1);
    Pattern(&l, rate, 2);
    lines.push_back(l);
  }
  {
    Line l{ "drive-types", {}, 0 };
    for (int p = 0; p < kNumPads; ++p) {
      SetPad(&l, p, "Drive Type", static_cast<float>(p % 7));
      Set(&l, "Drive", 1.0f);
    }
    Set(&l, "Pad", 0);
    Pattern(&l, rate, 1);
    lines.push_back(l);
  }
  {
    Line l{ "knob-ends", {}, 0 };
    static const char *const kKnobs[] = { "Tune", "Decay", "Level", "Tone", "Snap", "Sweep" };
    for (int p = 0; p < kNumPads; ++p) {
      for (int k = 0; k < 6; ++k) SetPad(&l, p, kKnobs[k], (p + k) % 3 == 0 ? 0.0f : 1.0f);
    }
    Set(&l, "Pad", 3);
    Pattern(&l, rate, 1);
    lines.push_back(l);
  }
  {
    Line l{ "kit-accent", {}, 0 };
    Set(&l, "Accent", 4.0f);
    Set(&l, "Velocity", 0.0f);
    Set(&l, "Volume", 1.0f);
    Pattern(&l, rate, 1);
    lines.push_back(l);
  }
  {
    // Rolls inside chunks: the kick, the hats (closed, pedal and open
    // choking each other) and the clap every 37 frames, 7 at a time.
    Line l{ "rolls", {}, 0 };
    Set(&l, "Accent", 1.0f);
    uint32_t f = 3;
    for (int k = 0; k < 64; ++k) {
      static const int kPads[] = { 0, 6, 10, 8, 3, 10, 6 };
      Hit(&l, f, kPads[k % 7], 30 + (k * 13) % 98);
      f += k % 7 == 6 ? 4410 : 37;
    }
    l.frames = f + static_cast<uint32_t>(rate * 2.0f);
    lines.push_back(l);
  }
  return lines;
}

// The pots a hit on pad `pad` sets on its voice, in the line's settings so
// far (knobs[pad][knob], dist[pad], kit), as fm1-x0x would: 9W9's integer pots.
struct Panel {
  float knob[kNumPads][7];
  int dist[kNumPads];
  int kit;
  int focus;
  float accent, velocity, volume;
};

void PanelInit(Panel *pn, const fm1_engine_t *e) {
  for (int p = 0; p < kNumPads; ++p) {
    for (int k = 0; k < 7; ++k) pn->knob[p][k] = e->params[1 + k].def;
    pn->dist[p] = 0;
  }
  pn->kit = 0;
  pn->focus = 0;
  pn->accent = e->params[ParamIndex(e, "Accent")].def;
  pn->velocity = e->params[ParamIndex(e, "Velocity")].def;
  pn->volume = e->params[ParamIndex(e, "Volume")].def;
}

void PanelSet(Panel *pn, const char *param, float v) {
  static const char *const kKnobs[] = { "Tune", "Decay", "Level", "Tone", "Snap", "Sweep", "Drive" };
  if (strcmp(param, "Pad") == 0) { pn->focus = static_cast<int>(v); return; }
  if (strcmp(param, "Kit") == 0) { pn->kit = static_cast<int>(v); return; }
  if (strcmp(param, "Drive Type") == 0) { pn->dist[pn->focus] = static_cast<int>(v); return; }
  if (strcmp(param, "Accent") == 0) { pn->accent = v; return; }
  if (strcmp(param, "Velocity") == 0) { pn->velocity = v; return; }
  if (strcmp(param, "Volume") == 0) { pn->volume = v; return; }
  for (int k = 0; k < 7; ++k) {
    if (strcmp(param, kKnobs[k]) == 0) { pn->knob[pn->focus][k] = v; return; }
  }
  fprintf(stderr, "oracle: no knob %s\n", param);
  exit(1);
}

void PanelHit(const Panel &pn, drum909_t *u, int pad) {
  const int v = kPadVoice[pad];
  for (int i = 0; i < drum909_nparams(v); ++i) {
    const x0x_param_t *p = drum909_param(v, i);
    const int knob = KnobOfPot(p->name);
    if (knob < 0) continue;
    if (knob == 7) {
      drum909_set(u, v, i, pn.dist[pad]);
      continue;
    }
    const int at = VoicingPot(pn.kit, pad, knob, p->def);
    drum909_set(u, v, i, KnobPot(knob, pn.knob[pad][knob], at));
  }
}

int Twin(float rate, uint32_t block) {
  const fm1_engine_t *e = Engine();
  fm1_host_t host = { FM1_ENGINE_API_VERSION, rate, block };
  const size_t bytes = e->instance_size(&host);
  int failures = 0;
  for (const Line &line : Lines(rate)) {
    std::vector<unsigned char> mem(bytes + 16);
    void *aligned = reinterpret_cast<void *>((reinterpret_cast<uintptr_t>(mem.data()) + 15) & ~uintptr_t(15));
    memset(aligned, 0xA5, bytes);
    void *self = e->create(aligned, &host);
    if (!self) {
      fprintf(stderr, "refused %g\n", rate);
      return 1;
    }
    // The settings at frame 0 (all of them are), before the copy is taken.
    Panel pn;
    PanelInit(&pn, e);
    for (const Ev &ev : line.evs) {
      if (ev.pad < 0) {
        e->set_param(self, static_cast<uint16_t>(ParamIndex(e, ev.param)), ev.value);
        PanelSet(&pn, ev.param, ev.value);
      }
    }
    drum909_t *unit = static_cast<drum909_t *>(malloc(sizeof(drum909_t)));
    memcpy(unit, fm1_comet_kit_unit(self), sizeof(drum909_t));
    // The kit's Accent and Velocity as 9W9's integer pots.
    drum909_set(unit, DR_KIT, 0, static_cast<int>(std::lround((pn.accent - 1.0f) * 127.0f / 3.0f)));
    drum909_set(unit, DR_KIT, 1, static_cast<int>(std::lround(pn.velocity * 1.27f)));
    const float r = pn.volume / 0.7f;
    const float gain = kOutGain * (r * r);

    // The engine, in host blocks split at the hits.
    std::vector<float> a(2 * line.frames), b(line.frames);
    std::vector<Ev> hits;
    for (const Ev &ev : line.evs) {
      if (ev.pad >= 0) hits.push_back(ev);
    }
    size_t h = 0;
    uint32_t f = 0;
    int state_max = 0;                // the engine's unit, after each render call
    while (f < line.frames) {
      while (h < hits.size() && hits[h].frame == f) {
        e->note_on(self, static_cast<uint8_t>(kFirstNote + hits[h].pad), static_cast<uint8_t>(hits[h].vel));
        ++h;
      }
      uint32_t n = block;
      if (n > line.frames - f) n = line.frames - f;
      if (h < hits.size() && hits[h].frame - f < n) n = hits[h].frame - f;
      e->render(self, &a[2 * f], n);
      const int sub = SubnormalState(*fm1_comet_kit_unit(self));
      if (sub > state_max) state_max = sub;
      f += n;
    }

    // The unit, in 16-sample chunks counted from create; a hit at frame f
    // lands on the first chunk that starts at or after f.
    float dry[kChunk], send[kChunk];
    h = 0;
    for (uint32_t c = 0; c * kChunk < line.frames; ++c) {
      while (h < hits.size() && hits[h].frame <= c * kChunk) {
        PanelHit(pn, unit, hits[h].pad);
        drum909_trigger(unit, kPadVoice[hits[h].pad], static_cast<float>(hits[h].vel) * (1.0f / 127.0f));
        ++h;
      }
      for (uint32_t k = 0; k < kChunk; ++k) dry[k] = send[k] = 0.0f;
      drum909_render(unit, dry, send, send, static_cast<int>(kChunk));
      for (uint32_t k = 0; k < kChunk && c * kChunk + k < line.frames; ++k) b[c * kChunk + k] = dry[k] * gain;
    }

    uint32_t differ = 0, lr = 0, out_subnormal = 0, nonfinite = 0;
    float maxdiff = 0.0f, peak = 0.0f;
    for (uint32_t k = 0; k < line.frames; ++k) {
      const float x = a[2 * k];
      if (x != b[k]) {
        ++differ;
        const float d = std::fabs(x - b[k]);
        if (d > maxdiff) maxdiff = d;
      }
      if (x != a[2 * k + 1]) ++lr;
      if (!std::isfinite(x)) ++nonfinite;
      if (std::fpclassify(x) == FP_SUBNORMAL) ++out_subnormal;
      if (std::fabs(x) > peak) peak = std::fabs(x);
    }
    printf("{\"line\":\"%s\",\"rate\":%g,\"block\":%u,\"samples\":%u,\"differ\":%u,\"maxdiff\":%g,"
           "\"left_right_differ\":%u,\"peak\":%g,\"nonfinite\":%u,\"subnormal_out\":%u,"
           "\"subnormal_state_max\":%d}\n",
           line.name, rate, block, line.frames, differ, maxdiff, lr, peak, nonfinite,
           out_subnormal, state_max);
    if (differ || lr || nonfinite) ++failures;
    free(unit);
    e->destroy(self);
  }
  return failures ? 2 : 0;
}

// ---- fields -----------------------------------------------------------------------------

void PrintVoice(const drum909_t &u, int v) {
  if (v <= DR_HT) {
    const d9_bt_t &b = u.bt[v];
    printf("\"tune\":%.9g,\"decay\":%.9g,\"level\":%.9g,\"attack\":%.9g,\"snappy\":%.9g,"
           "\"noise_decay\":%.9g,\"sweep_depth\":%.9g,\"pitch_mod\":%.9g,\"drive\":%.9g,\"dist\":%d",
           b.tune, b.decay, b.level, b.attack, b.snappy, b.noise_decay, b.sweep_depth, b.pitch_mod,
           b.drive, static_cast<int>(b.dist_type));
  } else if (v == DR_RS) {
    printf("\"tune\":%.9g,\"level\":%.9g,\"drive\":%.9g,\"dist\":%d", u.rim.tune, u.rim.level,
           u.rim.drive, static_cast<int>(u.rim.dist_type));
  } else if (v == DR_CP) {
    printf("\"tune\":%.9g,\"tail_decay\":%.9g,\"level\":%.9g,\"drive\":%.9g,\"dist\":%d",
           u.clap.tune, u.clap.tail_decay, u.clap.level, u.clap.drive,
           static_cast<int>(u.clap.dist_type));
  } else {
    const d9_smp_t &s = u.smp[v - DR_CH];
    printf("\"pitch\":%.9g,\"inc\":%u,\"incf\":%u,\"decay\":%.9g,\"volume\":%.9g,\"drive\":%.9g,"
           "\"dist\":%d", s.pitch, s.inc, s.incf, s.decay, s.volume, s.drive,
           static_cast<int>(s.dist_type));
  }
}

int Fields(float rate) {
  const fm1_engine_t *e = Engine();
  fm1_host_t host = { FM1_ENGINE_API_VERSION, rate, 64 };
  const size_t bytes = e->instance_size(&host);
  static const char *const kKnobs[] = { "Tune", "Decay", "Level", "Tone", "Snap", "Sweep", "Drive" };
  static const float kValues[] = { 0.0f, 0.25f, 0.5f, 0.75f, 1.0f };
  std::vector<unsigned char> mem(bytes + 16);
  void *aligned = reinterpret_cast<void *>((reinterpret_cast<uintptr_t>(mem.data()) + 15) & ~uintptr_t(15));
  for (int kit = 0; kit < 2; ++kit) {
    for (int pad = 0; pad < kNumPads; ++pad) {
      for (int k = 0; k < 8; ++k) {
        const int nv = k == 7 ? 7 : 5;
        for (int j = 0; j < nv; ++j) {
          const float value = k == 7 ? static_cast<float>(j) : kValues[j];
          void *self = e->create(aligned, &host);
          e->set_param(self, static_cast<uint16_t>(ParamIndex(e, "Kit")), static_cast<float>(kit));
          e->set_param(self, 0, static_cast<float>(pad));
          e->set_param(self, static_cast<uint16_t>(ParamIndex(e, k == 7 ? "Drive Type" : kKnobs[k])), value);
          e->note_on(self, static_cast<uint8_t>(kFirstNote + pad), 127);
          printf("{\"kit\":%d,\"pad\":%d,\"knob\":\"%s\",\"value\":%g,\"voice\":%d,", kit, pad,
                 k == 7 ? "Drive Type" : kKnobs[k], value, kPadVoice[pad]);
          PrintVoice(*fm1_comet_kit_unit(self), kPadVoice[pad]);
          printf("}\n");
          e->destroy(self);
        }
      }
    }
  }
  // The kit's Accent and Velocity.
  static const float kAccents[] = { 1.0f, 2.0f, 4.0f };
  static const float kVelocities[] = { 0.0f, 50.0f, 100.0f };
  for (int j = 0; j < 3; ++j) {
    void *self = e->create(aligned, &host);
    e->set_param(self, static_cast<uint16_t>(ParamIndex(e, "Accent")), kAccents[j]);
    e->set_param(self, static_cast<uint16_t>(ParamIndex(e, "Velocity")), kVelocities[j]);
    const drum909_t *u = fm1_comet_kit_unit(self);
    printf("{\"kit_accent\":%g,\"kit_velocity\":%g,\"accent\":%.9g,\"vel_depth\":%.9g}\n",
           kAccents[j], kVelocities[j], u->accent, u->vel_depth);
    e->destroy(self);
  }
  return 0;
}

// ---- state ------------------------------------------------------------------------------

int State(float rate) {
  const fm1_engine_t *e = Engine();
  fm1_host_t host = { FM1_ENGINE_API_VERSION, rate, 64 };
  std::vector<unsigned char> mem(e->instance_size(&host) + 16);
  void *aligned = reinterpret_cast<void *>((reinterpret_cast<uintptr_t>(mem.data()) + 15) & ~uintptr_t(15));
  int most = 0;
  uint32_t out_subnormal = 0;
  std::set<std::string> names;
  for (int kit = 0; kit < 2; ++kit) {
    void *self = e->create(aligned, &host);
    e->set_param(self, static_cast<uint16_t>(ParamIndex(e, "Kit")), static_cast<float>(kit));
    float out[2 * 64];
    const uint32_t blocks = static_cast<uint32_t>(rate * 6.0f) / 64;
    for (uint32_t b = 0; b < blocks; ++b) {
      if (b == 0 || b == blocks / 3) {
        for (int p = 0; p < kNumPads; ++p) e->note_on(self, static_cast<uint8_t>(kFirstNote + p), 127);
      }
      e->render(self, out, 64);
      for (int k = 0; k < 128; ++k) {
        if (std::fpclassify(out[k]) == FP_SUBNORMAL) ++out_subnormal;
      }
      const int n = SubnormalState(*fm1_comet_kit_unit(self), &names);
      if (n > most) most = n;
    }
    e->destroy(self);
  }
  printf("{\"rate\":%g,\"subnormal_state_max\":%d,\"subnormal_out\":%u,\"fields\":[", rate, most,
         out_subnormal);
  bool first = true;
  for (const std::string &n : names) {
    printf("%s\"%s\"", first ? "" : ",", n.c_str());
    first = false;
  }
  printf("]}\n");
  return 0;
}

}  // namespace

int main(int argc, char **argv) {
  float rate = 44118.0f;
  uint32_t block = 64;
  int mode = 0;
  for (int i = 1; i < argc; ++i) {
    if (!strcmp(argv[i], "--twin")) mode = 1;
    else if (!strcmp(argv[i], "--fields")) mode = 2;
    else if (!strcmp(argv[i], "--state")) mode = 3;
    else if (!strcmp(argv[i], "--rate") && i + 1 < argc) rate = static_cast<float>(atof(argv[++i]));
    else if (!strcmp(argv[i], "--block") && i + 1 < argc) block = static_cast<uint32_t>(atoi(argv[++i]));
    else {
      fprintf(stderr, "usage: fm1-comet-oracle --twin|--fields|--state [--rate HZ] [--block N]\n");
      return 2;
    }
  }
  if (mode == 1) return Twin(rate, block ? block : 1);
  if (mode == 2) return Fields(rate);
  if (mode == 3) return State(rate);
  fprintf(stderr, "usage: fm1-comet-oracle --twin|--fields|--state [--rate HZ] [--block N]\n");
  return 2;
}
