/* fm1_engine.h -- the engine API of the open FM-1 firmware (docs/11 §5.2).
 *
 * One struct describes a sound generator (later also audio and MIDI effects).
 * Engines never allocate: the host asks how many bytes an instance needs,
 * provides that memory, and the engine constructs itself inside it. That keeps
 * the same code usable on a desktop, on the JieLi AC79 dev board and on the
 * FM-1, where there is no heap worth the name.
 *
 * Audio is float, stereo interleaved, overwritten (not accumulated) by render.
 * The host calls render with at most host->max_frames frames (64 on the FM-1).
 *
 * The host makes no promise about the contents of instance memory before
 * create: an engine initialises every byte it later reads. Samples are
 * nominally within +/-1. Engines emit finite samples; an effect must not stay
 * broken after a non-finite one reaches it from upstream. The host's bus
 * guard (fm1_mix_limiter.h) turns non-finite samples into silence before the
 * DAC, but only there.
 *
 * Threads: create and destroy run on one control task and never concurrently
 * with each other. note_on, note_off, pitch_bend, set_param, set_param_note
 * and render for an instance run on the audio task, and may run while
 * another instance is created or destroyed. An engine may therefore set up
 * shared read-only tables in its first create, but must not rewrite them in
 * later ones.
 *
 * Parameters (API v2). Each has a uid, stable for its engine: what a
 * sequencer lock, a modulation route or a preset stores, so that reordering
 * or extending a table moves nothing. The flags say what a lock or a route
 * may do with it, and abbr and unit are what a matrix row shows. A uid means
 * something only next to its engine's id. engines/README.md, "Parameters",
 * has the rules and every engine's table.
 *
 * Per-note offsets (API v2, optional). An engine with set_param_note
 * keeps an offset per sounding voice for each POLY parameter and for the
 * note's pitch, so a host can move one note without touching the others
 * (docs/16 §6.3). Lifetime and rules: set_param_note below and
 * engines/README.md, "Per-note offsets".
 *
 * API v3 (2026-10-05) adds, without changing what a v2 engine does:
 * flags widened to 16 bits, with LOG (the parameter law below) and the dB
 * unit; and an optional extension for effects, fm1_fx_ext_t, through which
 * a host hands an effect a key (side-chain) input, the tempo and beat
 * position, and transport events (render_ext below). engines/README.md,
 * "Engine API v3", has the rules.
 *
 * Plain C99 so C and C++ engines (and a Schwung shim) can all implement it.
 * MIT licence, like the rest of this repository.
 */
#ifndef FM1_ENGINE_H_
#define FM1_ENGINE_H_

#include <stddef.h>
#include <stdint.h>

#include "fm1_math.h"

#ifdef __cplusplus
extern "C" {
#endif

#define FM1_ENGINE_API_VERSION 3u
#define FM1_ENGINE_MAGIC 0x464D3145u /* "FM1E" */

typedef enum {
  FM1_KIND_SOUND = 1,     /* notes in, audio out: render overwrites out_lr */
  FM1_KIND_AUDIO_FX = 2,  /* audio in, audio out: render processes out_lr in
                             place (it holds the input on entry); note_on,
                             note_off and pitch_bend may be NULL */
  FM1_KIND_MIDI_FX = 3    /* reserved */
} fm1_kind_t;

typedef enum {
  FM1_PARAM_FLOAT = 0,    /* continuous, min..max */
  FM1_PARAM_ENUM = 1      /* integer 0..n-1, names in enum_names */
} fm1_param_type_t;

/* Parameter flags (API v2; 16 bits since v3, the v2 bits unchanged). They
 * describe the parameter; the host acts on them (a lock on a NOLOCK
 * parameter is refused, fm1_seq_host.h). */
#define FM1_PARAM_LATCH  0x01u /* read at note-on: a change reaches the notes that
                                  start after it, never a sounding one */
#define FM1_PARAM_SMOOTH 0x02u /* continuous and read while notes sound: the
                                  engine ramps a change over 2.5 ms of its own
                                  samples while it sounds (fm1_smooth.h,
                                  docs/15 S7b); the host only calls set_param */
#define FM1_PARAM_NOLOCK 0x04u /* a change is destructive (it rebuilds voices,
                                  clears a buffer or moves the edit focus): never
                                  locked, never modulated */
