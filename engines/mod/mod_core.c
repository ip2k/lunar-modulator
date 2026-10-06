/* mod_core.c -- the modulation runtime (fm1_mod.h, docs/16 §2): the rack,
 * the slots, the bases (rule M1), the system sources, the tick and, since
 * MG9, the voices: one instance per note of each module that runs per
 * voice, and the per-note offsets VOICE slots send.
 *
 * Time. Tick k (k >= 1) runs at absolute frame t(k) = k x FM1_MOD_TICK and
 * covers [t(k-1), t(k)). System events are fed with their frame and kept
 * in two windows until a tick takes them: [0] holds what the next tick
 * takes (frames before t(k)), [1] what arrives at t(k) or later before that
 * tick has run (a note-off at a tick's own frame, which the bridge hands
 * over before the tick: M6). A tick takes window 0, so an event reaches
 * the tick after it whatever order the host feeds and ticks in. A voice's
 * gates are fed the same way.
 *
 * C99, no heap, no stdio, no libm; built with -ffp-contract=off. MIT
 * licence. */
#include "mod_int.h"

#include <string.h>

/* ---- system gates: compact indexes ---------------------------------------- */
enum {
  G_KEY = 0, G_TRIG, G_CLOCK, G_BEAT, G_BAR, G_RUN, G_START, G_RTRG, G_SEQ,
  G_SKEY = 16, G_STRIG = 20, G_SRTRG = 24      /* each sound unit's (MG9) */
};
typedef char mod_sys_gates_fit[G_SRTRG + FM1_MOD_SOUNDS == MOD_SYS_GATES ? 1 : -1];

static int gate_index(unsigned id) {
  if (id >= FM1_MOD_SRC_KEY && id <= FM1_MOD_SRC_RTRG) return (int)(id - FM1_MOD_SRC_KEY);
  if (id >= FM1_MOD_SRC_SEQ_GATE && id < FM1_MOD_SRC_SEQ_GATE + 8u) {
    return G_SEQ + (int)(id - FM1_MOD_SRC_SEQ_GATE);
  }
  if (id >= FM1_MOD_SRC_S_KEY && id < FM1_MOD_SRC_S_KEY + FM1_MOD_SOUNDS) {
    return G_SKEY + (int)(id - FM1_MOD_SRC_S_KEY);
  }
  if (id >= FM1_MOD_SRC_S_TRIG && id < FM1_MOD_SRC_S_TRIG + FM1_MOD_SOUNDS) {
    return G_STRIG + (int)(id - FM1_MOD_SRC_S_TRIG);
  }
  if (id >= FM1_MOD_SRC_S_RTRG && id < FM1_MOD_SRC_S_RTRG + FM1_MOD_SOUNDS) {
    return G_SRTRG + (int)(id - FM1_MOD_SRC_S_RTRG);
  }
  return -1;
}

/* ---- unit codes and sinks ------------------------------------------------------ */

typedef char mod_recs_fit_u8[MOD_SINK_RECS <= 255u && MOD_SINK_RECS >= FM1_MOD_HOST_PARAMS ? 1 : -1];

static const uint8_t kSinkUnit[MOD_SINK_UNITS] = {
  FM1_MOD_SOUND, FM1_MOD_FX1, FM1_MOD_FX2, FM1_MOD_HOST,
  FM1_MOD_SOUND_UNIT + 1, FM1_MOD_SOUND_UNIT + 2, FM1_MOD_SOUND_UNIT + 3,
  FM1_MOD_INSERT + 0, FM1_MOD_INSERT + 1, FM1_MOD_INSERT + 4, FM1_MOD_INSERT + 5,
  FM1_MOD_INSERT + 8, FM1_MOD_INSERT + 9, FM1_MOD_INSERT + 12, FM1_MOD_INSERT + 13,
};
typedef char mod_sink_table_size[sizeof(kSinkUnit) == MOD_SINK_UNITS &&
                                 FM1_MOD_SOUNDS == 4u && FM1_MOD_INSERTS == 2u ? 1 : -1];

unsigned fm1_mod_sink_unit(unsigned i) {
  return i < MOD_SINK_UNITS ? kSinkUnit[i] : FM1_MOD_NONE;
}

int fm1_mod_sink_index(unsigned unit) {
  unsigned i;
  unit = fm1_mod_unit_canonical(unit);
  for (i = 0; i < MOD_SINK_UNITS && unit != FM1_MOD_NONE; ++i) {
    if (kSinkUnit[i] == unit) return (int)i;
  }
  return -1;
}

unsigned fm1_mod_unit_canonical(unsigned unit) {
  unsigned i;
  if (unit == FM1_MOD_SOUND_UNIT) return FM1_MOD_SOUND;
  if (unit == FM1_MOD_MASTER || unit == FM1_MOD_MASTER + 1u) return FM1_MOD_FX1 + (unit - FM1_MOD_MASTER);
  if (unit >= FM1_MOD_MODULE && unit < FM1_MOD_MODULE + FM1_MOD_POSITIONS) return unit;
  for (i = 0; i < MOD_SINK_UNITS; ++i) {
    if (kSinkUnit[i] == unit) return unit;
  }
  return FM1_MOD_NONE;
}

int fm1_mod_unit_sound(unsigned unit) {
  unit = fm1_mod_unit_canonical(unit);
  if (unit == FM1_MOD_SOUND) return 0;
  if (unit > FM1_MOD_SOUND_UNIT && unit < FM1_MOD_SOUND_UNIT + FM1_MOD_SOUNDS) {
    return (int)(unit - FM1_MOD_SOUND_UNIT);
  }
  return -1;
}

/* ---- creation --------------------------------------------------------------- */

size_t fm1_mod_size(void) {
  return (sizeof(struct fm1_mod) + 15u) & ~(size_t)15u;
}

static fm1_host_t host_of(const fm1_mod_t *m) {
  fm1_host_t h;
  h.api_version = FM1_ENGINE_API_VERSION;
  h.sample_rate = m->rate;
  h.max_frames = m->max_frames;
  return h;
}

const fm1_mod_kind_t *mod_kind_at(const fm1_mod_t *m, unsigned pos) {
  if (pos >= FM1_MOD_POSITIONS || m->kind[pos] == MOD_NONE ||
      m->kind[pos] >= fm1_mod_kind_count) {
    return NULL;
  }
  return fm1_mod_kinds[m->kind[pos]];
}

static void *instance(fm1_mod_t *m, unsigned pos) {
  return m->arena + m->handle[pos];
}

fm1_mod_t *fm1_mod_create(void *mem, const fm1_host_t *host, uint32_t seed) {
  fm1_mod_t *m = (fm1_mod_t *)mem;
  unsigned i;
  if (!mem || ((uintptr_t)mem & 15u)) return NULL;
  memset(m, 0, sizeof(*m));
  m->magic = FM1_MOD_MAGIC;
  m->seed = seed;
  m->rate = host && host->sample_rate >= 1000.0f && host->sample_rate <= 384000.0f
                ? host->sample_rate : 44118.0f;
  m->max_frames = host && host->max_frames ? host->max_frames : 64u;
  m->bpm_x100 = 12000u;
  m->k = 1;
  m->next_tick = FM1_MOD_TICK;
  m->start_frame = MOD_NONE;
  m->rtrg_at = MOD_NO_FRAME;
  for (i = 0; i < FM1_MOD_SOUNDS; ++i) m->rtrg_at_s[i] = MOD_NO_FRAME;
  for (i = 0; i < FM1_MOD_POSITIONS; ++i) m->kind[i] = MOD_NONE;
  for (i = 0; i < MOD_SYS_GATES; ++i) m->trig_fall[i] = MOD_NO_FRAME;
  for (i = 0; i < FM1_MOD_SLOTS; ++i) {
    m->slot[i].via = MOD_NONE;
    fm1_mp_rng_seed(&m->srt[i].rng, mod_mix(seed, 0x100u + i));
  }
  fm1_mp_rng_seed(&m->note_rng, mod_mix(seed, 0x300u));
  fm1_mp_rng_seed(&m->voice_rng, mod_mix(seed, 0x301u));
  m->vctx = MOD_NONE;
  m->plan.vcap = FM1_MOD_VOICES;
  /* HOST's records come first and never move; every other sink starts
   * unbound, with no records, packed after them. */
  for (i = 0; i < FM1_MOD_HOST_PARAMS; ++i) {
    const fm1_param_t *p = &fm1_mod_host_params[i];
    mod_meta_t *q = &m->meta[i];
    q->min = p->min;
    q->max = p->max;
    q->def = p->def;
    q->uid = p->uid;
    q->type = (uint8_t)p->type;
    q->flags = p->flags;
    q->unit = p->unit;
    m->sink_base[i] = m->sink_sent[i] = p->def;
  }
  for (i = 0; i < MOD_SINK_UNITS; ++i) m->sink_first[i] = FM1_MOD_HOST_PARAMS;
  m->sink_first[MOD_HOST_SINK] = 0;
  m->sink_n[MOD_HOST_SINK] = FM1_MOD_HOST_PARAMS;
  m->dirty = 1;
  return m;
}

void fm1_mod_destroy(fm1_mod_t *m) {
  unsigned pos;
  if (!m) return;
  mod_voices_drop(m);
  for (pos = 0; pos < FM1_MOD_POSITIONS; ++pos) {
    const fm1_mod_kind_t *kd = mod_kind_at(m, pos);
    if (kd && kd->destroy) kd->destroy(instance(m, pos));
    m->kind[pos] = MOD_NONE;
  }
}

/* ---- units ------------------------------------------------------------------ */

/* The records the sinks hold now, HOST's included: the next free one. */
static unsigned records_used(const fm1_mod_t *m) {
  unsigned i, used = FM1_MOD_HOST_PARAMS;
  for (i = 0; i < MOD_SINK_UNITS; ++i) {
    const unsigned end = (unsigned)m->sink_first[i] + m->sink_n[i];
    if (m->sink_n[i] && end > used) used = end;   /* an unbound sink's first means nothing */
  }
  return used;
}

