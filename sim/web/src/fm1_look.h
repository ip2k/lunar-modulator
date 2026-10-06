/* fm1_look.h -- the virtual FM-1 screen's palette, geometry and the few
 * drawing helpers every mode shares (defined in fm1_app.c): the app's own
 * screens and the sequencer's (fm1_seq_view.c) look alike from one place.
 *
 * C99. MIT licence, like the rest of this repository.
 */
#ifndef FM1_LOOK_H_
#define FM1_LOOK_H_

#include <stddef.h>
#include <stdint.h>

#include "fm1_engine.h"
#include "fm1_tft.h"

#ifdef __cplusplus
extern "C" {
#endif

/* Lunar Modulator's palette: Rosé Pine Moon (rosepinetheme.com, MIT; values
 * from rose-pine/palette), the same tokens as the page's style.css. */
#define RP_BASE FM1_RGB565(0x23, 0x21, 0x36)
#define RP_SURFACE FM1_RGB565(0x2a, 0x27, 0x3f)
#define RP_OVERLAY FM1_RGB565(0x39, 0x35, 0x52)
#define RP_SUBTLE FM1_RGB565(0x90, 0x8c, 0xaa)
#define RP_TEXT FM1_RGB565(0xe0, 0xde, 0xf4)
#define RP_LOVE FM1_RGB565(0xeb, 0x6f, 0x92)
#define RP_GOLD FM1_RGB565(0xf6, 0xc1, 0x77)
#define RP_FOAM FM1_RGB565(0x9c, 0xcf, 0xd8)
#define RP_IRIS FM1_RGB565(0xc4, 0xa7, 0xe7)
#define RP_HIGHLIGHT_MED FM1_RGB565(0x44, 0x41, 0x5a)

#define C_BG RP_BASE
#define C_TEXT RP_TEXT
#define C_DIM RP_SUBTLE
#define C_ACCENT RP_IRIS
#define C_MODEL RP_GOLD
#define C_BAR_BG RP_HIGHLIGHT_MED
#define C_TITLE_BG RP_OVERLAY
#define C_BOTTOM_BG RP_SURFACE
#define C_WARN RP_LOVE
#define C_SCOPE_BG RP_SURFACE
#define C_SCOPE RP_FOAM
#define C_POPUP_BG RP_SURFACE
#define C_METER RP_FOAM
#define C_PLAY RP_FOAM

/* Screen geometry: 2x text is 12 px a character and 18 px tall, so a line
 * holds 19 characters between the 6 px margins. Every label, value and bar
 * keeps FM1_APP_LAYOUT_GAP (4 px) from the next, and from the title and
 * bottom bars. */
#define SCALE 2
#define MARGIN 6
#define LINE_CHARS 19
#define RIGHT (FM1_TFT_W - MARGIN)
#define TITLE_H 24
#define BOTTOM_Y 216
#define CONTENT_Y (TITLE_H + 4)        /* the first line under the title bar */
#define ROW_PITCH 36
#define BAR_DY 22
#define BAR_H 7
#define LINE_PITCH 22                  /* plain text lines: 18 px and a 4 px gap */
#define POPUP_PITCH 26
/* A list popup (fm1_panel.h's FM1_LIST_ROWS window): the list's title and
 * the chosen entry's place on the first line, then the entries LIST_PITCH
 * apart from LIST_Y, the chosen one on the accent. A LIST_MARK triangle
 * between the title and the entries says the list goes on above them, one
 * under the entries that it goes on below. */
#define LIST_X 12                      /* title and entries: 6 px inside the highlight */
#define LIST_TITLE_Y (TITLE_H + 6)
#define LIST_MARK_W 11
#define LIST_MARK_H 6
#define LIST_MORE_Y (LIST_TITLE_Y + 18 + 4)
#define LIST_Y (LIST_MORE_Y + LIST_MARK_H + 4)
#define LIST_PITCH 24                  /* 18 px text, the highlight 3 px above and 2 below */
#define LABEL_CHARS 10
#define NAME_CHARS 16
#define POPUP_CHARS 18

/* The three faces (fm1_tft.h; audit D7), each line keeping the same 4 px
 * from the next: MAIN, the 5 x 9 at x2 above (18 px, 19 characters a line);
 * MID, Spleen 8 x 16 at x1 (a 14 px box, capitals 10 px, 28 characters a
 * line); SMALL, Spleen 6 x 12 at x1 (12 px, capitals 8 px, 38 characters a
 * line), the smallest the screen uses. A run's y is the top of its box. */
#define MAIN_LINE_H FM1_TFT_MAIN_H
#define MID_ADVANCE FM1_TFT_MID_ADVANCE
#define MID_LINE_H FM1_TFT_MID_H
#define MID_CAP_H FM1_TFT_MID_CAP_H
#define MID_LINE_PITCH (MID_LINE_H + 4)
#define MID_LINE_CHARS FM1_TFT_MID_FIT(RIGHT - MARGIN)
#define SMALL_ADVANCE FM1_TFT_SMALL_ADVANCE
#define SMALL_LINE_H FM1_TFT_SMALL_H
#define SMALL_CAP_H FM1_TFT_SMALL_CAP_H
#define SMALL_LINE_PITCH (SMALL_LINE_H + 4)
#define SMALL_LINE_CHARS FM1_TFT_SMALL_FIT(RIGHT - MARGIN)

/* A parameter's value as the screen shows it: an ENUM's entry name, else a
 * number with 0, 1 or 2 decimals by range. */
void fm1_look_value(const fm1_param_t *p, float v, char *buf, size_t size);

/* A value bar, logged as one graphic: from the minimum (or from zero when
 * the range spans it), or an ENUM's segment, in `fill` over the bar's
 * background. */
void fm1_look_bar(fm1_tft_t *t, int x, int y, int w, int h, const fm1_param_t *p, float v,
                  uint16_t fill);

/* The bar's fill alone, painted over what is there and not logged: a second
 * value inside a bar already drawn (a lock over its base, docs/15 S8). */
void fm1_look_fill(fm1_tft_t *t, int x, int y, int w, int h, const fm1_param_t *p, float v,
                   uint16_t fill);

/* One line: a dim label of at most LABEL_CHARS on the left and its value,
 * right-aligned, in `color`, in what is left of the line. */
void fm1_look_row(fm1_tft_t *t, int y, const char *label, const char *value, uint16_t color);

#ifdef __cplusplus
}
#endif

#endif /* FM1_LOOK_H_ */
