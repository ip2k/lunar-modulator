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

#define FM1_ENGINE_API_VERSION 1u
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

typedef struct fm1_param {
  const char *name;            /* short label for the TFT, <= 12 chars */
  fm1_param_type_t type;
  float min, max, def;
  const char *const *enum_names; /* FM1_PARAM_ENUM only, (max - min + 1) names */
  uint8_t page;                /* UI page, four knobs to a page */
} fm1_param_t;

/* Clamp a set_param value into p's range; NaN becomes the default. A plain
 * `v < min ? min : ...` clamp lets NaN through, since comparisons with NaN
 * are false. */
static inline float fm1_param_clamp(const fm1_param_t *p, float v) {
  if (!(v == v)) return p->def;
  return v < p->min ? p->min : (v > p->max ? p->max : v);
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
  void (*pitch_bend)(void *self, float semitones);   /* may be NULL */
  void (*set_param)(void *self, uint16_t index, float value);
  void (*render)(void *self, float *out_lr, uint32_t frames);
} fm1_engine_t;

/* The static registry (engines/src/registry.cc). */
extern const fm1_engine_t *const fm1_engines[];
extern const size_t fm1_engine_count;
const fm1_engine_t *fm1_engine_find(const char *id);

#ifdef __cplusplus
}
#endif

#endif /* FM1_ENGINE_H_ */
