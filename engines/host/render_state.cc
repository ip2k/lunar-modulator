// render_state.cc -- fm1-render's --load and --save (render_state.h). Host
// code: stdio, the heap. MIT licence.
#include "render_state.h"

#include "fm1_dx7.h"
#include "fm1_state_mod.h"
#include "state_clip.h"

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <strings.h>

namespace render_state {
namespace {

// ---- Records, held ------------------------------------------------------------------
// A record with its pieces joined and its text owned.
struct Rec {
  fm1_rec_t r;
  std::string text;          // INFO, LINE, DATA
};

int Hold(void *ctx, const fm1_rec_t *r) {
  std::vector<Rec> *v = static_cast<std::vector<Rec> *>(ctx);
  if ((r->type == FM1_REC_INFO || r->type == FM1_REC_LINE || r->type == FM1_REC_DATA) &&
      !(r->piece & FM1_REC_FIRST) && !v->empty()) {
    Rec &last = v->back();
    if (r->type == FM1_REC_INFO) last.text.append(r->u.info.s, r->u.info.n);
    else if (r->type == FM1_REC_LINE) last.text.append(r->u.line.s, r->u.line.n);
    else last.text.append(reinterpret_cast<const char *>(r->u.data.b), r->u.data.n);
    last.r.piece = r->piece;
    return 1;
  }
  Rec x;
  x.r = *r;
  if (r->type == FM1_REC_INFO) x.text.assign(r->u.info.s, r->u.info.n);
  else if (r->type == FM1_REC_LINE) x.text.assign(r->u.line.s, r->u.line.n);
  else if (r->type == FM1_REC_DATA) x.text.assign(reinterpret_cast<const char *>(r->u.data.b), r->u.data.n);
  v->push_back(x);
  return 1;
}

// Feeds held records to a sink, pieces as one.
bool Feed(const std::vector<Rec> &v, fm1_rec_sink_t sink, void *ctx) {
  for (size_t i = 0; i < v.size(); ++i) {
    fm1_rec_t r = v[i].r;
    if (r.type == FM1_REC_INFO || r.type == FM1_REC_LINE || r.type == FM1_REC_DATA) {
      r.piece = FM1_REC_FIRST | FM1_REC_LAST;
      if (r.type == FM1_REC_INFO) { r.u.info.s = v[i].text.data(); r.u.info.n = static_cast<uint16_t>(v[i].text.size()); }
      else if (r.type == FM1_REC_LINE) { r.u.line.s = v[i].text.data(); r.u.line.n = static_cast<uint32_t>(v[i].text.size()); }
      else { r.u.data.b = reinterpret_cast<const uint8_t *>(v[i].text.data()); r.u.data.n = static_cast<uint16_t>(v[i].text.size()); }
    }
    if (!sink(ctx, &r)) return false;
  }
  return true;
}

uint32_t MemRead(void *ctx, uint32_t off, uint8_t *out, uint32_t n) {
  const std::string *s = static_cast<const std::string *>(ctx);
  if (off >= s->size()) return 0;
  if (n > s->size() - off) n = static_cast<uint32_t>(s->size() - off);
  memcpy(out, s->data() + off, n);
  return n;
}

void Put(void *ctx, const char *s, size_t n) { static_cast<std::string *>(ctx)->append(s, n); }

bool ReadFile(const std::string &path, std::string *out) {
  FILE *f = fopen(path.c_str(), "rb");
  if (!f) return false;
  char buf[65536];
  size_t got;
  out->clear();
  while ((got = fread(buf, 1, sizeof(buf), f)) > 0) {
    out->append(buf, got);
    if (out->size() > (1u << 20)) break;
  }
  fclose(f);
  return out->size() <= (1u << 20);
}

std::string Report(const fm1_state_report_t &rep) {
  char b[512];
  snprintf(b, sizeof(b), "%s: %s%s%s%s", fm1_state_code_name(rep.code), rep.what, rep.path[0] ? " at " : "",
           rep.path, rep.name[0] ? (std::string(" (") + rep.name + ")").c_str() : "");
  return b;
}

const fm1_state_names_t &Names() {
  static fm1_state_names_t nm;
  static bool done = false;
  if (!done) { fm1_state_names_default(&nm); done = true; }
  return nm;
}

// A unit's records as the (name, value) pairs fm1-render sets, a pad kit's
// pads after its other values and its focus last.
UnitIn UnitOf(const std::string &id, unsigned role, const std::vector<const Rec *> &recs, std::string *skipped) {
  UnitIn u;
  u.id = id;
  const fm1_engine_t *e = fm1_state_engine(&Names(), role, id.c_str());
  if (!e) return u;
  int focus_index = -1;
  float focus_value = 0.0f;
  bool has_focus = false;
  for (uint16_t i = 0; i < e->n_params; ++i) {
    if (fm1_state_param_focus(e, i) == 1) focus_index = i;
  }
  std::vector<std::pair<unsigned, std::pair<std::string, float> > > pads;
  for (size_t k = 0; k < recs.size(); ++k) {
    const fm1_rec_t &r = recs[k]->r;
    const int i = fm1_param_index(e, r.u.param.uid);
    if (i < 0) { *skipped += " #" + std::to_string(r.u.param.uid); continue; }
    const fm1_param_t &p = e->params[i];
    float v;
    if (r.u.param.vtype == FM1_VAL_INDEX) v = p.min + static_cast<float>(r.u.param.bits);
    else memcpy(&v, &r.u.param.bits, sizeof(v));
    if (r.u.param.focus != FM1_FOCUS_NONE) {
      pads.push_back(std::make_pair(static_cast<unsigned>(r.u.param.focus), std::make_pair(std::string(p.name), v)));
    } else if (i == focus_index) {
      has_focus = true;
      focus_value = v;
    } else {
      u.params.push_back(std::make_pair(std::string(p.name), v));
    }
  }
  if (focus_index >= 0 && !pads.empty()) {
    for (unsigned pad = 0; pad < FM1_STATE_PADS; ++pad) {
      bool first = true;
      for (size_t k = 0; k < pads.size(); ++k) {
        if (pads[k].first != pad) continue;
        if (first) u.params.push_back(std::make_pair(std::string(e->params[focus_index].name), e->params[focus_index].min + pad));
        first = false;
        u.params.push_back(pads[k].second);
      }
    }
    if (!has_focus) { has_focus = true; focus_value = e->params[focus_index].def; }
  }
  if (has_focus) u.params.push_back(std::make_pair(std::string(e->params[focus_index].name), focus_value));
  return u;
}

// A sound file's cable codes and sources, for sound unit k.
unsigned SoundCode(unsigned code, unsigned k) {
  if (code == FM1_MOD_SOUND) return fm1_mod_sound_unit(k);
  if (code == FM1_MOD_INSERT || code == FM1_MOD_INSERT + 1u) return fm1_mod_insert_unit(k, code - FM1_MOD_INSERT);
  return code;
}
unsigned SoundSource(unsigned src, unsigned k) {
  if (src >= FM1_MOD_SRC_S_NOTE && src < FM1_MOD_SRC_SYSTEM && (src - FM1_MOD_SRC_S_NOTE) % 4u == 0u) return src + k;
  return src;
}

size_t At44(const fm1_engine_t *e) {
  const fm1_host_t h = { FM1_ENGINE_API_VERSION, static_cast<float>(FM1_STATE_HZ), 64 };
  return (e->instance_size(&h) + 15u) & ~static_cast<size_t>(15u);
}

}  // namespace

// ---- --load ---------------------------------------------------------------------------
bool Load(const std::string &spec, bool without, Loaded *into, std::string *err) {
  std::string path = spec;
  int sound = -1, track = -1, slot = -1;
  if (spec.size() > 3 && spec[0] == 's' && spec[2] == ':' && spec[1] >= '1' && spec[1] <= '4') {
    sound = spec[1] - '1';
    path = spec.substr(3);
  } else if (spec.size() > 1 && spec[0] == 't') {
    int t = 0, s = 0, n = 0;
    if (sscanf(spec.c_str(), "t%d.%d:%n", &t, &s, &n) == 2 && n > 0 && t >= 1 && t <= 16 && s >= 1 && s <= 8) {
      track = t - 1;
      slot = s - 1;
      path = spec.substr(static_cast<size_t>(n));
    }
  }
  std::string data;
  if (!ReadFile(path, &data)) { *err = "cannot read " + path; return false; }
  // Pass 1: every record, and what the file needs.
  std::vector<Rec> recs;
  fm1_state_report_t rep;
  fm1_state_report_init(&rep);
  const int enc = fm1_state_sniff(reinterpret_cast<const uint8_t *>(data.data()), data.size());
  const bool ok = enc == 1 ? fm1_state_bin_read(MemRead, &data, static_cast<uint32_t>(data.size()), Hold, &recs, &rep, 0)
                           : fm1_state_json_read(&Names(), MemRead, &data, Hold, &recs, &rep);
  if (!ok) { *err = path + ": " + Report(rep); return false; }
  if (rep.unknown && !without) {
    *err = path + ": UNKNOWN: uses " + rep.name + ", which this build does not have (--without leaves it out)";
    return false;
  }
  const int kind = recs.empty() ? 0 : recs[0].r.u.head.kind;
  if (kind == FM1_STATE_SOUND && sound < 0) sound = 0;
  if (kind == FM1_STATE_CLIP && track < 0) {
    *err = path + ": a clip loads into a track and a slot: --load tT.S:" + path;
    return false;
  }
  size_t ram = 0;
  bool has_mod = false;
  for (size_t i = 0; i < recs.size(); ++i) {
    const fm1_rec_t &r = recs[i].r;
    if (r.type == FM1_REC_MOD) has_mod = true;
    if (r.type == FM1_REC_UNIT && r.u.unit.id[0] && r.role != FM1_ROLE_MFX) {
      const fm1_engine_t *e = fm1_state_engine(&Names(), r.role, r.u.unit.id);
      if (e) ram += At44(e);
    }
  }
  if (has_mod) ram += (fm1_mod_size() + 15u) & ~static_cast<size_t>(15u);
  if (ram > FM1_STATE_RAM_BUDGET) {
    *err = path + ": RAM: needs " + std::to_string(ram) + " B of instances at 44,118 Hz; the FM-1 has " +
           std::to_string(FM1_STATE_RAM_BUDGET) + " B";
    return false;
  }
  // Pass 2: into the renderer's places.
  into->kind = kind;
  std::string skipped;
  std::vector<int> mod_from;     // where this file's modules go
  int pos_map[8];
  for (int p = 0; p < 8; ++p) pos_map[p] = p;
  for (size_t i = 0; i < recs.size(); ++i) {
    const fm1_rec_t &r = recs[i].r;
    if (r.type != FM1_REC_UNIT) continue;
    std::vector<const Rec *> params;
    bool on = false;
    for (size_t j = i + 1; j < recs.size(); ++j) {
      const fm1_rec_t &q = recs[j].r;
      if (q.type == FM1_REC_PARAM && q.role == r.role && q.sound == r.sound && q.slot == r.slot) params.push_back(&recs[j]);
      if (q.type == FM1_REC_ON && q.role == r.role && q.sound == r.sound && q.slot == r.slot) on = q.u.on != 0;
    }
    const std::string id = fm1_state_engine(&Names(), r.role, r.u.unit.id) ? r.u.unit.id : "";
    UnitIn u = UnitOf(id, r.role, params, &skipped);
    u.on = on;
    const unsigned k = kind == FM1_STATE_SOUND ? static_cast<unsigned>(sound) : r.sound;
    switch (r.role) {
      case FM1_ROLE_SOUND:
        into->sound[k] = u;
        into->has_sound[k] = true;
        if (k) into->any_slot = true;
        break;
      case FM1_ROLE_INSERT:
        into->any_slot = true;
        if (into->inserts[k].size() <= r.slot) into->inserts[k].resize(r.slot + 1u);
        into->inserts[k][r.slot] = u;
        break;
      case FM1_ROLE_MFX:
        if (into->mfx[k].size() <= r.slot) into->mfx[k].resize(r.slot + 1u);
        into->mfx[k][r.slot] = u;
        break;
      case FM1_ROLE_MASTER:
        if (into->master.size() <= r.slot) into->master.resize(r.slot + 1u);
        into->master[r.slot] = u;
        break;
      default:
        break;
    }
  }
  bool mod_ok = true;
  for (size_t i = 0; i < recs.size(); ++i) {
    const fm1_rec_t &r = recs[i].r;
    switch (r.type) {
      case FM1_REC_LEVEL: {
        const unsigned k = kind == FM1_STATE_SOUND ? static_cast<unsigned>(sound) : r.sound;
        memcpy(&into->level[k], &r.u.level, sizeof(float));
        into->has_level[k] = true;
        into->any_slot = true;
        break;
      }
      case FM1_REC_DX7: {
        std::array<uint8_t, 155> v;
        memcpy(v.data(), r.u.dx7.vced, 155);
        into->dx7.push_back(std::make_pair(static_cast<unsigned>(r.slot), v));
        break;
      }
      case FM1_REC_MOD:
        into->has_mod = true;
        break;
      case FM1_REC_SEED:
        into->has_seed = true;
        into->seed = r.u.seed;
        break;
      case FM1_REC_MODULE: {
        // A sound's or an effects chain's modules go where they were if free,
        // else to a free position; a project's or a mod rack's replace.
        bool taken[8] = { false };
        for (size_t j = 0; j < into->mod.size(); ++j) {
          if (into->mod[j].type == FM1_REC_MODULE) taken[into->mod[j].slot] = true;
        }
        int p = r.slot;
        if (taken[p]) {
          for (p = 0; p < 8 && taken[p]; ++p) {}
          if (p == 8) {
            if (!without) {
              *err = path + ": NO_ROOM: the rack is full (8 of 8) (--without loads it without its modulation)";
              return false;
            }
            mod_ok = false;
            break;
          }
        }
        pos_map[r.slot] = p;
        fm1_rec_t x = r;
        x.slot = static_cast<uint8_t>(p);
        into->mod.push_back(x);
        into->mod_names.push_back("");
        break;
      }
      default:
        break;
    }
  }
  // fm1-render keeps no gap between a sound's inserts or in the --fx chain:
  // a null closes up, and the cables move with their units.
  int ins_map[4][2], fx_map[4];
  for (int k = 0; k < 4; ++k) {
    int n = 0;
    for (int j = 0; j < 2; ++j) {
      const bool on = static_cast<size_t>(j) < into->inserts[k].size() && !into->inserts[k][j].id.empty();
      ins_map[k][j] = on ? n++ : -1;
    }
  }
  {
    int n = 0;
    for (int j = 0; j < 4; ++j) {
      const bool on = static_cast<size_t>(j) < into->master.size() && !into->master[j].id.empty();
      fx_map[j] = on ? n++ : -1;
    }
  }
  if (mod_ok) {
    for (size_t i = 0; i < recs.size(); ++i) {
      const fm1_rec_t &r = recs[i].r;
      if (r.type == FM1_REC_PARAM && r.role == FM1_ROLE_MODULE) {
        fm1_rec_t x = r;
        x.slot = static_cast<uint8_t>(pos_map[r.slot]);
        into->mod.push_back(x);
        into->mod_names.push_back("");
      } else if (r.type == FM1_REC_CABLE) {
        fm1_rec_t x = r;
        fm1_mod_slot_t &s = x.u.cable.s;
        auto remap_src = [&](uint8_t v) -> uint8_t {
          if (v == FM1_MOD_NONE) return v;
          if (v >= FM1_MOD_SRC_MODULE) {
            const unsigned p = (v - FM1_MOD_SRC_MODULE) / 8u, port = (v - FM1_MOD_SRC_MODULE) % 8u;
            return static_cast<uint8_t>(FM1_MOD_SRC_MODULE + 8u * static_cast<unsigned>(pos_map[p]) + port);
          }
          return kind == FM1_STATE_SOUND ? static_cast<uint8_t>(SoundSource(v, static_cast<unsigned>(sound))) : v;
        };
        s.src = remap_src(s.src);
        s.via = remap_src(s.via);
        if (s.dst_unit >= FM1_MOD_MODULE && s.dst_unit < FM1_MOD_MODULE + 8u) {
          s.dst_unit = static_cast<uint8_t>(FM1_MOD_MODULE + static_cast<unsigned>(pos_map[s.dst_unit - FM1_MOD_MODULE]));
        } else if (kind == FM1_STATE_SOUND) {
          if (s.dst_unit == FM1_MOD_HOST && s.dst == FM1_MOD_HOST_PITCH_UID && sound > 0) {
            s.dst = static_cast<uint16_t>(FM1_MOD_HOST_PITCH2_UID + static_cast<unsigned>(sound) - 1u);
          }
          s.dst_unit = static_cast<uint8_t>(SoundCode(s.dst_unit, static_cast<unsigned>(sound)));
        }
        const bool own_units = kind == FM1_STATE_PROJECT || kind == FM1_STATE_SOUND || kind == FM1_STATE_FX;
        if (!own_units) {
          /* a mod rack names the units the renderer has: as they are */
        } else if (s.dst_unit >= FM1_MOD_INSERT && s.dst_unit < FM1_MOD_INSERT + 16u &&
                   (s.dst_unit - FM1_MOD_INSERT) % 4u < 2u) {
          const unsigned k = (s.dst_unit - FM1_MOD_INSERT) / 4u, j = (s.dst_unit - FM1_MOD_INSERT) % 4u;
          if (ins_map[k][j] < 0) { skipped += " a cable to an empty insert"; continue; }
          s.dst_unit = static_cast<uint8_t>(fm1_mod_insert_unit(k, static_cast<unsigned>(ins_map[k][j])));
        } else if (s.dst_unit == FM1_MOD_FX1 || s.dst_unit == FM1_MOD_FX2 || s.dst_unit == FM1_STATE_CHAIN3 ||
                   s.dst_unit == FM1_STATE_CHAIN4) {
          const int j = s.dst_unit == FM1_MOD_FX1 ? 0 : s.dst_unit == FM1_MOD_FX2 ? 1 : s.dst_unit == FM1_STATE_CHAIN3 ? 2 : 3;
          if (fx_map[j] < 0) { skipped += " a cable to an empty effect"; continue; }
          if (fx_map[j] > 1) { skipped += " a cable to a third or fourth effect (fm1-render modulates two)"; continue; }
          s.dst_unit = static_cast<uint8_t>(FM1_MOD_FX1 + static_cast<unsigned>(fx_map[j]));
        }
        // A free slot, its own if it can.
        bool taken[32] = { false };
        for (size_t j = 0; j < into->mod.size(); ++j) {
          if (into->mod[j].type == FM1_REC_CABLE) taken[into->mod[j].slot] = true;
        }
        int sl = r.slot;
        if (taken[sl]) {
          for (sl = 0; sl < 32 && taken[sl]; ++sl) {}
          if (sl == 32) {
            if (!without) {
              *err = path + ": NO_ROOM: the matrix is full (32 of 32)";
              return false;
            }
            continue;
          }
        }
        x.slot = static_cast<uint8_t>(sl);
        into->mod.push_back(x);
        into->mod_names.push_back(r.u.cable.name);
      }
    }
  }
  std::string lines;
  for (size_t i = 0; i < recs.size(); ++i) {
    if (recs[i].r.type != FM1_REC_LINE) continue;
    if (recs[i].r.u.line.which == FM1_LINES_SET) lines += recs[i].text + "\n";
    else into->clip.push_back(recs[i].text);
  }
  if (!lines.empty()) into->set = lines;
  if (kind == FM1_STATE_CLIP) { into->clip_track = track; into->clip_slot = slot; }
  if (kind == FM1_STATE_SET && enc == 1) into->set = lines;
  if (!skipped.empty() || rep.skipped || rep.repaired) {
    fprintf(stderr, "load %s: %u skipped, %u repaired%s%s\n", path.c_str(), rep.skipped, rep.repaired,
            skipped.empty() ? "" : "; not applied:", skipped.c_str());
  }
  return true;
}

// ---- --save ---------------------------------------------------------------------------
namespace {

void Add(std::vector<Rec> *v, const fm1_rec_t &r, const std::string &text = std::string()) {
  Rec x;
  x.r = r;
  x.text = text;
  v->push_back(x);
}

fm1_rec_t Blank(int type) {
  fm1_rec_t r;
  memset(&r, 0, sizeof(r));
  r.type = static_cast<uint8_t>(type);
  return r;
}

// A unit's parameters as records: the values the render set, a pad kit's
// per-pad ones by the focus they were set under.
void UnitRecs(std::vector<Rec> *v, const UnitOut &u, unsigned role, unsigned sound, unsigned slot) {
  fm1_rec_t r = Blank(FM1_REC_UNIT);
  r.role = static_cast<uint8_t>(role);
  r.sound = static_cast<uint8_t>(sound);
  r.slot = static_cast<uint8_t>(slot);
  if (u.e) strncpy(r.u.unit.id, u.e->id, sizeof(r.u.unit.id) - 1u);
  Add(v, r);
  if (!u.e) return;
  if (role == FM1_ROLE_MFX) {
    fm1_rec_t o = r;
    o.type = FM1_REC_ON;
    o.u.on = u.on ? 1 : 0;
    Add(v, o);
  }
  const fm1_engine_t *e = u.e;
  std::vector<float> value(e->n_params * (1u + FM1_STATE_PADS), 0.0f);
  std::vector<bool> set(value.size(), false);
  int focus_index = -1;
  unsigned focus = 0;
  for (uint16_t i = 0; i < e->n_params; ++i) {
    if (fm1_state_param_focus(e, i) == 1) {
      focus_index = i;
      focus = static_cast<unsigned>(e->params[i].def - e->params[i].min);
    }
  }
  for (size_t k = 0; u.params && k < u.params->size(); ++k) {
    const std::string &name = (*u.params)[k].first;
    const int i = fm1_state_param_find(&Names(), e->id, e->params, e->n_params, name.c_str(), name.size());
    if (i < 0) continue;
    const float x = fm1_param_clamp(&e->params[i], (*u.params)[k].second);
    if (i == focus_index) focus = static_cast<unsigned>(x - e->params[i].min + 0.5f) % FM1_STATE_PADS;
    const size_t at = fm1_state_param_focus(e, static_cast<unsigned>(i)) == 2 ? (1u + focus) * e->n_params + i
                                                                              : static_cast<size_t>(i);
    value[at] = x;
    set[at] = true;
  }
  for (unsigned f = 0; f <= FM1_STATE_PADS; ++f) {
    for (uint16_t i = 0; i < e->n_params; ++i) {
      const size_t at = f * e->n_params + i;
      if (!set[at]) continue;
      const fm1_param_t &p = e->params[i];
      fm1_rec_t q = r;
      q.type = FM1_REC_PARAM;
      q.u.param.uid = p.uid;
      q.u.param.focus = f ? static_cast<uint8_t>(f - 1u) : static_cast<uint8_t>(FM1_FOCUS_NONE);
      if (p.type == FM1_PARAM_ENUM) {
        q.u.param.vtype = FM1_VAL_INDEX;
        q.u.param.bits = static_cast<uint32_t>(value[at] - p.min + 0.5f);
      } else {
        float x = value[at] == 0.0f ? 0.0f : value[at];
        q.u.param.vtype = FM1_VAL_F32;
        memcpy(&q.u.param.bits, &x, sizeof(x));
      }
      Add(v, q);
    }
  }
}

int HoldMod(void *ctx, const fm1_rec_t *r) {
  static_cast<std::vector<fm1_rec_t> *>(ctx)->push_back(*r);
  return 1;
}

// The runtime's modules and the cables of `keep`, remapped by `code` and
// `src` (a sound file's own codes); only the modules those cables use.
void ModRecs(std::vector<Rec> *v, const Have &h, bool with_seed, bool all,
             bool (*keep)(const fm1_mod_slot_t &, unsigned), unsigned arg,
             unsigned (*code)(unsigned, unsigned), unsigned (*src)(unsigned, unsigned)) {
  std::vector<fm1_rec_t> m;
  fm1_state_mod_collect(h.mod, h.seed, with_seed, HoldMod, &m);
  bool used[8] = { false };
  for (size_t i = 0; i < m.size(); ++i) {
    if (m[i].type != FM1_REC_CABLE || (!all && !keep(m[i].u.cable.s, arg))) continue;
    const fm1_mod_slot_t &s = m[i].u.cable.s;
    if (s.src >= FM1_MOD_SRC_MODULE && s.src != FM1_MOD_NONE) used[(s.src - FM1_MOD_SRC_MODULE) / 8u] = true;
    if (s.via >= FM1_MOD_SRC_MODULE && s.via != FM1_MOD_NONE) used[(s.via - FM1_MOD_SRC_MODULE) / 8u] = true;
  }
  for (size_t i = 0; i < m.size(); ++i) {
    fm1_rec_t r = m[i];
    if (!all && (r.type == FM1_REC_MODULE || (r.type == FM1_REC_PARAM && r.role == FM1_ROLE_MODULE)) && !used[r.slot]) continue;
    if (r.type == FM1_REC_CABLE) {
      if (!all && !keep(r.u.cable.s, arg)) continue;
      if (code) r.u.cable.s.dst_unit = static_cast<uint8_t>(code(r.u.cable.s.dst_unit, arg));
      if (src) {
        if (r.u.cable.s.src < FM1_MOD_SRC_SYSTEM) r.u.cable.s.src = static_cast<uint8_t>(src(r.u.cable.s.src, arg));
        if (r.u.cable.s.via < FM1_MOD_SRC_SYSTEM) r.u.cable.s.via = static_cast<uint8_t>(src(r.u.cable.s.via, arg));
      }
    }
    Add(v, r);
  }
}

// The engine a unit code reaches in the renderer, or NULL.
const fm1_engine_t *EngineAt(const Have &h, unsigned code) {
  const unsigned u = fm1_mod_unit_canonical(code);
  const int k = fm1_mod_unit_sound(u);
  if (k >= 0) return h.sound[k].e;
  if (u == FM1_MOD_FX1 || u == FM1_MOD_FX2) return u - FM1_MOD_FX1 < h.fx.size() ? h.fx[u - FM1_MOD_FX1].e : NULL;
  if (u >= FM1_MOD_INSERT && u < FM1_MOD_INSERT + 16u) {
    const unsigned s = (u - FM1_MOD_INSERT) / 4u, j = (u - FM1_MOD_INSERT) % 4u;
    return j < h.inserts[s].size() ? h.inserts[s][j].e : NULL;
  }
  return NULL;
}

// A mod rack holds no engines: its cables name the project's units'
// parameters (the note's §7.3), so a uid goes back to its name.
void NameCables(std::vector<Rec> *v, size_t from, const Have &h) {
  for (size_t i = from; i < v->size(); ++i) {
    fm1_rec_t &r = (*v)[i].r;
    if (r.type != FM1_REC_CABLE || !r.u.cable.s.dst || (r.u.cable.s.flags & FM1_MOD_SLOT_GATE_DST)) continue;
    const fm1_engine_t *e = EngineAt(h, r.u.cable.s.dst_unit);
    const int p = e ? fm1_param_index(e, r.u.cable.s.dst) : -1;
    if (p < 0) continue;
    strncpy(r.u.cable.name, e->params[p].name, sizeof(r.u.cable.name) - 1u);
    r.u.cable.s.dst = 0;
  }
}

bool SoundsCable(const fm1_mod_slot_t &s, unsigned k) {
  const unsigned u = fm1_mod_unit_canonical(s.dst_unit);
  return u == fm1_mod_sound_unit(k) || u == fm1_mod_insert_unit(k, 0) || u == fm1_mod_insert_unit(k, 1) ||
         (s.dst_unit == FM1_MOD_HOST && s.dst == (k ? FM1_MOD_HOST_PITCH2_UID + k - 1u : FM1_MOD_HOST_PITCH_UID));
}
unsigned ToSoundFile(unsigned code, unsigned k) {
  if (code == fm1_mod_sound_unit(k)) return FM1_MOD_SOUND;
  if (code == fm1_mod_insert_unit(k, 0)) return FM1_MOD_INSERT;
  if (code == fm1_mod_insert_unit(k, 1)) return FM1_MOD_INSERT + 1u;
  return code;
}
unsigned SourceToSoundFile(unsigned src, unsigned k) {
  if (src >= FM1_MOD_SRC_S_NOTE && src < FM1_MOD_SRC_SYSTEM && (src - FM1_MOD_SRC_S_NOTE) % 4u == k) return src - k;
  return src;
}
bool ChainCable(const fm1_mod_slot_t &s, unsigned) {
  const unsigned u = fm1_mod_unit_canonical(s.dst_unit);
  return u == FM1_MOD_FX1 || u == FM1_MOD_FX2;
}

bool WriteOut(const std::vector<Rec> &recs, const std::string &path, std::string *err) {
  std::vector<char> jw(fm1_state_json_writer_size() + 16);
  std::string json;
  fm1_state_report_t rep;
  fm1_state_report_init(&rep);
  void *mem = reinterpret_cast<void *>((reinterpret_cast<uintptr_t>(jw.data()) + 15u) & ~static_cast<uintptr_t>(15u));
  fm1_state_writer_t *w = fm1_state_json_writer(mem, &Names(), 0, Put, &json, &rep);
  if (!Feed(recs, fm1_state_write, w)) { *err = Report(rep); return false; }
  std::string out = json;
  if (path.size() > 7 && path.compare(path.size() - 7, 7, ".lunarb") == 0) {
    std::vector<char> bw(fm1_state_bin_writer_size() + 16);
    void *bmem = reinterpret_cast<void *>((reinterpret_cast<uintptr_t>(bw.data()) + 15u) & ~static_cast<uintptr_t>(15u));
    static const uint8_t version[3] = { 0, 1, 0 };
    out.clear();
    fm1_state_report_t rep2;
    fm1_state_report_init(&rep2);
    fm1_state_writer_t *b = fm1_state_bin_writer(bmem, FM1_STATE_BIN_DEFLATE, FM1_STATE_WRITER_DESKTOP, version, Put,
                                                 &out, &rep2);
    if (!fm1_state_json_read(&Names(), MemRead, &json, fm1_state_bin_write, b, &rep2)) {
      *err = Report(rep2);
      return false;
    }
  }
  FILE *f = fopen(path.c_str(), "wb");
  if (!f) { *err = "cannot write " + path; return false; }
  fwrite(out.data(), 1, out.size(), f);
  return fclose(f) == 0;
}

void Head(std::vector<Rec> *v, int kind) {
  fm1_rec_t r = Blank(FM1_REC_HEAD);
  r.u.head.kind = static_cast<uint8_t>(kind);
  r.u.head.major = FM1_STATE_MAJOR;
  Add(v, r);
  r = Blank(FM1_REC_INFO);
  r.u.info.key = FM1_INFO_BY;
  Add(v, r, "desktop");
}

std::string SetText(const fm1_seq_t *seq) {
  if (!seq) return std::string();
  const size_t n = fm1_seq_export_movy1(seq, NULL, 0);
  std::string s(n + 1, '\0');
  fm1_seq_export_movy1(seq, &s[0], s.size());
  s.resize(n);
  return s;
}

}  // namespace

bool Save(const std::string &spec, const Have &h, std::string *err) {
  const size_t colon = spec.find(':');
  if (colon == std::string::npos) { *err = "--save wants KIND:FILE"; return false; }
  std::string kind = spec.substr(0, colon), path = spec.substr(colon + 1);
  std::vector<Rec> v;
  if (kind == "set") {
    if (!h.seq) { *err = "--save set needs a sequencer (--seq, --cmd or a loaded set)"; return false; }
    const std::string s = SetText(h.seq);
    FILE *f = fopen(path.c_str(), "wb");
    if (!f) { *err = "cannot write " + path; return false; }
    fwrite(s.data(), 1, s.size(), f);
    return fclose(f) == 0;
  }
  if (kind == "clip") {
    int t = 0, s = 0, n = 0;
    if (sscanf(path.c_str(), "%d.%d:%n", &t, &s, &n) != 2 || !n || t < 1 || t > 16 || s < 1 || s > 8) {
      *err = "--save wants clip:T.S:FILE";
      return false;
    }
    path = path.substr(static_cast<size_t>(n));
    if (!h.seq) { *err = "--save clip needs a sequencer"; return false; }
    const std::string set = SetText(h.seq);
    size_t count = 0;
    char **lines = fm1_state_clip_from(set.data(), set.size(), static_cast<unsigned>(t - 1),
                                       static_cast<unsigned>(s - 1), &count);
    if (!lines) { *err = "no clip at that track and slot"; return false; }
    Head(&v, FM1_STATE_CLIP);
    for (size_t i = 0; i < count; ++i) {
      fm1_rec_t r = Blank(FM1_REC_LINE);
      r.piece = FM1_REC_FIRST | FM1_REC_LAST;
      r.u.line.which = FM1_LINES_CLIP;
      Add(&v, r, lines[i]);
    }
    fm1_state_clip_free(lines, count);
    Add(&v, Blank(FM1_REC_END));
    return WriteOut(v, path, err);
  }
  if (kind == "project") {
    Head(&v, FM1_STATE_PROJECT);
    if (!h.sound[0].e) { *err = "a project's Sound 1 is never empty (no --engine)"; return false; }
    for (unsigned k = 0; k < 4; ++k) {
      UnitRecs(&v, h.sound[k], FM1_ROLE_SOUND, k, 0);
      if (h.sound[k].e) {
        fm1_rec_t r = Blank(FM1_REC_LEVEL);
        r.sound = static_cast<uint8_t>(k);
        memcpy(&r.u.level, &h.level[k], sizeof(float));
        Add(&v, r);
      }
      for (unsigned j = 0; j < 2; ++j) {
        UnitRecs(&v, j < h.inserts[k].size() ? h.inserts[k][j] : UnitOut(), FM1_ROLE_INSERT, k, j);
      }
      for (unsigned j = 0; j < h.mfx[k].size() && j < FM1_STATE_MFX; ++j) UnitRecs(&v, h.mfx[k][j], FM1_ROLE_MFX, k, j);
    }
    if (h.fx.size() > 2) fprintf(stderr, "--save project: a project's master has two slots; %zu --fx left out\n", h.fx.size() - 2);
    for (unsigned j = 0; j < 2; ++j) UnitRecs(&v, j < h.fx.size() ? h.fx[j] : UnitOut(), FM1_ROLE_MASTER, 0, j);
  } else if (kind.compare(0, 5, "sound") == 0) {
    const unsigned k = kind.size() == 6 && kind[5] >= '1' && kind[5] <= '4' ? static_cast<unsigned>(kind[5] - '1') : 0u;
    if (!h.sound[k].e) { *err = "that sound unit is empty"; return false; }
    Head(&v, FM1_STATE_SOUND);
    UnitRecs(&v, h.sound[k], FM1_ROLE_SOUND, 0, 0);
    fm1_rec_t r = Blank(FM1_REC_LEVEL);
    memcpy(&r.u.level, &h.level[k], sizeof(float));
    Add(&v, r);
    for (unsigned j = 0; j < 2; ++j) UnitRecs(&v, j < h.inserts[k].size() ? h.inserts[k][j] : UnitOut(), FM1_ROLE_INSERT, 0, j);
    for (unsigned j = 0; j < h.mfx[k].size() && j < FM1_STATE_MFX; ++j) UnitRecs(&v, h.mfx[k][j], FM1_ROLE_MFX, 0, j);
    if (h.mod) ModRecs(&v, h, false, false, SoundsCable, k, ToSoundFile, SourceToSoundFile);
  } else if (kind == "fx") {
    if (h.fx.empty()) { *err = "no --fx chain"; return false; }
    Head(&v, FM1_STATE_FX);
    for (unsigned j = 0; j < h.fx.size() && j < FM1_STATE_CHAIN; ++j) UnitRecs(&v, h.fx[j], FM1_ROLE_MASTER, 0, j);
    if (h.mod) ModRecs(&v, h, false, false, ChainCable, 0, NULL, NULL);
  } else if (kind == "mods") {
    if (!h.mod) { *err = "--save mods needs --mod or a loaded rack"; return false; }
    Head(&v, FM1_STATE_MODS);
  } else {
    *err = "--save KIND is project, sound[1-4], fx, mods, set or clip:T.S";
    return false;
  }
  if (kind == "project" || kind.compare(0, 5, "sound") == 0) {
    for (size_t i = 0; i < h.dx7.size(); ++i) {
      fm1_rec_t r = Blank(FM1_REC_DX7);
      r.slot = static_cast<uint8_t>(h.dx7[i].first);
      memcpy(r.u.dx7.vced, h.dx7[i].second.data(), 155);
      Add(&v, r);
    }
  }
  if (h.mod && (kind == "project" || kind == "mods")) {
    const size_t from = v.size();
    ModRecs(&v, h, true, true, NULL, 0, NULL, NULL);
    if (kind == "mods") NameCables(&v, from, h);
  }
  if (kind == "project" && h.seq) {
    const std::string s = SetText(h.seq);
    size_t start = 0;
    for (size_t i = 0; i < s.size(); ++i) {
      if (s[i] != '\n') continue;
      fm1_rec_t r = Blank(FM1_REC_LINE);
      r.piece = FM1_REC_FIRST | FM1_REC_LAST;
      r.u.line.which = FM1_LINES_SET;
      Add(&v, r, s.substr(start, i - start));
      start = i + 1;
    }
  }
  Add(&v, Blank(FM1_REC_END));
  return WriteOut(v, path, err);
}

namespace {
struct Bank {
  std::vector<std::pair<unsigned, std::array<uint8_t, 155> > > *out;
};
void Store(void *ctx, unsigned slot, const uint8_t vced[FM1_DX7_VCED_BYTES]) {
  Bank *b = static_cast<Bank *>(ctx);
  std::array<uint8_t, 155> v;
  memcpy(v.data(), vced, 155);
  for (size_t i = 0; i < b->out->size(); ++i) {
    if ((*b->out)[i].first == slot) { (*b->out)[i].second = v; return; }
  }
  b->out->push_back(std::make_pair(slot, v));
}
}  // namespace

void Sysex(const std::vector<std::string> &paths, std::vector<std::pair<unsigned, std::array<uint8_t, 155> > > *out) {
  unsigned slot = 0;
  Bank b = { out };
  for (size_t k = 0; k < paths.size(); ++k) {
    std::string data;
    if (!ReadFile(paths[k], &data)) continue;
    fm1_dx7_sysex_result_t r;
    const int n = fm1_dx7_read_sysex(reinterpret_cast<const uint8_t *>(data.data()), data.size(), slot, Store, &b, &r);
    if (n > 0) slot = (r.first_slot + static_cast<unsigned>(n)) % FM1_DX7_USER_SLOTS;
  }
}

}  // namespace render_state
