/* mod_plan.c -- the modulation runtime's planner (docs/16 §2.5): which slots
 * run, in which order the modules run, and which cables read a tick late.
 *
 *   1. A slot is active when it is on and both ends exist: a defined source
 *      (and VIA), and a destination that takes modulation (MOD and not
 *      NOLOCK; an ENUM only with MOD; a module's INPUT; a gate input with
 *      GATE_DST). One that is on but invalid is refused. A VOICE slot (MG9)
 *      must also reach something that moves per voice: a POLY parameter of a
 *      sound unit whose engine takes per-note offsets, a sound's pitch (HOST
 *      PITCH, PITCH2-4, PITCH_CUR), or a module that runs per voice; and at
 *      most FM1_MOD_VDESTS sound parameters at once. A module runs per voice
 *      when its kind is POLY_OK and a live VOICE slot reads it; a VOICE slot
 *      into a module is live when that module runs per voice. Every other
 *      VOICE slot is refused: poly never reaches mono.
 *   2. Strongly connected components (Tarjan) of the module-to-module
 *      cables, visiting modules in rack order and cables in slot order.
 *      System sources and sinks cannot be in a loop.
 *   3. The components in dependency order (Kahn); ties go to the component
 *      whose first member sits highest in the rack (the lowest position).
 *      Inside a component, modules run in rack order.
 *   4. A cable is delayed when both ends are in one component and its
 *      source sits at or below its destination: inside a loop the cable
 *      that runs up the rack, and every self-cable. It reads the previous
 *      tick. A cable between components is never delayed.
 *   5. Each destination's slots, in ascending slot order; VOICE slots' apart.
 *   6. Where the per-voice instances live: after the highest global
 *      instance, as many voices (up to FM1_MOD_VOICES) as the arena holds.
 *
 * The plan depends only on the slots, the rack, the bound engines and the
 * current sound, and under any permutation of the slot table it orders the
 * same modules the same way and delays the same cables (fm1-mod-core-test
 * fuzzes both). C99, no heap. MIT licence. */
#include "mod_int.h"

#include <string.h>

int mod_source_kind(const fm1_mod_t *m, unsigned src, uint8_t *unit) {
  if (src < FM1_MOD_SRC_SYSTEM) {
    const fm1_mod_source_info_t *si = fm1_mod_system_source(src);
    if (!si) return -1;
    if (unit) *unit = si->unit;
    return si->kind;
  } else {
    const unsigned pos = (src - FM1_MOD_SRC_MODULE) / 8u, port = (src - FM1_MOD_SRC_MODULE) % 8u;
    const fm1_mod_kind_t *kd = mod_kind_at(m, pos);
    if (!kd || port >= kd->n_out) return -1;
    if (unit) *unit = kd->out[port].unit;
    return kd->out[port].kind;
  }
}

static int takes_mod(uint8_t type, uint16_t flags) {
  (void)type;   /* every FLOAT carries MOD unless NOLOCK; an ENUM must say MOD */
  return (flags & (FM1_PARAM_MOD | FM1_PARAM_NOLOCK)) == FM1_PARAM_MOD;
}

/* A slot's destination is a module's (8 + position). */
static int is_module(unsigned unit) {
  return unit >= FM1_MOD_MODULE && unit < FM1_MOD_MODULE + FM1_MOD_POSITIONS;
}

int mod_slot_dst_param(const fm1_mod_t *m, const fm1_mod_slot_t *s) {
  unsigned i;
  int si;
  if (is_module(s->dst_unit)) {
    const unsigned pos = (unsigned)s->dst_unit - FM1_MOD_MODULE;
    const fm1_mod_kind_t *kd = mod_kind_at(m, pos);
    if (!kd) return -1;
    if (s->flags & FM1_MOD_SLOT_GATE_DST) return s->dst < kd->n_gate_in ? (int)s->dst : -1;
    for (i = 0; i < kd->n_params; ++i) {
      const fm1_param_t *p = &kd->params[i];
      if (p->uid != s->dst) continue;
      if (p->flags & FM1_PARAM_NOLOCK) return -1;
      return (p->flags & FM1_PARAM_INPUT) || takes_mod((uint8_t)p->type, p->flags) ? (int)i : -1;
    }
    return -1;
  }
  if (s->flags & FM1_MOD_SLOT_GATE_DST) return -1;
  if (s->dst_unit == FM1_MOD_HOST) {
    for (i = 0; i < FM1_MOD_HOST_PARAMS; ++i) {
      if (fm1_mod_host_params[i].uid == s->dst) return (int)i;
    }
    return -1;
  }
  si = fm1_mod_sink_index(s->dst_unit);
  if (si < 0 || !s->dst) return -1;
  for (i = 0; i < m->sink_n[si]; ++i) {
    const mod_meta_t *q = &m->meta[m->sink_first[si] + i];
    if (q->uid == s->dst) return takes_mod(q->type, q->flags) ? (int)i : -1;
  }
  return -1;
}

