/* fm1_app.h -- the virtual FM-1: a small firmware application that runs the
 * engine platform (engines/include/fm1_engine.h) behind the FM-1's front
 * panel, for the browser simulator in sim/web and its native test harness.
 *
 * It owns one sound engine and two audio-effect slots (with the lab switch,
 * up to four sound units with two inserts each, mixed into those two as
 * the master bus: below), renders them in host blocks of at most 64 frames
 * through the host's bus limiter (fm1_mix_limiter.h), and turns the
 * panel's inputs into engine calls:
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
 * panel (docs/15 S3 and S4), for the page's lab preview and the tests while
 * the public page hides it until step entry and recording work (owner
 * decision O24, 2026-10-02):
 *   SEQ           SEQ mode, the Track view (fm1_seq_view.h); HOME, FX and
 *                 GLO leave it. There the white keys are the bar's 16 steps
 *                 and the black keys the sequencer's roles (O1): they play
 *                 nothing, and fm1_seq_ui.h has every gesture (step entry,
 *                 the Step pages, bar paging)
 *   SEL           SHIFT outside FX mode (O2), in every mode; its LED is on
 *                 while it is held
 *   PLAY/STOP     `play` or `stop`, in every mode, as a typed command
 *                 through fm1_seq_ui.h and fm1_app_seq_cmd (SHIFT + PLAY
 *                 restarts); its LED is on while the transport runs, SEQ's
 *                 in SEQ mode, and in SEQ mode the keys' LEDs are the UI's
 *   notes         a note played outside SEQ mode or at MIDI IN is
 *                 remembered as the chord a step tap writes, and with steps
 *                 held in SEQ mode a MIDI IN note adds its pitch to them
 * With the switch off, SEQ and PLAY/STOP say they are not in the simulator
 * yet, as REC still does with it on, and SEL outside FX mode says where it
 * works.
 *
 * Multi-sound, also behind the lab switch (the owner's decision of
 * 2026-10-02, replacing docs/15 O10's default; §3.16 has the gestures): up
 * to FM1_APP_SOUNDS sound units at once, each an engine with its own
 * FM1_APP_INSERTS insert effects and its own level into the mix; the two
 * effect slots are the master bus after the mix. A track routed to the
 * engine plays the sound unit its route index names (fm1_app_unit_route).
 * The keys, MIDI IN, HOME, PRESETS and ALGORITHM act on the current sound
 * (SHIFT + PRESETS chooses it); FX mode shows its inserts, a Mix page with
 * every sound's level, and the master slots. A RAM meter against the FM-1's
 * budget (FM1_APP_RAM_BUDGET less the app's fixed costs, fm1_app_ram)
 * replaces the bottom bar's RAM figure, and refuses (-4) any engine or
 * effect that would take the chain past it. With the switch off there is
 * one sound and two effects, rendered exactly as before.
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
#include "fm1_panel.h"
#include "fm1_seq.h"
#include "fm1_seq_host.h"
#include "fm1_seq_ui.h"
#include "fm1_tft.h"

#ifdef __cplusplus
extern "C" {
#endif

#define FM1_APP_LEDS (FM1_APP_KEYS + FM1_APP_BUTTONS)
#define FM1_APP_FX_SLOTS 2              /* the master bus: after the sounds are mixed */
#define FM1_APP_SOUNDS 4                /* sound units with the lab switch on (owner, 2026-10-02) */
#define FM1_APP_INSERTS 2               /* insert effect slots per sound unit */
/* Every engine and effect instance the app holds ("units"), by id:
 *   0          sound unit 0 (the sound, with the lab switch off)
 *   1, 2       the master bus's effect slots, in order
 *   3 .. 5     sound units 1 .. 3 (lab switch on)
 *   6 .. 13    the inserts: 6 + FM1_APP_INSERTS x sound + slot (lab switch on)
 * Ids 0..2 are the ones the browser and the tests have always used;
 * fm1_app_sound_unit and fm1_app_insert_unit give the others. */
