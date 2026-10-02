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
 * It hosts the sequencer core (engines/include/fm1_seq.h) through the shared
 * host bridge (fm1_seq_host.h), as fm1-render does: script lines and typed
 * commands at block starts, then each block's events, with the sound
 * engine's render split at every note and lock of a track routed to it.
 * fm1_app_seq_* below drive it; the harness and the parity test play scripts
 * and sets through it.
 *
 * The lab switch (fm1_app_set_lab, off at init) puts the sequencer on the
 * panel (docs/15 S3), for the page's lab preview and the tests while the
 * public page hides it until step entry and recording work (owner decision
 * O24, 2026-10-02):
 *   SEQ           SEQ mode, the Track view (fm1_seq_view.h); HOME, FX and
 *                 GLO leave it; the keys still play the sound
 *   PLAY/STOP     `play` or `stop`, in every mode, as a typed command
 *                 through fm1_seq_ui.h and fm1_app_seq_cmd; its LED is on
 *                 while the transport runs, SEQ's in SEQ mode, and in SEQ
 *                 mode the white keys show the bar's steps and the playhead
 * and modulation (docs/16 stage MG3; fm1_mod_ui.h has the pages): the app
 * hosts a runtime (fm1_mod.h) on the same bridge, as fm1-render --mod does,
 * starting from the default rack (LFO1, LFO2, ENV1, ENV2, Chance) and two
 * cables, KEY into each Envelope's GATE, so the envelopes follow every note
 * on the sound
 *   LFO, ENV      a tap opens RACK at the LFOs or the Envelopes; held while
 *                 KNOB1-4 turn on HOME, FX or RACK, a cable from the
 *                 selected one to that knob's parameter (the gesture)
 *   EDIT          MATRIX, the slot list; SEL there opens CHAIN
 *   pages         a routed parameter shows its marker, bracket and live tick
 * With the switch off, SEQ, PLAY/STOP, ENV, LFO and EDIT say they are not in
 * the simulator yet, as REC still does with it on, and no runtime runs: the
 * public page is what it was.
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
#include "fm1_mod.h"
#include "fm1_mod_host.h"
#include "fm1_mod_ui.h"
#include "fm1_panel.h"
#include "fm1_seq.h"
#include "fm1_seq_host.h"
#include "fm1_seq_ui.h"
#include "fm1_tft.h"

