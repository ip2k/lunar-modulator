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
 * with each other. note_on, note_off, pitch_bend, set_param and render for an
 * instance run on the audio task, and may run while another instance is
 * created or destroyed. An engine may therefore set up shared read-only
 * tables in its first create, but must not rewrite them in later ones.
 *
 * Parameters (API v2). Each has a uid, stable for its engine: what a
 * sequencer lock, a modulation route or a preset stores, so that reordering
 * or extending a table moves nothing. The flags say what a lock or a route
 * may do with it, and abbr and unit are what a matrix row shows. A uid means
 * something only next to its engine's id. engines/README.md, "Parameters",
 * has the rules and every engine's table.
 *
 * Plain C99 so C and C++ engines (and a Schwung shim) can all implement it.
 * MIT licence, like the rest of this repository.
 */
#ifndef FM1_ENGINE_H_
#define FM1_ENGINE_H_

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define FM1_ENGINE_API_VERSION 2u
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

/* Parameter flags (API v2). They describe the parameter; the host acts on
 * them (a lock on a NOLOCK parameter is refused, fm1_seq_host.h). */
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
/* What a continuous parameter, read every block, takes. */
#define FM1_PARAM_CONTINUOUS (FM1_PARAM_SMOOTH | FM1_PARAM_MOD)

/* The unit a parameter's value is in, for display and for routes between
 * pitches (docs/16 §2.3). SEMI on a parameter is semitones; on a modulation
 * port it is semitones / 60. */
typedef enum {
  FM1_UNIT_NONE = 0,      /* a bare number (0..1 knobs, gains, indices) */
  FM1_UNIT_SEMI = 1,
  FM1_UNIT_MS = 2,
  FM1_UNIT_HZ = 3,
  FM1_UNIT_PCT = 4,       /* the value is the percentage itself, e.g. 0..100 */
  FM1_UNIT_DEG = 5
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
  uint8_t flags;               /* FM1_PARAM_* above */
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

typedef struct fm1_host {
  uint32_t api_version;
  float sample_rate;           /* 44118 on the FM-1 */
  uint32_t max_frames;         /* largest render call, 64 on the FM-1 */
} fm1_host_t;

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