#define FM1_PARAM_MOD    0x08u /* accepts modulation (docs/16): every FLOAT has
                                  it by default, an ENUM only when it says so,
                                  and is then rounded; never with NOLOCK */
#define FM1_PARAM_INPUT  0x10u /* a bare signal input: FLOAT -1..1, default 0,
                                  hidden from the knob pages (modulation
                                  modules, docs/16) */
#define FM1_PARAM_POLY   0x20u /* takes a per-note offset (set_param_note): the
                                  engine keeps one per sounding voice. FLOAT
                                  only, always with MOD */
#define FM1_PARAM_LOG    0x40u /* API v3: pitch- or time-like, FLOAT with min > 0
                                  (Hz or ms): stored, shown and saved in its
                                  unit, but it moves on a log scale, in octaves
                                  and ratios (the LOG law below) */
/* 0x80 is kept for KEYSRC (the side-chain stage: a key source the host
 * owns). Bits 0x0100-0x8000 are free. */
/* What a continuous parameter, read every block, takes. */
#define FM1_PARAM_CONTINUOUS (FM1_PARAM_SMOOTH | FM1_PARAM_MOD)
/* ...and a continuous pitch- or time-like one (a cutoff, a release). */
#define FM1_PARAM_CONTINUOUS_LOG (FM1_PARAM_CONTINUOUS | FM1_PARAM_LOG)

/* The unit a parameter's value is in, for display and for routes between
 * pitches (docs/16 §2.3). SEMI on a parameter is semitones; on a modulation
 * port it is semitones / 60. */
typedef enum {
  FM1_UNIT_NONE = 0,      /* a bare number (0..1 knobs, gains, indices) */
  FM1_UNIT_SEMI = 1,
  FM1_UNIT_MS = 2,
  FM1_UNIT_HZ = 3,
  FM1_UNIT_PCT = 4,       /* the value is the percentage itself, e.g. 0..100 */
  FM1_UNIT_DEG = 5,
  FM1_UNIT_DB = 6         /* API v3: decibels (a level, a gain, a threshold) */
} fm1_unit_t;

/* The largest uid; 0 is "no parameter". Uids fit 12 bits, so a lock target
 * can carry a 4-bit space beside one (docs/12 §5.3). */
#define FM1_PARAM_UID_MAX 0x0FFFu

typedef struct fm1_param {
  const char *name;            /* short label for the TFT, <= 12 chars */
  fm1_param_type_t type;
  float min, max, def;
  const char *const *enum_names; /* FM1_PARAM_ENUM only, (max - min + 1) names */
  uint8_t page;                /* UI page, four knobs to a page */
  /* API v2 */
  uint16_t uid;                /* 1..FM1_PARAM_UID_MAX, unique in the engine and
                                  never reused for another meaning */
  uint16_t flags;              /* FM1_PARAM_* above (8 bits in API v2) */
  uint8_t unit;                /* fm1_unit_t */
  const char *abbr;            /* <= 6 characters, for matrix rows; never NULL */
} fm1_param_t;

/* Clamp a set_param value into p's range; NaN becomes the default. A plain
 * `v < min ? min : ...` clamp lets NaN through, since comparisons with NaN
 * are false. */
static inline float fm1_param_clamp(const fm1_param_t *p, float v) {
  if (!(v == v)) return p->def;
  return v < p->min ? p->min : (v > p->max ? p->max : v);
}

/* Whether a sequencer lane may lock p. */
static inline int fm1_param_lockable(const fm1_param_t *p) {
  return !(p->flags & FM1_PARAM_NOLOCK);
}

/* Whether a modulation route may reach p: MOD and not NOLOCK. */
static inline int fm1_param_modulatable(const fm1_param_t *p) {
  return (p->flags & (FM1_PARAM_MOD | FM1_PARAM_NOLOCK)) == FM1_PARAM_MOD;
}

