/* fm1_app.h -- the virtual FM-1: a small firmware application that runs the
 * engine platform (engines/include/fm1_engine.h) behind the FM-1's front
 * panel, for the browser simulator in sim/web and its native test harness.
 *
 * It owns one sound engine and two audio-effect slots, renders them in host
 * blocks of at most 64 frames through the host's bus limiter
 * (fm1_mix_limiter.h), and turns the panel's inputs into engine calls:
 *
 *   27 keys       F3..G5: note = key + 53 + 12 * octave + transpose
 *                 (the M-VAVE manual's formula), with OCT-/OCT+ and
 *                 ALGORITHM-while-OCT-held transpose as stock does it
 *   MASTER        output volume (a gain after the limiter)
 *   SELECT        page within the current mode; in FX mode, the effect slot
 *   PRESETS       the sound engine
 *   ALGORITHM     the engine's first list parameter (its model, shape or
 *                 patch); in FX mode, the effect in the selected slot
 *   KNOB1-4       the four parameters of the current page
 *   FX, SEL, GLO, HOME   FX mode (SEL grabs a slot so SELECT reorders it),
 *                 the global page, home. The other buttons say they are not
 *                 in the simulator yet.
 *
 * The screen is a 240 x 240 RGB565 frame buffer (fm1_tft.h) drawn with the
 * stock layout: a top bar with the sound's name, the mode's content, and a
 * bottom bar with page and mode, plus one-second popups.
 *
 * Instance memory lives in fixed arenas inside fm1_app_t (no heap), and the
 * screen shows how much of the stock layout's free RAM the chain would take.
 * Threads: none; the caller serialises every call (the browser runs it all on
 * the audio thread, between render calls, like events at block boundaries in
 * engines/host/render.cc).
 *
 * C99. MIT licence, like the rest of this repository.
 */
#ifndef FM1_APP_H_
#define FM1_APP_H_

#include <stddef.h>
#include <stdint.h>

#include "fm1_engine.h"
#include "fm1_mix_limiter.h"
#include "fm1_tft.h"