int fm1_mod_bind(fm1_mod_t *m, unsigned unit, const fm1_engine_t *e) {
  const int si = fm1_mod_sink_index(unit);
  unsigned i, n, first, old_n, used;
  if (si < 0 || si == (int)MOD_HOST_SINK) return -1;
  n = e ? (e->n_params < FM1_MOD_UNIT_PARAMS ? e->n_params : FM1_MOD_UNIT_PARAMS) : 0u;
  /* Its old records go and the ones after them move down, so the pool
   * stays packed in binding order; then the new ones go at the end. */
  first = m->sink_first[si];
  old_n = m->sink_n[si];
  used = records_used(m);
  if (old_n) {
    const unsigned tail = used - (first + old_n);
    memmove(&m->meta[first], &m->meta[first + old_n], tail * sizeof(m->meta[0]));
    memmove(&m->sink_base[first], &m->sink_base[first + old_n], tail * sizeof(float));
    memmove(&m->sink_sent[first], &m->sink_sent[first + old_n], tail * sizeof(float));
    memmove(&m->sink_off[first], &m->sink_off[first + old_n], tail * sizeof(float));
    for (i = 0; i < MOD_SINK_UNITS; ++i) {
      if (i != (unsigned)si && m->sink_n[i] && m->sink_first[i] > first) {
        m->sink_first[i] = (uint8_t)(m->sink_first[i] - old_n);
      }
    }
    used -= old_n;
  }
  m->sink_n[si] = 0;
  m->sink_first[si] = (uint8_t)used;
  m->restore[si] = 0;
  m->sink_note[si] = 0;
  m->dirty = 1;
  {
    /* A new engine has no voice sounding, so none holds an offset: the
     * voices of this sound unit start from 0 (MG9). */
    const int snd = fm1_mod_unit_sound(unit);
    for (i = 0; snd >= 0 && i < FM1_MOD_VOICES; ++i) {
      mod_voice_t *vc = &m->voice[i];
      if (vc->state == MOD_V_FREE || vc->sound != (unsigned)snd) continue;
      memset(vc->sent, 0, sizeof(vc->sent));
      vc->changed = 0;
      vc->restore = 0;
    }
  }
  if (used + n > MOD_SINK_RECS) return -1;   /* no room: unbound, its cables refused */
  for (i = 0; i < n; ++i) {
    const fm1_param_t *p = &e->params[i];
    mod_meta_t *q = &m->meta[used + i];
    memset(q, 0, sizeof(*q));
    q->min = p->min;
    q->max = p->max;
    q->def = p->def;
    q->uid = p->uid;
    q->type = (uint8_t)p->type;
    q->flags = p->flags;
    q->unit = p->unit;
    m->sink_base[used + i] = m->sink_sent[used + i] = q->def;
    m->sink_off[used + i] = 0.0f;
  }
  m->sink_n[si] = (uint8_t)n;
  m->sink_note[si] = (uint8_t)(e && e->set_param_note && fm1_mod_unit_sound(unit) >= 0);
  return (int)n;
}

/* ---- the rack --------------------------------------------------------------- */

/* First fit: the lowest 16-aligned offset where `bytes` fits beside every
 * other position's instance. */
static int arena_fit(const fm1_mod_t *m, unsigned skip, uint32_t bytes, uint32_t *off) {
  uint32_t at = 0;
  for (;;) {
    unsigned p;
    int moved = 0;
    if (at + bytes > FM1_MOD_ARENA) return 0;
    for (p = 0; p < FM1_MOD_POSITIONS; ++p) {
      const uint32_t a = m->inst_off[p], b = a + m->inst_bytes[p];
      if (p == skip || m->kind[p] == MOD_NONE) continue;
      if (at < b && a < at + bytes) {
        at = (b + 15u) & ~15u;
        moved = 1;
      }
    }
    if (!moved) {
      *off = at;
      return 1;
    }
  }
}

static int touches(const fm1_mod_slot_t *s, unsigned pos) {
  const unsigned lo = FM1_MOD_SRC_MODULE + 8u * pos, hi = lo + 8u;
  return (s->src >= lo && s->src < hi) || (s->via != MOD_NONE && s->via >= lo && s->via < hi) ||
         s->dst_unit == FM1_MOD_MODULE + pos;
}

int fm1_mod_set_kind(fm1_mod_t *m, unsigned pos, int kind) {
  const fm1_mod_kind_t *old, *kd = NULL;
  fm1_host_t h = host_of(m);
  uint32_t bytes = 0, off = 0;
  unsigned i, j;
  int off_slots = 0;
  void *self;
  if (pos >= FM1_MOD_POSITIONS || kind >= (int)fm1_mod_kind_count) return -1;
  if (kind >= 0) {
    size_t want;
    kd = fm1_mod_kinds[kind];
    if (kd->magic != FM1_MOD_MAGIC || kd->api_version != FM1_MOD_API_VERSION ||
        kd->n_params > FM1_MOD_MAX_PARAMS || kd->n_gate_in > FM1_MOD_MAX_GATES ||
        kd->n_out > FM1_MOD_MAX_OUTS) {
      return -1;
    }
    want = kd->instance_size(&h);
    if (want > FM1_MOD_ARENA) return -1;
    bytes = ((uint32_t)want + 15u) & ~15u;
    if (!arena_fit(m, pos, bytes ? bytes : 16u, &off)) return -1;
  }
  /* The per-voice instances go first: the new one may be placed where
   * they were, and the plan lays them out again (MG9). */
  mod_voices_drop(m);
  old = mod_kind_at(m, pos);
  if (old && old->destroy) old->destroy(instance(m, pos));
  if (old && old != kd) {
    for (i = 0; i < FM1_MOD_SLOTS; ++i) {
      if ((m->slot[i].flags & FM1_MOD_SLOT_ON) && touches(&m->slot[i], pos)) {
        m->slot[i].flags = (uint8_t)(m->slot[i].flags & ~FM1_MOD_SLOT_ON);
        ++off_slots;
      }
    }
  }
  /* The outputs restart low, so every gate cable from this position does
   * too: one left high would hold its destination's gate open until the
   * new instance happened to rise and fall. */
  for (i = 0; i < FM1_MOD_SLOTS; ++i) {
    const unsigned lo = FM1_MOD_SRC_MODULE + 8u * pos;
    if (m->slot[i].src >= lo && m->slot[i].src < lo + 8u) {
      m->srt[i].level = 0;
      mod_voices_level_clear(m, 1u << i);
    }
  }
  m->kind[pos] = MOD_NONE;
  m->inst_off[pos] = m->inst_bytes[pos] = m->handle[pos] = 0;
  m->gin_level[pos] = 0;
  for (i = 0; i < FM1_MOD_MAX_PARAMS; ++i) m->base[pos][i] = m->peff[pos][i] = 0.0f;
  for (j = 0; j < 2u; ++j) {
    for (i = 0; i < FM1_MOD_MAX_OUTS; ++i) {
      m->out[j][pos][i] = 0.0f;
      mod_gate_clear(&m->gout[j][pos][i], 0);
    }
  }
  m->dirty = 1;
  if (!kd) return off_slots;
  self = kd->create(m->arena + off, &h, mod_mix(m->seed, 0x200u + pos));
  if (!self || (uint8_t *)self < m->arena || (uint8_t *)self >= m->arena + FM1_MOD_ARENA) {
    return -1;
  }
  m->kind[pos] = (uint8_t)kind;
  m->inst_off[pos] = (uint16_t)off;
  m->inst_bytes[pos] = (uint16_t)(bytes ? bytes : 16u);
  m->handle[pos] = (uint16_t)((uint8_t *)self - m->arena);
  for (i = 0; i < kd->n_params; ++i) m->base[pos][i] = m->peff[pos][i] = kd->params[i].def;
  return off_slots;
}

int fm1_mod_kind_at(const fm1_mod_t *m, unsigned pos) {
  return mod_kind_at(m, pos) ? (int)m->kind[pos] : -1;
}

void fm1_mod_default_rack(fm1_mod_t *m) {
  static const char *const kRack[] = { "lfo", "lfo", "env", "env", "chance" };
  unsigned i;
  for (i = 0; i < sizeof(kRack) / sizeof(kRack[0]); ++i) {
    fm1_mod_set_kind(m, i, fm1_mod_kind_find(kRack[i]));
  }
}

static uint8_t remap_src(uint8_t src, const uint8_t *perm) {
  if (src == MOD_NONE || src < FM1_MOD_SRC_MODULE) return src;
  return (uint8_t)(FM1_MOD_SRC_MODULE + 8u * perm[(src - FM1_MOD_SRC_MODULE) / 8u] +
                   (src - FM1_MOD_SRC_MODULE) % 8u);
}

int fm1_mod_move(fm1_mod_t *m, unsigned from, unsigned to) {
  uint8_t perm[FM1_MOD_POSITIONS], kind[FM1_MOD_POSITIONS], gin[FM1_MOD_POSITIONS];
  uint16_t off[FM1_MOD_POSITIONS], bytes[FM1_MOD_POSITIONS], handle[FM1_MOD_POSITIONS];
  unsigned p, i;
  if (from >= FM1_MOD_POSITIONS || to >= FM1_MOD_POSITIONS) return 0;
  if (from == to) return 1;
  mod_voices_drop(m);                   /* laid out by position: made again */
  for (p = 0; p < FM1_MOD_POSITIONS; ++p) {
    unsigned q = p;
    if (p == from) q = to;
    else if (from < to && p > from && p <= to) q = p - 1u;
    else if (from > to && p >= to && p < from) q = p + 1u;
    perm[p] = (uint8_t)q;
  }
  memcpy(kind, m->kind, sizeof(kind));
  memcpy(off, m->inst_off, sizeof(off));
  memcpy(bytes, m->inst_bytes, sizeof(bytes));
  memcpy(handle, m->handle, sizeof(handle));
  memcpy(gin, m->gin_level, sizeof(gin));
  for (p = 0; p < FM1_MOD_POSITIONS; ++p) {
    m->kind[perm[p]] = kind[p];
    m->inst_off[perm[p]] = off[p];
    m->inst_bytes[perm[p]] = bytes[p];
    m->handle[perm[p]] = handle[p];
    m->gin_level[perm[p]] = gin[p];
  }
  /* Rows of per-position state, moved through a rotation of one step at a
   * time so no scratch copy of the larger arrays is needed. */
  {
    const int step = from < to ? 1 : -1;
    unsigned at = from;
    while (at != to) {
      const unsigned nx = (unsigned)((int)at + step);
      float tb[FM1_MOD_MAX_PARAMS], tp[FM1_MOD_MAX_PARAMS], to_[2][FM1_MOD_MAX_OUTS];
      fm1_mod_gate_t tg[2][FM1_MOD_MAX_OUTS];
      memcpy(tb, m->base[at], sizeof(tb));
      memcpy(tp, m->peff[at], sizeof(tp));
      memcpy(m->base[at], m->base[nx], sizeof(tb));
      memcpy(m->peff[at], m->peff[nx], sizeof(tp));
      memcpy(m->base[nx], tb, sizeof(tb));
      memcpy(m->peff[nx], tp, sizeof(tp));
      for (i = 0; i < 2u; ++i) {
        memcpy(to_[i], m->out[i][at], sizeof(to_[i]));
        memcpy(m->out[i][at], m->out[i][nx], sizeof(to_[i]));
        memcpy(m->out[i][nx], to_[i], sizeof(to_[i]));
        memcpy(tg[i], m->gout[i][at], sizeof(tg[i]));
        memcpy(m->gout[i][at], m->gout[i][nx], sizeof(tg[i]));
        memcpy(m->gout[i][nx], tg[i], sizeof(tg[i]));
      }
      at = nx;
    }
  }
  for (i = 0; i < FM1_MOD_SLOTS; ++i) {
    fm1_mod_slot_t *s = &m->slot[i];
    s->src = remap_src(s->src, perm);
    s->via = remap_src(s->via, perm);
    if (s->dst_unit >= FM1_MOD_MODULE && s->dst_unit < FM1_MOD_MODULE + FM1_MOD_POSITIONS) {
      s->dst_unit = (uint8_t)(FM1_MOD_MODULE + perm[s->dst_unit - FM1_MOD_MODULE]);
    }
  }
  m->dirty = 1;
  return 1;
}

