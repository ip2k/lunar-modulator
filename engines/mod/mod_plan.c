/* mod_plan.c -- the modulation runtime's planner (docs/16 §2.5): which slots
 * run, in which order the modules run, and which cables read a tick late.
 *
 *   1. A slot is active when it is on and both ends exist: a defined source
 *      (and VIA), and a destination that takes modulation (MOD and not
 *      NOLOCK; an ENUM only with MOD; a module's INPUT; a gate input with
 *      GATE_DST). One that is on but invalid is refused.
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
 *   5. Each destination's slots, in ascending slot order.
 *
 * The plan depends only on the slots and the rack, and under any
 * permutation of the slot table it orders the same modules the same way
 * and delays the same cables (fm1-mod-core-test fuzzes both). C99, no
 * heap. MIT licence. */
#include "mod_int.h"

#include <string.h>

int mod_source_kind(const fm1_mod_t *m, unsigned src) {
  if (src < FM1_MOD_SRC_SYSTEM) {
    const fm1_mod_source_info_t *si = fm1_mod_system_source(src);
    if (!si) return -1;
    return si->kind;
  } else {
    const unsigned pos = (src - FM1_MOD_SRC_MODULE) / 8u, port = (src - FM1_MOD_SRC_MODULE) % 8u;
    const fm1_mod_kind_t *kd = mod_kind_at(m, pos);
    if (!kd || port >= kd->n_out) return -1;
    return kd->out[port].kind;
  }
}

static int takes_mod(uint8_t type, uint8_t flags) {
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

void mod_plan_build(fm1_mod_t *m) {
  mod_plan_t *p = &m->plan;
  const uint32_t old_active = p->active;
  uint32_t old_routed[MOD_SINK_UNITS];
  graph_t g;
  uint8_t cadj[FM1_MOD_POSITIONS], indeg[FM1_MOD_POSITIONS], cmin[FM1_MOD_POSITIONS];
  uint8_t done[FM1_MOD_POSITIONS], run_comp[FM1_MOD_POSITIONS];
  int dparam[FM1_MOD_SLOTS];
  unsigned i, u, pos;

  memcpy(old_routed, p->sink_routed, sizeof(old_routed));
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
    if (mod_source_kind(m, s->src) < 0 ||
        (s->via != MOD_NONE && mod_source_kind(m, s->via) < 0) || dparam[i] < 0) {
      p->refused |= 1u << i;
      dparam[i] = -1;
      continue;
    }
    p->active |= 1u << i;
  }

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

  /* 4. Delayed cables; 5. destinations, slots ascending. */
  for (i = 0; i < FM1_MOD_SLOTS; ++i) {
    const fm1_mod_slot_t *s = &m->slot[i];
    const unsigned gate = (s->flags & FM1_MOD_SLOT_GATE_DST) ? 1u : 0u;
    unsigned d;
    if (!((p->active >> i) & 1u)) continue;
    if (is_module(s->dst_unit)) {
      const int b = (int)s->dst_unit - FM1_MOD_MODULE;
      int a = module_of(s->src);
      if (a >= 0 && p->comp[a] == p->comp[b] && a >= b) p->delayed_src |= 1u << i;
      a = module_of(s->via);
      if (a >= 0 && p->comp[a] == p->comp[b] && a >= b) p->delayed_via |= 1u << i;
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
        if (gate) {
          p->gdest[b][dparam[i]] = (uint8_t)d;
          p->gate_conn[b] = (uint8_t)(p->gate_conn[b] | (1u << dparam[i]));
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
    if (!((old_active >> i) & 1u)) m->srt[i].level = 0;
  }

  /* A sink parameter no longer routed goes back to its base at the next
   * tick (if what was sent differs). */
  for (u = 0; u < MOD_SINK_UNITS; ++u) {
    const uint32_t valid = m->sink_n[u] >= 32u ? 0xFFFFFFFFu : (1u << m->sink_n[u]) - 1u;
    m->restore[u] |= old_routed[u] & ~p->sink_routed[u];
    m->restore[u] &= valid;
  }
  ++m->stats.plans;
  m->dirty = 0;
}