#ifdef __cplusplus
extern "C" {
#endif

#define FM1_APP_KEYS 27
#define FM1_APP_FIRST_NOTE 53          /* key 0 is F3 at octave 0, transpose 0 */
#define FM1_APP_BUTTONS 14
#define FM1_APP_LEDS (FM1_APP_KEYS + FM1_APP_BUTTONS)
#define FM1_APP_FX_SLOTS 2
#define FM1_APP_UNITS (1 + FM1_APP_FX_SLOTS)
#define FM1_APP_MAX_FRAMES 64
#define FM1_APP_MAX_PARAMS 32
#define FM1_APP_SCOPE 512

/* Pixels the screen keeps between any two labels, or a label and a bar
 * (fm1_tft_check_layout's gap in the tests). */
#define FM1_APP_LAYOUT_GAP 4

/* Arena sizes. The largest instances today are Shapes at 12 voices
 * (~206 KB) and PSX Verb (~134 KB); the arenas leave room for growth and
 * the screen reports the real total against the FM-1's budget below.
 * These 1 MiB of fixed arenas are a simulator convenience: on the FM-1
 * (578 KB of SRAM, about 379 KB free in the stock layout) the firmware
 * would size one arena to the chain it loads. */
#define FM1_APP_SOUND_BYTES (512u * 1024u)
#define FM1_APP_FX_BYTES (256u * 1024u)

/* RAM the stock layout leaves free (docs/11 §2, engines/README.md; part of
 * it is stock's heap, so this is an upper bound [inferred]). */
#define FM1_APP_RAM_BUDGET 387924u

#if defined(__GNUC__) || defined(__clang__)
#define FM1_APP_ALIGN16 __attribute__((aligned(16)))
#else
#define FM1_APP_ALIGN16
#endif

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

typedef enum { FM1_MODE_HOME = 0, FM1_MODE_FX, FM1_MODE_GLOBAL } fm1_app_mode_t;

typedef struct fm1_app_unit {
  const fm1_engine_t *e;         /* NULL when the slot is empty */
  void *self;
  int index;                     /* registry index, -1 when empty */
  size_t bytes;                  /* instance_size of the engine in it */
  unsigned char *mem;            /* this unit's arena */
  size_t cap;
  float value[FM1_APP_MAX_PARAMS];
} fm1_app_unit_t;

typedef struct fm1_app {
  fm1_host_t host;
  fm1_app_unit_t unit[FM1_APP_UNITS];   /* 0 sound, 1..2 effects in order */
  fm1_mix_limiter_t limiter;
  float master;                  /* MASTER position, 0..1 */
  float gain;                    /* master * master */
  float out[2 * FM1_APP_MAX_FRAMES];
  uint64_t frames;               /* rendered so far: the app's clock */

  int mode;                      /* fm1_app_mode_t */
  int page;                      /* sound page in HOME */
  int fx_slot, fx_page;          /* FX mode selection */
  int fx_grab;                   /* SEL pressed: SELECT moves the slot */
  int octave, transpose;
  uint8_t key_down[FM1_APP_KEYS];
  uint8_t key_note[FM1_APP_KEYS];      /* note each held key started */
  uint8_t note_count[128];             /* notes sounding, from any source */
  uint8_t button_down[FM1_APP_BUTTONS];

  char popup[3][24];
  int popup_lines, popup_mark;   /* popup_mark: highlighted line, or -1 */
  uint64_t popup_until;

  int dirty;                     /* screen content changed */
  uint64_t last_draw;            /* a->frames at the last redraw */
  float scope[FM1_APP_SCOPE];
  int scope_pos;
  float peak;                    /* largest output sample since the last redraw */
  float meter;                   /* level shown, with a falling decay */
  uint8_t led[FM1_APP_LEDS];     /* keys 0..26, then buttons in enum order */
  int leds_changed;

  fm1_tft_t tft;
  unsigned char sound_mem[FM1_APP_SOUND_BYTES] FM1_APP_ALIGN16;
  unsigned char fx_mem[FM1_APP_FX_SLOTS][FM1_APP_FX_BYTES] FM1_APP_ALIGN16;
} fm1_app_t;

/* Set up at `sample_rate` with 64-frame blocks: no engine loaded, MASTER at
 * full gain, octave and transpose 0, HOME mode. */
void fm1_app_init(fm1_app_t *a, float sample_rate);

/* The registry index of an engine id, or -1. */
int fm1_app_find(const char *id);

/* Load registry entry `index` into a unit (0 = sound, 1..2 = effects; -1
 * empties an effect slot). The instance memory is zeroed and the engine
 * created with its defaults, as fm1-render does. Changing the sound releases
 * its notes first. Returns 0, or -1 (wrong kind or unknown), -2 (does not
 * fit the arena; the unit keeps its engine) or -3 (the engine refused this
 * host, e.g. a Plaits-based one above 47,872 Hz; the unit's previous engine
 * is created again with its values). */
int fm1_app_select(fm1_app_t *a, int unit, int index);

/* The browser's starting chain: Macro, then Plate. If Macro refuses the
 * host's rate, the first sound that loads instead, with a popup saying why.
 * Returns 0, or the first fm1_app_select error. */
int fm1_app_default_chain(fm1_app_t *a);

/* Parameters of a unit, by index (fm1_app_param_index finds a name, case
 * insensitive; -1 if absent). Values clamp as fm1_param_clamp does. */
int fm1_app_param_index(const fm1_app_t *a, int unit, const char *name);
void fm1_app_set_param(fm1_app_t *a, int unit, int index, float value);
float fm1_app_get_param(const fm1_app_t *a, int unit, int index);

/* Notes as MIDI sends them (any source), pitch bend in semitones (finite,
 * clamped to +/-48), and a release of every sounding note. */
void fm1_app_note_on(fm1_app_t *a, int note, int velocity);
void fm1_app_note_off(fm1_app_t *a, int note);
void fm1_app_pitch_bend(fm1_app_t *a, float semitones);
void fm1_app_all_notes_off(fm1_app_t *a);

/* The panel: key 0..26 down/up with a velocity, a button down/up, an encoder
 * turned by `delta` detents, MASTER at 0..1 (popup when `show`). */
void fm1_app_key(fm1_app_t *a, int key, int down, int velocity);
void fm1_app_button(fm1_app_t *a, int button, int down);
void fm1_app_encoder(fm1_app_t *a, int encoder, int delta);
void fm1_app_master(fm1_app_t *a, float position, int show);

/* Render `frames` (at most 64; more are clamped) into a->out, stereo
 * interleaved, and return it. Sound, effects in order, bus limiter, MASTER. */
const float *fm1_app_render(fm1_app_t *a, uint32_t frames);

/* Redraw the screen if anything on it changed (or the scope is live, at most
 * once per `min_frames` of audio). Returns 1 when a->tft.px was redrawn. */
int fm1_app_draw(fm1_app_t *a, uint32_t min_frames);

/* Redraw now, logging boxes for fm1_tft_check_layout. */
void fm1_app_draw_checked(fm1_app_t *a);

/* Bytes of instance memory the current chain uses. */
size_t fm1_app_ram(const fm1_app_t *a);

/* A JSON description of every registered engine and effect (ids, names,
 * kinds, voices, credits, parameters with ranges, pages and list names).
 * Built once into a static buffer; NULL if it did not fit. */
const char *fm1_app_catalog_json(void);

#ifdef __cplusplus
}
#endif

#endif /* FM1_APP_H_ */