/* ---- parameters, slots, bases ----------------------------------------------- */

int fm1_mod_set_param(fm1_mod_t *m, unsigned pos, unsigned index, float value) {
  const fm1_mod_kind_t *kd = mod_kind_at(m, pos);
  if (!kd || index >= kd->n_params) return 0;
  m->base[pos][index] = fm1_param_clamp(&kd->params[index], value);
  return 1;
}

float fm1_mod_param_base(const fm1_mod_t *m, unsigned pos, unsigned index) {
  return pos < FM1_MOD_POSITIONS && index < FM1_MOD_MAX_PARAMS ? m->base[pos][index] : 0.0f;
}

float fm1_mod_param(const fm1_mod_t *m, unsigned pos, unsigned index) {
  return pos < FM1_MOD_POSITIONS && index < FM1_MOD_MAX_PARAMS ? m->peff[pos][index] : 0.0f;
}

int16_t fm1_mod_q14(float x) {
  x = mod_clampf(x, -1.0f, 1.0f, 0.0f) * (float)FM1_MOD_Q14;
  return (int16_t)mod_round(x);
}

/* Whether two slots join the same ends: an amount, offset, polarity, curve
 * or ON edit keeps the cable (fm1_mod.h). */
static int same_ends(const fm1_mod_slot_t *a, const fm1_mod_slot_t *b) {
  return a->src == b->src && a->via == b->via && a->dst_unit == b->dst_unit &&
         a->dst == b->dst && !((a->flags ^ b->flags) & FM1_MOD_SLOT_GATE_DST);
}

int fm1_mod_set_slot(fm1_mod_t *m, unsigned i, const fm1_mod_slot_t *s) {
  fm1_mod_slot_t c;
  if (i >= FM1_MOD_SLOTS || !s) return 0;
  c = *s;
  {                                     /* an alias is kept as its canonical code */
    const unsigned u = fm1_mod_unit_canonical(c.dst_unit);
    if (u != FM1_MOD_NONE) c.dst_unit = (uint8_t)u;
  }
  if (!same_ends(&m->slot[i], &c) || ((m->slot[i].flags ^ c.flags) & FM1_MOD_SLOT_VOICE)) {
    /* Rewired, or moved between global and per voice: it starts low,
     * globally and in every voice (MG9). */
    m->srt[i].level = 0;
    mod_voices_level_clear(m, 1u << i);
  }
  if (!same_ends(&m->slot[i], &c)) fm1_mp_rng_seed(&m->srt[i].rng, mod_mix(m->seed, 0x100u + i));
  m->slot[i] = c;
  m->dirty = 1;
  return 1;
}

int fm1_mod_get_slot(const fm1_mod_t *m, unsigned i, fm1_mod_slot_t *out) {
  if (i >= FM1_MOD_SLOTS || !out) return 0;
  *out = m->slot[i];
  return 1;
}

/* A sink parameter's record (sink index si, parameter index), or -1 when
 * the index is out of range. */
static int sink_rec(const fm1_mod_t *m, int si, unsigned index) {
  if (si < 0 || si >= (int)MOD_SINK_UNITS || index >= m->sink_n[si]) return -1;
  return (int)m->sink_first[si] + (int)index;
}

static float meta_clamp(const mod_meta_t *q, float v) {
  v = mod_clampf(v, q->min, q->max, q->def);
  return q->type == FM1_PARAM_ENUM ? mod_round(v) : v;
}

/* Whether a sink record moves on the LOG law (fm1_param_is_log, engine API
 * v3): its routes sum in octaves. */
static int meta_log(const mod_meta_t *q) {
  return (q->flags & FM1_PARAM_LOG) && q->type == FM1_PARAM_FLOAT && q->min > 0.0f &&
         q->max > q->min;
}

/* A base moved by its routes' sum: base + off, or for a LOG parameter base
 * x 2^off, off in octaves; clamped as the engine holds it. A sum of 0
 * leaves the base's bits as they are either way. */
static float meta_apply(const mod_meta_t *q, float base, float off) {
  if (meta_log(q)) {
    const float g = fm1_exp2f(off);
    return meta_clamp(q, base * g);
  }
  return meta_clamp(q, base + off);
}

float fm1_mod_set_base(fm1_mod_t *m, unsigned unit, unsigned index, float value) {
  const int si = fm1_mod_sink_index(unit);
  const int r = sink_rec(m, si, index);
  const mod_meta_t *q;
  if (r < 0) return value;
  q = &m->meta[r];
  m->sink_base[r] = mod_clampf(value, q->min, q->max, q->def);
  if ((m->plan.sink_routed[si] >> index) & 1u) {
    const float v = meta_apply(q, m->sink_base[r], m->sink_off[r]);
    m->sink_sent[r] = v;
    return v;
  }
  m->sink_sent[r] = meta_clamp(q, value);   /* what the engine holds */
  return value;
}

float fm1_mod_base(const fm1_mod_t *m, unsigned unit, unsigned index) {
  const int r = sink_rec(m, fm1_mod_sink_index(unit), index);
  return r >= 0 ? m->sink_base[r] : 0.0f;
}

float fm1_mod_sent(const fm1_mod_t *m, unsigned unit, unsigned index) {
  const int r = sink_rec(m, fm1_mod_sink_index(unit), index);
  return r >= 0 ? m->sink_sent[r] : 0.0f;
}

/* ---- system sources: feeding -------------------------------------------------- */

/* The window an absolute frame falls in, and its offset there. */
static unsigned window_of(const fm1_mod_t *m, uint64_t at, unsigned *off) {
  if (at < m->next_tick) {
    const uint64_t w0 = m->next_tick - FM1_MOD_TICK;
    *off = at <= w0 ? 0u : (unsigned)(at - w0);
    return 0;
  }
  *off = at - m->next_tick >= FM1_MOD_TICK ? FM1_MOD_TICK - 1u : (unsigned)(at - m->next_tick);
  return 1;
}

static void feed_edge(fm1_mod_t *m, unsigned g, uint64_t at, unsigned high) {
  unsigned off;
  const unsigned w = window_of(m, at, &off);
  fm1_mod_gate_t *pg = &m->pend_g[w][g];
  if (w == 1 && pg->n == 0) pg->start = (uint8_t)fm1_mod_gate_end(&m->pend_g[0][g]);
  mod_gate_edge(pg, off, high, &m->stats.edges_dropped);
  m->glvl_fed[g] = (uint8_t)(high != 0);
}

static void feed_level(fm1_mod_t *m, unsigned g, uint64_t at, unsigned high) {
  if ((m->glvl_fed[g] != 0) != (high != 0)) feed_edge(m, g, at, high);
}

/* A trigger: the pending fall first if it comes at or before this rise,
 * else a retrigger; the new fall FM1_MOD_TICK frames later. */
static void feed_trigger(fm1_mod_t *m, unsigned g, uint64_t at) {
  if (m->trig_fall[g] != MOD_NO_FRAME && m->trig_fall[g] <= at) {
    feed_edge(m, g, m->trig_fall[g], 0);
  }
  m->trig_fall[g] = MOD_NO_FRAME;
  if (m->glvl_fed[g]) feed_edge(m, g, at, 0);
  feed_edge(m, g, at, 1);
  m->trig_fall[g] = at + FM1_MOD_TICK;
}

static void feed_cv(fm1_mod_t *m, unsigned id, uint64_t at, float v) {
  unsigned off;
  const unsigned w = window_of(m, at, &off);
  m->pend_cv[w][id] = v;
  m->cv_has[w] |= 1ull << id;
}

static int key_bit(const uint32_t *bits, unsigned key) { return (int)((bits[key >> 5] >> (key & 31u)) & 1u); }
static int any_bit(const uint32_t *bits) { return (bits[0] | bits[1] | bits[2] | bits[3]) != 0; }

/* RTRG and each sound's: KEY, but a note-on while it is high falls and
 * rises again at its frame, once a frame (a chord's notes share one onset). */
static void feed_rtrg(fm1_mod_t *m, unsigned g, uint64_t *last, uint64_t at) {
  if (m->glvl_fed[g] && *last != at) feed_edge(m, g, at, 0);
  if (*last != at || !m->glvl_fed[g]) feed_edge(m, g, at, 1);
  *last = at;
}

static int any_key(const fm1_mod_t *m) {
  unsigned k;
  for (k = 0; k < FM1_MOD_SOUNDS; ++k) {
    if (any_bit(m->keys[k])) return 1;
  }
  return 0;
}

/* ---- voices (MG9) ------------------------------------------------------------- */

/* An edge of a voice's gate g at absolute frame `at`, windowed as the
 * system gates are (feed_edge). */
static void feed_vedge(fm1_mod_t *m, mod_voice_t *vc, unsigned g, uint64_t at, unsigned high) {
  unsigned off;
  const unsigned w = window_of(m, at, &off);
  fm1_mod_gate_t *pg = &vc->pend[w][g];
  if (w == 1 && pg->n == 0) pg->start = (uint8_t)fm1_mod_gate_end(&vc->pend[0][g]);
  mod_gate_edge(pg, off, high, &m->stats.edges_dropped);
  vc->fed[g] = (uint8_t)(high != 0);
}

/* The instances voice v holds go: their kinds' destroy, at the layout
 * they were made in. */
static void voice_drop_with(fm1_mod_t *m, unsigned v, uint16_t vbase, uint16_t vsize,
                            const uint16_t *voff) {
  mod_voice_t *vc = &m->voice[v];
  unsigned pos;
  for (pos = 0; pos < FM1_MOD_POSITIONS && vc->ready; ++pos) {
    const uint8_t *blk = m->arena + vbase + (uint32_t)v * vsize + voff[pos];
    const mod_vblk_t *h = (const mod_vblk_t *)blk;
    if (!((vc->ready >> pos) & 1u)) continue;
    if (h->kind < fm1_mod_kind_count && fm1_mod_kinds[h->kind]->destroy) {
      fm1_mod_kinds[h->kind]->destroy(m->arena + h->handle);
    }
  }
  vc->ready = 0;
}

uint32_t mod_slots_from(const fm1_mod_t *m, uint32_t poly) {
  uint32_t mask = 0;
  unsigned i;
  for (i = 0; i < FM1_MOD_SLOTS; ++i) {
    const uint8_t src = m->slot[i].src;
    if (src != MOD_NONE && src >= FM1_MOD_SRC_MODULE && ((poly >> ((src - FM1_MOD_SRC_MODULE) / 8u)) & 1u)) {
      mask |= 1u << i;
    }
  }
  return mask;
}

void mod_voices_drop(fm1_mod_t *m) {
  unsigned v;
  mod_voices_level_clear(m, mod_slots_from(m, m->plan.poly));
  for (v = 0; v < FM1_MOD_VOICES; ++v) {
    voice_drop_with(m, v, m->plan.vbase, m->plan.vsize, m->plan.voff);
  }
}

