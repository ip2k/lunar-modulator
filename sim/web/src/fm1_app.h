/* fm1_app.h -- the virtual FM-1: a small firmware application that runs the
 * engine platform (engines/include/fm1_engine.h) behind the FM-1's front
 * panel, for the browser simulator in sim/web and its native test harness.
 *
 * It owns up to four sound units with two insert effects each, mixed into
 * two audio-effect slots as the master bus (below), renders them in host
 * blocks of at most 64 frames through the host's bus limiter
 * (fm1_mix_limiter.h), and turns the panel's inputs into engine calls:
 *
 *   27 keys       F3..G5: note = key + 53 + 12 * octave + transpose
 *                 (the M-VAVE manual's formula), with OCT-/OCT+ and
 *                 ALGORITHM-while-OCT-held transpose as stock does it;
 *                 with a pad kit as the current sound (an engine with
 *                 pad_count, fm1_engine.h: Sophie, Drums), the 16 white
 *                 keys play its first 16 pads at any octave and the black
 *                 keys are silent
 *   MASTER        output volume (a gain after the limiter)
 *   SELECT        page within the current mode; in FX mode, the effect slot
 *   PRESETS       the sound engine
 *   ALGORITHM     the engine's first list parameter (its model, shape or
 *                 patch); in FX mode, the effect in the selected slot
 *   KNOB1-4       the four parameters of the current page
 *   FX, SEL, GLO, HOME   FX mode (SEL grabs a slot so SELECT reorders it),
 *                 the global page, home
 *   SAVE          the project to the host's store, when it has one (the
 *                 page's browser storage; fm1_app_saved below)
 *   GLO pages     SELECT the page: 1 Globe (what the instrument runs: rate,
 *                 block, RAM, voices, the master slots, octave and
 *                 transpose) and 2 Key, the project key (below); KNOB1
 *                 its root and KNOB2 its scale, on either page, which
 *                 turns to Key
 *   ARP           the arpeggiator on the current sound (below)
 *
 * It hosts the sequencer core (engines/include/fm1_seq.h) through the shared
 * host bridge (fm1_seq_host.h), as fm1-render does: script lines and typed
 * commands at block starts, then each block's events, with the sound
 * engine's render split at every note and lock of a track routed to it.
 * fm1_app_seq_* below drive it; the harness and the parity test play scripts
 * and sets through it.
 *
 * The sequencer is on the panel (docs/15 S3 to S8; behind a lab switch
 * until 2026-10-05, owner decision O24):
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
 *                 held in SEQ mode a MIDI IN note adds its pitch to them;
 *                 one that no step takes is live input to the focused track
 *                 (fm1_app_seq_note_in), for recording and Capture (S5)
 *   REC           `rec`; held while stopped in SEQ mode, step record; with
 *                 SHIFT, Capture, whose stopped tempo picker or fitted tempo
 *                 stays over the screen until a press (fm1_seq_ui.h, S5).
 *                 Its LED: on while recording, fast during a count-in, slow
 *                 while Capture holds notes
 * and modulation (docs/16 stage MG3; fm1_mod_ui.h has the pages): the app
 * hosts a runtime (fm1_mod.h) on the same bridge, as fm1-render --mod does,
 * starting from the default rack (LFO1, LFO2, ENV3, ENV4, CHN5) and two
 * cables, RTRG (the note gate, retriggered by each note-on) into each
 * Envelope's GATE, so every note on every sound restarts the envelopes
 *   LFO, ENV      a tap opens RACK at the LFOs or the Envelopes; held while
 *                 KNOB1-4 turn on HOME, FX or RACK, a cable from the
 *                 selected one to that knob's parameter (the gesture)
 *   EDIT          MATRIX, the slot list; SEL there opens CHAIN, and in RACK
 *                 grabs the module (SEL is SHIFT in every other mode but FX)
 *   pages         a routed parameter shows its marker, bracket and live tick
 * A cable reaches every sound unit, its inserts, the master effects and
 * the host (fm1_mod.h's unit codes; fm1_app_mod_unit maps the app's unit
 * ids onto them); on HOME the gesture takes the current sound's
 * parameters, and the runtime runs over every sound unit's slot
 * (fm1_seq_host_dispatch_slots_ticks).
 *
 * The arpeggiator (engine API v3's MIDI effects, fm1_mfx_host.h): every
 * sound unit has one, "arp" (engines/midi_fx/), bypassed until switched on,
 * in the first slot of the chain in front of it, on the bridge as
 * fm1-render --mfx runs it. While it is on, the keys, MIDI IN and the
 * sequencer's notes for that sound go through it; the sequencer still
 * records the keys as they were played (owner, 2026-10-05), so a recorded
 * part arpeggiates again on playback.
 *   ARP tap       on or off for the current sound; switched on, the ARP
 *                 pages open (FM1_MODE_ARP), switched off there, they close
 *   ARP held      FM1_APP_ARP_HOLD_S: Latch on (and the arp on), or off while
 *                 the arp is on and latched
 *   SHIFT + ARP   the ARP pages, without switching
 *   ARP pages     SELECT the page (PLAY, RHYTHM, CHANCE, FEEL, MORE, KEYS,
 *                 SEED), KNOB1-4 its parameters, ALGORITHM the stock FM-1's
 *                 arp modes as presets (Up, Down, Up/Down, Down/Up, Random,
 *                 Played) and, after them, every other MIDI effect in the
 *                 build, which then takes the slot (Acid Gen while the GPL
 *                 switch is on: its pages LINE, KEY, PLAY and SEED); the
 *                 keys play
 * Its LED is lit while the current sound's arp is on, and blinks while it
 * latches. A change of the sound, a panic, a sequencer reset or import
 * flush it; a bypass flushes it at once; every note-on it sent gets its
 * note-off. Every change reaches on_mfx, so a native run replays through
 * fm1-render --mfx. While the sequencer plays, the arp's steps fall on its
 * grid; its Stop lets go of the notes it gave the arp, latched or not, and
 * the keys latched by hand play on (owner, 2026-10-06).
 *
 * The project key (owner, 2026-10-06: one key for the project): a root and
 * a scale (engine API v3's FM1_KEY_*), which every MIDI effect gets in its
 * context; the arp reads none of it yet. It is the set's, kept with the
 * tempo (the sequencer's `key` verb and the set's `key` line), so the
 * global page's KNOB1 and KNOB2 send `key` as a typed command, which a
 * native run logs and fm1-render replays.
 *
 * Multi-sound (the owner's decision of 2026-10-02, replacing docs/15 O10's
 * default; §3.16 has the gestures): up to FM1_APP_SOUNDS sound units at
 * once, each an engine with its own
 * FM1_APP_INSERTS insert effects and its own level into the mix; the two
 * effect slots are the master bus after the mix. A track routed to the
 * engine plays the sound unit its route index names (fm1_app_unit_route).
 * The keys, MIDI IN, HOME, PRESETS and ALGORITHM act on the current sound
 * (SHIFT + PRESETS chooses it); FX mode shows its inserts, a Mix page with
 * every sound's level, and the master slots. A RAM meter on the bottom bar,
 * against the FM-1's budget (FM1_APP_RAM_BUDGET less the app's fixed
 * costs, fm1_app_ram), refuses (-4) any engine or effect that would take
 * the chain past it.
 *
 * The screen is a 240 x 240 RGB565 frame buffer (fm1_tft.h) drawn with the
 * stock layout: a top bar with the sound's name, the mode's content, and a
 * bottom bar with page and mode, plus one-second popups: a message, or a
 * list (PRESETS, ALGORITHM, the modulation pickers) with its title, the
 * chosen entry's place in it and as many entries as the middle holds.
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

#include "fm1_dx7.h"
#include "fm1_engine.h"
#include "fm1_mfx_host.h"
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
#define FM1_APP_FX_SLOTS 2              /* the master bus: after the sounds are mixed */
#define FM1_APP_SOUNDS 4                /* sound units (owner, 2026-10-02) */
#define FM1_APP_INSERTS 2               /* insert effect slots per sound unit */
/* Every engine and effect instance the app holds ("units"), by id:
 *   0          sound unit 0 (Sound 1)
 *   1, 2       the master bus's effect slots, in order
 *   3 .. 5     sound units 1 .. 3
 *   6 .. 13    the inserts: 6 + FM1_APP_INSERTS x sound + slot
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

/* A message popup's tone (audit Q2): a confirmation, or a refusal, whose
 * rules and reason lines are C_REFUSE: with REFUSE the first line names
 * what was refused and stays text ("Shapes" / "does not fit"), with
 * REFUSE_ALL every line is the reason ("No LFO" / "in the rack"). */
