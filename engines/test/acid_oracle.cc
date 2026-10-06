// acid_oracle.cc -- fm1-acid-oracle: "Acid Bass" (src/acid_bass.cc) against
// fm1-x0x's 303 bass driven directly (tests/test_engine_acid_bass.py).
// Built only while the GPL switch is on (mk/fm1-x0x.mk).
//
//   fm1-acid-oracle --twin [--rate HZ] [--block N]
//       Plays a set of 303 lines (triggers, slides, accents, rests, the
//       Devilfish and drive settings) through the engine in host blocks of
//       N frames, and through a copy of its vendored unit, taken after
//       create and the line's settings, driven as fm1-x0x's sequencer drives
//       it: bass303_note_on with the slide flag, bass303_note_off, and
//       bass303_render in 16-sample chunks counted from create, each event
//       on the chunk after its frame. Prints one JSON line per line played:
//       samples, how many differ, the largest difference, the peak. At
//       Volume 0.7 the two must be the same, bit for bit.
//   fm1-acid-oracle --fields [--rate HZ]
//       For a list of parameter settings, each on a fresh instance, the
//       unit's own values after set_param: the cutoff in Hz, the resonance,
//       the decay and slide coefficients, the drive, as JSON lines, for the
//       test to hold against the parameters' units.
//
// MIT licence (this file).

#include "fm1_engine.h"
#include "acid_bass.h"

#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>