static int find_voice(const fm1_mod_t *m, unsigned sound, uint8_t key) {
  unsigned v;
  for (v = 0; v < FM1_MOD_VOICES; ++v) {
    const mod_voice_t *vc = &m->voice[v];
    if (vc->state != MOD_V_FREE && vc->sound == sound && vc->key == key) return (int)v;
  }
  return -1;
}

/* A voice for a new note: a free one, else the oldest released, else the
 * oldest held (stolen), among the first plan.vcap; -1 when there are none. */
static int voice_alloc(const fm1_mod_t *m) {
  int best = -1;
  unsigned v, pass;
  for (pass = 0; pass < 3u && best < 0; ++pass) {
    for (v = 0; v < m->plan.vcap && v < FM1_MOD_VOICES; ++v) {
      const mod_voice_t *vc = &m->voice[v];
      const unsigned want = pass == 0 ? MOD_V_FREE : pass == 1 ? MOD_V_RELEASED : MOD_V_HELD;
      if (vc->state != want) continue;
      if (pass == 0) return (int)v;
      if (best < 0 || vc->age < m->voice[best].age) best = (int)v;
    }
  }
  return best;
}

/* A note-on on a sound unit whose notes start voices: its voice starts, or
 * the voice its key holds already retriggers (the engines retrigger a key
 * in its own voice, and note_on sets its offsets to 0). */
static void voice_on(fm1_mod_t *m, uint64_t at, unsigned sound, uint8_t key, uint8_t vel) {
  mod_voice_t *vc;
  int v;
  if (m->dirty) mod_plan_build(m);
  if (!((m->plan.vsounds >> sound) & 1u)) return;
  v = find_voice(m, sound, key);
  if (v < 0 || (unsigned)v >= m->plan.vcap) {
    if (v >= 0) {                       /* past the arena's room now: its key's new */
      m->voice[v].state = MOD_V_FREE;   /* note_on put its offsets back to 0 already */
      m->voice[v].changed = 0;
      m->voice[v].restore = 0;
    }
    v = voice_alloc(m);
    if (v < 0) return;
    vc = &m->voice[v];
    if (vc->state != MOD_V_FREE) ++m->stats.voice_steals;
    voice_drop_with(m, (unsigned)v, m->plan.vbase, m->plan.vsize, m->plan.voff);
    memset(vc, 0, sizeof(*vc));
    vc->trig_fall = vc->gate_at = MOD_NO_FRAME;
    vc->sound = (uint8_t)sound;
    vc->key = key;
    vc->serial = ++m->vserial;
    fm1_mp_rng_seed(&vc->rng, mod_mix(m->seed, 0x400u + vc->serial));
    ++m->stats.voice_starts;
  }
  vc = &m->voice[v];
  vc->state = MOD_V_HELD;
  vc->age = ++m->vage;
  vc->velocity = vel > 127 ? 127 : vel;
  vc->vel = (float)vc->velocity * (1.0f / 127.0f);
  vc->note = (float)((int)key - 60) * (1.0f / 60.0f);
  vc->rand = fm1_mp_rng_bipolar(&m->voice_rng);
  /* Its gate rises, or falls and rises again (once a frame); TRIG fires. */
  if (vc->fed[MOD_VG_GATE] && vc->gate_at != at) feed_vedge(m, vc, MOD_VG_GATE, at, 0);
  if (vc->gate_at != at || !vc->fed[MOD_VG_GATE]) feed_vedge(m, vc, MOD_VG_GATE, at, 1);
  vc->gate_at = at;
  if (vc->trig_fall != MOD_NO_FRAME && vc->trig_fall <= at) {
    feed_vedge(m, vc, MOD_VG_TRIG, vc->trig_fall, 0);
  }
  vc->trig_fall = MOD_NO_FRAME;
  if (vc->fed[MOD_VG_TRIG]) feed_vedge(m, vc, MOD_VG_TRIG, at, 0);
  feed_vedge(m, vc, MOD_VG_TRIG, at, 1);
  vc->trig_fall = at + FM1_MOD_TICK;
  /* The engine's note_on put every offset of the key's voice back to 0. */
  memset(vc->sent, 0, sizeof(vc->sent));
  vc->changed = 0;
  vc->restore = 0;
}

static void voice_off(fm1_mod_t *m, uint64_t at, unsigned sound, uint8_t key) {
  const int v = find_voice(m, sound, key);
  mod_voice_t *vc;
  if (v < 0) return;
  vc = &m->voice[v];
  if (vc->state != MOD_V_HELD) return;
  if (vc->fed[MOD_VG_GATE]) feed_vedge(m, vc, MOD_VG_GATE, at, 0);
  vc->state = MOD_V_RELEASED;
}

static void note_at(fm1_mod_t *m, uint64_t at, unsigned sound, uint8_t key, uint8_t vel) {
  uint32_t *keys;
  if (key > 127 || sound >= FM1_MOD_SOUNDS) return;
  keys = m->keys[sound];
  if (vel) {
    const float v = (float)(vel > 127 ? 127 : vel) * (1.0f / 127.0f);
    const float n = (float)((int)key - 60) * (1.0f / 60.0f);
    keys[key >> 5] |= 1u << (key & 31u);
    feed_level(m, G_KEY, at, 1);
    feed_rtrg(m, G_RTRG, &m->rtrg_at, at);
    feed_trigger(m, G_TRIG, at);
    feed_cv(m, FM1_MOD_SRC_VEL, at, v);
    feed_cv(m, FM1_MOD_SRC_NOTE, at, n);
    feed_cv(m, FM1_MOD_SRC_RAND, at, fm1_mp_rng_bipolar(&m->note_rng));
    /* This sound unit's own (MG9). */
    feed_level(m, G_SKEY + sound, at, 1);
    feed_rtrg(m, G_SRTRG + sound, &m->rtrg_at_s[sound], at);
    feed_trigger(m, G_STRIG + sound, at);
    feed_cv(m, FM1_MOD_SRC_S_VEL + sound, at, v);
    feed_cv(m, FM1_MOD_SRC_S_NOTE + sound, at, n);
    voice_on(m, at, sound, key, vel);
  } else if (key_bit(keys, key)) {
    keys[key >> 5] &= ~(1u << (key & 31u));
    if (!any_bit(keys)) {
      feed_level(m, G_SKEY + sound, at, 0);
      feed_level(m, G_SRTRG + sound, at, 0);
    }
    if (!any_key(m)) {
      feed_level(m, G_KEY, at, 0);
      feed_level(m, G_RTRG, at, 0);
    }
    voice_off(m, at, sound, key);
  }
}

void fm1_mod_live_note(fm1_mod_t *m, uint8_t key, uint8_t velocity) {
  note_at(m, m->now, 0, key, velocity);
}

void fm1_mod_live_sound_note(fm1_mod_t *m, unsigned sound, uint8_t key, uint8_t velocity) {
  note_at(m, m->now, sound, key, velocity);
}

void fm1_mod_note(fm1_mod_t *m, uint32_t frame, uint8_t key, uint8_t velocity) {
  note_at(m, m->blk + frame, 0, key, velocity);
}

void fm1_mod_sound_note(fm1_mod_t *m, uint32_t frame, unsigned sound, uint8_t key,
                        uint8_t velocity) {
  note_at(m, m->blk + frame, sound, key, velocity);
}

void fm1_mod_set_current(fm1_mod_t *m, unsigned sound) {
  if (sound >= FM1_MOD_SOUNDS || sound == m->cur_sound) return;
  m->cur_sound = (uint8_t)sound;
  m->dirty = 1;                 /* PITCH_CUR's cables move to the new sound */
}

unsigned fm1_mod_current(const fm1_mod_t *m) { return m->cur_sound; }

void fm1_mod_seq_note(fm1_mod_t *m, uint32_t frame, uint8_t track, uint8_t key, uint8_t velocity) {
  const uint64_t at = m->blk + frame;
  uint32_t *bits;
  if (track >= 8u || key > 127) return;
  bits = m->seq_keys[track];
  if (velocity) {
    bits[key >> 5] |= 1u << (key & 31u);
    feed_level(m, G_SEQ + track, at, 1);
    feed_cv(m, FM1_MOD_SRC_SEQ_VEL + track, at,
            (float)(velocity > 127 ? 127 : velocity) * (1.0f / 127.0f));
  } else if (key_bit(bits, key)) {
    bits[key >> 5] &= ~(1u << (key & 31u));
    if (!any_bit(bits)) feed_level(m, G_SEQ + track, at, 0);
  }
}

void fm1_mod_seq_clock(fm1_mod_t *m, uint32_t frame, uint32_t tick) {
  const uint64_t at = m->blk + frame;
  if (tick % 24u == 0) feed_trigger(m, G_CLOCK, at);
  if (tick % 96u == 0) feed_trigger(m, G_BEAT, at);
  if (tick % 384u == 0) feed_trigger(m, G_BAR, at);
}

void fm1_mod_seq_run(fm1_mod_t *m, uint32_t frame, int running) {
  const uint64_t at = m->blk + frame;
  feed_level(m, G_RUN, at, running != 0);
  if (running) feed_trigger(m, G_START, at);
}

uint32_t fm1_mod_begin(fm1_mod_t *m, uint32_t frames, uint32_t bpm_x100) {
  m->blk = m->now;
  m->now += frames;
  if (bpm_x100) m->bpm_x100 = bpm_x100;
  if (m->next_tick < m->blk) {
    /* Blocks went by without their ticks (a host that skipped the hook):
     * carry on from the first tick inside this block. */
    m->k = (m->blk + FM1_MOD_TICK - 1u) / FM1_MOD_TICK;
    if (m->k == 0) m->k = 1;
    m->next_tick = m->k * FM1_MOD_TICK;
  }
  return m->next_tick - m->blk < frames ? (uint32_t)(m->next_tick - m->blk) : frames;
}

/* ---- the tick ------------------------------------------------------------------- */

static mod_voice_t *voice_ctx(fm1_mod_t *m) {
  return m->vctx < FM1_MOD_VOICES ? &m->voice[m->vctx] : NULL;
}

/* Voice v's outputs at position pos, as it last ran, or NULL when the
 * position does not run per voice or the voice holds no instance there. */
static float *voice_outs(fm1_mod_t *m, unsigned v, unsigned pos) {
  if (v >= FM1_MOD_VOICES || pos >= FM1_MOD_POSITIONS || !((m->plan.poly >> pos) & 1u) ||
      !((m->voice[v].ready >> pos) & 1u)) {
    return NULL;
  }
  return (float *)(mod_vblock(m, v, pos) + MOD_VBLK_HEAD);
}

static fm1_mod_gate_t *voice_gouts(fm1_mod_t *m, unsigned v, unsigned pos, const fm1_mod_kind_t *kd) {
  float *o = voice_outs(m, v, pos);
  return o ? (fm1_mod_gate_t *)(o + kd->n_out) : NULL;
}

