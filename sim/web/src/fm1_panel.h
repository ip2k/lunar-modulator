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

/* FM1_MODE_SEQ is reachable only with the lab switch on (fm1_app_set_lab). */
typedef enum {
  FM1_MODE_HOME = 0, FM1_MODE_FX, FM1_MODE_GLOBAL, FM1_MODE_SEQ
} fm1_app_mode_t;

#ifdef __cplusplus
}
#endif

#endif /* FM1_PANEL_H_ */