#define FM1_APP_TONE_SAY 0
#define FM1_APP_TONE_REFUSE 1
#define FM1_APP_TONE_REFUSE_ALL 2
#define FM1_APP_TONE_ASK 3          /* a question: its first line in C_REFUSE (the CLEAR confirm) */

/* Arena sizes. The largest instances today are Shapes at 12 voices
 * (~206 KB) and PSX Verb (~134 KB); the arenas leave room for growth and
 * the screen reports the real total against the FM-1's budget below.
 * These fixed arenas are a simulator convenience: four sound arenas of
 * 512 KiB and ten effect arenas of 256 KiB (two master slots and two inserts
 * per sound), 4.5 MiB, inside the module's fixed 8 MiB of memory. On the
 * FM-1 (578 KB of SRAM, about 379 KB free in the stock layout) the firmware
 * would size one arena to the chain it loads, and the RAM meter keeps
 * every chain the simulator plays inside that budget. */
#define FM1_APP_SOUND_BYTES (512u * 1024u)
#define FM1_APP_FX_BYTES (256u * 1024u)

/* RAM the stock layout leaves free (docs/11 §2, engines/README.md; part of
 * it is stock's heap, so this is an upper bound [inferred]). The meter
 * counts what lives in RAM: instances (each engine's instance_size at the
 * FM-1's rate, FM1_APP_RAM_RATE, whatever rate the host runs at) and the
 * costs below. Const tables an engine reads are flash on the FM-1 and are
 * not counted, msfa's among them since 2026-10-06 (engines/msfa.md, "Tables
 * in flash"); a table an engine keeps in RAM is in its instance and
 * counted, as FM6's frequency table would be at any rate but 44,118 Hz. */
#define FM1_APP_RAM_BUDGET 387924u

/* The rate the RAM rule sizes instances at: the FM-1's (owner, 2026-10-06:
 * the page asks the browser for 44,100 Hz, and the rule stays at 44,118).
 * Each unit is created at the host's rate; the meter and every refusal
 * count its instance_size at this one (fm1_app_unit_t.ram). */