/* A note source as a voice reads it: one sound unit's (S1NOTE ... S4RTRG)
 * in a voice of that sound unit is its note's, as the plain one is; another
 * sound unit's stays that sound's (its last note). */
static unsigned voice_note_id(const mod_voice_t *vc, unsigned src) {
  static const uint8_t kPlain[5] = { FM1_MOD_SRC_NOTE, FM1_MOD_SRC_VEL, FM1_MOD_SRC_KEY,
                                     FM1_MOD_SRC_TRIG, FM1_MOD_SRC_RTRG };
  if (src >= FM1_MOD_SRC_S_NOTE && src < FM1_MOD_SRC_S_RTRG + FM1_MOD_SOUNDS &&
      (src - FM1_MOD_SRC_S_NOTE) % FM1_MOD_SOUNDS == vc->sound) {
    return kPlain[(src - FM1_MOD_SRC_S_NOTE) / FM1_MOD_SOUNDS];
  }
  return src;
}
typedef char mod_s_sources_fit[FM1_MOD_SRC_S_VEL == FM1_MOD_SRC_S_NOTE + FM1_MOD_SOUNDS &&
                               FM1_MOD_SRC_S_KEY == FM1_MOD_SRC_S_VEL + FM1_MOD_SOUNDS &&
                               FM1_MOD_SRC_S_TRIG == FM1_MOD_SRC_S_KEY + FM1_MOD_SOUNDS &&
                               FM1_MOD_SRC_S_RTRG == FM1_MOD_SRC_S_TRIG + FM1_MOD_SOUNDS ? 1 : -1];

/* A note source read in a voice (VEL, NOTE, RAND, KEY, TRIG, RTRG, and its
 * own sound unit's): its value there in *v; 0 when src is none of them. */
static int voice_note_source(const mod_voice_t *vc, unsigned src, float *v) {
  switch (voice_note_id(vc, src)) {
    case FM1_MOD_SRC_VEL: *v = vc->vel; return 1;
    case FM1_MOD_SRC_NOTE: *v = vc->note; return 1;
    case FM1_MOD_SRC_RAND: *v = vc->rand; return 1;
    case FM1_MOD_SRC_KEY:
    case FM1_MOD_SRC_RTRG: *v = (float)fm1_mod_gate_end(&vc->gate[MOD_VG_GATE]); return 1;
    case FM1_MOD_SRC_TRIG: *v = (float)fm1_mod_gate_end(&vc->gate[MOD_VG_TRIG]); return 1;
    default: return 0;
  }
}

/* A note gate in a voice: its gate for KEY and RTRG, its trigger for TRIG
 * (and its own sound unit's S1KEY ... as those). */
static const fm1_mod_gate_t *voice_note_gate(const mod_voice_t *vc, unsigned src) {
  src = voice_note_id(vc, src);
  if (src == FM1_MOD_SRC_KEY || src == FM1_MOD_SRC_RTRG) return &vc->gate[MOD_VG_GATE];
  if (src == FM1_MOD_SRC_TRIG) return &vc->gate[MOD_VG_TRIG];
  return NULL;
}

/* A source's value now and its port kind and unit. A module output reads
 * the previous tick when the cable is delayed. In a voice (`voice`, MG9)
 * the note sources are its note's and a per-voice module's output its own
 * instance's (one buffer: a delayed cable reads it before the module runs
 * again). Non-finite becomes 0. */
static float read_src(fm1_mod_t *m, unsigned src, int delayed, int voice, uint8_t *kind,
                      uint8_t *unit) {
  float v = 0.0f;
  *kind = FM1_PORT_CV_BI;
  *unit = FM1_UNIT_NONE;
  if (src < FM1_MOD_SRC_SYSTEM) {
    const fm1_mod_source_info_t *si = fm1_mod_system_source(src);
    const int g = gate_index(src);
    if (!si) return 0.0f;
    *kind = si->kind;
    *unit = si->unit;
    if (!voice || !voice_note_source(voice_ctx(m), src, &v)) {
      v = g >= 0 ? (float)fm1_mod_gate_end(&m->sys_gate[g]) : m->sys_cv[src];
    }
  } else {
    const unsigned pos = (src - FM1_MOD_SRC_MODULE) / 8u, port = (src - FM1_MOD_SRC_MODULE) % 8u;
    const fm1_mod_kind_t *kd = mod_kind_at(m, pos);
    if (!kd || port >= kd->n_out) return 0.0f;
    *kind = kd->out[port].kind;
    *unit = kd->out[port].unit;
    if (voice && ((m->plan.poly >> pos) & 1u)) {
      const float *o = voice_outs(m, m->vctx, pos);
      v = o ? o[port] : 0.0f;
    } else {
      v = m->out[delayed ? m->cur ^ 1u : m->cur][pos][port];
    }
  }
  if (!mod_finite(v)) {
    ++m->stats.nonfinite;
    return 0.0f;
  }
  return v;
}

/* Whether slot i is read in the voice being run: a VOICE slot, in a voice. */
static int in_voice(const fm1_mod_t *m, unsigned i) {
  return m->vctx != MOD_NONE && (m->slot[i].flags & FM1_MOD_SLOT_VOICE);
}

/* The cable's signal before its amount: polarity, curve, offset, VIA. */
static float signal(fm1_mod_t *m, unsigned i, uint8_t *unit) {
  const fm1_mod_slot_t *s = &m->slot[i];
  const int voice = in_voice(m, i);
  uint8_t kind;
  float x = read_src(m, s->src, (int)((m->plan.delayed_src >> i) & 1u), voice, &kind, unit);
  switch ((s->flags & FM1_MOD_SLOT_POL_MASK) >> FM1_MOD_SLOT_POL_SHIFT) {
    case FM1_MOD_POL_UNI: if (kind == FM1_PORT_CV_BI) x = (x + 1.0f) * 0.5f; break;
    case FM1_MOD_POL_BI: if (kind != FM1_PORT_CV_BI) x = x * 2.0f - 1.0f; break;
    case FM1_MOD_POL_INV: x = kind == FM1_PORT_CV_BI ? -x : 1.0f - x; break;
    default: break;
  }
  x = fm1_mod_curve((s->flags & FM1_MOD_SLOT_CURVE_MASK) >> FM1_MOD_SLOT_CURVE_SHIFT,
                    mod_clampf(x, -1.0f, 1.0f, 0.0f));
  x = x + (float)mod_clampf((float)s->offset, -16384.0f, 16384.0f, 0.0f) * (1.0f / 16384.0f);
  if (s->via != MOD_NONE) {
    uint8_t vk, vu;
    float v = read_src(m, s->via, (int)((m->plan.delayed_via >> i) & 1u), voice, &vk, &vu);
    if (vk == FM1_PORT_CV_BI) v = (v + 1.0f) * 0.5f;
    x = x * mod_clampf(v, 0.0f, 1.0f, 0.0f);
  }
  return x;
}

static float amount_of(const fm1_mod_slot_t *s) {
  return mod_clampf((float)s->amount, -16384.0f, 16384.0f, 0.0f) * (1.0f / 16384.0f);
}

/* Slot i's contribution to a parameter of range [min, max] (rule: amount x
 * signal x range; an INPUT takes amount x signal; SEMI into SEMI is
 * amount x signal x 60 semitones). Into a LOG parameter (log set; engine
 * API v3) it is in octaves: amount x signal x log2(max / min), the same
 * share of its knob, and from a SEMI source the octave rule, amount x
 * signal x 60 semitones / 12, so NOTE at +100 % keytracks exactly. */
static float contribution(fm1_mod_t *m, unsigned i, float min, float max, uint16_t flags,
                          uint8_t unit, int log) {
  uint8_t su;
  const float x = signal(m, i, &su);
  const float a = amount_of(&m->slot[i]);
  float c;
  if (flags & FM1_PARAM_INPUT) {
    c = a * x;
  } else if (su == FM1_UNIT_SEMI && (unit == FM1_UNIT_SEMI || log)) {
    /* Semitones, on a grid of 1/1024 (0.1 cent) so that whole notes stay
     * whole: (67 - 60) / 60 x 60 is 7.0000005 in float, 7 here; twelve of
     * them are one octave exactly. */
    c = mod_round(x * 61440.0f) * (1.0f / 1024.0f);
    if (log) c = c / 12.0f;
    c = a * c;
  } else if (log) {
    c = a * x;
    c = c * fm1_log2f(max / min);
  } else {
    c = a * x * (max - min);
  }
  if (!mod_finite(c)) {
    ++m->stats.nonfinite;
    return 0.0f;
  }
  return c;
}

static float sum_slots(fm1_mod_t *m, uint32_t slots, float min, float max, uint16_t flags,
                       uint8_t unit, int log) {
  float acc = 0.0f;
  unsigned i;
  for (i = 0; slots; ++i, slots >>= 1) {
    if (slots & 1u) acc = acc + contribution(m, i, min, max, flags, unit, log);
  }
  return acc;
}

/* One cable into a gate input, as its own alternating gate; *level and
 * *rng are its running state (the slot's, or in a voice the voice's). */
static void cable_gate(fm1_mod_t *m, unsigned i, fm1_mod_gate_t *c, uint8_t *level,
                       fm1_mp_rng_t *rng) {
  const fm1_mod_slot_t *s = &m->slot[i];
  const int voice = in_voice(m, i);
  const fm1_mod_gate_t *src = NULL;
  uint8_t kind = FM1_PORT_CV_BI, unit;
  mod_gate_clear(c, *level);
  if (s->src < FM1_MOD_SRC_SYSTEM) {
    const fm1_mod_source_info_t *si = fm1_mod_system_source(s->src);
    const int g = gate_index(s->src);
    if (si) kind = si->kind;
    if (voice) src = voice_note_gate(voice_ctx(m), s->src);
    if (!src && g >= 0) src = &m->sys_gate[g];
  } else {
    const unsigned pos = (s->src - FM1_MOD_SRC_MODULE) / 8u, port = (s->src - FM1_MOD_SRC_MODULE) % 8u;
    const fm1_mod_kind_t *kd = mod_kind_at(m, pos);
    if (kd && port < kd->n_out) {
      kind = kd->out[port].kind;
      if (kind == FM1_PORT_GATE) {
        if (voice && ((m->plan.poly >> pos) & 1u)) {
          fm1_mod_gate_t *go = voice_gouts(m, m->vctx, pos, kd);
          src = go ? &go[port] : NULL;
          if (!src) kind = FM1_PORT_CV_UNI;            /* no instance yet: reads low */
        } else {
          src = &m->gout[(m->plan.delayed_src >> i) & 1u ? m->cur ^ 1u : m->cur][pos][port];
        }
      }
    }
  }
  if (kind == FM1_PORT_GATE && src) {
    /* Each rising edge passes with probability = amount, one draw per rise
     * whatever the amount, so turning it never shifts the stream; a fall
     * passes when the cable is high. */
    const float a = amount_of(s);
    const uint64_t threshold = a >= 1.0f ? 0x100000000ull
                               : a <= 0.0f ? 0u : (uint64_t)(a * 4294967296.0f);
    unsigned e;
    for (e = 0; e < src->n; ++e) {
      if (src->ev[e].high) {
        const uint32_t draw = fm1_mp_rng_next(rng);
        if ((uint64_t)draw < threshold) {
          if (*level) mod_gate_edge(c, src->ev[e].frame, 0, &m->stats.edges_dropped);
          mod_gate_edge(c, src->ev[e].frame, 1, &m->stats.edges_dropped);
          *level = 1;
        }
      } else if (*level) {
        mod_gate_edge(c, src->ev[e].frame, 0, &m->stats.edges_dropped);
        *level = 0;
      }
    }
  } else {
    /* CV into a gate: a comparator that rises at 0.5 and falls below 0.25,
     * seen at tick resolution, so its edge sits at the tick's first frame. */
    const float v = amount_of(s) * signal(m, i, &unit);
    if (!*level && v >= 0.5f) {
      mod_gate_edge(c, 0, 1, &m->stats.edges_dropped);
      *level = 1;
    } else if (*level && v < 0.25f) {
      mod_gate_edge(c, 0, 0, &m->stats.edges_dropped);
      *level = 0;
    }
  }
}