#ifdef __cplusplus
extern "C" {
#endif

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

/* The sequencer (docs/15 §2.5 and §2.6). Its instance takes the FM-1's
 * default limits (fm1_seq_limits_default) for FM1_APP_SEQ_TRACKS tracks:
 * 31,880 B at 8 tracks, Capture included, the same on 32- and 64-bit
 * builds. Every block's commands and events share one buffer of
 * FM1_APP_SEQ_EVENTS (3,072 B). With the pending command record (240 B) and
 * the UI state (fm1_seq_ui_t, at most 1,024 B) that is 36,216 B of the
 * sequencer's 36,864 B budget, half of docs/13 §5's 72 KiB. The track count
 * is the owner's decision O3 (docs/15 §8, answered 2026-10-02): 8, the
 * count the firmware will use (4 would have left room for docs/13's undo
 * ring). */
#define FM1_APP_SEQ_TRACKS 8
#define FM1_APP_SEQ_BYTES 32768u      /* the instance's arena */
#define FM1_APP_SEQ_EVENTS 256u       /* the block's event buffer, in events */
#define FM1_APP_SEQ_BUDGET 36864u     /* the sequencer's share of FM-1 RAM */
#define FM1_APP_SEQ_UI_BYTES 1024u    /* the SEQ mode UI state's bound */

/* Modulation (docs/16 MG3): the runtime's memory (fm1_mod_size() is 20,016 B
 * on 32- and 64-bit builds, the 8 KB arena included) and the room for a
 * block's writes to the effects and AMP (at most 65 a tick, two ticks a
 * 64-frame block). The runtime counts in the RAM figure while it runs. */
#define FM1_APP_MOD_BYTES 20480u
#define FM1_APP_MOD_WRITES 192u
#define FM1_APP_MOD_SEED 1u           /* the lab's runtime; a log records it */

/* What fm1_app_seq_cmd did with a command. */
enum {
  FM1_APP_SEQ_REFUSED = -1,   /* no sequencer */
  FM1_APP_SEQ_BUSY = 0,       /* a held command waits already: send it again
                                 after the next fm1_app_render */
  FM1_APP_SEQ_APPLIED = 1,    /* applied now: its events lead the next block */
  FM1_APP_SEQ_HELD = 2        /* too little room this block: held, and applied
                                 at the start of the next block, before any
                                 other sequencer input */
};

#if defined(__GNUC__) || defined(__clang__)
#define FM1_APP_ALIGN16 __attribute__((aligned(16)))
#else
#define FM1_APP_ALIGN16
#endif

typedef struct fm1_app_unit {
  const fm1_engine_t *e;         /* NULL when the slot is empty */
  void *self;
  int index;                     /* registry index, -1 when empty */
  size_t bytes;                  /* instance_size of the engine in it */
  unsigned char *mem;            /* this unit's arena */
  size_t cap;
  float value[FM1_APP_MAX_PARAMS];
} fm1_app_unit_t;

/* A tick's write to an effect or to AMP, at its frame in the block. */
typedef struct fm1_app_mod_write {
  uint32_t frame;
  fm1_mod_write_t w;
} fm1_app_mod_write_t;

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

  /* The sequencer. fm1_app_init zeroes these; its memory is after tft. */
  fm1_seq_t *seq;                /* in seq_mem; NULL only if it did not fit */
  fm1_seq_limits_t seq_lim;
  fm1_seq_host_t seq_host;       /* the bridge over seq and seq_ev */
  uint32_t seq_last_n;           /* events the last block held (seq_ev[0..)) */
  uint8_t seq_note_count[128];   /* sequencer notes sounding on unit 0 */
  float lock_shown[FM1_APP_MAX_PARAMS];   /* the last lock of each parameter, */
  uint32_t lock_mask;                     /* for the screen; never in value[] */
  int seq_pending;               /* seq_pend waits for room (event-room rule) */
  fm1_seq_cmd_t seq_pend;
  uint64_t seq_dropped_before;   /* events dropped by instances since replaced */
  uint64_t seq_held, seq_busy;   /* commands held for room, and refused */
  uint32_t seq_gen;              /* bumped by every sequencer input */
  /* Native-harness hook: every typed command as it is applied, with the
   * frame of the block it leads. NULL in the browser. */
  void (*on_cmd)(void *ctx, uint64_t frame, const fm1_seq_cmd_t *c);
  void *on_cmd_ctx;

  /* The sequencer on the panel, behind the lab switch. */
  int lab;
  fm1_seq_ui_t ui;

  /* Modulation (docs/16 MG3). mod is NULL while the lab switch is off (and
   * until fm1_app_mod_reset); its memory is after tft. */
  fm1_mod_t *mod;
  fm1_mod_glue_t mod_glue;       /* the bridge's control-rate hook */
  fm1_mod_ramp_t mod_amp;        /* HOST AMP, before the limiter */
  int mod_amp_used;
  uint32_t mod_nwr;              /* this block's writes to the effects and AMP */
  fm1_app_mod_write_t mod_wr[FM1_APP_MOD_WRITES];
  uint32_t mod_seed;             /* the runtime's seed, for a log */
  float bend;                    /* the pitch bend: HOST PITCH's base */
  fm1_mod_ui_t mui;              /* RACK, MATRIX, CHAIN and the gesture */
  /* Native-harness hook: every modulation edit as a line of fm1-render's
   * --mod format (engines/host/mod_script.h), with the frame of the block
   * it leads. NULL in the browser. */
  void (*on_mod)(void *ctx, uint64_t frame, const char *line);
  void *on_mod_ctx;

  fm1_tft_t tft;
  unsigned char sound_mem[FM1_APP_SOUND_BYTES] FM1_APP_ALIGN16;
  unsigned char fx_mem[FM1_APP_FX_SLOTS][FM1_APP_FX_BYTES] FM1_APP_ALIGN16;
  unsigned char seq_mem[FM1_APP_SEQ_BYTES] FM1_APP_ALIGN16;
  fm1_seq_ev_t seq_ev[FM1_APP_SEQ_EVENTS];
  unsigned char mod_mem[FM1_APP_MOD_BYTES] FM1_APP_ALIGN16;
} fm1_app_t;