/* ---- The LOG law (API v3) -------------------------------------------------
 * A parameter's position u, 0..1, is where it sits on its knob. For a LOG
 * parameter u = log2(v / min) / log2(max / min); for any other FLOAT it is
 * (v - min) / (max - min). The value stays the stored, shown and saved
 * unit (Hz, ms); the position is what moves:
 *   - a knob detent moves u by 1/100 (1.2 semitones on a 20 Hz..18 kHz
 *     cutoff), and a bar shows u;
 *   - a sequencer lock's 7-bit value v7 is u = v7 / 127 (fm1_seq_host.h);
 *   - a modulation route adds amount x signal x log2(max / min) octaves,
 *     the same share of the knob a linear parameter moves, and the value
 *     is base x 2^(sum), clamped. The octave rule: a SEMI source (NOTE, a
 *     quantizer's pitch) into a LOG destination moves it by amount x signal
 *     x 60 semitones, as into a SEMI one, so NOTE at +100 % into a cutoff
 *     tracks the keys one octave per octave (docs/16 §2.3).
 * libm-free (fm1_math.h), so every build computes the same bits. Engines
 * need none of it: they receive values in their own unit. */

/* Whether p moves on the LOG law: the flag on a FLOAT with 0 < min < max
 * (tests/test_engine_params.py holds every LOG parameter to that). */
static inline int fm1_param_is_log(const fm1_param_t *p) {
  return (p->flags & FM1_PARAM_LOG) && p->type == FM1_PARAM_FLOAT && p->min > 0.0f &&
         p->max > p->min;
}

/* Octaves from min to max, log2(max / min), for a LOG parameter. */
static inline float fm1_param_octaves(const fm1_param_t *p) {
  return fm1_log2f(p->max / p->min);
}

/* p's position for value v, 0..1: log for LOG, else linear (an ENUM's
 * entries spread evenly). v is clamped first (NaN is the default). */
static inline float fm1_param_pos(const fm1_param_t *p, float v) {
  float u;
  v = fm1_param_clamp(p, v);
  if (!(p->max > p->min)) return 0.0f;
  if (fm1_param_is_log(p)) {
    u = fm1_log2f(v / p->min);
    u = u / fm1_param_octaves(p);
  } else {
    u = (v - p->min) / (p->max - p->min);
  }
  return u < 0.0f ? 0.0f : (u > 1.0f ? 1.0f : u);
}

/* The value at position u (clamped to 0..1, NaN is 0): exactly min at 0
 * and max at 1. For a LOG parameter min x 2^(u x octaves), else min + u x
 * (max - min); an ENUM is not rounded here. */
static inline float fm1_param_at(const fm1_param_t *p, float u) {
  float v;
  if (!(u > 0.0f)) return p->min;
  if (u >= 1.0f) return p->max;
  if (fm1_param_is_log(p)) {
    v = u * fm1_param_octaves(p);
    v = fm1_exp2f(v);
    v = p->min * v;
  } else {
    v = u * (p->max - p->min);
    v = p->min + v;
  }
  return v < p->min ? p->min : (v > p->max ? p->max : v);
}

/* A LOG parameter's value `base` moved by `octaves` (a route's sum):
 * base x 2^octaves, clamped as set_param clamps. */
static inline float fm1_param_log_shift(const fm1_param_t *p, float base, float octaves) {
  float v = fm1_exp2f(octaves);
  v = base * v;
  return fm1_param_clamp(p, v);
}

/* Per-note offsets (API v2, set_param_note below). */

/* set_param_note's index for the note's own pitch: an offset in semitones,
 * added after the key and the pitch bend. No parameter has this index. */
#define FM1_PARAM_NOTE_PITCH 0xFFFFu
/* A per-note pitch offset is clamped to +/- this many semitones, the pitch
 * bend's range. */
#define FM1_NOTE_PITCH_MAX 48.0f

/* Whether a per-note offset may reach p: POLY, and modulatable. */
static inline int fm1_param_poly(const fm1_param_t *p) {
  return (p->flags & FM1_PARAM_POLY) && fm1_param_modulatable(p);
}