#define FM1_APP_UNITS (1 + FM1_APP_FX_SLOTS + (FM1_APP_SOUNDS - 1) + FM1_APP_SOUNDS * FM1_APP_INSERTS)
#define FM1_APP_EFFECTS (FM1_APP_FX_SLOTS + FM1_APP_SOUNDS * FM1_APP_INSERTS)
#define FM1_APP_MAX_FRAMES 64
#define FM1_APP_MAX_PARAMS 32
#define FM1_APP_SCOPE 512

/* Pixels the screen keeps between any two labels, or a label and a bar
 * (fm1_tft_check_layout's gap in the tests). */
#define FM1_APP_LAYOUT_GAP 4

/* Arena sizes. The largest instances today are Shapes at 12 voices
 * (~206 KB) and PSX Verb (~134 KB); the arenas leave room for growth and
 * the screen reports the real total against the FM-1's budget below.
 * These fixed arenas are a simulator convenience: four sound arenas of
 * 512 KiB and ten effect arenas of 256 KiB (two master slots and two inserts
 * per sound), 4.5 MiB, inside the module's fixed 8 MiB of memory. On the
 * FM-1 (578 KB of SRAM, about 379 KB free in the stock layout) the firmware
 * would size one arena to the chain it loads, and the RAM meter (lab) keeps
 * every chain the simulator plays inside that budget. */
#define FM1_APP_SOUND_BYTES (512u * 1024u)
#define FM1_APP_FX_BYTES (256u * 1024u)

/* RAM the stock layout leaves free (docs/11 §2, engines/README.md; part of
 * it is stock's heap, so this is an upper bound [inferred]). */
#define FM1_APP_RAM_BUDGET 387924u

/* What else the RAM meter counts on the FM-1 besides the instances, with the
 * lab switch on (fm1_app_ram): the sequencer's instance, its event buffer,
 * its pending command record and its UI state's bound (36,216 B at 8
 * tracks), and one 64-frame stereo block (512 B) for each sound unit past
 * the first, which renders and runs its inserts there before the mix (the
 * first renders in the output block) [inferred: the firmware's layout]. */
#define FM1_APP_MIX_BLOCK_BYTES (2u * FM1_APP_MAX_FRAMES * 4u)

/* fm1_app_select's results. */
enum {
  FM1_APP_SELECT_OK = 0,
  FM1_APP_SELECT_BAD = -1,      /* wrong kind, unknown, or a unit the lab switch hides */
  FM1_APP_SELECT_ARENA = -2,    /* larger than the unit's arena */
  FM1_APP_SELECT_RATE = -3,     /* the engine refused this host */
  FM1_APP_SELECT_RAM = -4       /* lab: the chain would pass the FM-1's RAM budget */
};

/* A sound unit's level into the mix, in percent (100: unity, as before). */
#define FM1_APP_LEVEL_MAX 100.0f

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

struct fm1_app;

/* The sequencer's sink for one sound unit (the bridge's ctx). */
typedef struct fm1_app_sink_ctx {
  struct fm1_app *a;
  int sound;
} fm1_app_sink_ctx_t;

