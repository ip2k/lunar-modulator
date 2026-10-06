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
 * from rose-pine/palette), the same tokens as the page's style.css. Pine is
 * left out on purpose: it fails as text and as a mark on this screen. */
#define RP_BASE FM1_RGB565(0x23, 0x21, 0x36)
#define RP_SURFACE FM1_RGB565(0x2a, 0x27, 0x3f)
#define RP_OVERLAY FM1_RGB565(0x39, 0x35, 0x52)
#define RP_MUTED FM1_RGB565(0x6e, 0x6a, 0x86)  /* marks on base only, never text */
#define RP_SUBTLE FM1_RGB565(0x90, 0x8c, 0xaa)
#define RP_TEXT FM1_RGB565(0xe0, 0xde, 0xf4)
#define RP_LOVE FM1_RGB565(0xeb, 0x6f, 0x92)
#define RP_GOLD FM1_RGB565(0xf6, 0xc1, 0x77)
#define RP_ROSE FM1_RGB565(0xea, 0x9a, 0x97)
#define RP_FOAM FM1_RGB565(0x9c, 0xcf, 0xd8)
#define RP_IRIS FM1_RGB565(0xc4, 0xa7, 0xe7)
#define RP_HIGHLIGHT_MED FM1_RGB565(0x44, 0x41, 0x5a)
#define RP_HIGHLIGHT_HIGH FM1_RGB565(0x56, 0x52, 0x6e)

/* Lunar Modulator's own hues, one for each sound (sim/web/PALETTE.md):
 * derived in OKLCH at Moon's accent lightness and chroma, in the hues Moon
 * leaves free, and each a fixed point of the RGB565 round trip, so the page
 * shows exactly what the screen does. tools/palette.py checks them. */
#define LM_NEBULA FM1_RGB565(0x63, 0xa6, 0xff)  /* blue */
#define LM_NOVA FM1_RGB565(0xef, 0x8a, 0x4a)    /* orange */
#define LM_AURORA FM1_RGB565(0x52, 0xd2, 0xa5)  /* green */
#define LM_COMET FM1_RGB565(0xc5, 0xdf, 0x7b)   /* yellow-green */

/* One meaning per colour: the semantic map (sim/web/PALETTE.md). Screen code
 * names the role, not the hue; tools/palette.py checks these against it. */
#define C_SELECT RP_IRIS    /* selection and the value being edited: bars, notes, the selected row, slot or chip */
#define C_HELD RP_GOLD      /* held and locked: held steps, locks and lanes, the grabbed module or slot, the count-in */
#define C_LIVE RP_FOAM      /* live signal: the scope, the meters, PLAY, trig ticks */
#define C_MOD RP_FOAM       /* modulation: a modulated label, its range bracket, MATRIX's sources */
#define C_REFUSE RP_LOVE    /* refusal, recording, over the limit */
#define C_CONTEXT RP_ROSE   /* the context line under the title bar and a list's title; never beside love */
#define C_HINT RP_TEXT      /* hints, and modulation's live tick */
#define C_LABEL RP_SUBTLE   /* labels, secondary text, idle states, a list's place */
#define C_SOUND_1 LM_NEBULA
#define C_SOUND_2 LM_NOVA
#define C_SOUND_3 LM_AURORA
#define C_SOUND_4 LM_COMET

/* A sound's colour, by its index (0 is S1); text outside S1-S4. The
 * S-number stays on screen beside it, for readers who cannot tell the
 * colours apart. */
static inline uint16_t fm1_sound_colour(int sound) {
  switch (sound) {
    case 0: return C_SOUND_1;
    case 1: return C_SOUND_2;
    case 2: return C_SOUND_3;
    case 3: return C_SOUND_4;
    default: return RP_TEXT;
  }
}

