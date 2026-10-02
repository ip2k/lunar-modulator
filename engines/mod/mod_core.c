/* mod_core.c -- the modulation runtime (fm1_mod.h, docs/16 §2): the rack,
 * the slots, the bases (rule M1), the system sources and the tick.
 *
 * Time. Tick k (k >= 1) runs at absolute frame t(k) = k x FM1_MOD_TICK and
 * covers [t(k-1), t(k)). System events are fed with their frame and kept
 * in two windows until a tick takes them: [0] holds what the next tick
 * takes (frames before t(k)), [1] what arrives at t(k) or later before that
 * tick has run (a note-off at a tick's own frame, which the bridge hands
 * over before the tick: M6). A tick takes window 0, so an event reaches
 * the tick after it whatever order the host feeds and ticks in.
 *
 * C99, no heap, no stdio, no libm; built with -ffp-contract=off. MIT
 * licence. */
#include "mod_int.h"

#include <string.h>

/* ---- system gates: compact indexes ---------------------------------------- */
enum { G_KEY = 0, G_TRIG, G_CLOCK, G_BEAT, G_BAR, G_RUN, G_START, G_SEQ };

static int gate_index(unsigned id) {
  if (id >= FM1_MOD_SRC_KEY && id <= FM1_MOD_SRC_START) return (int)(id - FM1_MOD_SRC_KEY);
  if (id >= FM1_MOD_SRC_SEQ_GATE && id < FM1_MOD_SRC_SEQ_GATE + 8u) {
    return G_SEQ + (int)(id - FM1_MOD_SRC_SEQ_GATE);
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
  for (i = 0; i < FM1_MOD_POSITIONS; ++i) m->kind[i] = MOD_NONE;
  for (i = 0; i < MOD_SYS_GATES; ++i) m->trig_fall[i] = MOD_NO_FRAME;
  for (i = 0; i < FM1_MOD_SLOTS; ++i) {
    m->slot[i].via = MOD_NONE;
    fm1_mp_rng_seed(&m->srt[i].rng, mod_mix(seed, 0x100u + i));
  }
  fm1_mp_rng_seed(&m->note_rng, mod_mix(seed, 0x300u));
  m->sink_base[FM1_MOD_HOST][FM1_MOD_HOST_AMP] = 1.0f;
  m->sink_sent[FM1_MOD_HOST][FM1_MOD_HOST_AMP] = 1.0f;
  m->dirty = 1;
  return m;
}

void fm1_mod_destroy(fm1_mod_t *m) {
  unsigned pos;
  if (!m) return;
  for (pos = 0; pos < FM1_MOD_POSITIONS; ++pos) {
    const fm1_mod_kind_t *kd = mod_kind_at(m, pos);
    if (kd && kd->destroy) kd->destroy(instance(m, pos));
    m->kind[pos] = MOD_NONE;
  }
}

/* ---- units ------------------------------------------------------------------ */

int fm1_mod_bind(fm1_mod_t *m, unsigned unit, const fm1_engine_t *e) {
  unsigned i, n;
  if (unit > FM1_MOD_FX2) return -1;
  n = e ? (e->n_params < FM1_MOD_UNIT_PARAMS ? e->n_params : FM1_MOD_UNIT_PARAMS) : 0u;
  memset(m->meta[unit], 0, sizeof(m->meta[unit]));
  for (i = 0; i < FM1_MOD_UNIT_PARAMS; ++i) {
    mod_meta_t *q = &m->meta[unit][i];
    if (i < n) {
      const fm1_param_t *p = &e->params[i];
      q->min = p->min;
      q->max = p->max;
      q->def = p->def;
      q->uid = p->uid;
      q->type = (uint8_t)p->type;
      q->flags = p->flags;
      q->unit = p->unit;
    }
    m->sink_base[unit][i] = m->sink_sent[unit][i] = q->def;
    m->sink_off[unit][i] = 0.0f;
  }
  m->sink_n[unit] = (uint8_t)n;
  m->restore[unit] = 0;
  m->dirty = 1;
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
  m->kind[pos] = MOD_NONE;
  m->inst_off[pos] = m->inst_bytes[pos] = m->handle[pos] = 0;
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
  uint8_t perm[FM1_MOD_POSITIONS], kind[FM1_MOD_POSITIONS];
  uint16_t off[FM1_MOD_POSITIONS], bytes[FM1_MOD_POSITIONS], handle[FM1_MOD_POSITIONS];
  unsigned p, i;
  if (from >= FM1_MOD_POSITIONS || to >= FM1_MOD_POSITIONS) return 0;
  if (from == to) return 1;
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
  for (p = 0; p < FM1_MOD_POSITIONS; ++p) {
    m->kind[perm[p]] = kind[p];
    m->inst_off[perm[p]] = off[p];
    m->inst_bytes[perm[p]] = bytes[p];
    m->handle[perm[p]] = handle[p];
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

int fm1_mod_set_slot(fm1_mod_t *m, unsigned i, const fm1_mod_slot_t *s) {
  if (i >= FM1_MOD_SLOTS || !s) return 0;
  m->slot[i] = *s;
  m->srt[i].level = 0;
  fm1_mp_rng_seed(&m->srt[i].rng, mod_mix(m->seed, 0x100u + i));
  m->dirty = 1;
  return 1;
}

int fm1_mod_get_slot(const fm1_mod_t *m, unsigned i, fm1_mod_slot_t *out) {
  if (i >= FM1_MOD_SLOTS || !out) return 0;
  *out = m->slot[i];
  return 1;
}

/* A sink parameter's range (SOUND, FX1, FX2 from their binding; HOST from
 * its own table). 0 when the index is out of range. */
static int sink_meta(const fm1_mod_t *m, unsigned unit, unsigned index, mod_meta_t *q) {
  if (unit == FM1_MOD_HOST) {
    const fm1_param_t *p;
    if (index >= FM1_MOD_HOST_PARAMS) return 0;
    p = &fm1_mod_host_params[index];
    q->min = p->min;
    q->max = p->max;
    q->def = p->def;
    q->uid = p->uid;
    q->type = (uint8_t)p->type;
    q->flags = p->flags;
    q->unit = p->unit;
    return 1;
  }
  if (unit > FM1_MOD_FX2 || index >= m->sink_n[unit]) return 0;
  *q = m->meta[unit][index];
  return 1;
}

static float meta_clamp(const mod_meta_t *q, float v) {
  v = mod_clampf(v, q->min, q->max, q->def);
  return q->type == FM1_PARAM_ENUM ? mod_round(v) : v;
}

float fm1_mod_set_base(fm1_mod_t *m, unsigned unit, unsigned index, float value) {
  mod_meta_t q;
  if (!sink_meta(m, unit, index, &q)) return value;
  m->sink_base[unit][index] = mod_clampf(value, q.min, q.max, q.def);
  if ((m->plan.sink_routed[unit] >> index) & 1u) {
    const float v = meta_clamp(&q, m->sink_base[unit][index] + m->sink_off[unit][index]);
    m->sink_sent[unit][index] = v;
    return v;
  }
  m->sink_sent[unit][index] = value;
  return value;
}

float fm1_mod_base(const fm1_mod_t *m, unsigned unit, unsigned index) {
  return unit < MOD_SINK_UNITS && index < FM1_MOD_UNIT_PARAMS ? m->sink_base[unit][index] : 0.0f;
}

float fm1_mod_sent(const fm1_mod_t *m, unsigned unit, unsigned index) {
  return unit < MOD_SINK_UNITS && index < FM1_MOD_UNIT_PARAMS ? m->sink_sent[unit][index] : 0.0f;
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

static void note_at(fm1_mod_t *m, uint64_t at, uint8_t key, uint8_t vel) {
  if (key > 127) return;
  if (vel) {
    m->keys[key >> 5] |= 1u << (key & 31u);
    feed_level(m, G_KEY, at, 1);
    feed_trigger(m, G_TRIG, at);
    feed_cv(m, FM1_MOD_SRC_VEL, at, (float)(vel > 127 ? 127 : vel) * (1.0f / 127.0f));
    feed_cv(m, FM1_MOD_SRC_NOTE, at, (float)((int)key - 60) * (1.0f / 60.0f));
    feed_cv(m, FM1_MOD_SRC_RAND, at, fm1_mp_rng_bipolar(&m->note_rng));
  } else if (key_bit(m->keys, key)) {
    m->keys[key >> 5] &= ~(1u << (key & 31u));
    if (!any_bit(m->keys)) feed_level(m, G_KEY, at, 0);
  }
}

void fm1_mod_live_note(fm1_mod_t *m, uint8_t key, uint8_t velocity) {
  note_at(m, m->now, key, velocity);
}

void fm1_mod_note(fm1_mod_t *m, uint32_t frame, uint8_t key, uint8_t velocity) {
  note_at(m, m->blk + frame, key, velocity);
}

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

uint32_t fm1_mod_begin(fm1_mod_t *m, uint32_t frames, uint32_t bpm_x100, int running) {
  m->blk = m->now;
  m->now += frames;
  if (bpm_x100) m->bpm_x100 = bpm_x100;
  m->running = (uint8_t)(running != 0);
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

/* A source's value now and its port kind and unit. A module output reads
 * the previous tick when the cable is delayed. Non-finite becomes 0. */
static float read_src(fm1_mod_t *m, unsigned src, int delayed, uint8_t *kind, uint8_t *unit) {
  float v = 0.0f;
  *kind = FM1_PORT_CV_BI;
  *unit = FM1_UNIT_NONE;
  if (src < FM1_MOD_SRC_SYSTEM) {
    const fm1_mod_source_info_t *si = fm1_mod_system_source(src);
    const int g = gate_index(src);
    if (!si) return 0.0f;
    *kind = si->kind;
    *unit = si->unit;
    v = g >= 0 ? (float)fm1_mod_gate_end(&m->sys_gate[g]) : m->sys_cv[src];
  } else {
    const unsigned pos = (src - FM1_MOD_SRC_MODULE) / 8u, port = (src - FM1_MOD_SRC_MODULE) % 8u;
    const fm1_mod_kind_t *kd = mod_kind_at(m, pos);
    if (!kd || port >= kd->n_out) return 0.0f;
    *kind = kd->out[port].kind;
    *unit = kd->out[port].unit;
    v = m->out[delayed ? m->cur ^ 1u : m->cur][pos][port];
  }
  if (!mod_finite(v)) {
    ++m->stats.nonfinite;
    return 0.0f;
  }
  return v;
}

/* The cable's signal before its amount: polarity, curve, offset, VIA. */
static float signal(fm1_mod_t *m, unsigned i, uint8_t *unit) {
  const fm1_mod_slot_t *s = &m->slot[i];
  uint8_t kind;
  float x = read_src(m, s->src, (int)((m->plan.delayed_src >> i) & 1u), &kind, unit);
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
    float v = read_src(m, s->via, (int)((m->plan.delayed_via >> i) & 1u), &vk, &vu);
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
 * amount x signal x 60 semitones). */
static float contribution(fm1_mod_t *m, unsigned i, float min, float max, uint8_t flags,
                          uint8_t unit) {
  uint8_t su;
  const float x = signal(m, i, &su);
  const float a = amount_of(&m->slot[i]);
  float c;
  if (flags & FM1_PARAM_INPUT) {
    c = a * x;
  } else if (su == FM1_UNIT_SEMI && unit == FM1_UNIT_SEMI) {
    /* Semitones, on a grid of 1/1024 (0.1 cent) so that whole notes stay
     * whole: (67 - 60) / 60 x 60 is 7.0000005 in float, 7 here. */
    c = a * (mod_round(x * 61440.0f) * (1.0f / 1024.0f));
  } else {
    c = a * x * (max - min);
  }
  if (!mod_finite(c)) {
    ++m->stats.nonfinite;
    return 0.0f;
  }
  return c;
}

static float sum_slots(fm1_mod_t *m, uint32_t slots, float min, float max, uint8_t flags,
                       uint8_t unit) {
  float acc = 0.0f;
  unsigned i;
  for (i = 0; slots; ++i, slots >>= 1) {
    if (slots & 1u) acc = acc + contribution(m, i, min, max, flags, unit);
  }
  return acc;
}

/* One cable into a gate input, as its own alternating gate. */
static void cable_gate(fm1_mod_t *m, unsigned i, fm1_mod_gate_t *c) {
  const fm1_mod_slot_t *s = &m->slot[i];
  mod_slot_rt_t *rt = &m->srt[i];
  const fm1_mod_gate_t *src = NULL;
  uint8_t kind = FM1_PORT_CV_BI, unit;
  mod_gate_clear(c, rt->level);
  if (s->src < FM1_MOD_SRC_SYSTEM) {
    const fm1_mod_source_info_t *si = fm1_mod_system_source(s->src);
    const int g = gate_index(s->src);
    if (si) kind = si->kind;
    if (g >= 0) src = &m->sys_gate[g];
  } else {
    const unsigned pos = (s->src - FM1_MOD_SRC_MODULE) / 8u, port = (s->src - FM1_MOD_SRC_MODULE) % 8u;
    const fm1_mod_kind_t *kd = mod_kind_at(m, pos);
    if (kd && port < kd->n_out) {
      kind = kd->out[port].kind;
      if (kind == FM1_PORT_GATE) {
        src = &m->gout[(m->plan.delayed_src >> i) & 1u ? m->cur ^ 1u : m->cur][pos][port];
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
        const uint32_t draw = fm1_mp_rng_next(&rt->rng);
        if ((uint64_t)draw < threshold) {
          if (rt->level) mod_gate_edge(c, src->ev[e].frame, 0, &m->stats.edges_dropped);
          mod_gate_edge(c, src->ev[e].frame, 1, &m->stats.edges_dropped);
          rt->level = 1;
        }
      } else if (rt->level) {
        mod_gate_edge(c, src->ev[e].frame, 0, &m->stats.edges_dropped);
        rt->level = 0;
      }
    }
  } else {
    /* CV into a gate: a comparator that rises at 0.5 and falls below 0.25,
     * seen at tick resolution, so its edge sits at the tick's first frame. */
    const float v = amount_of(s) * signal(m, i, &unit);
    if (!rt->level && v >= 0.5f) {
      mod_gate_edge(c, 0, 1, &m->stats.edges_dropped);
      rt->level = 1;
    } else if (rt->level && v < 0.25f) {
      mod_gate_edge(c, 0, 0, &m->stats.edges_dropped);
      rt->level = 0;
    }
  }
}

/* Several cables into one gate input combine by OR; edges at one frame go
 * in slot order. */
static void gate_merge(fm1_mod_t *m, uint32_t slots, fm1_mod_gate_t *g) {
  struct { uint8_t frame, slot, seq, high; } ev[FM1_MOD_SLOTS * FM1_MOD_EDGES];
  unsigned n = 0, i, a, b, high = 0;
  for (i = 0; slots; ++i, slots >>= 1) {
    fm1_mod_gate_t c;
    if (!(slots & 1u)) continue;
    cable_gate(m, i, &c);
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

static void run_module(fm1_mod_t *m, unsigned pos, const fm1_mod_transport_t *tp) {
  const fm1_mod_kind_t *kd = mod_kind_at(m, pos);
  const unsigned prev = m->cur ^ 1u;
  fm1_mod_gate_t gin[FM1_MOD_MAX_GATES];
  fm1_mod_io_t io;
  float *out = m->out[m->cur][pos];
  fm1_mod_gate_t *gout = m->gout[m->cur][pos];
  unsigned i;
  if (!kd) return;
  for (i = 0; i < kd->n_params; ++i) {
    const fm1_param_t *p = &kd->params[i];
    const uint8_t d = m->plan.pdest[pos][i];
    float v = m->base[pos][i];
    if (d != MOD_NONE) v = v + sum_slots(m, m->plan.dest[d].slots, p->min, p->max, p->flags, p->unit);
    v = fm1_param_clamp(p, v);
    m->peff[pos][i] = p->type == FM1_PARAM_ENUM ? mod_round(v) : v;
  }
  for (i = 0; i < kd->n_gate_in; ++i) {
    const uint8_t d = m->plan.gdest[pos][i];
    const int normal = gate_index(kd->gate_in[i].normal);
    if (d != MOD_NONE) gate_merge(m, m->plan.dest[d].slots, &gin[i]);
    else if (normal >= 0) gin[i] = m->sys_gate[normal];
    else mod_gate_clear(&gin[i], 0);
  }
  for (i = 0; i < kd->n_out; ++i) {
    out[i] = m->out[prev][pos][i];
    mod_gate_clear(&gout[i], (unsigned)fm1_mod_gate_end(&m->gout[prev][pos][i]));
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
  /* Whatever a kind returns, outputs are finite and in range, and gate
   * edges alternate in frame order. */
  for (i = 0; i < kd->n_out; ++i) {
    if (kd->out[i].kind == FM1_PORT_GATE) {
      const fm1_mod_gate_t raw = gout[i];
      unsigned e;
      mod_gate_clear(&gout[i], (unsigned)fm1_mod_gate_end(&m->gout[prev][pos][i]));
      for (e = 0; e < raw.n && e < FM1_MOD_EDGES; ++e) {
        mod_gate_edge(&gout[i], raw.ev[e].frame, raw.ev[e].high, &m->stats.edges_dropped);
      }
      out[i] = (float)fm1_mod_gate_end(&gout[i]);
    } else {
      if (!mod_finite(out[i])) {
        ++m->stats.nonfinite;
        out[i] = 0.0f;
      }
      out[i] = kd->out[i].kind == FM1_PORT_CV_UNI ? mod_clampf(out[i], 0.0f, 1.0f, 0.0f)
                                                  : mod_clampf(out[i], -1.0f, 1.0f, 0.0f);
    }
  }
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

static void write_sinks(fm1_mod_t *m) {
  unsigned u;
  for (u = 0; u < MOD_SINK_UNITS; ++u) {
    uint32_t mask = m->plan.sink_routed[u] | m->restore[u];
    unsigned i;
    for (i = 0; mask; ++i, mask >>= 1) {
      mod_meta_t q;
      float v, off = 0.0f;
      const uint8_t d = m->plan.sdest[u][i];
      if (!(mask & 1u) || !sink_meta(m, u, i, &q)) continue;
      if (d != MOD_NONE && ((m->plan.sink_routed[u] >> i) & 1u)) {
        off = sum_slots(m, m->plan.dest[d].slots, q.min, q.max, q.flags, q.unit);
      }
      v = meta_clamp(&q, m->sink_base[u][i] + off);
      m->sink_off[u][i] = off;
      if (mod_bits(v) != mod_bits(m->sink_sent[u][i])) {
        fm1_mod_write_t *w = &m->wr[m->n_wr++];
        w->unit = (uint8_t)u;
        w->reserved = 0;
        w->index = (uint16_t)i;
        w->value = v;
        m->sink_sent[u][i] = v;
      }
    }
    m->restore[u] = 0;
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
  tp.running = m->running;
  tp.start = m->start_frame;
  tp.reserved[0] = tp.reserved[1] = 0;
  for (i = 0; i < m->plan.n_order; ++i) run_module(m, m->plan.order[i], &tp);
  write_sinks(m);
  m->stats.writes += m->n_wr;
  ++m->stats.ticks;
  ++m->k;
  m->next_tick += FM1_MOD_TICK;
  return m->n_wr;
}

void fm1_mod_reset(fm1_mod_t *m, uint32_t why) {
  unsigned pos;
  for (pos = 0; pos < FM1_MOD_POSITIONS; ++pos) {
    const fm1_mod_kind_t *kd = mod_kind_at(m, pos);
    if (kd && kd->reset) kd->reset(instance(m, pos), why);
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
  out->reserved[0] = out->reserved[1] = 0;
  for (i = 0; i < FM1_MOD_POSITIONS; ++i) {
    out->order[i] = i < m->plan.n_order ? m->plan.order[i] : MOD_NONE;
    out->comp[i] = i < m->plan.n_order ? m->plan.comp[m->plan.order[i]] : MOD_NONE;
  }
}

void fm1_mod_get_stats(const fm1_mod_t *m, fm1_mod_stats_t *out) {
  *out = m->stats;
}

int fm1_mod_sink(fm1_mod_t *m, unsigned i, fm1_mod_sink_info_t *out) {
  unsigned u;
  if (m->dirty) mod_plan_build(m);
  for (u = 0; u < MOD_SINK_UNITS; ++u) {
    uint32_t mask = m->plan.sink_routed[u];
    unsigned p;
    for (p = 0; mask; ++p, mask >>= 1) {
      mod_meta_t q;
      uint32_t s;
      uint16_t n = 0;
      if (!(mask & 1u)) continue;
      if (i--) continue;
      sink_meta(m, u, p, &q);
      for (s = m->plan.dest[m->plan.sdest[u][p]].slots; s; s >>= 1) n = (uint16_t)(n + (s & 1u));
      out->unit = (uint8_t)u;
      out->reserved = 0;
      out->index = (uint16_t)p;
      out->uid = q.uid;
      out->slots = n;
      out->base = m->sink_base[u][p];
      out->value = m->sink_sent[u][p];
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

int fm1_mod_ramp_settled(const fm1_mod_ramp_t *r, uint64_t frame, float value) {
  return r->to == value && (r->from == r->to || frame >= r->t0 + FM1_MOD_TICK);
}
