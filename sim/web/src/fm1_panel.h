/* fm1_panel.h -- the virtual FM-1's front panel as the firmware sees it: the
 * keys, the 14 buttons in the M-VAVE manual's order, the seven encoders and
 * the screen's modes. Shared by the app (fm1_app.h) and the sequencer's UI
 * (fm1_seq_ui.h), which reads the same edges.
 *
 * C99. MIT licence, like the rest of this repository.
 */
#ifndef FM1_PANEL_H_
#define FM1_PANEL_H_

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define FM1_APP_KEYS 27
#define FM1_APP_FIRST_NOTE 53          /* key 0 is F3 at octave 0, transpose 0 */
#define FM1_APP_BUTTONS 14
#define FM1_APP_WHITE_KEYS 16

/* Key index (0..26, semitones above F3) of white key n (0..15), numbered
 * from the left as the manual numbers steps. */
static inline int fm1_white_key(int n) {
  static const uint8_t k[FM1_APP_WHITE_KEYS] = { 0, 2, 4, 6, 7, 9, 11, 12, 14, 16, 18, 19,
                                                 21, 23, 24, 26 };
  return n >= 0 && n < FM1_APP_WHITE_KEYS ? k[n] : -1;
}

typedef enum {
  FM1_BTN_OCT_DOWN = 0, FM1_BTN_OCT_UP,
  FM1_BTN_FX, FM1_BTN_SEL, FM1_BTN_ENV, FM1_BTN_LFO, FM1_BTN_EDIT, FM1_BTN_GLO,
  FM1_BTN_HOME, FM1_BTN_SAVE, FM1_BTN_ARP, FM1_BTN_SEQ, FM1_BTN_PLAY, FM1_BTN_REC
} fm1_app_button_t;

typedef enum {
  FM1_ENC_SELECT = 0, FM1_ENC_PRESETS, FM1_ENC_ALGORITHM,
  FM1_ENC_KNOB1, FM1_ENC_KNOB2, FM1_ENC_KNOB3, FM1_ENC_KNOB4,
  FM1_ENC_COUNT
} fm1_app_encoder_t;

/* A list popup (PRESETS, ALGORITHM, the modulation pickers, Capture's
 * tempos, a knob on a list parameter) shows as many entries of its list at
 * a time as the screen's middle holds under the list's title, in the face
 * its list is drawn in (audit D9, notes/2026-10-06-ui-audit.md):
 *
 *   face            entries  characters an entry
 *   FM1_LIST_MAIN   6        18   the 5 x 9 at x2, 24 px apart
 *   FM1_LIST_MID    8        27   Spleen 8 x 16, 18 px apart
 *   FM1_LIST_SMALL  9        36   Spleen 6 x 12, 16 px apart
 *
 * (the values are fm1_tft.h's FM1_TFT_MAIN, _MID and _SMALL; fm1_app.c
 * checks the rows and characters against the geometry in fm1_look.h).
 * FM1_LIST_ROWS is MAIN's six, the most a list showed until then. A list
 * of the app's own picks its face; a modulation picker's window (which
 * fm1_mod_ui fills, fm1_mod_ui_say_t) is drawn in the face named below for
 * it, so the code that fills it takes fm1_list_rows and fm1_list_chars of
 * that face. Every entry fits FM1_LIST_ENTRY bytes with its NUL. */
#define FM1_LIST_MAIN 0
#define FM1_LIST_MID 1
#define FM1_LIST_SMALL 2
#define FM1_LIST_ROWS 6
#define FM1_LIST_MAX_ROWS 9
#define FM1_LIST_ENTRY 40
#define FM1_LIST_FACE_KIND FM1_LIST_MID   /* RACK's kind picker: 17 kinds */
#define FM1_LIST_FACE_DEST FM1_LIST_MID   /* MATRIX's destination picker: full names fit 27 */

static inline int fm1_list_rows(int face) {
  return face == FM1_LIST_MID ? 8 : (face == FM1_LIST_SMALL ? 9 : FM1_LIST_ROWS);
}

static inline int fm1_list_chars(int face) {
  return face == FM1_LIST_MID ? 27 : (face == FM1_LIST_SMALL ? 36 : 18);
}

/* The first entry such a window shows with entry `sel` of `total` chosen:
 * the choice on the third row where it can be, so two entries before it
 * and three after it show, and the window never runs past either end. */
static inline int fm1_list_first(int total, int sel, int rows) {
  int first = sel - (rows - 1) / 2;
  if (first > total - rows) first = total - rows;
  return first < 0 ? 0 : first;
}

/* FM1_MODE_SEQ (from SEQ) and the modulation pages (docs/16 §5, stage MG3:
 * RACK from LFO or ENV, MATRIX from EDIT, CHAIN from SEL in MATRIX). */
typedef enum {
  FM1_MODE_HOME = 0, FM1_MODE_FX, FM1_MODE_GLOBAL, FM1_MODE_SEQ,
  FM1_MODE_RACK, FM1_MODE_MATRIX, FM1_MODE_CHAIN
} fm1_app_mode_t;

#ifdef __cplusplus
}
#endif

#endif /* FM1_PANEL_H_ */
