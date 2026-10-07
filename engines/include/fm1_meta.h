/* fm1_meta.h -- the parameter metadata export (notes/2026-10-06-state-files.md
 * §7.7; engines/state/schema/metadata.schema.json): everything a build can
 * make, written from its registries as one JSON document, so an editor (the
 * advanced web editor, the guide's tools) builds its controls from it and
 * never hard-codes a name, a range or a uid.
 *
 * It holds every engine, audio effect and MIDI effect with each parameter's
 * uid, name, abbreviation, type, range, default, unit, page and knob, flags
 * (LOG, and API v4's FOCUS and PER_FOCUS among them), list entries and
 * aliases, and its instance bytes at the FM-1's rate; every modulation kind
 * with its parameters, ports and pattern data; the system sources, the
 * cable units, the host's parameters, the polarities and curves; FM6's VCED
 * fields; the project keys; the ids the build knows but lacks (fm1_known.h);
 * the reader's caps (fm1_state_caps.h); and the build: the engine and
 * modulation API versions, the rate, the RAM budget and the GPL switch.
 *
 * Versioned by its `lunar` level: a minor level adds members and never moves
 * one. Written in the canonical layout (tests/state_canon.py: two spaces of
 * indent, one member a line, members in the schema's order, a float as the
 * shortest decimal that reads back to its float32, in ECMAScript's format),
 * so the same build always writes the same bytes, on any host. fm1-render
 * --meta prints it; the simulator will (fm1w_meta, stage A1).
 *
 * Plain C99. Floats are written by the state files' exact formatter
 * (fm1_num.h), so the export and a saved file write a number alike. It is
 * for the desktop tools and the simulator, never the firmware (which writes
 * no JSON). No heap: the text goes out through put() in pieces. MIT
 * licence, like the rest of this repository.
 */
#ifndef FM1_META_H_
#define FM1_META_H_

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* The format level the export is written at (its `lunar`). 1.1 (stage ED0,
 * 2026-10-06) added, for the advanced editor, each module's licence, its
 * page names and an audio effect's group, each parameter's knob detent
 * (`step`), the effect groups, the refusal codes with their words, the
 * telemetry block's layout and the export's id (`meta_id`). 1.2 (the editor's
 * v1 completion, 2026-10-07) added the modulation sources' groups (`group`
 * and `mod.source_groups`), the curves' points (`mod.curve_points`), a
 * refusal's repair (`fix`) and the matrix marks (`marks`). */
#define FM1_META_LUNAR "1.2"
/* The rate files are checked at and instance bytes are given at: the FM-1's. */
#define FM1_META_RATE 44118u
/* The bytes the engines, effects and modulation may take on the FM-1: the
 * virtual FM-1's FM1_APP_RAM_BUDGET (sim/web/src/fm1_app.h), which
 * tests/test_engine_metadata.py holds this to. */
#define FM1_META_RAM_BUDGET 387924u

typedef void (*fm1_meta_put_t)(void *ctx, const char *bytes, size_t n);

typedef struct fm1_meta_build {
  const char *by;               /* who writes it: "desktop", "simulator" */
  const char *version;          /* the build's version, "0.0.0" when unknown */
  const char *commit;           /* its commit, "0000000" when unknown */
  uint32_t rate;                /* FM1_META_RATE */
  uint32_t ram_budget;          /* FM1_META_RAM_BUDGET */
  int gpl;                      /* the GPL switch was on (FM1_GPL_MODS) */
} fm1_meta_build_t;

/* The build as this object was compiled: by "desktop", FM1_BUILD_VERSION
 * and FM1_BUILD_COMMIT when defined (else the placeholders), the FM-1's
 * rate and budget, and FM1_GPL_MODS. */
void fm1_meta_build_default(fm1_meta_build_t *b);

/* Writes the export through put(ctx, bytes, n), in pieces, ending with a
 * newline. Returns the bytes written. */
size_t fm1_meta_write(const fm1_meta_build_t *b, fm1_meta_put_t put, void *ctx);

/* The export's id, its `meta_id`: CRC-32 (zlib's) of the export as
 * fm1_meta_write writes it but without its `made` and `meta_id` members, so
 * two builds with the same registries, rate, budget and GPL switch have the
 * same id whoever wrote the file and when. The virtual FM-1's module
 * returns it (fm1w_meta_id), and an editor holding a static meta.json
 * checks the two agree before it trusts the file. Computed once, then
 * remembered: the first call writes the whole export into a CRC (a few
 * milliseconds), so a host asks it off its audio thread (the editor's
 * shadow Worker, stage ED1) or before audio starts. */
uint32_t fm1_meta_id(void);
/* The same for build b (its `made` is not counted). */
uint32_t fm1_meta_id_of(const fm1_meta_build_t *b);

#ifdef __cplusplus
}
#endif

#endif /* FM1_META_H_ */