namespace {

struct Ev {
  uint32_t frame;
  int key;        // -1: none
  int vel;        // 0: note-off
};

struct Line {
  const char *name;
  std::vector<std::pair<const char *, float> > params;
  std::vector<Ev> evs;
  uint32_t frames;
};

const fm1_engine_t *Engine() {
  const fm1_engine_t *e = fm1_engine_find("acid-bass");
  if (!e) {
    fprintf(stderr, "acid-bass is not in this build (FM1_GPL_MODS=0?)\n");
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

// A 303 line on 16ths at `bpm`: steps of {key or -1 rest, accent, slide}.
struct Step {
  int key;
  bool accent, slide;
};

Line MakeLine(const char *name, float rate, float bpm, const std::vector<Step> &steps,
              std::vector<std::pair<const char *, float> > params, int loops) {
  Line l;
  l.name = name;
  l.params = params;
  const double step = rate * 60.0 / bpm / 4.0;
  int held = -1;
  const int n = static_cast<int>(steps.size());
  for (int i = 0; i < n * loops; ++i) {
    const Step &s = steps[i % n];
    const uint32_t at = static_cast<uint32_t>(i * step);
    const uint32_t half = static_cast<uint32_t>(i * step + step / 2);
    if (s.key < 0) {
      if (held >= 0) l.evs.push_back(Ev{at, held, 0});
      held = -1;
      continue;
    }
    if (held >= 0 && held == s.key) {        // a slide into the same key: a tie
    } else {
      l.evs.push_back(Ev{at, s.key, s.accent ? 118 : 72});
      if (held >= 0) l.evs.push_back(Ev{at, held, 0});   // legato: the new key first
    }
    held = s.key;
    if (!s.slide) {
      l.evs.push_back(Ev{half, held, 0});
      held = -1;
    }
  }
  const uint32_t end = static_cast<uint32_t>(n * loops * step);
  if (held >= 0) l.evs.push_back(Ev{end, held, 0});
  l.frames = end + static_cast<uint32_t>(rate * 0.7);   // and the tail, to idle
  return l;
}

std::vector<Line> Lines(float rate) {
  std::vector<Line> out;
  const std::vector<Step> acid = {
    {45, true, false}, {45, false, true}, {57, false, false}, {-1, false, false},
    {48, false, true}, {52, true, true}, {55, false, false}, {45, false, false},
    {-1, false, false}, {57, true, false}, {45, false, true}, {43, false, true},
    {45, true, false}, {-1, false, false}, {60, false, true}, {57, false, false},
  };
  out.push_back(MakeLine("defaults", rate, 128, acid, {}, 2));
  out.push_back(MakeLine("squelch", rate, 132, acid,
                         {{"Cutoff", 420}, {"Resonance", 92}, {"Env Mod", 85}, {"Decay", 300},
                          {"Accent", 90}}, 2));
  out.push_back(MakeLine("square-devilfish", rate, 120, acid,
                         {{"Wave", 1}, {"Slide", 250}, {"Acc Decay", 1500}, {"Cutoff", 1500},
                          {"Resonance", 70}}, 2));
  out.push_back(MakeLine("soft-drive", rate, 125, acid,
                         {{"Drive", 60}, {"Drive Type", 1}, {"Resonance", 80}}, 2));
  out.push_back(MakeLine("rat-drive", rate, 125, acid,
                         {{"Drive", 75}, {"Drive Type", 2}, {"Env Mod", 100}}, 2));
  const std::vector<Step> held = {{40, false, true}, {40, true, true}, {52, false, true},
                                  {40, false, false}};
  out.push_back(MakeLine("ties-and-long-slides", rate, 90, held, {{"Slide", 360}}, 3));
  return out;
}

// The unit's running state: every float that decays toward 0 while a tail
// rings out, where a subnormal could sit.
int SubnormalState(const bass303_t *u) {
  const float *f[] = {
    &u->phase, &u->env_y, &u->rc1_y, &u->rc2_y, &u->amp_y, &u->slew_y, &u->c_inc, &u->c_b0,
    &u->c_k, &u->c_g2, &u->c_a, &u->dc.x1, &u->dc.x2, &u->dc.y1, &u->dc.y2, &u->hp1_x1,
    &u->hp1_y1, &u->f_y1, &u->f_y2, &u->f_y3, &u->f_y4, &u->fb_x1, &u->fb_y1, &u->ap_x1,
    &u->ap_y1, &u->hp2_x1, &u->hp2_y1, &u->nt.x1, &u->nt.x2, &u->nt.y1, &u->nt.y2,
    &u->s_pre.z1, &u->s_pre.z2, &u->s_post.z1, &u->s_post.z2, &u->up_lp.z1, &u->up_lp.z2,
    &u->down_lp.z1, &u->down_lp.z2, &u->r_z[0], &u->r_z[1], &u->r_z[2], &u->r_corr_z,
    &u->r_tone_z, &u->dcb_x1, &u->dcb_y1,
  };
  int n = 0;
  for (unsigned k = 0; k < sizeof(f) / sizeof(f[0]); ++k) n += std::fpclassify(*f[k]) == FP_SUBNORMAL;
  for (int k = 0; k < 6; ++k) {
    n += std::fpclassify(u->hb1[k].x1) == FP_SUBNORMAL;
    n += std::fpclassify(u->hb1[k].y1) == FP_SUBNORMAL;
  }
  return n;
}

bool Twin(float rate, uint32_t block) {
  const fm1_engine_t *e = Engine();
  fm1_host_t host = { FM1_ENGINE_API_VERSION, rate, block };
  bool ok = true;
  for (const Line &l : Lines(rate)) {
    std::vector<unsigned char> mem(e->instance_size(&host) + 16);
    void *aligned = reinterpret_cast<void *>((reinterpret_cast<uintptr_t>(mem.data()) + 15) &
                                             ~static_cast<uintptr_t>(15));
    void *self = e->create(aligned, &host);
    if (!self) {
      printf("{\"line\":\"%s\",\"refused\":true}\n", l.name);
      return false;
    }
    for (const auto &p : l.params) e->set_param(self, static_cast<uint16_t>(ParamIndex(e, p.first)), p.second);
    bass303_t twin = *fm1_acid_bass_unit(self);

    std::vector<float> a(2 * l.frames), b(l.frames);
    // The engine: host blocks of `block`, each event at its frame.
    size_t next = 0;
    int state_subnormal = 0;
    for (uint32_t f = 0; f < l.frames;) {
      while (next < l.evs.size() && l.evs[next].frame <= f) {
        const Ev &ev = l.evs[next++];
        if (ev.vel) e->note_on(self, static_cast<uint8_t>(ev.key), static_cast<uint8_t>(ev.vel));
        else e->note_off(self, static_cast<uint8_t>(ev.key));
      }
      uint32_t n = block;
      if (next < l.evs.size() && l.evs[next].frame - f < n) n = l.evs[next].frame - f;
      if (l.frames - f < n) n = l.frames - f;
      e->render(self, &a[2 * f], n);
      const int sub = SubnormalState(fm1_acid_bass_unit(self));
      if (sub > state_subnormal) state_subnormal = sub;
      f += n;
    }
    // The twin: 16-sample chunks; an event lands on the chunk after its frame.
    next = 0;
    int held = -1;
    for (uint32_t c = 0; c < l.frames; c += fm1::acid_bass::kChunk) {
      while (next < l.evs.size() && l.evs[next].frame <= c) {
        const Ev &ev = l.evs[next++];
        if (ev.vel) {
          bass303_note_on(&twin, ev.key, ev.vel >= 100, held >= 0 ? 1 : 0);
          held = ev.key;
        } else if (ev.key == held) {
          bass303_note_off(&twin);
          held = -1;
        }
      }
      float chunk[fm1::acid_bass::kChunk];
      bass303_render(&twin, chunk, static_cast<int>(fm1::acid_bass::kChunk));
      for (uint32_t k = 0; k < fm1::acid_bass::kChunk && c + k < l.frames; ++k) b[c + k] = chunk[k];
    }
    uint32_t differ = 0, lr = 0, out_subnormal = 0, nonfinite = 0;
    double maxd = 0, peak = 0;
    for (uint32_t k = 0; k < l.frames; ++k) {
      const double d = std::fabs(static_cast<double>(a[2 * k]) - b[k]);
      if (a[2 * k] != b[k]) ++differ;
      if (std::fpclassify(a[2 * k]) == FP_SUBNORMAL) ++out_subnormal;
      if (!std::isfinite(a[2 * k])) ++nonfinite;
      if (a[2 * k] != a[2 * k + 1]) ++lr;
      if (d > maxd) maxd = d;
      if (std::fabs(a[2 * k]) > peak) peak = std::fabs(a[2 * k]);
    }
    printf("{\"line\":\"%s\",\"rate\":%g,\"block\":%u,\"samples\":%u,\"differ\":%u,\"max_diff\":%.9g,"
           "\"left_right_differ\":%u,\"peak\":%.6f,\"idle_at_end\":%s,\"nonfinite\":%u,"
           "\"subnormal_out\":%u,\"subnormal_state_max\":%d}\n",
           l.name, rate, block, l.frames, differ, maxd, lr, peak,
           fm1_acid_bass_unit(self)->idle ? "true" : "false", nonfinite, out_subnormal,
           state_subnormal);
    ok = ok && differ == 0 && lr == 0 && nonfinite == 0;
    e->destroy(self);
  }
  return ok;
}

void Fields(float rate) {
  const fm1_engine_t *e = Engine();
  fm1_host_t host = { FM1_ENGINE_API_VERSION, rate, 64 };
  struct Setting { const char *name; float value; };
  static const Setting kSettings[] = {
    {"", 0}, {"Cutoff", 314}, {"Cutoff", 1000}, {"Cutoff", 2394}, {"Resonance", 0},
    {"Resonance", 37.5f}, {"Resonance", 100}, {"Env Mod", 0}, {"Env Mod", 100}, {"Decay", 200},
    {"Decay", 1000}, {"Decay", 2000}, {"Accent", 25}, {"Slide", 2}, {"Slide", 60}, {"Slide", 360},
    {"Acc Decay", 30}, {"Acc Decay", 200}, {"Acc Decay", 3000}, {"Drive", 40}, {"Drive Type", 2},
    {"Wave", 1},
  };
  for (const Setting &s : kSettings) {
    std::vector<unsigned char> mem(e->instance_size(&host) + 16);
    void *aligned = reinterpret_cast<void *>((reinterpret_cast<uintptr_t>(mem.data()) + 15) &
                                             ~static_cast<uintptr_t>(15));
    void *self = e->create(aligned, &host);
    if (s.name[0]) e->set_param(self, static_cast<uint16_t>(ParamIndex(e, s.name)), s.value);
    const bass303_t *u = fm1_acid_bass_unit(self);
    printf("{\"param\":\"%s\",\"value\":%.9g,\"sr\":%.9g,\"cutoff\":%.9g,\"reso\":%.9g,"
           "\"env_scaler\":%.9g,\"env_offset\":%.9g,\"decay_c\":%.9g,\"accdec_c\":%.9g,"
           "\"accent\":%.9g,\"slew_c\":%.9g,\"drv_amt\":%.9g,\"wave\":%d,\"drv_type\":%d,"
           "\"tuning\":%.9g,\"amp_scaler\":%.9g,\"idle\":%d}\n",
           s.name, s.value, u->sr, u->cutoff, u->reso, u->env_scaler, u->env_offset, u->decay_c,
           u->accdec_c, u->accent, u->slew_c, u->drv_amt, u->wave, u->drv_type, u->tuning,
           u->amp_scaler, u->idle);
    e->destroy(self);
  }
}

}  // namespace

int main(int argc, char **argv) {
  float rate = 44100.0f;
  uint32_t block = 64;
  bool twin = false, fields = false;
  for (int i = 1; i < argc; ++i) {
    if (!strcmp(argv[i], "--twin")) twin = true;
    else if (!strcmp(argv[i], "--fields")) fields = true;
    else if (!strcmp(argv[i], "--rate") && i + 1 < argc) rate = static_cast<float>(atof(argv[++i]));
    else if (!strcmp(argv[i], "--block") && i + 1 < argc) block = static_cast<uint32_t>(atoi(argv[++i]));
    else {
      fprintf(stderr, "usage: fm1-acid-oracle --twin [--rate HZ] [--block N] | --fields [--rate HZ]\n");
      return 2;
    }
  }
  if (!block) block = 1;
  if (fields) Fields(rate);
  if (twin) return Twin(rate, block) ? 0 : 1;
  return twin || fields ? 0 : 2;
}