/* Several cables into one gate input combine by OR; edges at one frame go
 * in slot order. In a voice each cable's state is the voice's. */
static void gate_merge(fm1_mod_t *m, uint32_t slots, fm1_mod_gate_t *g) {
  struct { uint8_t frame, slot, seq, high; } ev[FM1_MOD_SLOTS * FM1_MOD_EDGES];
  mod_voice_t *vc = voice_ctx(m);
  unsigned n = 0, i, a, b, high = 0;
  for (i = 0; slots; ++i, slots >>= 1) {
    fm1_mod_gate_t c;
    if (!(slots & 1u)) continue;
    if (vc && in_voice(m, i)) {
      uint8_t level = (uint8_t)((vc->glevel >> i) & 1u);
      cable_gate(m, i, &c, &level, &vc->rng);
      vc->glevel = (vc->glevel & ~(1u << i)) | ((uint32_t)level << i);
    } else {
      cable_gate(m, i, &c, &m->srt[i].level, &m->srt[i].rng);
    }
    high += c.start;
    for (a = 0; a < c.n; ++a) {
      ev[n].frame = c.ev[a].frame;
      ev[n].slot = (uint8_t)i;
      ev[n].seq = (uint8_t)a;
      ev[n].high = c.ev[a].high;
      ++n;
    }
  }
  for (a = 1; a < n; ++a) {   /* insertion sort by (frame, slot, seq): stable and small */
    for (b = a; b > 0; --b) {
      const unsigned x = ((unsigned)ev[b - 1].frame << 16) | ((unsigned)ev[b - 1].slot << 8) | ev[b - 1].seq;
      const unsigned y = ((unsigned)ev[b].frame << 16) | ((unsigned)ev[b].slot << 8) | ev[b].seq;
      if (x <= y) break;
      {
        const uint8_t f = ev[b].frame, s = ev[b].slot, q = ev[b].seq, h = ev[b].high;
        ev[b] = ev[b - 1];
        ev[b - 1].frame = f;
        ev[b - 1].slot = s;
        ev[b - 1].seq = q;
        ev[b - 1].high = h;
      }
    }
  }
  mod_gate_clear(g, high > 0);
  for (a = 0; a < n; ++a) {
    if (ev[a].high) ++high;
    else if (high) --high;
    mod_gate_edge(g, ev[a].frame, high > 0, &m->stats.edges_dropped);
  }
}

/* The module at pos's effective parameters: base plus its slots, clamped,
 * ENUMs rounded. In a voice (MG9) the global slots, read globally (mono to
 * poly), and then the VOICE ones, read in the voice. */
static void module_params(fm1_mod_t *m, unsigned pos, const fm1_mod_kind_t *kd, float *peff) {
  unsigned i;
  for (i = 0; i < kd->n_params; ++i) {
    const fm1_param_t *p = &kd->params[i];
    const uint8_t d = m->plan.pdest[pos][i];
    const uint8_t vd = m->vctx != MOD_NONE && ((m->plan.vrouted[pos] >> i) & 1u)
                           ? mod_vdest_of(m, pos, i, 0) : (uint8_t)MOD_NONE;
    const int log = fm1_param_is_log(p);
    float v = m->base[pos][i];
    if (d != MOD_NONE || vd != MOD_NONE) {
      float off = 0.0f;
      if (d != MOD_NONE) off = sum_slots(m, m->plan.dest[d].slots, p->min, p->max, p->flags, p->unit, log);
      if (vd != MOD_NONE) {
        off = off + sum_slots(m, m->plan.dest[vd].slots, p->min, p->max, p->flags, p->unit, log);
      }
      if (log) {
        const float g = fm1_exp2f(off);
        v = v * g;
      } else {
        v = v + off;
      }
    }
    v = fm1_param_clamp(p, v);
    peff[i] = p->type == FM1_PARAM_ENUM ? mod_round(v) : v;
  }
}

/* The module at pos's gate inputs this tick: its cables, else its normal
 * (in a voice a note normal is the voice's own, and only VOICE cables
 * patch it). *levels is bit j: input j's level at the last tick's end. */
static void module_gates(fm1_mod_t *m, unsigned pos, const fm1_mod_kind_t *kd,
                         fm1_mod_gate_t *gin, uint8_t *levels) {
  const mod_voice_t *vc = voice_ctx(m);
  unsigned i;
  for (i = 0; i < kd->n_gate_in; ++i) {
    const uint8_t d = !vc ? m->plan.gdest[pos][i]
                      : ((m->plan.vgate_conn[pos] >> i) & 1u) ? mod_vdest_of(m, pos, i, 1)
                                                               : (uint8_t)MOD_NONE;
    const fm1_mod_gate_t *vn = vc ? voice_note_gate(vc, kd->gate_in[i].normal) : NULL;
    const int normal = gate_index(kd->gate_in[i].normal);
    const unsigned was = (*levels >> i) & 1u;
    if (d != MOD_NONE) gate_merge(m, m->plan.dest[d].slots, &gin[i]);
    else if (vn) gin[i] = *vn;
    else if (normal >= 0) gin[i] = m->sys_gate[normal];
    else mod_gate_clear(&gin[i], 0);
    if (gin[i].start != was) {
      /* A cable patched or pulled, or a normal broken, since the last tick:
       * the module sees the jump as an edge at the tick's first frame, so a
       * gate it holds never sticks. */
      const fm1_mod_gate_t g = gin[i];
      unsigned e;
      mod_gate_clear(&gin[i], was);
      mod_gate_edge(&gin[i], 0, g.start, &m->stats.edges_dropped);
      for (e = 0; e < g.n; ++e) {
        mod_gate_edge(&gin[i], g.ev[e].frame, g.ev[e].high, &m->stats.edges_dropped);
      }
    }
    *levels = (uint8_t)((*levels & ~(1u << i)) | ((unsigned)fm1_mod_gate_end(&gin[i]) << i));
  }
}

/* Whatever a kind returns, outputs are finite and in range, and gate
 * edges alternate in frame order; prev_end[i] is gate output i's level
 * before the tick. Returns 1 when an output moved (MG9's voice end). */
static int module_outputs(fm1_mod_t *m, const fm1_mod_kind_t *kd, float *out, fm1_mod_gate_t *gout,
                          const uint8_t *prev_end, const float *prev_out) {
  unsigned i;
  int moved = 0;
  for (i = 0; i < kd->n_out; ++i) {
    if (kd->out[i].kind == FM1_PORT_GATE) {
      const fm1_mod_gate_t raw = gout[i];
      unsigned e;
      mod_gate_clear(&gout[i], prev_end[i]);
      for (e = 0; e < raw.n && e < FM1_MOD_EDGES; ++e) {
        mod_gate_edge(&gout[i], raw.ev[e].frame, raw.ev[e].high, &m->stats.edges_dropped);
      }
      out[i] = (float)fm1_mod_gate_end(&gout[i]);
      if (gout[i].n) moved = 1;
    } else {
      if (!mod_finite(out[i])) {
        ++m->stats.nonfinite;
        out[i] = 0.0f;
      }
      out[i] = kd->out[i].kind == FM1_PORT_CV_UNI ? mod_clampf(out[i], 0.0f, 1.0f, 0.0f)
                                                  : mod_clampf(out[i], -1.0f, 1.0f, 0.0f);
    }
    if (prev_out && mod_bits(out[i]) != mod_bits(prev_out[i])) moved = 1;
  }
  return moved;
}

static void run_module(fm1_mod_t *m, unsigned pos, const fm1_mod_transport_t *tp) {
  const fm1_mod_kind_t *kd = mod_kind_at(m, pos);
  const unsigned prev = m->cur ^ 1u;
  fm1_mod_gate_t gin[FM1_MOD_MAX_GATES];
  uint8_t prev_end[FM1_MOD_MAX_OUTS];
  fm1_mod_io_t io;
  float *out = m->out[m->cur][pos];
  fm1_mod_gate_t *gout = m->gout[m->cur][pos];
  unsigned i;
  if (!kd) return;
  module_params(m, pos, kd, m->peff[pos]);
  module_gates(m, pos, kd, gin, &m->gin_level[pos]);
  for (i = 0; i < kd->n_out; ++i) {
    out[i] = m->out[prev][pos][i];
    prev_end[i] = (uint8_t)fm1_mod_gate_end(&m->gout[prev][pos][i]);
    mod_gate_clear(&gout[i], prev_end[i]);
  }
  io.tick = m->k;
  io.p = m->peff[pos];
  io.routed = m->plan.routed[pos];
  io.gate_connected = m->plan.gate_conn[pos];
  io.gate = gin;
  io.tp = tp;
  io.out = out;
  io.gout = gout;
  kd->process(instance(m, pos), &io);
  module_outputs(m, kd, out, gout, prev_end, NULL);
}

/* Voice v's instance at pos runs (MG9): made from its kind's defaults the
 * first time, then like the global one but in the voice. Returns 1 when
 * one of its outputs moved. */