/* Whether a VOICE slot's destination moves per voice (step 1), given its
 * parameter (or gate) index. */
static int voice_target(const fm1_mod_t *m, const fm1_mod_slot_t *s, int dparam) {
  const int snd = fm1_mod_unit_sound(s->dst_unit);
  if (is_module(s->dst_unit)) {
    const fm1_mod_kind_t *kd = mod_kind_at(m, (unsigned)s->dst_unit - FM1_MOD_MODULE);
    return kd && (kd->flags & FM1_MOD_KIND_POLY_OK);
  }
  if (s->dst_unit == FM1_MOD_HOST) {
    const int k = fm1_mod_host_pitch_sound((unsigned)dparam);
    const int to = k == -2 ? (int)m->cur_sound : k;
    return to >= 0 && m->sink_note[fm1_mod_sink_index(fm1_mod_sound_unit((unsigned)to))];
  }
  if (snd >= 0) {
    const int si = fm1_mod_sink_index(s->dst_unit);
    const mod_meta_t *q = &m->meta[m->sink_first[si] + (unsigned)dparam];
    return m->sink_note[si] && (q->flags & FM1_PARAM_POLY) && q->type == FM1_PARAM_FLOAT;
  }
  return 0;   /* an effect, a master slot, HOST AMP: mono */
}

static int module_of(unsigned src) {
  if (src == MOD_NONE || src < FM1_MOD_SRC_MODULE) return -1;
  return (int)((src - FM1_MOD_SRC_MODULE) / 8u);
}

typedef struct graph {
  uint8_t adj[FM1_MOD_POSITIONS][2u * FM1_MOD_SLOTS];  /* successors, in slot order */
  uint8_t nadj[FM1_MOD_POSITIONS];
  uint8_t index[FM1_MOD_POSITIONS], low[FM1_MOD_POSITIONS], on[FM1_MOD_POSITIONS];
  uint8_t stack[FM1_MOD_POSITIONS], sp, counter, ncomp;
  uint8_t comp[FM1_MOD_POSITIONS];                     /* Tarjan's numbering */
} graph_t;

static void strong(graph_t *g, unsigned v) {
  unsigned k;
  g->index[v] = g->low[v] = ++g->counter;
  g->stack[g->sp++] = (uint8_t)v;
  g->on[v] = 1;
  for (k = 0; k < g->nadj[v]; ++k) {
    const unsigned w = g->adj[v][k];
    if (!g->index[w]) {
      strong(g, w);
      if (g->low[w] < g->low[v]) g->low[v] = g->low[w];
    } else if (g->on[w] && g->index[w] < g->low[v]) {
      g->low[v] = g->index[w];
    }
  }
  if (g->low[v] == g->index[v]) {
    unsigned w;
    do {
      w = g->stack[--g->sp];
      g->on[w] = 0;
      g->comp[w] = g->ncomp;
    } while (w != v);
    ++g->ncomp;
  }
}

/* The sound and the entry of a VOICE slot into a sink (HOST pitch or a
 * sound unit's parameter): its sound unit, whether it is the pitch, and
 * the parameter index. */
static void vdest_key(const fm1_mod_t *m, const fm1_mod_slot_t *s, int dparam, unsigned *sound,
                      unsigned *pitch, unsigned *index) {
  if (s->dst_unit == FM1_MOD_HOST) {
    const int k = fm1_mod_host_pitch_sound((unsigned)dparam);
    *sound = k == -2 ? m->cur_sound : (unsigned)k;
    *pitch = 1;
    *index = 0;
  } else {
    *sound = (unsigned)fm1_mod_unit_sound(s->dst_unit);
    *pitch = 0;
    *index = (unsigned)dparam;
  }
}

