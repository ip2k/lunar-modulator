/* fm1_tele.h -- the live block an editor reads (notes/2026-10-06-web-editor.md
 * §5, §12, decision ED11; stage ED0 sets its layout, ED1 fills it): one array
 * of floats, sent at most FM1_TELE_HZ times a second in a transferred
 * buffer, with only the rows the editor subscribes to filled in.
 *
 * The block is a run of sections. A section has rows, each row items (one
 * unnamed item when it names none) and each item fields, so field f of item
 * i of row r is the float at
 *
 *     offset + (r * items + i) * fields + f
 *
 * and row r is bit `mask + r` of the subscription mask (FM1_TELE_MASK_WORDS
 * words of 32 bits, bit k in word k / 32). A row the mask leaves out is not
 * written: its floats keep what the buffer held. The sections:
 *
 *   meters       per point (each sound's engine and inserts, the Mix, the
 *                master slots, the output after the limiter): peak and RMS
 *                over the frame, linear (1 is full scale);
 *   reduction    per effect slot and the output limiter: gain reduction in
 *                dB, 0 where the effect reduces nothing (all but Comp,
 *                Limiter and Squash, today), then gate (0 open, 1 closing,
 *                2 closed, NaN where no gate applies);
 *   voices       per voice the runtime tracks: its sound (1-4, 0 when free)
 *                and its MIDI note;
 *   outs         per rack position and output: the last value and the
 *                smallest and largest over the frame, so a fast LFO draws
 *                its envelope; in the output's own range (cv_bi -1..1,
 *                cv_uni 0..1, a gate 0 or 1);
 *   voice_outs   per rack position and output: each voice's last value,
 *                for a module that runs per voice;
 *   dests        per matrix slot: the effective value of what it reaches,
 *                in that parameter's unit, after every cable into it;
 *   voice_dests  per matrix slot: each voice's effective value, for a
 *                per-voice cable.
 *
 * Every count comes from the runtime's constants (fm1_mod.h) and the
 * virtual FM-1's four sounds, two inserts each and two master slots. The
 * metadata export (fm1_meta.h) writes the layout with every name, so an
 * editor reads the block by name. A new section or row goes at the end and
 * raises FM1_TELE_VERSION.
 *
 * Plain C99, constant data. MIT licence, like the rest of this repository.
 */
#ifndef FM1_TELE_H_
#define FM1_TELE_H_

#include <stddef.h>
#include <stdint.h>

#include "fm1_mod.h"

#ifdef __cplusplus
extern "C" {
#endif

#define FM1_TELE_VERSION 2u
#define FM1_TELE_HZ 30u                 /* blocks a second, at most */
#define FM1_TELE_SOUNDS 4u
#define FM1_TELE_INSERTS 2u             /* per sound */
#define FM1_TELE_MASTERS 2u             /* master slots */
/* Meter points: each sound's engine and inserts, then the Mix, the master
 * slots and the output. */
#define FM1_TELE_POINTS (FM1_TELE_SOUNDS * (1u + FM1_TELE_INSERTS) + 1u + FM1_TELE_MASTERS + 1u)
/* Effect slots with a reduction meter, and the output limiter. */
#define FM1_TELE_REDUCERS (FM1_TELE_SOUNDS * FM1_TELE_INSERTS + FM1_TELE_MASTERS + 1u)

enum {
  FM1_TELE_METERS = 0,
  FM1_TELE_REDUCTION,
  FM1_TELE_VOICES,
  FM1_TELE_OUTS,
  FM1_TELE_VOICE_OUTS,
  FM1_TELE_DESTS,
  FM1_TELE_VOICE_DESTS,
  FM1_TELE_SECTIONS
};

typedef struct fm1_tele_section {
  const char *name;             /* "meters" */
  const char *unit;             /* the fields' unit: a parameter unit's name
                                   ("none", "db", "semi"), "port" (the output's
                                   own range) or "param" (the destination's unit) */
  uint16_t offset;              /* floats from the block's start */
  uint16_t rows, items, fields; /* items 1 when a row names none */
  uint16_t mask;                /* the subscription bit of row 0 */
} fm1_tele_section_t;

/* Section s (FM1_TELE_*), or NULL. */
const fm1_tele_section_t *fm1_tele_section(unsigned s);
/* Floats in the whole block, and the mask's bits. */
unsigned fm1_tele_floats(void);
unsigned fm1_tele_mask_bits(void);
#define FM1_TELE_MASK_WORDS 4u          /* enough for fm1_tele_mask_bits() */

/* Names, written into buf (at most n bytes with the 0): row r of section s
 * ("snd1.fx2", "pos3", "slot12", "v4"), its item i ("out2", "v4"; "" when
 * the rows name no items) and its field f ("peak", "value", "v4"). Each
 * returns buf, or "" for an index out of range. */
const char *fm1_tele_row_name(unsigned s, unsigned r, char *buf, size_t n);
const char *fm1_tele_item_name(unsigned s, unsigned i, char *buf, size_t n);
const char *fm1_tele_field_name(unsigned s, unsigned f, char *buf, size_t n);

#ifdef __cplusplus
}
#endif

#endif /* FM1_TELE_H_ */