static int run_voice_module(fm1_mod_t *m, unsigned v, unsigned pos, const fm1_mod_transport_t *tp) {
  const fm1_mod_kind_t *kd = mod_kind_at(m, pos);
  mod_voice_t *vc = &m->voice[v];
  uint8_t *blk = mod_vblock(m, v, pos);
  mod_vblk_t *h = (mod_vblk_t *)blk;
  float *out = (float *)(blk + MOD_VBLK_HEAD);
  fm1_mod_gate_t *gout = (fm1_mod_gate_t *)(out + kd->n_out);
  fm1_mod_gate_t gin[FM1_MOD_MAX_GATES];
  float peff[FM1_MOD_MAX_PARAMS], prev_out[FM1_MOD_MAX_OUTS];
  uint8_t prev_end[FM1_MOD_MAX_OUTS];
  fm1_mod_io_t io;
  unsigned i;
  if (!((vc->ready >> pos) & 1u)) {
    const fm1_host_t hst = host_of(m);
    void *self;
    memset(blk, 0, m->plan.vhdr[pos]);
    for (i = 0; i < kd->n_out; ++i) mod_gate_clear(&gout[i], 0);
    self = kd->create(blk + m->plan.vhdr[pos], &hst, mod_mix(m->seed, 0x10000u + 8u * vc->serial + pos));
    if (!self || (uint8_t *)self < m->arena || (uint8_t *)self >= m->arena + FM1_MOD_ARENA) return 0;
    h->handle = (uint16_t)((uint8_t *)self - m->arena);
    h->kind = m->kind[pos];
    vc->ready = (uint8_t)(vc->ready | (1u << pos));
  }
  module_params(m, pos, kd, peff);
  module_gates(m, pos, kd, gin, &h->gin);
  for (i = 0; i < kd->n_out; ++i) {
    prev_out[i] = out[i];
    prev_end[i] = (uint8_t)fm1_mod_gate_end(&gout[i]);
    mod_gate_clear(&gout[i], prev_end[i]);
  }
  io.tick = m->k;
  io.p = peff;
  io.routed = m->plan.routed[pos] | m->plan.vrouted[pos];
  io.gate_connected = m->plan.vgate_conn[pos];
  io.gate = gin;
  io.tp = tp;
  io.out = out;
  io.gout = gout;
  kd->process(m->arena + h->handle, &io);
  h->moved = (uint8_t)module_outputs(m, kd, out, gout, prev_end, prev_out);
  return h->moved;
}

/* Takes window 0 of the system sources for this tick and moves window 1 up. */
static void take_system(fm1_mod_t *m) {
  unsigned g, id;
  for (g = 0; g < MOD_SYS_GATES; ++g) {
    if (m->trig_fall[g] < m->next_tick) {
      feed_edge(m, g, m->trig_fall[g], 0);
      m->trig_fall[g] = MOD_NO_FRAME;
    }
    m->sys_gate[g] = m->pend_g[0][g];
    m->pend_g[0][g] = m->pend_g[1][g];
    m->pend_g[0][g].start = (uint8_t)fm1_mod_gate_end(&m->sys_gate[g]);
    mod_gate_clear(&m->pend_g[1][g], (unsigned)fm1_mod_gate_end(&m->pend_g[0][g]));
  }
  for (id = 0; id < FM1_MOD_SRC_SYSTEM; ++id) {
    if ((m->cv_has[0] >> id) & 1u) {
      const float v = m->pend_cv[0][id];
      if (mod_finite(v)) m->sys_cv[id] = v;
      else ++m->stats.nonfinite;
    }
    if ((m->cv_has[1] >> id) & 1u) m->pend_cv[0][id] = m->pend_cv[1][id];
  }
  m->cv_has[0] = m->cv_has[1];
  m->cv_has[1] = 0;
  m->start_frame = MOD_NONE;
  {
    const fm1_mod_gate_t *s = &m->sys_gate[G_START];
    unsigned e;
    for (e = 0; e < s->n; ++e) {
      if (s->ev[e].high) {
        m->start_frame = s->ev[e].frame;
        break;
      }
    }
  }
}

/* The same for a voice's gate and trigger. */
static void take_voice(fm1_mod_t *m, mod_voice_t *vc) {
  unsigned g;
  if (vc->trig_fall < m->next_tick) {
    feed_vedge(m, vc, MOD_VG_TRIG, vc->trig_fall, 0);
    vc->trig_fall = MOD_NO_FRAME;
  }
  for (g = 0; g < 2u; ++g) {
    vc->gate[g] = vc->pend[0][g];
    vc->pend[0][g] = vc->pend[1][g];
    vc->pend[0][g].start = (uint8_t)fm1_mod_gate_end(&vc->gate[g]);
    mod_gate_clear(&vc->pend[1][g], (unsigned)fm1_mod_gate_end(&vc->pend[0][g]));
  }
}

/* The HOST record of the current sound's pitch gets PITCH_CUR's cables
 * too (owner, 2026-10-05); PITCH_CUR itself is never sent. */
static float sink_offset(fm1_mod_t *m, unsigned u, unsigned i, const mod_meta_t *q, uint8_t d) {
  float off = 0.0f;
  if (d != MOD_NONE) off = sum_slots(m, m->plan.dest[d].slots, q->min, q->max, q->flags, q->unit, meta_log(q));
  if (u == MOD_HOST_SINK && i == fm1_mod_host_pitch(m->cur_sound)) {
    const uint8_t dc = m->plan.sdest[m->sink_first[MOD_HOST_SINK] + FM1_MOD_HOST_PITCH_CUR];
    if (dc != MOD_NONE) {
      off = off + sum_slots(m, m->plan.dest[dc].slots, q->min, q->max, q->flags, q->unit, meta_log(q));
    }
  }
  return off;
}

static void write_sinks(fm1_mod_t *m) {
  unsigned u;
  for (u = 0; u < MOD_SINK_UNITS; ++u) {
    uint32_t mask = m->plan.sink_routed[u] | m->restore[u];
    unsigned i;
    if (u == MOD_HOST_SINK) mask &= ~(1u << FM1_MOD_HOST_PITCH_CUR);
    for (i = 0; mask; ++i, mask >>= 1) {
      const int r = sink_rec(m, (int)u, i);
      const mod_meta_t *q;
      float v, off = 0.0f;
      if (!(mask & 1u) || r < 0) continue;
      q = &m->meta[r];
      if ((m->plan.sink_routed[u] >> i) & 1u) off = sink_offset(m, u, i, q, m->plan.sdest[r]);
      v = meta_apply(q, m->sink_base[r], off);
      m->sink_off[r] = off;
      if (mod_bits(v) != mod_bits(m->sink_sent[r]) && m->n_wr < MOD_MAX_WRITES) {
        fm1_mod_write_t *w = &m->wr[m->n_wr++];
        w->unit = kSinkUnit[u];
        w->key = MOD_NONE;
        w->index = (uint16_t)i;
        w->value = v;
        m->sink_sent[r] = v;
      }
    }
    m->restore[u] = 0;
  }
}

/* Voice v's per-note offsets, into its sent[] (marked changed when their
 * bits move): each VOICE sink destination of its sound summed in the
 * voice. Into a LOG parameter the octaves become the offset that takes the
 * value the engine holds there to it x 2^octaves. */
static void voice_sinks(fm1_mod_t *m, unsigned v) {
  mod_voice_t *vc = &m->voice[v];
  unsigned j;
  for (j = 0; j < m->plan.n_vd; ++j) {
    const mod_vdest_t *e = &m->plan.vd[j];
    const mod_meta_t *q;
    float off, value;
    int r;
    if (e->sound != vc->sound) continue;
    if (e->pitch) {
      r = (int)FM1_MOD_HOST_PITCH;               /* HOST's records come first */
    } else {
      r = sink_rec(m, fm1_mod_sink_index(fm1_mod_sound_unit(e->sound)), e->index);
      if (r < 0) continue;
    }
    q = &m->meta[r];
    off = sum_slots(m, e->slots, q->min, q->max, q->flags, q->unit, meta_log(q));
    if (!e->pitch && meta_log(q)) {
      const float held = m->sink_sent[r];
      const float g = fm1_exp2f(off);
      value = held * g;
      value = value - held;
    } else {
      value = off;
    }
    if (!mod_finite(value)) {
      ++m->stats.nonfinite;
      value = 0.0f;
    }
    if (mod_bits(value) != mod_bits(vc->sent[j])) {
      vc->sent[j] = value;
      vc->changed = (uint8_t)(vc->changed | (1u << j));
    }
  }
}

/* Every offset voice vc holds that is not 0 goes back to 0, marked to be
 * sent (voice_out). */
static void voice_zero(fm1_mod_t *m, mod_voice_t *vc) {
  unsigned j;
  for (j = 0; j < m->plan.n_vd; ++j) {
    if (m->plan.vd[j].sound != vc->sound || !mod_bits(vc->sent[j])) continue;
    vc->sent[j] = 0.0f;
    vc->changed = (uint8_t)(vc->changed | (1u << j));
  }
}

/* Every voice, after the global modules and sinks (MG9): its gate and
 * trigger, its instances in plan order, its offsets; a released voice whose
 * gate is down and whose instances stopped moving ends. */
static void run_voices(fm1_mod_t *m, const fm1_mod_transport_t *tp) {
  unsigned v, k;
  for (v = 0; v < FM1_MOD_VOICES; ++v) {
    mod_voice_t *vc = &m->voice[v];
    int moved = 0;
    if (vc->state == MOD_V_FREE) continue;
    take_voice(m, vc);
    if (v >= m->plan.vcap) {               /* the arena holds fewer voices now */
      /* Its note sounds on, no longer moved per voice: every offset it
       * holds goes back to 0 (the next fm1_mod_voice_writes), so none stays
       * where it was left. */
      voice_drop_with(m, v, m->plan.vbase, m->plan.vsize, m->plan.voff);
      voice_zero(m, vc);
      vc->state = MOD_V_FREE;
      continue;
    }
    m->vctx = (uint8_t)v;
    for (k = 0; k < m->plan.n_order; ++k) {
      const unsigned pos = m->plan.order[k];
      if ((m->plan.poly >> pos) & 1u) moved |= run_voice_module(m, v, pos, tp);
    }
    voice_sinks(m, v);
    m->vctx = MOD_NONE;
    if (vc->state == MOD_V_RELEASED && !moved && !fm1_mod_gate_end(&vc->gate[MOD_VG_GATE]) &&
        !vc->gate[MOD_VG_GATE].n && !vc->pend[0][MOD_VG_GATE].n && !vc->pend[0][MOD_VG_GATE].start &&
        !vc->pend[1][MOD_VG_GATE].n && vc->trig_fall == MOD_NO_FRAME) {
      voice_drop_with(m, v, m->plan.vbase, m->plan.vsize, m->plan.voff);
      vc->state = MOD_V_FREE;
      ++m->stats.voice_ends;
    }
  }
}

uint32_t fm1_mod_tick(fm1_mod_t *m, uint32_t frame, const fm1_mod_write_t **w) {
  fm1_mod_transport_t tp;
  unsigned i;
  m->n_wr = 0;
  if (w) *w = m->wr;
  if (m->blk + frame != m->next_tick) return 0;   /* not this runtime's next tick */
  if (m->dirty) mod_plan_build(m);
  take_system(m);
  m->cur ^= 1u;
  tp.bpm_x100 = m->bpm_x100;
  tp.running = m->sys_gate[G_RUN].start;   /* at t(k-1), from Start and Stop at their frames */
  tp.start = m->start_frame;
  tp.reserved[0] = tp.reserved[1] = 0;
  for (i = 0; i < m->plan.n_order; ++i) run_module(m, m->plan.order[i], &tp);
  write_sinks(m);
  run_voices(m, &tp);
  m->stats.writes += m->n_wr;
  ++m->stats.ticks;
  ++m->k;
  m->next_tick += FM1_MOD_TICK;
  return m->n_wr;
}