#define FM1_APP_RAM_RATE 44118.0f

/* What else the RAM meter counts on the FM-1 besides the instances
 * (fm1_app_ram): the sequencer's instance, its event buffer,
 * its pending command record and its UI state's bound (36,216 B at 8
 * tracks), and one 64-frame stereo block (512 B) for each sound unit past
 * the first, which renders and runs its inserts there before the mix (the
 * first renders in the output block) [inferred: the firmware's layout]. */
#define FM1_APP_MIX_BLOCK_BYTES (2u * FM1_APP_MAX_FRAMES * 4u)

/* fm1_app_select's results. */
enum {
  FM1_APP_SELECT_OK = 0,
  FM1_APP_SELECT_BAD = -1,      /* wrong kind, unknown, or no such unit */
  FM1_APP_SELECT_ARENA = -2,    /* larger than the unit's arena */
  FM1_APP_SELECT_RATE = -3,     /* the engine refused this host */
  FM1_APP_SELECT_RAM = -4       /* the chain would pass the FM-1's RAM budget */
};

/* A sound unit's level into the mix, in percent (100: unity, as before). */
#define FM1_APP_LEVEL_MAX 100.0f

/* The sequencer (docs/15 §2.5 and §2.6). Its instance takes the FM-1's
 * default limits (fm1_seq_limits_default) for FM1_APP_SEQ_TRACKS tracks:
 * 31,880 B at 8 tracks, Capture included, the same on 32- and 64-bit
 * builds. Every block's commands and events share one buffer of
 * FM1_APP_SEQ_EVENTS (3,264 B). With the pending command record (240 B),
 * the UI state (fm1_seq_ui_t, at most 1,024 B) and the metronome's click
 * voice (20 B) that is 36,428 B of the sequencer's 36,864 B budget, half of
 * docs/13 §5's 72 KiB. The track count is the owner's decision O3 (docs/15
 * §8, answered 2026-10-02): 8, the count the firmware will use (4 would
 * have left room for docs/13's undo ring). The buffer was 256 events until
 * stage S6: one short of the worst burst measured, seq_bench's 193 events
 * in a block beside the 64 gates' note-offs the core keeps room for (257);
 * 272 holds it whole, and fits the budget at 8 tracks. */
#define FM1_APP_SEQ_TRACKS 8
#define FM1_APP_SEQ_BYTES 32768u      /* the instance's arena */
#define FM1_APP_SEQ_EVENTS 272u       /* the block's event buffer, in events */
#define FM1_APP_SEQ_BUDGET 36864u     /* the sequencer's share of FM-1 RAM */
#define FM1_APP_SEQ_UI_BYTES 1024u    /* the SEQ mode UI state's bound */

/* Modulation (docs/16 MG3): the runtime's memory (fm1_mod_size(), the same
 * on 32- and 64-bit builds, the 8 KB arena included) and the room for a
 * block's writes to the effects and AMP (every effect parameter and AMP
 * twice: two ticks a 64-frame block). The runtime counts in the RAM figure
 * while it runs. */
#define FM1_APP_MOD_BYTES 26880u
#define FM1_APP_MOD_WRITES \
  ((FM1_APP_MAX_FRAMES / FM1_MOD_TICK) * (FM1_APP_EFFECTS * FM1_MOD_UNIT_PARAMS + FM1_MOD_HOST_PARAMS))
#define FM1_APP_MOD_SEED 1u           /* fm1_app_init's runtime; a log records it */

/* The arpeggiator (MIDI effects, engine API v3). One per sound unit, in the
 * first of its chain's FM1_MFX_SLOTS slots: the owner's design has four
 * MIDI-effect slots per track (2026-10-05), and the stage keeps room for
 * them, but the panel fills only the first, the MIDI-FX slot, with the arp
 * or another MIDI effect (fm1_app_mfx_select). Each instance has its own
 * arena; the RAM meter counts each effect that is on, and the stage while
 * one is (fm1_app_ram). */
#define FM1_APP_MFX_BYTES 768u        /* a MIDI effect's arena: the arp takes 736 B */
#define FM1_APP_ARP_PARAMS 32         /* a MIDI effect's parameters, at most */
#define FM1_APP_ARP_HOLD_S 0.5f       /* ARP held this long latches */

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

/* FM6's user bank (engine id "dx7"; engines/msfa.md): the DX7 voices loaded
 * from SysEx files, by the page's "Load DX7 patches" (fm1w_dx7_load) or the
 * harness's --sysex. It stands for the voices the FM-1 would keep in flash:
 * every FM6 sound gets them in its user slots when it is created and when a
 * file is loaded, and FM6's Patch list shows their names in place of
 * "User N" (a loaded voice with a blank name keeps "User N"). The bank is
 * not counted in the RAM meter; each FM6 instance's copy of it is, in the
 * instance. */
#define FM1_APP_DX7_FILE_MAX 65536u   /* the largest file read: the page's text buffer */
#define FM1_APP_DX7_PATCHES 64        /* FM6's Patch list: 32 built in, then User 1..32 */

