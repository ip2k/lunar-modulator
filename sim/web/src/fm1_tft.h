/* fm1_tft.h -- a 240 x 240 RGB565 frame buffer with the drawing the virtual
 * FM-1's screen needs: fills, bars, lines and bitmap text in three faces
 * (below: the hand-made 5 x 9 at x2, Spleen 8 x 16 and Spleen 6 x 12).
 *
 * The FM-1 drives a 240 x 240 RGB565 TFT over SPI and flushes it in ten
 * 240 x 24 strips (docs/01 §3); this buffer is the whole screen, in the same
 * pixel format, so the page can show exactly what the panel would.
 *
 * Layout check: while `record` is set, every text run and every graphic
 * (bar, meter, line) is logged as a box. A text run's box is the rows and
 * columns its face's characters can paint, whichever characters it holds.
 * An opaque fill drawn later hides the boxes it touches (a popup over the
 * page). fm1_tft_check_layout() then reports any box outside the screen and
 * any two visible boxes closer than a gap, so tests can prove that no label
 * overlaps or crowds another. The rule is the same for every face: only the
 * boxes count.
 *
 * C99, no heap. MIT licence, like the rest of this repository.
 */
#ifndef FM1_TFT_H_
#define FM1_TFT_H_

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define FM1_TFT_W 240
#define FM1_TFT_H 240
#define FM1_TFT_MAX_BOXES 96

/* Text cells: 5 x 9 glyphs plus one column of spacing, times the scale. */
#define FM1_TFT_ADVANCE(scale) (6 * (scale))
#define FM1_TFT_TEXT_H(scale) (9 * (scale))

/* The text faces (notes/2026-10-06-ui-audit.md, D7). MAIN is the hand-made
 * 5 x 9 at x2 (tools/font5x9.txt), every screen's face until then; MID and
 * SMALL are Spleen 8 x 16 and 6 x 12 at x1 (Frederic Cambus, BSD 2-Clause:
 * sim/web/third_party/spleen/), for dense screens. SMALL is the smallest the
 * screen uses. */
typedef enum fm1_tft_font {
  FM1_TFT_MAIN = 0,
  FM1_TFT_MID = 1,
  FM1_TFT_SMALL = 2
} fm1_tft_font_t;
#define FM1_TFT_FONTS 3

/* Each face's metrics, in pixels:
 *   ADVANCE   from one character to the next;
 *   H         a run's box height: every row a character can paint (the
 *             5 x 9's descenders included; Spleen 8 x 16 less its top and
 *             bottom rows, which no character here paints), so a run's y
 *             is the top of its box;
 *   INK_W     the last character's share of the box: a run of n characters
 *             is (n - 1) * ADVANCE + INK_W wide (the 5 x 9 leaves its
 *             spacing column out; some of Spleen's reach the cell's last
 *             column: 8 x 16's '*' and 'T', 6 x 12's '&', '*' and '}');
 *   CAP_H     a capital's height (capitals start BASELINE - CAP_H rows
 *             below the box's top);
 *   BASELINE  rows of the box above the baseline.
 * fm1_tft.c checks them against the generated tables at compile time. */
#define FM1_TFT_MAIN_ADVANCE 12
#define FM1_TFT_MAIN_H 18
#define FM1_TFT_MAIN_INK_W 10
#define FM1_TFT_MAIN_CAP_H 14
#define FM1_TFT_MAIN_BASELINE 14
#define FM1_TFT_MID_ADVANCE 8
#define FM1_TFT_MID_H 14
#define FM1_TFT_MID_INK_W 8
#define FM1_TFT_MID_CAP_H 10
#define FM1_TFT_MID_BASELINE 11
#define FM1_TFT_SMALL_ADVANCE 6
#define FM1_TFT_SMALL_H 12
#define FM1_TFT_SMALL_INK_W 6
#define FM1_TFT_SMALL_CAP_H 8
#define FM1_TFT_SMALL_BASELINE 9

/* A run of n characters' width (0 for none), and how many characters fit
 * in w pixels, for a face's ADVANCE and INK_W; then per face. */
#define FM1_TFT_RUN_W(adv, ink_w, n) ((n) > 0 ? ((n) - 1) * (adv) + (ink_w) : 0)
#define FM1_TFT_FIT(adv, ink_w, w) ((w) < (ink_w) ? 0 : ((w) - (ink_w)) / (adv) + 1)
#define FM1_TFT_MAIN_W(n) FM1_TFT_RUN_W(FM1_TFT_MAIN_ADVANCE, FM1_TFT_MAIN_INK_W, n)
#define FM1_TFT_MID_W(n) FM1_TFT_RUN_W(FM1_TFT_MID_ADVANCE, FM1_TFT_MID_INK_W, n)
#define FM1_TFT_SMALL_W(n) FM1_TFT_RUN_W(FM1_TFT_SMALL_ADVANCE, FM1_TFT_SMALL_INK_W, n)
#define FM1_TFT_MAIN_FIT(w) FM1_TFT_FIT(FM1_TFT_MAIN_ADVANCE, FM1_TFT_MAIN_INK_W, w)
#define FM1_TFT_MID_FIT(w) FM1_TFT_FIT(FM1_TFT_MID_ADVANCE, FM1_TFT_MID_INK_W, w)
#define FM1_TFT_SMALL_FIT(w) FM1_TFT_FIT(FM1_TFT_SMALL_ADVANCE, FM1_TFT_SMALL_INK_W, w)

typedef struct fm1_tft_metrics {
  uint8_t advance, height, ink_w, cap_h, baseline;
} fm1_tft_metrics_t;