/* The names the screen code has used so far; they stay until each screen
 * moves to the roles above. */
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
/* A list popup (fm1_panel.h's window, fm1_list_rows of its face): the
 * list's title in the context colour and the chosen entry's place in MID on
 * the first line, then the entries from LIST_Y, the chosen one on the
 * selection bar. A LIST_MARK triangle between the title and the entries
 * says the list goes on above them, one under the entries that it goes on
 * below. Per face (audit D9), the entries' pitch and the bar round the
 * chosen one (above its box, and its height): MAIN 24 px, 3 above, 23 tall;
 * MID 18 px, 2 above, 17 tall; SMALL 16 px, 2 above, 15 tall. Each keeps
 * 4 px between entries' boxes, 3 px of bar above a capital, and the last
 * entry and its triangle above the bottom rule (LIST_BOTTOM). */
#define LIST_X 12                      /* title and entries: 6 px inside the highlight */
#define LIST_TITLE_Y (TITLE_H + 6)
#define LIST_MARK_W 11
#define LIST_MARK_H 6
#define LIST_MORE_Y (LIST_TITLE_Y + MID_LINE_H + 4)
#define LIST_Y (LIST_MORE_Y + LIST_MARK_H + 4)
#define LIST_BOTTOM (BOTTOM_Y - 2 - 4 - LIST_MARK_H - 4)   /* the last entry's box ends by here */
#define LIST_PITCH 24                  /* MAIN: 18 px text, the highlight 3 px above and 2 below */
#define LIST_PITCH_MID 18
#define LIST_PITCH_SMALL 16
/* Characters MAIN gives a label, a title-bar name and a popup line (the
 * MID and SMALL versions: fm1_look_fit). */
#define LABEL_CHARS 10
#define NAME_CHARS 16
#define POPUP_CHARS 18

/* L1's banner: a one-line confirmation of at most BANNER_CHARS in MAIN,
 * or of at most BANNER_CHARS_MID in MID (audit D9), over the page's bottom
 * BANNER_H px, between selection rules; the text 3 px inside them (MAIN)
 * or centred between them (MID). */
#define BANNER_H 28
#define BANNER_Y (BOTTOM_Y - BANNER_H)
#define BANNER_RULE 2
#define BANNER_TEXT_Y (BANNER_Y + BANNER_RULE + 3)
#define BANNER_TEXT_Y_MID (BANNER_Y + BANNER_RULE + (BANNER_H - 2 * BANNER_RULE - MID_LINE_H) / 2)
#define BANNER_CHARS POPUP_CHARS
#define BANNER_CHARS_MID 27

/* The context line under the title bar (audit Q4): what the page is about
 * (the model, the slot's effect, "Step 7") in C_CONTEXT, on the left, and
 * where it is ("1/8") or its role ("insert") in C_LABEL on the right, in
 * MID, so a page's rows start CONTEXT_NEXT_Y. */
#define CONTEXT_Y CONTENT_Y
#define CONTEXT_NEXT_Y (CONTEXT_Y + MID_LINE_H + 4)

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

/* How many characters of `font` fit between x and the right margin. */
static inline int fm1_look_fit(int x, fm1_tft_font_t font) { return fm1_tft_font_fit(RIGHT - x, font); }

/* The context line at y (audit Q4): `text` in C_CONTEXT on the left, in
 * MID, and `place` (NULL for none) in C_LABEL right-aligned, the text
 * taking what the place and the 4 px gap leave. Used by HOME (the model
 * and its place, "VA+Filter 1/8"), FX mode (the slot's effect and its
 * role); the sequencer's headings can take it too. */
void fm1_look_context(fm1_tft_t *t, int y, const char *text, const char *place);

/* An entry's full name (audit D9): where an engine, effect or list entry
 * only offers a short form ("PhaseDist", "Comp", "Studio S"), the name it
 * stands for, from the engine's own source; else `name` itself. For lists
 * and the context line, where a face has the room. */
const char *fm1_look_full_name(const char *name);

#ifdef __cplusplus
}
#endif

#endif /* FM1_LOOK_H_ */