typedef struct fm1_app_dx7 {
  int index;                     /* FM6's registry index, -1 if not in this build */
  int patch;                     /* its Patch parameter's index */
  uint8_t voice[FM1_DX7_USER_SLOTS][FM1_DX7_VCED_BYTES];   /* VCED data, clamped */
  uint8_t loaded[FM1_DX7_USER_SLOTS];                      /* 1: from a file */
  char name[FM1_DX7_USER_SLOTS][FM1_DX7_NAME_BYTES + 1];   /* trimmed */
  const char *names[FM1_APP_DX7_PATCHES];   /* the Patch list as the screen shows it */
  fm1_param_t params[FM1_APP_MAX_PARAMS];   /* FM6's, Patch naming these */
  fm1_engine_t engine;           /* FM6 as the app shows it: the registry's entry
                                    with these params; units holding FM6 point here */
  unsigned next;                 /* the slot the next single voice goes to */
  fm1_dx7_sysex_result_t last;   /* what the last file held */
} fm1_app_dx7_t;

/* fm1_app_dx7_load's refusals (nothing changes). */
enum {
  FM1_APP_DX7_NONE = 0,          /* no voice or bank dump in the file */
  FM1_APP_DX7_TOO_BIG = -1,      /* past FM1_APP_DX7_FILE_MAX */
  FM1_APP_DX7_NO_FM6 = -2        /* no FM6 in this build */
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
  size_t bytes;                  /* instance_size of the engine in it, at the host's rate */
  size_t ram;                    /* ... and at FM1_APP_RAM_RATE: what the RAM meter counts */
  unsigned char *mem;            /* this unit's arena */
  size_t cap;
  float value[FM1_APP_MAX_PARAMS];
  int driven;                    /* FM1_PARAM_DRIVEN as last sent (0: as created) */
} fm1_app_unit_t;

/* A tick's write to an effect or to AMP, at its frame in the block. */
typedef struct fm1_app_mod_write {
  uint32_t frame;
  fm1_mod_write_t w;
} fm1_app_mod_write_t;

struct fm1_app;

/* A project's words (the `name`, `title`, `about`, `author` and `licence`
 * members), as a load read them; empty for a new project. */
typedef struct fm1_app_info {
  char name[33];
  char title[65];
  char about[513];
  char author[65];
  char licence[33];
} fm1_app_info_t;

/* Device settings (a settings file's keys; ST10): the metronome and full
 * velocity are the sequencer's and its UI's own (`metro`, SHIFT + 10) and
 * are read from there; these two have no panel control yet and are kept for
 * the stages that use them (the count-in's click, MIDI IN's channel). */
typedef struct fm1_app_settings {
  uint8_t count_in_click;        /* the count-in clicks */
  uint8_t midi_in_channel;       /* 0 every channel (omni), 1-16 */
} fm1_app_settings_t;

/* The sequencer's sink for one sound unit (the bridge's ctx). */
typedef struct fm1_app_sink_ctx {
  struct fm1_app *a;
  int sound;
} fm1_app_sink_ctx_t;