/* A per-voice block's head holds 16 bytes an output: its value and its gate. */
typedef char mod_vblk_out_fit[sizeof(float) + sizeof(fm1_mod_gate_t) <= 16u &&
                              sizeof(mod_vblk_t) == MOD_VBLK_HEAD ? 1 : -1];

/* The per-voice blocks' layout for the positions in `poly` (step 6). */
static void layout(fm1_mod_t *m, mod_plan_t *p) {
  const fm1_host_t h = { FM1_ENGINE_API_VERSION, m->rate, m->max_frames };
  uint32_t gend = 0, sum = 0;
  unsigned pos;
  for (pos = 0; pos < FM1_MOD_POSITIONS; ++pos) {
    if (mod_kind_at(m, pos)) {
      const uint32_t e = (uint32_t)m->inst_off[pos] + m->inst_bytes[pos];
      if (e > gend) gend = e;
    }
  }
  gend = (gend + 15u) & ~15u;
  for (pos = 0; pos < FM1_MOD_POSITIONS; ++pos) {
    const fm1_mod_kind_t *kd = mod_kind_at(m, pos);
    uint32_t hdr, inst;
    if (!kd || !((p->poly >> pos) & 1u)) continue;
    hdr = (MOD_VBLK_HEAD + 16u * kd->n_out + 15u) & ~15u;   /* outputs: floats and gates */
    inst = ((uint32_t)kd->instance_size(&h) + 15u) & ~15u;
    p->voff[pos] = (uint16_t)sum;
    p->vhdr[pos] = (uint16_t)hdr;
    sum += hdr + (inst ? inst : 16u);
  }
  p->vbase = (uint16_t)gend;
  p->vsize = (uint16_t)sum;
  p->vcap = (uint8_t)(!sum ? FM1_MOD_VOICES
                           : gend + sum > FM1_MOD_ARENA ? 0u
                           : (FM1_MOD_ARENA - gend) / sum < FM1_MOD_VOICES ? (FM1_MOD_ARENA - gend) / sum
                           : FM1_MOD_VOICES);
}