/* One colour span of a multi-colour run (fm1_tft_span_text). */
typedef struct fm1_tft_span {
  const char *s;              /* NULL draws nothing */
  uint16_t color;
} fm1_tft_span_t;

#define FM1_RGB565(r, g, b) \
  ((uint16_t)((((r) & 0xF8) << 8) | (((g) & 0xFC) << 3) | ((b) >> 3)))

typedef enum { FM1_BOX_TEXT = 1, FM1_BOX_GRAPHIC = 2 } fm1_box_kind_t;

typedef struct fm1_tft_box {
  int16_t x, y, w, h;
  uint8_t kind;
  uint8_t hidden;
  uint8_t font;               /* a text box's face (the 5 x 9 at any scale is MAIN) */
} fm1_tft_box_t;

typedef struct fm1_tft {
  uint16_t px[FM1_TFT_W * FM1_TFT_H];
  int record;                 /* log boxes for fm1_tft_check_layout */
  int n_boxes;
  int overflow;               /* more boxes than FM1_TFT_MAX_BOXES */
  int truncated;              /* text runs cut short by max_chars */
  fm1_tft_box_t boxes[FM1_TFT_MAX_BOXES];
} fm1_tft_t;

/* Start a frame: clear to `color` and forget the logged boxes. */
void fm1_tft_begin(fm1_tft_t *t, uint16_t color);

/* Opaque background fill; hides logged boxes it touches. */
void fm1_tft_fill(fm1_tft_t *t, int x, int y, int w, int h, uint16_t color);

/* One-pixel outline; a background element, not logged. */
void fm1_tft_frame(fm1_tft_t *t, int x, int y, int w, int h, uint16_t color);

/* A graphic (bar, meter, trace) inside the given box: logged, then drawn by
 * the fill or pixel calls that follow. */
void fm1_tft_graphic(fm1_tft_t *t, int x, int y, int w, int h);

/* Fill without logging, for drawing inside a box already logged. */
void fm1_tft_paint(fm1_tft_t *t, int x, int y, int w, int h, uint16_t color);
void fm1_tft_pixel(fm1_tft_t *t, int x, int y, uint16_t color);

/* Width in pixels of the first max_chars characters of s at `scale`
 * (without the trailing spacing column). */
int fm1_tft_text_width(const char *s, int max_chars, int scale);

/* Draw at most max_chars characters of s with its top-left at (x, y);
 * characters outside 0x20..0x7E draw as '?'. Logged as one text box; a
 * string longer than max_chars counts as truncated. Returns the width
 * drawn. */
int fm1_tft_text(fm1_tft_t *t, int x, int y, const char *s, int max_chars, int scale,
                 uint16_t color);

/* The faces (FM1_TFT_MAIN, _MID, _SMALL; any other value is MAIN). */
const fm1_tft_metrics_t *fm1_tft_metrics(fm1_tft_font_t font);

/* Width in pixels of the first max_chars characters of s in `font`: its
 * box's width, 0 for none. */
int fm1_tft_font_width(const char *s, int max_chars, fm1_tft_font_t font);

/* How many characters of `font` fit in w pixels. */
int fm1_tft_font_fit(int w, fm1_tft_font_t font);

/* fm1_tft_text in a face: at most max_chars characters of s, the top-left
 * of its box at (x, y); characters outside 0x20..0x7E draw as '?'. Logged
 * as one text box; a string longer than max_chars counts as truncated.
 * Returns the width drawn. FM1_TFT_MAIN draws what fm1_tft_text draws at
 * scale 2, pixel for pixel and box for box. */
int fm1_tft_font_text(fm1_tft_t *t, int x, int y, const char *s, int max_chars,
                      fm1_tft_font_t font, uint16_t color);

/* A multi-colour run: the spans' strings one after another, each in its
 * own colour, as if they were one string (at most max_chars characters in
 * all, a span cut short counting as truncated text). Logged as ONE text
 * box, so fields set apart by colour alone (MATRIX's source, mark and
 * destination: audit L2) keep the layout rules of one run. Returns the
 * width drawn; fm1_tft_span_width measures it. */
int fm1_tft_span_text(fm1_tft_t *t, int x, int y, const fm1_tft_span_t *spans, int n_spans,
                      int max_chars, fm1_tft_font_t font);
int fm1_tft_span_width(const fm1_tft_span_t *spans, int n_spans, int max_chars,
                       fm1_tft_font_t font);
/* The same run with lead[k] more pixels before span k (lead NULL for
 * none): a narrow gap inside one run where a space would cost a whole
 * character, as MATRIX's state mark keeps from the source and the
 * destination. A lead counts only before a span that draws a character
 * and is not the run's first; the box and the width include the leads. */
int fm1_tft_span_text_lead(fm1_tft_t *t, int x, int y, const fm1_tft_span_t *spans,
                           const uint8_t *lead, int n_spans, int max_chars, fm1_tft_font_t font);
int fm1_tft_span_width_lead(const fm1_tft_span_t *spans, const uint8_t *lead, int n_spans,
                            int max_chars, fm1_tft_font_t font);

/* Count layout faults among visible boxes: a box not wholly on screen, two
 * text boxes, or a text box and a graphic, closer than `gap` pixels (or
 * overlapping), and each text run cut short by its max_chars. Graphics may
 * touch each other. Writes up to max_report descriptions of the faults
 * (pairs of box indices; -1 -1 for too many boxes, -2 -2 for truncated
 * text) when report is not NULL. */
int fm1_tft_check_layout(const fm1_tft_t *t, int gap, int *report, int max_report);

#ifdef __cplusplus
}
#endif

#endif /* FM1_TFT_H_ */