typedef struct fm1_app {
  fm1_host_t host;
  fm1_app_unit_t unit[FM1_APP_UNITS];   /* by id: see FM1_APP_UNITS */
  fm1_mix_limiter_t limiter;
  float master;                  /* MASTER position, 0..1 */
  float gain;                    /* master * master */
  float out[2 * FM1_APP_MAX_FRAMES];
  uint64_t frames;               /* rendered so far: the app's clock */

  int mode;                      /* fm1_app_mode_t */
  int page;                      /* sound page in HOME */
  int fx_slot, fx_page;          /* FX mode selection: the master slot 0..1, or with
                                    the lab switch In1, In2, Mix, M1, M2 (0..4) */
  int fx_grab;                   /* SEL pressed: SELECT moves the slot */
  int octave, transpose;
  uint8_t key_down[FM1_APP_KEYS];
  uint8_t key_note[FM1_APP_KEYS];      /* note each held key started */
  uint8_t key_vel[FM1_APP_KEYS];       /* ...and its velocity, 1..127 */
  uint8_t key_sound[FM1_APP_KEYS];     /* ...and the sound unit it plays */
  uint8_t note_count[FM1_APP_SOUNDS][128];   /* notes sounding on each sound unit,
                                                from the keys and MIDI IN */
  uint8_t button_down[FM1_APP_BUTTONS];

  /* Multi-sound (lab): the current sound, each sound unit's level into the
   * mix (percent), and their render blocks and sequencer sinks. */
  int sound;
  float level[FM1_APP_SOUNDS];
  size_t ram_over;               /* the last RAM refusal: bytes past the budget */
  float mix[FM1_APP_SOUNDS][2 * FM1_APP_MAX_FRAMES];
  fm1_app_sink_ctx_t sink_ctx[FM1_APP_SOUNDS];

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
  uint8_t seq_note_count[FM1_APP_SOUNDS][128];   /* sequencer notes sounding, per sound */
  float lock_shown[FM1_APP_SOUNDS][FM1_APP_MAX_PARAMS];   /* the last lock of each */
  uint32_t lock_mask[FM1_APP_SOUNDS];     /* parameter, for the screen; never in value[] */
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

  fm1_tft_t tft;
  unsigned char sound_mem[FM1_APP_SOUNDS][FM1_APP_SOUND_BYTES] FM1_APP_ALIGN16;
  unsigned char fx_mem[FM1_APP_EFFECTS][FM1_APP_FX_BYTES] FM1_APP_ALIGN16;
  unsigned char seq_mem[FM1_APP_SEQ_BYTES] FM1_APP_ALIGN16;
  fm1_seq_ev_t seq_ev[FM1_APP_SEQ_EVENTS];
} fm1_app_t;

/* Set up at `sample_rate` with 64-frame blocks: no engine loaded, MASTER at
 * full gain, octave and transpose 0, HOME mode, and a sequencer of
 * FM1_APP_SEQ_TRACKS tracks at lrintf(sample_rate) (as fm1-render creates
 * it), stopped and empty, every track on its default USB-MIDI route. */
void fm1_app_init(fm1_app_t *a, float sample_rate);

/* The registry index of an engine id, or -1. */
int fm1_app_find(const char *id);

/* Load registry entry `index` into a unit (FM1_APP_UNITS: 0 = the sound,
 * 1..2 = the master effects, and with the lab switch the other sound units
 * and the inserts; -1 empties any unit but 0). The instance memory is zeroed
 * and the engine created with its defaults, as fm1-render does. Changing a
 * sound releases its notes first. Returns 0, or FM1_APP_SELECT_BAD (-1:
 * wrong kind, unknown, or a lab unit with the switch off), _ARENA (-2: does
 * not fit the arena; the unit keeps its engine), _RATE (-3: the engine
 * refused this host, e.g. a Plaits-based one above 47,872 Hz; the unit's
 * previous engine is created again with its values) or, with the lab switch
 * on, _RAM (-4: the chain would pass the FM-1's RAM budget and grow; the
 * unit keeps its engine). */
int fm1_app_select(fm1_app_t *a, int unit, int index);

/* The browser's starting chain: Macro, then Plate. If Macro refuses the
 * host's rate, the first sound that loads instead, with a popup saying why.
 * Then the sequencer's default route (fm1_app_seq_default_route) and, with
 * the lab switch on, the demo pattern (fm1_app_seq_demo). Returns 0, or the
 * first fm1_app_select error. */
int fm1_app_default_chain(fm1_app_t *a);

/* The lab switch: on, the sequencer is on the panel (SEQ mode, PLAY/STOP,
 * their LEDs) and so is multi-sound; off (as fm1_app_init leaves it), those
 * buttons say they are not in the simulator yet and nothing of either
 * shows. Turning it off in SEQ mode goes back to HOME, and empties every
 * sound unit but 0 and every insert, releasing their notes. */
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