void mod_plan_build(fm1_mod_t *m) {
  mod_plan_t *p = &m->plan;
  const uint32_t old_active = p->active;
  uint32_t old_routed[MOD_SINK_UNITS];
  mod_vdest_t old_vd[FM1_MOD_VDESTS];
  uint16_t old_voff[FM1_MOD_POSITIONS];
  const uint16_t old_vbase = p->vbase, old_vsize = p->vsize;
  const uint8_t old_n_vd = p->n_vd, old_poly = p->poly, old_vcap = p->vcap;
  graph_t g;
  uint8_t cadj[FM1_MOD_POSITIONS], indeg[FM1_MOD_POSITIONS], cmin[FM1_MOD_POSITIONS];
  uint8_t done[FM1_MOD_POSITIONS], run_comp[FM1_MOD_POSITIONS];
  int dparam[FM1_MOD_SLOTS];
  uint32_t voice_ok = 0, live = 0, to_module = 0;
  unsigned i, u, pos;

  memcpy(old_routed, p->sink_routed, sizeof(old_routed));
  memcpy(old_vd, p->vd, sizeof(old_vd));
  memcpy(old_voff, p->voff, sizeof(old_voff));
  memset(p, 0, sizeof(*p));
  memset(p->pdest, MOD_NONE, sizeof(p->pdest));
  memset(p->gdest, MOD_NONE, sizeof(p->gdest));
  memset(p->sdest, MOD_NONE, sizeof(p->sdest));
  memset(p->order, MOD_NONE, sizeof(p->order));
  memset(p->comp, MOD_NONE, sizeof(p->comp));
  memset(&g, 0, sizeof(g));

  /* 1. Which slots run. */
  for (i = 0; i < FM1_MOD_SLOTS; ++i) {
    const fm1_mod_slot_t *s = &m->slot[i];
    dparam[i] = -1;
    if (!(s->flags & FM1_MOD_SLOT_ON)) continue;
    dparam[i] = mod_slot_dst_param(m, s);
    if (mod_source_kind(m, s->src, NULL) < 0 ||
        (s->via != MOD_NONE && mod_source_kind(m, s->via, NULL) < 0) || dparam[i] < 0 ||
        ((s->flags & FM1_MOD_SLOT_VOICE) && !voice_target(m, s, dparam[i]))) {
      p->refused |= 1u << i;
      dparam[i] = -1;
      continue;
    }
    if (s->flags & FM1_MOD_SLOT_VOICE) {
      voice_ok |= 1u << i;              /* live or not: below */
      if (is_module(s->dst_unit)) to_module |= 1u << i;
      continue;
    }
    p->active |= 1u << i;
  }
  /* 1b. VOICE slots into sinks: one entry per sound parameter (or pitch),
   * at most FM1_MOD_VDESTS; the rest are refused. */
  for (i = 0; i < FM1_MOD_SLOTS; ++i) {
    unsigned snd, pitch, index, k;
    if (!((voice_ok & ~to_module) >> i & 1u)) continue;
    vdest_key(m, &m->slot[i], dparam[i], &snd, &pitch, &index);
    for (k = 0; k < p->n_vd; ++k) {
      if (p->vd[k].sound == snd && p->vd[k].pitch == pitch && p->vd[k].index == index) break;
    }
    if (k == p->n_vd) {
      if (k == FM1_MOD_VDESTS) continue;  /* refused below: not live */
      p->vd[k].sound = (uint8_t)snd;
      p->vd[k].pitch = (uint8_t)pitch;
      p->vd[k].index = (uint16_t)index;
      ++p->n_vd;
    }
    p->vd[k].slots |= 1u << i;
    live |= 1u << i;
  }
  /* 1c. Which modules run per voice: POLY_OK kinds a live VOICE slot reads,
   * and which VOICE slots into modules are live: those into one of them. */
  for (;;) {
    uint32_t more = 0;
    for (i = 0; i < FM1_MOD_SLOTS; ++i) {
      const fm1_mod_slot_t *s = &m->slot[i];
      const int a = module_of(s->src), b = module_of(s->via);
      if (!((live >> i) & 1u)) continue;
      if (a >= 0 && (mod_kind_at(m, (unsigned)a)->flags & FM1_MOD_KIND_POLY_OK)) p->poly |= (uint8_t)(1u << a);
      if (b >= 0 && (mod_kind_at(m, (unsigned)b)->flags & FM1_MOD_KIND_POLY_OK)) p->poly |= (uint8_t)(1u << b);
    }
    for (i = 0; i < FM1_MOD_SLOTS; ++i) {
      if (((to_module & ~live) >> i & 1u) &&
          ((p->poly >> (m->slot[i].dst_unit - FM1_MOD_MODULE)) & 1u)) {
        more |= 1u << i;
      }
    }
    if (!more) break;
    live |= more;
  }
  /* 6, early: the arena's room decides whether any of it runs. */
  layout(m, p);
  if (p->poly && !p->vcap) {            /* not one voice fits: no voices at all */
    live = 0;
    p->poly = 0;
    p->n_vd = 0;
    memset(p->vd, 0, sizeof(p->vd));
    layout(m, p);
  }
  p->vslots = live;
  p->active |= live;
  p->refused |= voice_ok & ~live;
  for (i = 0; i < p->n_vd; ++i) p->vsounds = (uint8_t)(p->vsounds | (1u << p->vd[i].sound));

  /* 2. The module graph, cables in slot order, and its components. */
  for (i = 0; i < FM1_MOD_SLOTS; ++i) {
    const fm1_mod_slot_t *s = &m->slot[i];
    int a, b;
    if (!((p->active >> i) & 1u) || !is_module(s->dst_unit)) continue;
    b = (int)s->dst_unit - FM1_MOD_MODULE;
    a = module_of(s->src);
    if (a >= 0) g.adj[a][g.nadj[a]++] = (uint8_t)b;
    a = module_of(s->via);
    if (a >= 0) g.adj[a][g.nadj[a]++] = (uint8_t)b;
  }
  for (pos = 0; pos < FM1_MOD_POSITIONS; ++pos) {
    if (mod_kind_at(m, pos) && !g.index[pos]) strong(&g, pos);
  }

  /* 3. Kahn over the components; the lowest first position wins a tie. */
  memset(cadj, 0, sizeof(cadj));
  memset(indeg, 0, sizeof(indeg));
  memset(done, 0, sizeof(done));
  memset(cmin, MOD_NONE, sizeof(cmin));
  for (pos = 0; pos < FM1_MOD_POSITIONS; ++pos) {
    unsigned k;
    if (!mod_kind_at(m, pos)) continue;
    if (pos < cmin[g.comp[pos]]) cmin[g.comp[pos]] = (uint8_t)pos;
    for (k = 0; k < g.nadj[pos]; ++k) {
      const unsigned a = g.comp[pos], b = g.comp[g.adj[pos][k]];
      if (a != b && !((cadj[a] >> b) & 1u)) {
        cadj[a] = (uint8_t)(cadj[a] | (1u << b));
        ++indeg[b];
      }
    }
  }
  for (u = 0; u < g.ncomp; ++u) {
    unsigned c, best = MOD_NONE;
    for (c = 0; c < g.ncomp; ++c) {
      if (!done[c] && !indeg[c] && (best == MOD_NONE || cmin[c] < cmin[best])) best = c;
    }
    if (best == MOD_NONE) break;   /* cannot happen: the condensation is acyclic */
    done[best] = 1;
    run_comp[best] = (uint8_t)u;
    for (pos = 0; pos < FM1_MOD_POSITIONS; ++pos) {
      if (mod_kind_at(m, pos) && g.comp[pos] == best) p->order[p->n_order++] = (uint8_t)pos;
    }
    for (c = 0; c < g.ncomp; ++c) {
      if ((cadj[best] >> c) & 1u) --indeg[c];
    }
  }
  for (pos = 0; pos < FM1_MOD_POSITIONS; ++pos) {
    if (mod_kind_at(m, pos)) p->comp[pos] = run_comp[g.comp[pos]];
  }

  /* 4. Delayed cables; 5. destinations, slots ascending. A VOICE slot into
   * a sink has its entry already (1b); one into a module gets a
   * destination of its own (gate 2 or 3), apart from the global ones. */
  for (i = 0; i < FM1_MOD_SLOTS; ++i) {
    const fm1_mod_slot_t *s = &m->slot[i];
    const unsigned voice = (s->flags & FM1_MOD_SLOT_VOICE) ? 2u : 0u;
    const unsigned gate = ((s->flags & FM1_MOD_SLOT_GATE_DST) ? 1u : 0u) | voice;
    unsigned d;
    if (!((p->active >> i) & 1u)) continue;
    if (is_module(s->dst_unit)) {
      const int b = (int)s->dst_unit - FM1_MOD_MODULE;
      int a = module_of(s->src);
      if (a >= 0 && p->comp[a] == p->comp[b] && a >= b) p->delayed_src |= 1u << i;
      a = module_of(s->via);
      if (a >= 0 && p->comp[a] == p->comp[b] && a >= b) p->delayed_via |= 1u << i;
    } else if (voice) {
      continue;
    }
    for (d = 0; d < p->n_dest; ++d) {
      if (p->dest[d].unit == s->dst_unit && p->dest[d].gate == gate &&
          p->dest[d].index == (uint16_t)dparam[i]) {
        break;
      }
    }
    if (d == p->n_dest) {
      p->dest[d].unit = s->dst_unit;
      p->dest[d].gate = (uint8_t)gate;
      p->dest[d].index = (uint16_t)dparam[i];
      p->dest[d].slots = 0;
      ++p->n_dest;
      if (is_module(s->dst_unit)) {
        const unsigned b = (unsigned)s->dst_unit - FM1_MOD_MODULE;
        if (gate == 1u) {
          p->gdest[b][dparam[i]] = (uint8_t)d;
          p->gate_conn[b] = (uint8_t)(p->gate_conn[b] | (1u << dparam[i]));
        } else if (gate == 3u) {
          p->vgate_conn[b] = (uint8_t)(p->vgate_conn[b] | (1u << dparam[i]));
        } else if (gate == 2u) {
          p->vrouted[b] |= 1u << dparam[i];
        } else {
          p->pdest[b][dparam[i]] = (uint8_t)d;
          p->routed[b] |= 1u << dparam[i];
        }
      } else {
        const int si = fm1_mod_sink_index(s->dst_unit);   /* valid: the slot is active */
        p->sdest[m->sink_first[si] + dparam[i]] = (uint8_t)d;
        p->sink_routed[si] |= 1u << dparam[i];
      }
    }
    p->dest[d].slots |= 1u << i;
    if (!((old_active >> i) & 1u)) {
      m->srt[i].level = 0;
      mod_voices_level_clear(m, 1u << i);
    }
  }
  /* PITCH_CUR's cables bend the current sound: its pitch is routed too. */
  if ((p->sink_routed[MOD_HOST_SINK] >> FM1_MOD_HOST_PITCH_CUR) & 1u) {
    p->sink_routed[MOD_HOST_SINK] |= 1u << fm1_mod_host_pitch(m->cur_sound);
  }

  /* A sink parameter no longer routed goes back to its base at the next
   * tick (if what was sent differs). */
  for (u = 0; u < MOD_SINK_UNITS; ++u) {
    const uint32_t valid = m->sink_n[u] >= 32u ? 0xFFFFFFFFu : (1u << m->sink_n[u]) - 1u;
    m->restore[u] |= old_routed[u] & ~p->sink_routed[u];
    m->restore[u] &= valid;
  }

  /* The voices' offsets follow their entries; one whose entry went is put
   * back to 0, and a new entry is sent whatever it is (MG9). */
  for (i = 0; i < FM1_MOD_VOICES; ++i) {
    mod_voice_t *vc = &m->voice[i];
    float sent[FM1_MOD_VDESTS];
    uint8_t changed = 0;
    unsigned j, k;
    if (vc->state == MOD_V_FREE) continue;
    for (k = 0; k < p->n_vd; ++k) {
      union { uint32_t u; float f; } nan;
      nan.u = 0x7FC00000u;              /* never the bits of a value: sent next time */
      sent[k] = nan.f;
    }
    for (j = 0; j < old_n_vd; ++j) {
      const mod_vdest_t *o = &old_vd[j];
      if (o->sound != vc->sound) continue;
      for (k = 0; k < p->n_vd; ++k) {
        if (p->vd[k].sound == o->sound && p->vd[k].pitch == o->pitch && p->vd[k].index == o->index) break;
      }
      if (k < p->n_vd) {
        sent[k] = vc->sent[j];
        changed = (uint8_t)(changed | (((vc->changed >> j) & 1u) << k));
      } else if (mod_bits(vc->sent[j]) != 0u || ((vc->changed >> j) & 1u)) {
        vc->restore |= 1ull << (o->pitch ? MOD_PITCH_BIT : o->index);
      }
    }
    for (k = 0; k < p->n_vd; ++k) {
      if (p->vd[k].sound == vc->sound) vc->restore &= ~(1ull << (p->vd[k].pitch ? MOD_PITCH_BIT : p->vd[k].index));
    }
    memcpy(vc->sent, sent, sizeof(sent[0]) * p->n_vd);
    vc->changed = changed;
  }
  /* 6. A layout that moved makes every per-voice instance again. */
  if (p->vbase != old_vbase || p->vsize != old_vsize || p->poly != old_poly || p->vcap != old_vcap ||
      memcmp(p->voff, old_voff, sizeof(old_voff)) != 0) {
    /* Their outputs restart low: so do the voices' gate cables from them. */
    mod_voices_level_clear(m, mod_slots_from(m, old_poly));
    for (i = 0; i < FM1_MOD_VOICES; ++i) {
      mod_voice_t *vc = &m->voice[i];
      unsigned q;
      for (q = 0; q < FM1_MOD_POSITIONS && vc->ready; ++q) {
        const mod_vblk_t *h;
        if (!((vc->ready >> q) & 1u)) continue;
        h = (const mod_vblk_t *)(m->arena + old_vbase + (uint32_t)i * old_vsize + old_voff[q]);
        if (h->kind < fm1_mod_kind_count && fm1_mod_kinds[h->kind]->destroy) {
          fm1_mod_kinds[h->kind]->destroy(m->arena + h->handle);
        }
      }
      vc->ready = 0;
    }
  }
  ++m->stats.plans;
  m->dirty = 0;
}