/* Voice v's changed offsets, and the ones to put back to 0, as writes. */
static uint32_t voice_out(fm1_mod_t *m, unsigned v, fm1_mod_write_t *out, uint32_t n, uint32_t cap) {
  mod_voice_t *vc = &m->voice[v];
  const unsigned unit = fm1_mod_sound_unit(vc->sound);
  unsigned j;
  for (j = 0; j < m->plan.n_vd && n < cap; ++j) {
    if (!((vc->changed >> j) & 1u)) continue;
    out[n].unit = (uint8_t)unit;
    out[n].key = vc->key;
    out[n].index = m->plan.vd[j].pitch ? (uint16_t)FM1_PARAM_NOTE_PITCH : m->plan.vd[j].index;
    out[n].value = vc->sent[j];
    vc->changed = (uint8_t)(vc->changed & ~(1u << j));
    ++n;
  }
  for (j = 0; j <= MOD_PITCH_BIT && vc->restore && n < cap; ++j) {
    if (!((vc->restore >> j) & 1u)) continue;
    out[n].unit = (uint8_t)unit;
    out[n].key = vc->key;
    out[n].index = j == MOD_PITCH_BIT ? (uint16_t)FM1_PARAM_NOTE_PITCH : (uint16_t)j;
    out[n].value = 0.0f;
    vc->restore &= ~(1ull << j);
    ++n;
  }
  return n;
}

uint32_t fm1_mod_voice_writes(fm1_mod_t *m, fm1_mod_write_t *out, uint32_t cap) {
  uint32_t n = 0;
  unsigned v;
  for (v = 0; v < FM1_MOD_VOICES && n < cap; ++v) {
    if (m->voice[v].changed || m->voice[v].restore) n = voice_out(m, v, out, n, cap);
  }
  m->stats.voice_writes += n;
  return n;
}

uint32_t fm1_mod_voice_start(fm1_mod_t *m, unsigned sound, uint8_t key, fm1_mod_write_t *out,
                             uint32_t cap) {
  int v;
  uint32_t n;
  if (m->dirty) mod_plan_build(m);
  v = find_voice(m, sound, key);
  if (v < 0 || m->voice[v].state != MOD_V_HELD || (unsigned)v >= m->plan.vcap) return 0;
  m->vctx = (uint8_t)v;
  voice_sinks(m, (unsigned)v);
  m->vctx = MOD_NONE;
  n = voice_out(m, (unsigned)v, out, 0, cap);
  m->stats.voice_writes += n;
  return n;
}

uint32_t fm1_mod_voice_clear(fm1_mod_t *m, fm1_mod_write_t *out, uint32_t cap) {
  uint32_t n = 0;
  unsigned v;
  for (v = 0; v < FM1_MOD_VOICES; ++v) {
    mod_voice_t *vc = &m->voice[v];
    if (vc->state == MOD_V_FREE && !vc->changed && !vc->restore) continue;
    voice_zero(m, vc);                  /* a pending offset of a voice just ended too */
    n = voice_out(m, v, out, n, cap);
  }
  return n;
}

void fm1_mod_reset(fm1_mod_t *m, uint32_t why) {
  unsigned pos, v;
  for (pos = 0; pos < FM1_MOD_POSITIONS; ++pos) {
    const fm1_mod_kind_t *kd = mod_kind_at(m, pos);
    if (kd && kd->reset) kd->reset(instance(m, pos), why);
  }
  for (v = 0; v < FM1_MOD_VOICES; ++v) {
    for (pos = 0; pos < FM1_MOD_POSITIONS; ++pos) {
      const mod_vblk_t *h;
      if (!((m->voice[v].ready >> pos) & 1u)) continue;
      h = (const mod_vblk_t *)mod_vblock(m, v, pos);
      if (h->kind < fm1_mod_kind_count && fm1_mod_kinds[h->kind]->reset) {
        fm1_mod_kinds[h->kind]->reset(m->arena + h->handle, why);
      }
    }
  }
}

/* ---- reading state ---------------------------------------------------------------- */

float fm1_mod_out(const fm1_mod_t *m, unsigned pos, unsigned port) {
  return pos < FM1_MOD_POSITIONS && port < FM1_MOD_MAX_OUTS ? m->out[m->cur][pos][port] : 0.0f;
}

const fm1_mod_gate_t *fm1_mod_gate_out(const fm1_mod_t *m, unsigned pos, unsigned port) {
  return pos < FM1_MOD_POSITIONS && port < FM1_MOD_MAX_OUTS ? &m->gout[m->cur][pos][port] : NULL;
}

float fm1_mod_system_value(const fm1_mod_t *m, unsigned id) {
  const int g = gate_index(id);
  if (g >= 0) return (float)fm1_mod_gate_end(&m->sys_gate[g]);
  return id < FM1_MOD_SRC_SYSTEM ? m->sys_cv[id] : 0.0f;
}

const fm1_mod_gate_t *fm1_mod_system_gate(const fm1_mod_t *m, unsigned id) {
  const int g = gate_index(id);
  return g >= 0 ? &m->sys_gate[g] : NULL;
}

void fm1_mod_get_plan(fm1_mod_t *m, fm1_mod_plan_info_t *out) {
  unsigned i;
  if (m->dirty) mod_plan_build(m);
  out->active = m->plan.active;
  out->refused = m->plan.refused;
  out->delayed = m->plan.delayed_src | m->plan.delayed_via;
  out->n_order = m->plan.n_order;
  out->n_dest = m->plan.n_dest;
  out->poly = m->plan.poly;
  out->voice_cap = m->plan.vcap;
  out->voice = m->plan.vslots;
  out->voice_sounds = m->plan.vsounds;
  out->n_vdest = m->plan.n_vd;
  out->voice_bytes = m->plan.poly ? m->plan.vsize : 0u;
  for (i = 0; i < FM1_MOD_POSITIONS; ++i) {
    out->order[i] = i < m->plan.n_order ? m->plan.order[i] : MOD_NONE;
    out->comp[i] = i < m->plan.n_order ? m->plan.comp[m->plan.order[i]] : MOD_NONE;
  }
}

void fm1_mod_get_stats(const fm1_mod_t *m, fm1_mod_stats_t *out) {
  *out = m->stats;
}

int fm1_mod_voice(const fm1_mod_t *m, unsigned i, fm1_mod_voice_info_t *out) {
  const mod_voice_t *vc;
  if (i >= FM1_MOD_VOICES || m->voice[i].state == MOD_V_FREE) return 0;
  vc = &m->voice[i];
  out->sound = vc->sound;
  out->key = vc->key;
  out->state = vc->state;
  out->velocity = vc->velocity;
  out->age = vc->age;
  return 1;
}

float fm1_mod_voice_out(const fm1_mod_t *m, unsigned i, unsigned pos, unsigned port) {
  const fm1_mod_kind_t *kd = mod_kind_at(m, pos);
  const float *o;
  if (!kd || port >= kd->n_out || i >= FM1_MOD_VOICES || m->voice[i].state == MOD_V_FREE) return 0.0f;
  o = voice_outs((fm1_mod_t *)m, i, pos);   /* reads only */
  return o ? o[port] : 0.0f;
}

unsigned fm1_mod_voice_count(const fm1_mod_t *m) {
  unsigned v, n = 0;
  for (v = 0; v < FM1_MOD_VOICES; ++v) n += m->voice[v].state != MOD_V_FREE;
  return n;
}

int fm1_mod_sink(fm1_mod_t *m, unsigned i, fm1_mod_sink_info_t *out) {
  unsigned u;
  if (m->dirty) mod_plan_build(m);
  for (u = 0; u < MOD_SINK_UNITS; ++u) {
    uint32_t mask = m->plan.sink_routed[u];
    unsigned p;
    for (p = 0; mask; ++p, mask >>= 1) {
      const int r = sink_rec(m, (int)u, p);
      uint32_t s;
      uint16_t n = 0;
      uint8_t d;
      if (!(mask & 1u) || r < 0) continue;
      if (i--) continue;
      /* Its own slots, and for the current sound's pitch PITCH_CUR's (a
       * pitch routed by those alone has no destination of its own). */
      d = m->plan.sdest[r];
      for (s = d != MOD_NONE ? m->plan.dest[d].slots : 0u; s; s >>= 1) n = (uint16_t)(n + (s & 1u));
      if (u == MOD_HOST_SINK && p == fm1_mod_host_pitch(m->cur_sound)) {
        d = m->plan.sdest[m->sink_first[MOD_HOST_SINK] + FM1_MOD_HOST_PITCH_CUR];
        for (s = d != MOD_NONE ? m->plan.dest[d].slots : 0u; s; s >>= 1) n = (uint16_t)(n + (s & 1u));
      }
      out->unit = kSinkUnit[u];
      out->reserved = 0;
      out->index = (uint16_t)p;
      out->uid = m->meta[r].uid;
      out->slots = n;
      out->base = m->sink_base[r];
      out->value = m->sink_sent[r];
      return 1;
    }
  }
  return 0;
}

/* ---- helpers ------------------------------------------------------------------------ */

float fm1_mod_exp2(float x) {
  union { float f; uint32_t u; } s;
  float f, t, p;
  int32_t n;
  x = mod_clampf(x, -60.0f, 60.0f, 0.0f);
  n = (int32_t)mod_round(x);
  f = x - (float)n;
  t = f * 0.693147181f;
  p = 1.0f + t * (1.0f / 7.0f);
  p = 1.0f + t * (1.0f / 6.0f) * p;
  p = 1.0f + t * (1.0f / 5.0f) * p;
  p = 1.0f + t * 0.25f * p;
  p = 1.0f + t * (1.0f / 3.0f) * p;
  p = 1.0f + t * 0.5f * p;
  p = 1.0f + t * p;
  s.u = (uint32_t)(n + 127) << 23;
  return p * s.f;
}

void fm1_mod_ramp_init(fm1_mod_ramp_t *r, float value) {
  r->t0 = 0;
  r->from = r->to = mod_finite(value) ? value : 0.0f;
}

static float ramp_at(const fm1_mod_ramp_t *r, uint64_t frame) {
  uint64_t d;
  if (frame >= r->t0 + FM1_MOD_TICK || r->from == r->to) return r->to;
  d = frame > r->t0 ? frame - r->t0 : 0u;
  return r->from + (r->to - r->from) * ((float)d * (1.0f / (float)FM1_MOD_TICK));
}

void fm1_mod_ramp_set(fm1_mod_ramp_t *r, uint64_t frame, float value) {
  r->from = ramp_at(r, frame);
  r->to = mod_finite(value) ? value : r->from;
  r->t0 = frame;
}

void fm1_mod_ramp_apply(const fm1_mod_ramp_t *r, uint64_t frame, float *lr, uint32_t n) {
  uint32_t i;
  for (i = 0; i < n; ++i) {
    const float g = ramp_at(r, frame + i);
    lr[2u * i] *= g;
    lr[2u * i + 1u] *= g;
  }
}