typedef struct fm1_app {
  fm1_host_t host;
  fm1_host_t ram_host;           /* host at FM1_APP_RAM_RATE: the RAM rule's sizes */
  fm1_app_unit_t unit[FM1_APP_UNITS];   /* by id: see FM1_APP_UNITS */
  fm1_mix_limiter_t limiter;
  float master;                  /* MASTER position, 0..1 */
  float gain;                    /* master * master */
  float out[2 * FM1_APP_MAX_FRAMES];
  uint64_t frames;               /* rendered so far: the app's clock */

  int mode;                      /* fm1_app_mode_t */
  int page;                      /* sound page in HOME */
  int glo_page;                  /* the global page shown: 0 Globe, 1 Key */
  int fx_slot, fx_page;          /* FX mode selection: In1, In2, Mix, M1, M2 (0..4) */
  int fx_grab;                   /* SEL pressed: SELECT moves the slot */
  int octave, transpose;
  uint8_t key_down[FM1_APP_KEYS];
  uint8_t key_note[FM1_APP_KEYS];      /* note each held key started */
  uint8_t key_vel[FM1_APP_KEYS];       /* ...and its velocity, 1..127 */
  uint8_t key_sound[FM1_APP_KEYS];     /* ...and the sound unit it plays */
  uint8_t note_count[FM1_APP_SOUNDS][128];   /* notes sounding on each sound unit,
                                                from the keys and MIDI IN */
  uint8_t button_down[FM1_APP_BUTTONS];

  /* Multi-sound: the current sound, each sound unit's level into the
   * mix (percent), and their render blocks and sequencer sinks. */
  int sound;
  float level[FM1_APP_SOUNDS];
  size_t ram_over;               /* the last RAM refusal: bytes past the budget (its
                                    popup shows budget + this as a percentage) */
  float mix[FM1_APP_SOUNDS][2 * FM1_APP_MAX_FRAMES];
  fm1_app_sink_ctx_t sink_ctx[FM1_APP_SOUNDS];

  /* The popup: up to three lines of a message, or a list's window (PRESETS,
   * ALGORITHM, the pickers; fm1_panel.h): popup[0] is entry popup_first
   * of popup_total under popup_title, in face popup_face. popup_total is
   * 0 for a message. A refusal (popup_tone) draws its reason in C_REFUSE;
   * a confirmation that fits one line of BANNER_CHARS is a banner over the
   * page's bottom (audit L1, fm1_app_banner). A list entry, or the title,
   * may start with a sound's tag ("S2"), drawn in that sound's colour:
   * popup_tag holds each line's sound + 1 (bit 4k), 0 for none. */
  char popup[FM1_LIST_MAX_ROWS][FM1_LIST_ENTRY];
  int popup_lines, popup_mark;   /* popup_mark: highlighted line, or -1 */
  char popup_title[FM1_LIST_ENTRY];
  int popup_first, popup_total;
  int popup_face;                /* a list's: FM1_LIST_MAIN, _MID or _SMALL */
  int popup_tone;                /* FM1_APP_TONE_* */
  int popup_title_tag;           /* the title's sound + 1, or 0 */
  uint32_t popup_dim;            /* a list's lines drawn dim (an Empty entry) */
  uint64_t popup_tag;            /* each line's sound + 1, four bits a line */
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
  fm1_seq_click_t click;         /* the metronome's click (O11), from the block's events */
  /* Native-harness hooks: every typed command as it is applied, and every
   * live note given to the sequencer (velocity 0: its release), with the
   * frame of the block they lead. NULL in the browser. */
  void (*on_cmd)(void *ctx, uint64_t frame, const fm1_seq_cmd_t *c);
  void (*on_note_in)(void *ctx, uint64_t frame, int track, int pitch, int velocity);
  void *on_cmd_ctx;

  /* The sequencer on the panel. */
  fm1_seq_ui_t ui;
  int seq_from_mode;             /* the mode SEQ was pressed in: a track focused
                                    while it is held goes back there (S6) */
  uint8_t key_sound_only[FM1_APP_KEYS];   /* step record's keys: the sound only */
  uint8_t seq_fed[128];                   /* notes down given to the sequencer as */
  uint8_t seq_fed_track[128];             /* live input, and the track each went to */

  /* Modulation (docs/16 MG3). mod is NULL only if the runtime did not fit;
   * its memory is after tft. */
  fm1_mod_t *mod;
  fm1_mod_glue_t mod_glue;       /* the bridge's control-rate hook */
  fm1_mod_ramp_t mod_amp;        /* HOST AMP, before the limiter */
  int mod_amp_used;
  uint32_t mod_nwr;              /* this block's writes to the effects and AMP */
  fm1_app_mod_write_t mod_wr[FM1_APP_MOD_WRITES];
  uint32_t mod_seed;             /* the runtime's seed, for a log */
  float bend[FM1_APP_SOUNDS];     /* each sound unit's pitch bend: the base of
                                    its HOST pitch (PITCH, PITCH2-4; MG9) */
  fm1_mod_ui_t mui;              /* RACK, MATRIX, CHAIN and the gesture */

  /* The arpeggiator: the MIDI effects' stage on the bridge, each sound's
   * arp's parameters as set, and the ARP pages. */
  fm1_mfx_t mfx;
  float arp_value[FM1_APP_SOUNDS][FM1_APP_ARP_PARAMS];
  int arp_page;
  int arp_from_mode;             /* the mode the ARP pages were opened from */
  uint64_t arp_down_at;          /* a->frames when ARP went down */
  uint8_t arp_down, arp_used, arp_hold_done;
  /* Native-harness hook: every change of a MIDI-FX slot, with the frame of
   * the block it leads: `param` -1 for on (value 1) or bypassed (0), -2 for
   * another effect put in it (value: its index in fm1_midi_fxs), else the
   * parameter's index and its new value. NULL in the browser. */
  void (*on_mfx)(void *ctx, uint64_t frame, int sound, int param, float value);
  /* Native-harness hook: every modulation edit as a line of fm1-render's
   * --mod format (engines/host/mod_script.h), with the frame of the block
   * it leads. NULL in the browser. */
  void (*on_mod)(void *ctx, uint64_t frame, const char *line);
  void *on_mod_ctx;
  /* The edit layer (fm1_edit.h, stage ED1): its change ring, telemetry and
   * the source of what is being edited now. The host's; NULL without one
   * (the hooks then do nothing). A project load keeps it. */
  struct fm1_edit *edit;

  fm1_app_dx7_t dx7;             /* FM6's user bank */
  /* The bottom bar's left text as last drawn ("2/7 RHYTHM", "1/4 Sound"):
   * the native harness checks the panel's page names against the metadata
   * export's with it (--page-labels). */
  char bottom_label[24];

  /* Saved state (stage A1, fm1_app_state.h). The project's own words, kept
   * so a save writes back what a load read; the device settings (a
   * settings file, never in a project); SAVE's requests and the host's
   * store. */
  fm1_app_info_t info;
  fm1_app_settings_t settings;
  uint32_t save_gen;             /* bumped by each SAVE press */
  int store_ready;               /* a host store answers SAVE (fm1_app_saved) */

  fm1_tft_t tft;
  unsigned char sound_mem[FM1_APP_SOUNDS][FM1_APP_SOUND_BYTES] FM1_APP_ALIGN16;
  unsigned char fx_mem[FM1_APP_EFFECTS][FM1_APP_FX_BYTES] FM1_APP_ALIGN16;
  unsigned char seq_mem[FM1_APP_SEQ_BYTES] FM1_APP_ALIGN16;
  fm1_seq_ev_t seq_ev[FM1_APP_SEQ_EVENTS];
  unsigned char mod_mem[FM1_APP_MOD_BYTES] FM1_APP_ALIGN16;
  unsigned char mfx_mem[FM1_APP_SOUNDS][FM1_APP_MFX_BYTES] FM1_APP_ALIGN16;
} fm1_app_t;

