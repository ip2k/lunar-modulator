// crater_oracle.cc -- fm1-crater-oracle: "Crater Kit" (src/crater_kit.cc)
// against fm1-x0x's 808 driven directly (tests/test_engine_crater_kit.py).
// Built only while the GPL switch is on (mk/x0x-crater.mk).
//
//   fm1-crater-oracle --twin [--rate HZ] [--block N]
//       Plays a set of 808 patterns (every pad, velocities from soft to the
//       accent, the hats choking, toms and congas on one channel, settings
//       on several pads, a dense bar of every pad on every 16th) through the
//       engine in host blocks of N frames, and through a copy of its
//       vendored kit, taken after create and the pattern's settings, driven
//       as fm1-x0x drives it: the track's switch set and drum808_trigger
//       with the velocity law of crater_kit.h, and drum808_render in
//       16-sample chunks counted from create, each hit on the chunk after
//       its frame, times kOutScale. Prints one JSON line per pattern:
//       samples, how many differ, the peak, non-finite and subnormal
//       samples, and the most subnormal floats seen in the kit's running
//       state after a render call, in all of it and in the circuits that
//       are running. At Volume 0.7 the two must be the same, bit for bit.
//   fm1-crater-oracle --fields
//       For a list of parameter settings, each on a fresh instance, the
//       vendored kit's own values after set_param (the sound's pot, its
//       value, the kit's velocity depth and choke), as JSON lines, for the
//       test to hold against the parameters' laws.
//   fm1-crater-oracle --pads
//       Each pad struck alone at velocities 88 and 127: its peak, and the
//       samples until it has ended (the kit silent), as JSON lines.
//
// MIT licence (this file).

#include "fm1_engine.h"
#include "crater_kit.h"

#include <cmath>
#include <cstddef>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>