/* Notes as MIDI sends them (any source) on the current sound; a note-off
 * releases the current sound's note of that pitch, else the first sound
 * unit holding one. Pitch bend in semitones (finite, clamped to +/-48) on
 * the current sound, and a release of every sounding note on every sound:
 * the sequencer's too (a later sequencer note-off for one of them changes
 * nothing). */
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

/* Redraw the screen if anything on it changed (or the scope is live, at most
 * once per `min_frames` of audio). Returns 1 when a->tft.px was redrawn. */
int fm1_app_draw(fm1_app_t *a, uint32_t min_frames);

/* Redraw now, logging boxes for fm1_tft_check_layout. */
void fm1_app_draw_checked(fm1_app_t *a);

/* Bytes of instance memory the current chain uses: the engines' instances,
 * the sequencer's (fm1_seq_size) and its event buffer. With the lab switch
 * on, the RAM meter's figure: that, and the sequencer's pending command
 * record and UI state bound, and a mix block per sound unit past the first
 * (FM1_APP_MIX_BLOCK_BYTES). */
size_t fm1_app_ram(const fm1_app_t *a);

/* What fm1_app_ram would be with registry entry `index` in `unit` (-1:
 * emptied): the RAM meter's test before a load. */
size_t fm1_app_ram_with(const fm1_app_t *a, int unit, int index);

/* ---- Sound units (multi-sound, lab switch) --------------------------------
 * `sound` is 0 .. FM1_APP_SOUNDS - 1; the user's Sound 1 is 0. Stage S6
 * routes tracks with these (docs/15 §3.16). */

/* Unit ids (FM1_APP_UNITS) of sound unit `sound` and of its insert `slot`
 * (0 .. FM1_APP_INSERTS - 1); -1 out of range. */
int fm1_app_sound_unit(int sound);
int fm1_app_insert_unit(int sound, int slot);

/* Sound units the panel offers: FM1_APP_SOUNDS with the lab switch on, else
 * 1. */
int fm1_app_unit_count(const fm1_app_t *a);

/* A sound unit's engine, NULL when it is empty (or out of range). */
const fm1_engine_t *fm1_app_unit_engine(const fm1_app_t *a, int sound);

/* The current sound: what the keys and MIDI IN play, and HOME, PRESETS,
 * ALGORITHM and FX mode's inserts edit. Setting it needs the lab switch for
 * any sound but 0; returns 0, or -1. */
int fm1_app_unit_current(const fm1_app_t *a);
int fm1_app_unit_set_current(fm1_app_t *a, int sound);

/* Loads an engine into a sound unit (-1 empties it, never sound 0), or an
 * effect into one of its inserts: fm1_app_select's results. */
int fm1_app_unit_select(fm1_app_t *a, int sound, int index);
int fm1_app_unit_insert(fm1_app_t *a, int sound, int slot, int index);

/* A sound unit's level into the mix, in percent (0..100, default 100). */
float fm1_app_unit_level(const fm1_app_t *a, int sound);
void fm1_app_unit_set_level(fm1_app_t *a, int sound, float percent);

/* A note on a given sound unit, whatever the current sound. */
void fm1_app_unit_note_on(fm1_app_t *a, int sound, int note, int velocity);
void fm1_app_unit_note_off(fm1_app_t *a, int sound, int note);

/* Routes a track to a sound unit (`route t 1 sound`), with the lab switch
 * on: 1 if accepted. fm1_app_unit_of_track is the sound unit a track plays
 * (with the switch off every engine-routed track plays sound 0, as
 * fm1-render's one engine), or -1 for a MIDI-routed one. */
int fm1_app_unit_route(fm1_app_t *a, int track, int sound);
int fm1_app_unit_of_track(const fm1_app_t *a, int track);

/* A JSON description of every registered engine and effect (ids, names,
 * kinds, voices, credits, parameters with ranges, pages and list names).
 * Built once into a static buffer; NULL if it did not fit. */
const char *fm1_app_catalog_json(void);

#ifdef __cplusplus
}
#endif

#endif /* FM1_APP_H_ */