/* Set up at `sample_rate` with 64-frame blocks: no engine loaded, MASTER at
 * full gain, octave and transpose 0, HOME mode, Sound 1 current, every
 * level at 100 %, a sequencer of FM1_APP_SEQ_TRACKS tracks at
 * lrintf(sample_rate) (as fm1-render creates it), stopped and empty, every
 * track on its default USB-MIDI route, and the modulation runtime with
 * FM1_APP_MOD_SEED and the default rack: LFO1, LFO2, ENV3, ENV4 and CHN5,
 * with RTRG cabled into both envelopes' GATE. */
void fm1_app_init(fm1_app_t *a, float sample_rate);

/* The registry index of an engine id, or -1. */
int fm1_app_find(const char *id);

/* FM6's user bank (fm1_app_dx7_t). fm1_app_dx7_load reads the DX7 voices in
 * a .syx file's bytes (fm1_dx7_read_sysex: single voices and 32-voice
 * banks, several in a file, values clamped) into the bank, from the slot
 * after the last single voice (User 1 first; a bank fills User 1..32 and
 * the next single voice goes to User 1, as fm1-render --sysex orders them),
 * gives every FM6 sound the bank and puts up a popup. It changes no engine
 * and no parameter. Fills res when not NULL (also in a->dx7.last) and
 * returns the voices stored, or FM1_APP_DX7_NONE (0), _TOO_BIG or _NO_FM6,
 * which leave the bank as it was. */
int fm1_app_dx7_load(fm1_app_t *a, const uint8_t *data, size_t len, fm1_dx7_sysex_result_t *res);

/* What the page does after a load: the current sound becomes FM6, unless it
 * is already (fm1_app_select's code if that is refused), and plays user slot
 * `slot` (0..31: its Patch set to that slot). 0, or a negative code. */
int fm1_app_dx7_play(fm1_app_t *a, unsigned slot);

/* The name user slot `slot` shows: the loaded voice's, or "User N" (a slot
 * not loaded, or a blank name); "" for a slot out of range. */
const char *fm1_app_dx7_name(const fm1_app_t *a, unsigned slot);

/* Load registry entry `index` into a unit (FM1_APP_UNITS: 0 = Sound 1,
 * 1..2 = the master effects, then the other sound units and the inserts;
 * -1 empties any unit but 0). The instance memory is zeroed and the engine
 * created with its defaults, as fm1-render does. Changing a sound releases
 * its notes first. Returns 0, or FM1_APP_SELECT_BAD (-1: wrong kind or
 * unknown), _ARENA (-2: does not fit the arena; the unit keeps its engine),
 * _RATE (-3: the engine refused this host, e.g. a Plaits-based one above
 * 47,872 Hz; the unit's previous engine is created again with its values)
 * or _RAM (-4: the chain would pass the FM-1's RAM budget and grow; the
 * unit keeps its engine, and a popup names it and what the chain would need). */
int fm1_app_select(fm1_app_t *a, int unit, int index);

/* The browser's starting chain: Macro, then Plate. If Macro refuses the
 * host's rate, the first sound that loads instead, with a popup saying why.
 * Then the sequencer's default route (fm1_app_seq_default_route), the
 * browser's routes (fm1_app_seq_start_routes) and the demo pattern
 * (fm1_app_seq_demo). Returns 0, or the first fm1_app_select error. */
int fm1_app_default_chain(fm1_app_t *a);

/* The demo pattern (owner decision O4): a one-bar, 16-step figure on track
 * 1 (index 0), as one line of verbs; the browser's start chain applies it,
 * and nothing else does, so the tests and the parity runs start empty. 1 if
 * it went in whole. */
int fm1_app_seq_demo(fm1_app_t *a);
extern const char fm1_app_demo_pattern[];

/* The browser's routes (owner decision O10 as changed on 2026-10-02, docs/15
 * S6): every track but the first that is still on its default MIDI route
 * plays Sound 1 (`route t 1 0`), so each can be heard before the user routes
 * it on its Track page; track 1 plays Sound 1 by the default-route rule.
 * The start chain applies it after the default route; nothing else does,
 * so tests and parity runs route with verbs.
 * Returns the tracks routed. */
int fm1_app_seq_start_routes(fm1_app_t *a);

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

/* Live notes for recording and Capture (velocity 0 releases), at frame 0
 * of the coming block, as a `non` or `nof` op would be applied there; the
 * harness's on_note_in hook logs it so. The app gives it the notes it plays
 * that no step took (fm1_seq_ui_note). */
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

/* A new runtime with `seed` in place of the one running: an empty rack, no
 * slot, every unit bound with its parameters' current values as bases, as
 * fm1-render --mod builds its own (a script scenario's modulation). It runs
 * from the next block. */
void fm1_app_mod_reset(fm1_app_t *a, uint32_t seed);

/* One line of fm1-render's --mod format (engines/host/mod_script.h) on the
 * runtime, as fm1-render applies it; 1, or 0 with a message in err (no
 * runtime, or a bad line). A `seed` line does nothing here. */
int fm1_app_mod_line(fm1_app_t *a, const char *line, char *err, size_t cap);

/* The runtime's whole state as script lines, to `emit` (a log's start). 1
 * when every line could be written. */
int fm1_app_mod_dump(fm1_app_t *a, void (*emit)(void *ctx, const char *line), void *ctx);

/* The runtime's unit code (fm1_mod.h) for an app unit id (FM1_APP_UNITS):
 * sound units, their inserts and the master slots; -1 out of range. */
int fm1_app_mod_unit(int unit);

