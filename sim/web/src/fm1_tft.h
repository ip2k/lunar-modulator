/* fm1_tft.h -- a 240 x 240 RGB565 frame buffer with the drawing the virtual
 * FM-1's screen needs: fills, bars, lines and 5 x 9 bitmap text.
 *
 * The FM-1 drives a 240 x 240 RGB565 TFT over SPI and flushes it in ten
 * 240 x 24 strips (docs/01 §3); this buffer is the whole screen, in the same
 * pixel format, so the page can show exactly what the panel would.
 *
 * Layout check: while `record` is set, every text run and every graphic
 * (bar, meter, line) is logged as a box. An opaque fill drawn later hides the
 * boxes it touches (a popup over the page). fm1_tft_check_layout() then
 * reports any box outside the screen and any two visible boxes closer than a
 * gap, so tests can prove that no label overlaps or crowds another.
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

#define FM1_RGB565(r, g, b) \
  ((uint16_t)((((r) & 0xF8) << 8) | (((g) & 0xFC) << 3) | ((b) >> 3)))

typedef enum { FM1_BOX_TEXT = 1, FM1_BOX_GRAPHIC = 2 } fm1_box_kind_t;

typedef struct fm1_tft_box {
  int16_t x, y, w, h;
  uint8_t kind;
  uint8_t hidden;
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
 * the fill calls that follow. */
void fm1_tft_graphic(fm1_tft_t *t, int x, int y, int w, int h);

/* Fill without logging, for drawing inside a box already logged. */
void fm1_tft_paint(fm1_tft_t *t, int x, int y, int w, int h, uint16_t color);

/* Width in pixels of the first max_chars characters of s at `scale`
 * (without the trailing spacing column). */
int fm1_tft_text_width(const char *s, int max_chars, int scale);

/* Draw at most max_chars characters of s with its top-left at (x, y);
 * characters outside 0x20..0x7E draw as '?'. Logged as one text box; a
 * string longer than max_chars counts as truncated. Returns the width
 * drawn. */
int fm1_tft_text(fm1_tft_t *t, int x, int y, const char *s, int max_chars, int scale,
                 uint16_t color);

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