/* A per-note offset as an engine keeps it. NaN is 0, no offset (as NaN is
 * the default for set_param). Beyond the parameter's span, max - min, the
 * sum is at an end whatever the base, so the offset is cut to the span:
 * +/-inf then pin the parameter at max or min, as they do through
 * set_param. p NULL: the note's pitch, cut to +/-FM1_NOTE_PITCH_MAX. */
static inline float fm1_param_note_offset(const fm1_param_t *p, float offset) {
  const float span = p ? p->max - p->min : FM1_NOTE_PITCH_MAX;
  if (!(offset == offset)) return 0.0f;
  return offset < -span ? -span : (offset > span ? span : offset);
}

/* The value a voice plays: its base (from set_param) plus its offset,
 * clamped as set_param clamps. */
static inline float fm1_param_note_value(const fm1_param_t *p, float base, float offset) {
  return fm1_param_clamp(p, base + offset);
}

typedef struct fm1_host {
  uint32_t api_version;
  float sample_rate;           /* 44118 on the FM-1 */
  uint32_t max_frames;         /* largest render call, 64 on the FM-1 */
} fm1_host_t;

/* ---- The effect extension (API v3, optional) ------------------------------
 * What a host tells an effect about the piece of a block it renders,
 * besides the audio. An effect that wants it sets fx_wants and provides
 * render_ext (fm1_engine_t, below); the host then calls render_ext, never
 * render, with an fm1_fx_ext_t filled for that piece. A v2 effect, and any
 * engine with render_ext NULL, is called through render exactly as before.
 *
 * Wants. TEMPO: the host splits the effect's render at the first frame of
 * every beat and marks it FM1_FX_EV_BEAT. TRANSPORT: it splits at every
 * Start and Stop of the sequencer and marks them. KEY: the effect reads
 * key_lr; a host offers a key source for it (the side-chain stage; until
 * then every host passes NULL). Every field is filled whatever the effect
 * asked for; events only carry what it asked for, and always at the first
 * frame of a piece, so they land on the same frames at any block size. An
 * effect that acts at a beat uses FM1_FX_EV_BEAT, never a phase it runs
 * forward itself, which would round differently with the pieces.
 *
 * The key. key_lr is stereo interleaved, valid for exactly `frames`
 * frames of this call, read-only, never aliases io_lr, and is never kept
 * past the call (so the instance's size is the same at 32 and 64 bits).
 * NULL means the effect's own input is its key: the output is then what it
 * would be with a copy of the input passed as the key, bit for bit. A host
 * guards a key as it guards an input (no NaN or infinity reaches it).
 *
 * Position. beat and phase are the sequencer's position at the piece's
 * first frame, exact (from its integer clock), 96 ticks to the beat: a
 * beat starts at the frame where the sequencer services tick 96 k, the
 * frame its step-0 notes and its metronome sound on. Between Start and the
 * first tick, and while stopped, both are 0. bpm is the sequencer's tempo,
 * running or not (it is the set tempo while stopped), or a host's own
 * tempo without a sequencer. */
#define FM1_FX_WANT_KEY 0x01u          /* reads key_lr */
#define FM1_FX_WANT_TEMPO 0x02u        /* splits and FM1_FX_EV_BEAT at each beat */
#define FM1_FX_WANT_TRANSPORT 0x04u    /* splits and events at Start and Stop */

/* Events at a piece's first frame (fm1_fx_ext_t.events). At one frame
 * they happen in this order: STOP, START, BEAT. */
#define FM1_FX_EV_STOP 0x01u           /* the transport stopped (TRANSPORT) */
#define FM1_FX_EV_START 0x02u          /* it started from the top: drop tails,
                                          restart phases (TRANSPORT) */
#define FM1_FX_EV_BEAT 0x04u           /* beat `beat` starts here (TEMPO) */
#define FM1_FX_EV_RESET 0x08u          /* drop every tail: a preset load, a
                                          panic (any effect with render_ext;
                                          the hosts here send none yet) */