/* ---- The arpeggiator (MIDI effects) ---------------------------------------
 * `sound` is a sound unit, 0 .. FM1_APP_SOUNDS - 1; `index` an arp
 * parameter (fm1_app_arp_engine's list, its knob order). */

/* The arp's engine description (a MIDI effect), or NULL. */
const fm1_engine_t *fm1_app_arp_engine(void);

/* An arp parameter's index by name (case insensitive), or -1. */
int fm1_app_arp_param_index(const char *name);

/* Whether a sound's arp is on; switching it, 0 (or -1 out of range, or
 * FM1_APP_SELECT_RAM when it would take the chain past the RAM budget,
 * with a popup). Bypassing ends its notes at once. An arp takes RAM only
 * while it is on (fm1_app_ram). */
int fm1_app_arp_on(const fm1_app_t *a, int sound);
int fm1_app_arp_set_on(fm1_app_t *a, int sound, int on);

/* A sound's arp parameter: set (clamped, a list's entry rounded) and read. */
void fm1_app_arp_set_param(fm1_app_t *a, int sound, int index, float value);
float fm1_app_arp_get_param(const fm1_app_t *a, int sound, int index);

/* The MIDI effect in a sound's MIDI-FX slot, the ARP slot: the arp, unless
 * ALGORITHM (or fm1_app_mfx_select) put another there. Its parameters are
 * what fm1_app_arp_set_param and fm1_app_arp_get_param reach. */
const fm1_engine_t *fm1_app_mfx_engine(const fm1_app_t *a, int sound);

/* That effect's parameter index by name (case insensitive), or -1. */
int fm1_app_mfx_param_index(const fm1_app_t *a, int sound, const char *name);

/* Puts the registry's MIDI effect `id` in a sound's MIDI-FX slot, a fresh
 * instance at its defaults, on if the slot's effect was on; the one it
 * replaces ends its notes. 0; -1 for an unknown id or sound; or
 * FM1_APP_SELECT_RAM, with a popup, when it would take the chain past the
 * RAM budget. */
int fm1_app_mfx_select(fm1_app_t *a, int sound, const char *id);

/* The stock FM-1's arp modes as presets (Up, Down, Up/Down, Down/Up,
 * Random, Played): each sets Mode and Order, putting the arp back in the
 * slot if another effect is there; then one entry for each other MIDI
 * effect of the registry, which puts that effect in the slot. The count, a
 * preset's name, applying one to a sound (0, or -1, or
 * FM1_APP_SELECT_RAM), and the preset a sound's slot is on now (-1:
 * none). */
int fm1_app_arp_preset_count(void);
const char *fm1_app_arp_preset_name(int preset);
int fm1_app_arp_preset(fm1_app_t *a, int sound, int preset);
int fm1_app_arp_preset_of(const fm1_app_t *a, int sound);

/* ---- The project key (owner, 2026-10-06) ---------------------------------
 * One key for the project: `root` 0 C .. 11 B and `scale` FM1_KEY_*
 * (fm1_engine.h). With the sequencer, the set's (fm1_seq_get_key); without
 * one, the MIDI effects' stage's. Setting it sends `key root scale` as a
 * typed command (fm1_app_seq_cmd): 0 when applied or held for the next
 * block, -1 refused (out of range, or the sequencer busy: send it again
 * after the next render). The names are the global page's. The panel steps
 * the scales in FM1_APP_KEY_ORDER: Major, Minor, the church modes in their
 * order, then Chromatic. */
#define FM1_APP_GLO_PAGES 2
int fm1_app_project_key(const fm1_app_t *a, int *scale);   /* the root; *scale the scale */
int fm1_app_set_project_key(fm1_app_t *a, int root, int scale);
const char *fm1_app_key_root_name(int root);        /* "C" .. "B" ("C#", sharps) */
const char *fm1_app_key_scale_name(int scale);      /* "Major", "Minor", ...; NULL out of range */
int fm1_app_key_scale_at(int place);                /* the scale at the panel's place, or -1 */

/* Redraw the screen if anything on it changed (or the scope is live, at most
 * once per `min_frames` of audio). Returns 1 when a->tft.px was redrawn. */
int fm1_app_draw(fm1_app_t *a, uint32_t min_frames);

/* Redraw now, logging boxes for fm1_tft_check_layout. */
void fm1_app_draw_checked(fm1_app_t *a);

/* Whether the open popup draws as a banner (audit L1: a confirmation, no
 * list, no refusal, its lines joined by spaces one line): 1 + FM1_TFT_MAIN
 * for at most 18 characters, 1 + FM1_TFT_MID for at most 27 (fm1_look.h's
 * BANNER_CHARS, _MID), that line in buf; else 0. */
int fm1_app_banner(const fm1_app_t *a, char *buf, size_t size);

/* Bytes of FM-1 RAM the current chain would use, the RAM meter's figure:
 * the engines' instances, the sequencer's (fm1_seq_size), its event
 * buffer, its pending command record, its UI state bound and click voice,
 * the modulation runtime (fm1_mod_size) while it runs, and a mix block per
 * sound unit past the first (FM1_APP_MIX_BLOCK_BYTES). */
size_t fm1_app_ram(const fm1_app_t *a);

/* What fm1_app_ram would be with registry entry `index` in `unit` (-1:
 * emptied): the RAM meter's test before a load. */
size_t fm1_app_ram_with(const fm1_app_t *a, int unit, int index);