/* Set up at `sample_rate` with 64-frame blocks: no engine loaded, MASTER at
 * full gain, octave and transpose 0, HOME mode, and a sequencer of
 * FM1_APP_SEQ_TRACKS tracks at lrintf(sample_rate) (as fm1-render creates
 * it), stopped and empty, every track on its default USB-MIDI route. */
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
 * Then the sequencer's default route (fm1_app_seq_default_route) and, with
 * the lab switch on, the demo pattern (fm1_app_seq_demo). Returns 0, or the
 * first fm1_app_select error. */
int fm1_app_default_chain(fm1_app_t *a);

/* The lab switch: on, the sequencer is on the panel (SEQ mode, PLAY/STOP,
 * their LEDs) and modulation runs (a new runtime with the default rack and
 * its two cables; RACK, MATRIX, CHAIN); off (as fm1_app_init leaves it),
 * those buttons say they are not in the simulator yet, nothing of the
 * sequencer shows and the runtime is gone, every parameter back at its
 * base. Turning it off in SEQ mode or a modulation page goes back to HOME. */
void fm1_app_set_lab(fm1_app_t *a, int on);

/* The demo pattern (owner decision O4): a one-bar, 16-step figure on track
 * 1 (index 0), as one line of verbs; the browser's start chain applies it
 * with the lab switch on, and nothing else does, so the tests and the parity
 * runs start empty. 1 if it went in whole. */
int fm1_app_seq_demo(fm1_app_t *a);
extern const char fm1_app_demo_pattern[];

/* Parameters of a unit, by index (fm1_app_param_index finds a name, case
 * insensitive; -1 if absent). Values clamp as fm1_param_clamp does. */
int fm1_app_param_index(const fm1_app_t *a, int unit, const char *name);
void fm1_app_set_param(fm1_app_t *a, int unit, int index, float value);
float fm1_app_get_param(const fm1_app_t *a, int unit, int index);

/* Notes as MIDI sends them (any source), pitch bend in semitones (finite,
 * clamped to +/-48), and a release of every sounding note: the sequencer's
 * too (a later sequencer note-off for one of them changes nothing). */
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
 * interleaved, and return it: a held sequencer command if it now fits, the
 * sequencer's block (fm1_seq_host_advance), the sound split at its events
 * (fm1_seq_host_dispatch; with no sound engine the events are dropped, as
 * in fm1-render), effects in order, bus limiter, MASTER. */
const float *fm1_app_render(fm1_app_t *a, uint32_t frames);

/* ---- The sequencer ------------------------------------------------------
 * Input applies at the start of the coming block, as in fm1-render: the
 * caller (the worklet between render calls, the harness before each block)
 * sends it, then renders. Every input obeys the event-room rule
 * (fm1_seq_host.h): an op is applied only while the buffer has room for the
 * most it could cause plus the block's own minimum. */

/* One line of a verb script (Movy ops separated by ';', or "rt F8|FA|FB|FC"),
 * applied op by op, as fm1_seq_apply_line would. Returns the bytes consumed:
 * `len` when the whole line went in, less when the room ran out before an
 * op (the caller sends the rest, from there, after the next render, before
 * anything newer), 0 while a held command waits. A line with a leading
 * "#<n>;" batch tag goes in whole or not at all (the tag is the core's). */
size_t fm1_app_seq_line(fm1_app_t *a, const char *ops, size_t len);

/* One typed command (the UI's): FM1_APP_SEQ_APPLIED, _HELD, _BUSY or
 * _REFUSED. */
int fm1_app_seq_cmd(fm1_app_t *a, const fm1_seq_cmd_t *c);