namespace {

struct Ev {
  uint32_t frame;
  int key;
  int vel;
};

struct Pattern {
  const char *name;
  std::vector<std::pair<const char *, float> > params;   // in order; "Pad" moves the focus
  std::vector<Ev> evs;
  uint32_t frames;
};

const fm1_engine_t *Engine() {
  const fm1_engine_t *e = fm1_engine_find("crater");
  if (!e) {
    fprintf(stderr, "crater is not in this build (FM1_GPL_MODS=0?)\n");
    exit(1);
  }
  return e;
}

int ParamIndex(const fm1_engine_t *e, const char *name) {
  for (uint16_t i = 0; i < e->n_params; ++i) {
    if (strcmp(e->params[i].name, name) == 0) return i;
  }
  fprintf(stderr, "no parameter %s\n", name);
  exit(2);
}

// A pattern on 16ths at `bpm`: rows of {key, 16 steps of velocity or 0}.
struct Row {
  int key;
  const char *steps;   // '.' rest, 'x' 88 (normal), 'A' 127 (accent), 's' 40, 'm' 64, 'h' 110
};

int StepVel(char c) {
  switch (c) {
    case 'x': return 88;
    case 'A': return 127;
    case 's': return 40;
    case 'm': return 64;
    case 'h': return 110;
    default: return 0;
  }
}

Pattern Make(const char *name, float rate, float bpm, const std::vector<Row> &rows, int bars,
             std::vector<std::pair<const char *, float> > params, float tail_s) {
  Pattern p;
  p.name = name;
  p.params = params;
  const double step = rate * 60.0 / bpm / 4.0;
  for (int b = 0; b < bars; ++b) {
    for (int i = 0; i < 16; ++i) {
      const uint32_t at = static_cast<uint32_t>((b * 16 + i) * step);
      for (const Row &r : rows) {
        const int v = StepVel(r.steps[i]);
        if (v) p.evs.push_back(Ev{at, r.key, v});
      }
    }
  }
  p.frames = static_cast<uint32_t>(bars * 16 * step + rate * tail_s);
  return p;
}

std::vector<Pattern> Patterns(float rate) {
  std::vector<Pattern> out;
  // The classic: kick, snare, hats choking, a clap and a cowbell.
  const std::vector<Row> groove = {
    {36, "A..x..x...A..x.."}, {38, "....A.......x..h"}, {42, "x.x.x.x.x.x.x.x."},
    {46, "..x.......x....."}, {39, "........A......."}, {51, "......x.....m..."},
    {37, ".x.....x........"},
  };
  out.push_back(Make("groove", rate, 120, groove, 2, {}, 1.5f));
  // Every pad, soft to accented, one after another.
  std::vector<Row> all;
  for (int k = 0; k < 16; ++k) {
    static char steps[16][17];
    for (int i = 0; i < 16; ++i) steps[k][i] = i == k ? "smxhA"[k % 5] : '.';
    steps[k][16] = 0;
    all.push_back(Row{36 + k, steps[k]});
  }
  out.push_back(Make("every-pad", rate, 100, all, 1, {}, 2.5f));
  // Toms and congas on their shared channels, rim and claves, clap and maracas.
  const std::vector<Row> perc = {
    {41, "x...x.....A....."}, {43, "..x...x.A.......", }, {45, "....x...x...A..."},
    {47, ".x.....x....x..."}, {48, "..A.......x...x."}, {50, "...x...x.....x.."},
    {37, "x.......x......."}, {40, "....x.......x..."}, {39, "......x.......x."},
    {44, "x.x.x.x.x.x.x.x."},
  };
  out.push_back(Make("toms-congas", rate, 112, perc, 2, {}, 1.5f));
  // Settings on several pads: tuned, longer and shorter, driven through each
  // distortion, the mutual choke, a lower accent depth.
  out.push_back(Make("settings", rate, 126, groove, 2,
                     {{"Pad", 0}, {"Tune", -5}, {"Decay", 0.9f}, {"Tone", 0.8f}, {"Snap", 0.2f},
                      {"Drive", 0.4f}, {"Dist", 2},
                      {"Pad", 2}, {"Tune", 3}, {"Snap", 1}, {"Tone", 0}, {"Drive", 0.7f}, {"Dist", 5},
                      {"Pad", 6}, {"Decay", 0.1f}, {"Drive", 0.3f}, {"Dist", 6},
                      {"Pad", 10}, {"Decay", 1}, {"Tune", 7}, {"Level", 0.8f},
                      {"Pad", 3}, {"Dist", 3}, {"Drive", 0.9f},
                      {"Pad", 15}, {"Tune", -12}, {"Dist", 1}, {"Drive", 1},
                      {"Choke", 2}, {"Accent", 40}}, 1.5f));
  // Every pad on every 16th, accents on the beats: the dense case.
  std::vector<Row> dense;
  for (int k = 0; k < 16; ++k) dense.push_back(Row{36 + k, "AxxxAxxxAxxxAxxx"});
  out.push_back(Make("dense", rate, 125, dense, 2, {}, 1.0f));
  return out;
}

// Subnormal floats among `n` floats.
int Sub(const float *f, size_t n) {
  int c = 0;
  for (size_t k = 0; k < n; ++k) c += std::fpclassify(f[k]) == FP_SUBNORMAL;
  return c;
}
// ...in the leading floats of a struct, up to the member at `end` bytes.
int SubPrefix(const void *p, size_t end) {
  return Sub(static_cast<const float *>(p), end / sizeof(float));
}

// The kit's running state, every float that a circuit carries from one
// sample to the next (and its coefficients, which never go subnormal):
// [0] in all of it, [1] in the circuits that run (active).
void SubnormalState(const drum808_t *d, int out[2]) {
  int all = 0, run = 0;
  auto add = [&](int n, bool active) { all += n; if (active) run += n; };
  add(SubPrefix(&d->bd, offsetof(d8_bd_t, gate)), d->bd.active);
  add(SubPrefix(&d->sd, offsetof(d8_sd_t, rng)), d->sd.active);
  for (int k = 0; k < 3; ++k) add(SubPrefix(&d->tom[k], offsetof(d8_tom_t, rng)), d->tom[k].active);
  add(SubPrefix(&d->rs.env, offsetof(d8_env_t, count)) + Sub(&d->rs.tri_ph, 2) +
      SubPrefix(&d->rs.peak, 3 * sizeof(d8_bq_t)), d->rs.active);
  add(SubPrefix(&d->cl, offsetof(d8_clave_t, gate)), d->cl.active);
  add(SubPrefix(&d->ma, offsetof(d8_ma_t, rng)), d->ma.active);
  add(SubPrefix(&d->cp, offsetof(d8_cp_t, rng)), d->cp.active);
  {
    const bool metal = d->cb.active || d->ch.active || d->oh.active || d->cy.active;
    add(Sub(d->bank.drift, 6) + Sub(d->bank.jm1, 6), metal);
  }
  add(SubPrefix(&d->cb, offsetof(d8_cb_t, quiet)), d->cb.active);
  add(SubPrefix(&d->ch, offsetof(d8_hat_t, lin_hold)), d->ch.active);
  add(SubPrefix(&d->oh, offsetof(d8_hat_t, lin_hold)), d->oh.active);
  add(SubPrefix(&d->cy, offsetof(d8_cy_t, e1_n)), d->cy.active);
  for (int k = 0; k < 13; ++k) add(Sub(d->lane[k].crush, 2), false);
  out[0] = all;
  out[1] = run;
}

void *NewInstance(const fm1_engine_t *e, const fm1_host_t *host, std::vector<unsigned char> *mem) {
  mem->assign(e->instance_size(host) + 16, 0);
  void *aligned = reinterpret_cast<void *>((reinterpret_cast<uintptr_t>(mem->data()) + 15) &
                                           ~static_cast<uintptr_t>(15));
  return e->create(aligned, host);
}

bool Twin(float rate, uint32_t block) {
  using namespace fm1::crater;
  const fm1_engine_t *e = Engine();
  fm1_host_t host = { FM1_ENGINE_API_VERSION, rate, block };
  bool ok = true;
  for (const Pattern &pt : Patterns(rate)) {
    std::vector<unsigned char> mem;
    void *self = NewInstance(e, &host, &mem);
    if (!self) {
      printf("{\"pattern\":\"%s\",\"refused\":true}\n", pt.name);
      return false;
    }
    for (const auto &p : pt.params) e->set_param(self, static_cast<uint16_t>(ParamIndex(e, p.first)), p.second);
    drum808_t *twin = new drum808_t(*fm1_crater_unit(self));

    std::vector<float> a(2 * pt.frames), b(pt.frames);
    size_t next = 0;
    int state_max[2] = { 0, 0 };
    for (uint32_t f = 0; f < pt.frames;) {
      while (next < pt.evs.size() && pt.evs[next].frame <= f) {
        const Ev &ev = pt.evs[next++];
        e->note_on(self, static_cast<uint8_t>(ev.key), static_cast<uint8_t>(ev.vel));
      }
      uint32_t n = block;
      if (next < pt.evs.size() && pt.evs[next].frame - f < n) n = pt.evs[next].frame - f;
      if (pt.frames - f < n) n = pt.frames - f;
      e->render(self, &a[2 * f], n);
      int st[2];
      SubnormalState(fm1_crater_unit(self), st);
      for (int k = 0; k < 2; ++k) if (st[k] > state_max[k]) state_max[k] = st[k];
      f += n;
    }
    // The twin: 16-sample chunks; a hit lands on the chunk after its frame.
    next = 0;
    float rev[kChunk], dly[kChunk];
    for (uint32_t c = 0; c < pt.frames; c += kChunk) {
      while (next < pt.evs.size() && pt.evs[next].frame <= c) {
        const Ev &ev = pt.evs[next++];
        const Pad &pad = kPads[ev.key - kFirstNote];
        twin->sw[pad.track] = pad.sw;
        drum808_trigger(twin, pad.track, VelocityOf(static_cast<uint8_t>(ev.vel)));
      }
      float chunk[kChunk];
      for (uint32_t k = 0; k < kChunk; ++k) chunk[k] = rev[k] = dly[k] = 0.0f;
      if (drum808_active(twin)) drum808_render(twin, chunk, rev, dly, static_cast<int>(kChunk));
      for (uint32_t k = 0; k < kChunk && c + k < pt.frames; ++k) b[c + k] = chunk[k] * kOutScale;
    }
    uint32_t differ = 0, lr = 0, out_subnormal = 0, nonfinite = 0;
    double maxd = 0, peak = 0;
    for (uint32_t k = 0; k < pt.frames; ++k) {
      const double d = std::fabs(static_cast<double>(a[2 * k]) - b[k]);
      if (a[2 * k] != b[k]) ++differ;
      if (std::fpclassify(a[2 * k]) == FP_SUBNORMAL) ++out_subnormal;
      if (!std::isfinite(a[2 * k])) ++nonfinite;
      if (a[2 * k] != a[2 * k + 1]) ++lr;
      if (d > maxd) maxd = d;
      if (std::fabs(a[2 * k]) > peak) peak = std::fabs(a[2 * k]);
    }
    printf("{\"pattern\":\"%s\",\"rate\":%g,\"block\":%u,\"samples\":%u,\"hits\":%zu,\"differ\":%u,"
           "\"max_diff\":%.9g,\"left_right_differ\":%u,\"peak\":%.6f,\"silent_at_end\":%s,"
           "\"nonfinite\":%u,\"subnormal_out\":%u,\"subnormal_state_max\":%d,"
           "\"subnormal_running_max\":%d}\n",
           pt.name, rate, block, pt.frames, pt.evs.size(), differ, maxd, lr, peak,
           drum808_active(fm1_crater_unit(self)) ? "false" : "true", nonfinite, out_subnormal,
           state_max[0], state_max[1]);
    ok = ok && differ == 0 && lr == 0 && nonfinite == 0;
    delete twin;
    e->destroy(self);
  }
  return ok;
}

void Fields() {
  using namespace fm1::crater;
  const fm1_engine_t *e = Engine();
  fm1_host_t host = { FM1_ENGINE_API_VERSION, 44100.0f, 64 };
  struct Setting { int pad; const char *name; float value; };
  static const Setting kSettings[] = {
    {0, "", 0}, {0, "Tune", -12}, {0, "Tune", 7}, {0, "Tune", 12}, {5, "Tune", -12}, {5, "Tune", 2},
    {5, "Tune", 12}, {13, "Tune", -12}, {13, "Tune", 12}, {15, "Tune", 5},
    {0, "Decay", 0}, {0, "Decay", 0.25f}, {0, "Decay", 0.75f}, {0, "Decay", 1}, {2, "Decay", 0},
    {2, "Decay", 1}, {10, "Decay", 0.25f}, {10, "Decay", 1},
    {0, "Level", 0}, {0, "Level", 1}, {4, "Level", 0.25f},
    {0, "Tone", 0}, {0, "Tone", 1}, {2, "Tone", 0}, {2, "Tone", 1}, {6, "Tone", 1},
    {0, "Snap", 0}, {0, "Snap", 1}, {2, "Snap", 0}, {2, "Snap", 1}, {8, "Snap", 1}, {6, "Snap", 1},
    {0, "Drive", 0.5f}, {0, "Drive", 1}, {0, "Dist", 3}, {0, "Dist", 6},
    {0, "Accent", 0}, {0, "Accent", 50}, {0, "Choke", 0}, {0, "Choke", 2},
  };
  for (const Setting &s : kSettings) {
    std::vector<unsigned char> mem;
    void *self = NewInstance(e, &host, &mem);
    e->set_param(self, static_cast<uint16_t>(ParamIndex(e, "Pad")), static_cast<float>(s.pad));
    if (s.name[0]) e->set_param(self, static_cast<uint16_t>(ParamIndex(e, s.name)), s.value);
    const drum808_t *u = fm1_crater_unit(self);
    const int snd = kPads[s.pad].sound;
    printf("{\"pad\":%d,\"param\":\"%s\",\"value\":%.9g,\"sound\":%d,\"potx\":[", s.pad, s.name, s.value, snd);
    for (int k = 0; k < D8P_NUM; ++k) printf("%s%.9g", k ? "," : "", u->potx[snd][k]);
    printf("],\"potv\":[");
    for (int k = 0; k < D8P_NUM; ++k) printf("%s%.9g", k ? "," : "", u->potv[snd][k]);
    printf("],\"drive\":%.9g,\"vel_depth\":%.9g,\"choke\":%d,\"vol\":%.9g}\n", u->shp[snd].drive,
           u->vel_depth, static_cast<int>(u->choke), u->vol);
    e->destroy(self);
  }
}

void Pads() {
  using namespace fm1::crater;
  const fm1_engine_t *e = Engine();
  fm1_host_t host = { FM1_ENGINE_API_VERSION, 44118.0f, 64 };
  for (int p = 0; p < kNumPads; ++p) {
    for (int vel : {88, 127}) {
      std::vector<unsigned char> mem;
      void *self = NewInstance(e, &host, &mem);
      e->note_on(self, static_cast<uint8_t>(kFirstNote + p), static_cast<uint8_t>(vel));
      float buf[128];
      double peak = 0;
      uint32_t frames = 0, ended = 0;
      const uint32_t limit = static_cast<uint32_t>(44118 * 8);
      while (frames < limit) {
        e->render(self, buf, 64);
        for (int k = 0; k < 64; ++k) {
          if (std::fabs(buf[2 * k]) > peak) peak = std::fabs(buf[2 * k]);
        }
        frames += 64;
        if (!drum808_active(fm1_crater_unit(self))) {
          ended = frames;
          break;
        }
      }
      printf("{\"pad\":%d,\"key\":%d,\"vel\":%d,\"peak\":%.6f,\"ends_after\":%u}\n", p, kFirstNote + p,
             vel, peak, ended);
      e->destroy(self);
    }
  }
}

}  // namespace

int main(int argc, char **argv) {
  float rate = 44118.0f;
  uint32_t block = 64;
  bool twin = false, fields = false, pads = false;
  for (int i = 1; i < argc; ++i) {
    if (!strcmp(argv[i], "--twin")) twin = true;
    else if (!strcmp(argv[i], "--fields")) fields = true;
    else if (!strcmp(argv[i], "--pads")) pads = true;
    else if (!strcmp(argv[i], "--rate") && i + 1 < argc) rate = static_cast<float>(atof(argv[++i]));
    else if (!strcmp(argv[i], "--block") && i + 1 < argc) block = static_cast<uint32_t>(atoi(argv[++i]));
    else {
      fprintf(stderr, "usage: fm1-crater-oracle --twin [--rate HZ] [--block N] | --fields | --pads\n");
      return 2;
    }
  }
  if (!block) block = 1;
  if (fields) Fields();
  if (pads) Pads();
  if (twin) return Twin(rate, block) ? 0 : 1;
  return fields || pads ? 0 : 2;
}