typedef struct fm1_fx_ext {
  const float *key_lr;         /* the key, or NULL for the effect's own input */
  float bpm;                   /* tempo, beats a minute (20..300) */
  float phase;                 /* how far into beat `beat`, 0 <= phase < 1 */
  uint32_t beat;               /* beats since the last Start */
  uint8_t running;             /* 1 while the transport runs */
  uint8_t events;              /* FM1_FX_EV_* at this piece's first frame */
  uint8_t reserved[2];         /* 0 */
} fm1_fx_ext_t;

typedef struct fm1_engine {
  uint32_t magic;              /* FM1_ENGINE_MAGIC */
  uint32_t api_version;        /* FM1_ENGINE_API_VERSION */
  fm1_kind_t kind;
  const char *id;              /* stable identifier, e.g. "macro" */
  const char *name;            /* display name */
  const char *credits;         /* upstream code and licence, shown in About */
  const fm1_param_t *params;
  uint16_t n_params;
  uint8_t max_voices;          /* polyphony the engine was built for */

  /* Bytes (aligned to 16) the host must provide for one instance. */
  size_t (*instance_size)(const fm1_host_t *host);
  /* Construct an instance inside mem; returns the instance handle, or NULL
   * if the engine refuses this host (the Schwung shim refuses a second sample
   * rate). The host must not call anything else on a NULL instance. */
  void *(*create)(void *mem, const fm1_host_t *host);
  void (*destroy)(void *self);

  void (*note_on)(void *self, uint8_t key, uint8_t velocity);   /* NULL for FX */
  void (*note_off)(void *self, uint8_t key);                     /* NULL for FX */
  void (*pitch_bend)(void *self, float semitones);   /* may be NULL; the host
                                   * passes finite values within +/-48 */
  void (*set_param)(void *self, uint16_t index, float value);
  void (*render)(void *self, float *out_lr, uint32_t frames);

  /* API v2, optional: NULL when the engine has no per-note offsets. Sets the
   * offset, in the parameter's own units, that the voice sounding `key` adds
   * to the base value set_param gave parameter `index` (a POLY parameter),
   * or, with index FM1_PARAM_NOTE_PITCH, to the voice's pitch in semitones.
   * A call replaces that voice's previous offset for the index; it does not
   * add to it. The voice plays fm1_param_note_value(base, offset), and a
   * base that moves keeps the offset on top. Offsets pass through
   * fm1_param_note_offset (NaN is 0). A call takes effect where set_param's
   * would, so output does not depend on the host's block size.
   * Lifetime: the offsets belong to the voice. note_on starts the voice for
   * its key at 0 (a host sends a new note's offsets after note_on, at the
   * same frame); note_off keeps them, so the release is moved too; a voice
   * that is stolen or ends drops them. A call for a key no voice sounds is
   * ignored, not kept for a later note. Every voice sounding the key takes
   * it (the engines here retrigger a key in its own voice, so one does).
   * Any other index is ignored. Same thread as set_param. */
  void (*set_param_note)(void *self, uint8_t key, uint16_t index, float offset);

  /* API v3, optional: effects only (FM1_KIND_AUDIO_FX); 0 and NULL for
   * none. With render_ext set, a host calls it in place of render, with
   * the extension above filled for the piece; fx_wants (FM1_FX_WANT_*)
   * says what the effect reads and where the host must split. render stays
   * defined: called directly, it behaves as render_ext with a NULL key, no
   * events and the transport stopped at the last tempo seen. Same thread as
   * render. */
  uint32_t fx_wants;
  void (*render_ext)(void *self, float *io_lr, uint32_t frames, const fm1_fx_ext_t *ext);
} fm1_engine_t;

/* The index of e's parameter with this uid, or -1 (uid 0 included). */
static inline int fm1_param_index(const fm1_engine_t *e, uint16_t uid) {
  uint16_t i;
  if (!e || !uid) return -1;
  for (i = 0; i < e->n_params; ++i) {
    if (e->params[i].uid == uid) return (int)i;
  }
  return -1;
}

/* The static registry (engines/src/registry.cc). */
extern const fm1_engine_t *const fm1_engines[];
extern const size_t fm1_engine_count;
const fm1_engine_t *fm1_engine_find(const char *id);

#ifdef __cplusplus
}
#endif

#endif /* FM1_ENGINE_H_ */