/* Live notes for recording and Capture (velocity 0 releases), at frame 0. */
void fm1_app_seq_note_in(fm1_app_t *a, int track, int pitch, int velocity);

/* A new, empty instance of `tracks` tracks (1..FM1_APP_SEQ_TRACKS): the
 * sequencer's notes sounding on the engine are released first, a held
 * command and the queued events are dropped. Routes are the core's
 * defaults afterwards. 0, or -1 for a bad count. */
int fm1_app_seq_reset(fm1_app_t *a, int tracks);

/* Replaces the set from `movy1` text, after releasing the sequencer's notes
 * as fm1_app_seq_reset does. Every route is back on USB-MIDI channel t+1
 * unless the set routes it (`rt` lines). 1 if the text was a set, else 0
 * (nothing changed). */
int fm1_app_seq_import(fm1_app_t *a, const char *txt, size_t len);

/* Routes a track to the sound engine (kind FM1_SEQ_ROUTE_ENGINE, index 0)
 * or a USB-MIDI channel 1..16 (logged only: the simulator has no MIDI
 * out). 1 if accepted. */
int fm1_app_seq_route(fm1_app_t *a, int track, int kind, int index);

/* The default-route rule, fm1-render's (fm1_seq_default_route): track 0
 * plays the sound engine when one is loaded and no track is routed. A host
 * applies it after init, reset or an import unless it routes tracks itself.
 * Returns 1 when it routed track 0. */
int fm1_app_seq_default_route(fm1_app_t *a);

/* The instance (for reading state), the last block's events, in emission
 * order (valid until the next sequencer input or render), and the events
 * dropped since init: nonzero means a note may have hung. */
const fm1_seq_t *fm1_app_seq(const fm1_app_t *a);
const fm1_seq_ev_t *fm1_app_seq_events(const fm1_app_t *a, uint32_t *n);
uint64_t fm1_app_seq_dropped(const fm1_app_t *a);

/* ---- Modulation (docs/16 MG3) --------------------------------------------
 * The runtime's state changes only through these and the panel, and every
 * change reaches on_mod as a script line, so a native run that logs them
 * replays through fm1-render --mod (fm1-sim-render --log-cmds). */

/* A new runtime with `seed`: an empty rack, no slot, every unit bound with
 * its parameters' current values as bases, as fm1-render --mod builds its
 * own. It runs from the next block, lab switch or not (a script scenario's
 * modulation); fm1_app_set_lab(a, 0) removes it. */
void fm1_app_mod_reset(fm1_app_t *a, uint32_t seed);

/* One line of fm1-render's --mod format (engines/host/mod_script.h) on the
 * runtime, as fm1-render applies it; 1, or 0 with a message in err (no
 * runtime, or a bad line). A `seed` line does nothing here. */
int fm1_app_mod_line(fm1_app_t *a, const char *line, char *err, size_t cap);

/* The runtime's whole state as script lines, to `emit` (a log's start). 1
 * when every line could be written. */
int fm1_app_mod_dump(fm1_app_t *a, void (*emit)(void *ctx, const char *line), void *ctx);

/* The runtime (NULL while none runs) and the panel's state of it. */
const fm1_mod_t *fm1_app_mod(const fm1_app_t *a);

/* Redraw the screen if anything on it changed (or the scope is live, at most
 * once per `min_frames` of audio). Returns 1 when a->tft.px was redrawn. */
int fm1_app_draw(fm1_app_t *a, uint32_t min_frames);

/* Redraw now, logging boxes for fm1_tft_check_layout. */
void fm1_app_draw_checked(fm1_app_t *a);

/* Bytes of instance memory the current chain uses: the engines' instances,
 * the sequencer's (fm1_seq_size) and its event buffer, and the modulation
 * runtime (fm1_mod_size) while it runs. */
size_t fm1_app_ram(const fm1_app_t *a);

/* A JSON description of every registered engine and effect (ids, names,
 * kinds, voices, credits, parameters with ranges, pages and list names).
 * Built once into a static buffer; NULL if it did not fit. */
const char *fm1_app_catalog_json(void);

#ifdef __cplusplus
}
#endif

#endif /* FM1_APP_H_ */