/* `bytes` as the user sees a RAM figure (owner, 2026-10-06: memory only as
 * a percentage of the FM-1's budget, on the screen, the page and in every
 * refusal; bytes only in developer docs): a whole percentage of
 * FM1_APP_RAM_BUDGET, rounded up, so a figure past the budget, which is
 * what a refusal reports, never reads 100. The meter, GLO's RAM line and
 * the refusals all use it, and the page (app.js) rounds the same way. */
unsigned fm1_app_ram_percent(size_t bytes);
/* An engine's instance bytes at FM1_APP_RAM_RATE, as the meter counts them. */
size_t fm1_app_ram_of(const fm1_engine_t *e);

/* SAVE (stage A1). A press bumps save_gen and, while a host store is ready
 * (store_ready, set by the page once its browser storage opens: stage W1),
 * the host saves the project and calls fm1_app_saved with the result:
 * `ok` shows the L1 banner "SAVED" with the RAM figure, else the refusal
 * "NOT SAVED" and `why`. Without a store the press says there is none.
 * Nothing is ever written to a device (CLAUDE.md, the one rule). */
void fm1_app_saved(fm1_app_t *a, int ok, const char *why);

/* For the state layer (fm1_app_state.c): a message popup (`tone`
 * FM1_APP_TONE_*), each sink's engine in fm1_mod_sink_unit's order, and a
 * DX7 voice into user slot `slot` of FM6's bank, given to every FM6
 * instance (0, or -1 without FM6 or past the slots). */
void fm1_app_say(fm1_app_t *a, int tone, const char *l0, const char *l1, const char *l2);
void fm1_app_mod_units(const fm1_app_t *a, const fm1_engine_t **units);
int fm1_app_dx7_put(fm1_app_t *a, unsigned slot, const uint8_t vced[FM1_DX7_VCED_BYTES]);

/* ---- Sound units (multi-sound) --------------------------------------------
 * `sound` is 0 .. FM1_APP_SOUNDS - 1; the user's Sound 1 is 0. Stage S6
 * routes tracks with these (docs/15 §3.16). */

/* Unit ids (FM1_APP_UNITS) of sound unit `sound` and of its insert `slot`
 * (0 .. FM1_APP_INSERTS - 1); -1 out of range. */
int fm1_app_sound_unit(int sound);
int fm1_app_insert_unit(int sound, int slot);

/* A sound unit's engine, NULL when it is empty (or out of range). */
const fm1_engine_t *fm1_app_unit_engine(const fm1_app_t *a, int sound);

/* The current sound: what the keys and MIDI IN play, and HOME, PRESETS,
 * ALGORITHM and FX mode's inserts edit. Setting it returns 0, or -1 out of
 * range. */
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

/* Routes a track to a sound unit: a typed `route t 1 sound` sent as the
 * panel sends its commands (fm1_app_seq_cmd, so the harness logs it and
 * fm1-render --slots replays it). Returns fm1_app_seq_cmd's result
 * (FM1_APP_SEQ_APPLIED: in effect now; _HELD: at the next block; _BUSY:
 * send it again after the next render), or FM1_APP_SEQ_REFUSED with no
 * sequencer or an argument out of range. fm1_app_unit_of_track is the
 * sound unit a track plays, as fm1-render --slots routes it, or -1 for a
 * MIDI-routed one or one routed past the last sound unit. */
int fm1_app_unit_route(fm1_app_t *a, int track, int sound);
int fm1_app_unit_of_track(const fm1_app_t *a, int track);

/* A JSON description of every registered engine and effect (ids, names,
 * kinds, voices, credits, parameters with ranges, pages and list names).
 * Built once into a static buffer; NULL if it did not fit. */
/* ---- for the edit layer (fm1_edit.h, stage ED1) ----------------------------------
 * The panel's own edits as calls, so the editor's ops reach the same code:
 * two effect units trade places with their cables (SEL, then SELECT; 0, or
 * FM1_APP_SELECT_BAD); a rack position's kind, a module parameter's base, a
 * matrix slot and a module's move, as the RACK and MATRIX pages make them
 * (fm1_mod_ui.h: emitted as --mod lines; the runtime's results); the page
 * the panel shows, from a view's mode (FM1_VIEW_*) and its 1-based keys,
 * checked (0, or -1 with nothing changed); and what KNOB1-4 turn now: per
 * knob, kind 0 nothing, 1 unit[k]'s parameter index[k], 2 sound unit[k]'s
 * level, 3 sound unit[k]'s MIDI effect's parameter index[k], 4 rack position
 * unit[k]'s parameter index[k]. */
int fm1_app_swap_units(fm1_app_t *a, int ua, int ub);
int fm1_app_mod_edit_kind(fm1_app_t *a, unsigned pos, int kind);
int fm1_app_mod_edit_param(fm1_app_t *a, unsigned pos, unsigned index, float value);
int fm1_app_mod_edit_slot(fm1_app_t *a, unsigned i, const fm1_mod_slot_t *s);
int fm1_app_mod_edit_move(fm1_app_t *a, unsigned from, unsigned to);
int fm1_app_show(fm1_app_t *a, unsigned mode, unsigned has, const uint8_t *keys);
void fm1_app_knobs(const fm1_app_t *a, int kind[4], int unit[4], int index[4]);

const char *fm1_app_catalog_json(void);

#ifdef __cplusplus
}
#endif

#endif /* FM1_APP_H_ */
