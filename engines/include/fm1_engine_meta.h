/* fm1_engine_meta.h -- what an editor shows of a module beside its
 * parameter table (notes/2026-10-06-web-editor.md §6, stage ED0), kept
 * beside the registries so the panel and the metadata export (fm1_meta.h)
 * read the same words:
 *
 *   - a knob page's name, where the panel names it (the arpeggiator's PLAY
 *     ... SEED); every other page the panel shows by its number ("2/4
 *     Sound", "1/2 M1"), and so does an editor ("Page 2 · KNOB1-3");
 *   - the group an audio effect is listed under, as the project's page
 *     groups the effects (Reverbs; Chorus, space and delay; Filters and EQ;
 *     Grit and colour; Dynamics), an editor's hint and never a rule;
 *   - a knob's detent, the step one click of a knob moves a parameter.
 *
 * A module the tables do not name has no page names and, for an audio
 * effect, no group: tests/test_engine_editor_meta.py fails until it has one.
 *
 * Plain C99 (the inline helpers need no libm). MIT licence, like the rest
 * of this repository.
 */
#ifndef FM1_ENGINE_META_H_
#define FM1_ENGINE_META_H_

#include <stddef.h>
#include <stdint.h>

#include "fm1_engine.h"

#ifdef __cplusplus
extern "C" {
#endif

/* The name of knob page `page` (0-based) of the module `id` (an engine's,
 * an effect's, a MIDI effect's or a modulation kind's), or NULL where the
 * panel shows the page by its number. */
const char *fm1_page_name(const char *id, unsigned page);

/* The knob pages of a parameter table as the panel pages it: the highest
 * page of a parameter on a knob (not an INPUT) plus one, at least one. */
static inline unsigned fm1_param_pages(const fm1_param_t *ps, unsigned n) {
  unsigned pages = 1, i;
  for (i = 0; ps && i < n; ++i) {
    if (!(ps[i].flags & FM1_PARAM_INPUT) && ps[i].page + 1u > pages) pages = ps[i].page + 1u;
  }
  return pages;
}

typedef struct fm1_fx_group {
  const char *id;               /* "reverb" */
  const char *name;             /* "Reverbs" */
} fm1_fx_group_t;

/* The groups, in the order the page lists them. */
extern const fm1_fx_group_t fm1_fx_groups[];
extern const size_t fm1_fx_group_count;

/* The group audio effect `id` is listed under, or NULL. */
const fm1_fx_group_t *fm1_fx_group_of(const char *id);

/* A knob detent on p, in its own unit: one entry of a list; for a linear
 * FLOAT a hundredth of its range, or whole units on a wide integer range
 * (0..127 moves by 1, 0..1000 by 10). A LOG parameter moves a hundredth of
 * its position instead (FM1_PARAM_LOG_DETENT; fm1_param_pos), so its step
 * is a ratio. The panel's knobs, the rack's and an editor's arrow keys all
 * step by this. A knob over a parameter a sequencer lane locks moves on
 * the lane's 7-bit grid instead (fm1_seq_value7_step). */
#define FM1_PARAM_LOG_DETENT 0.01f
static inline float fm1_param_detent(const fm1_param_t *p) {
  float range, s;
  if (p->type == FM1_PARAM_ENUM) return 1.0f;
  range = p->max - p->min;
  if (range >= 10.0f && p->min == (float)(int)p->min && p->max == (float)(int)p->max) {
    s = (float)(int)(range / 100.0f + 0.5f);
    return s < 1.0f ? 1.0f : s;
  }
  return range / 100.0f;
}

#ifdef __cplusplus
}
#endif

#endif /* FM1_ENGINE_META_H_ */
