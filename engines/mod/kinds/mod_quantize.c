/* kinds/mod_quantize.c -- the Quantize module kind (docs/16 §3.6): a pitch
 * quantiser after Mutable Instruments' Braids.
 *
 * IN is a bare signal input; IN x 12 x Range semitones is the pitch above
 * or below middle C (Range 5, the default, makes IN the SEMI unit, so the
 * NOTE source or another pitch passes in tune). Quantize snaps it to the
 * nearest note of Scale (Braids' 49: the church modes, blues, pentatonics,
 * world and quarter-tone scales and 25 ragas) on Root, with Braids'
 * hysteresis: a pitch must move a little past the midpoint to change note.
 * Trans then adds whole semitones. PITCH is SEMI (semitones / 60), so into
 * a SEMI destination at 100 % it plays exact notes. Scale Off passes the
 * pitch through unquantised.
 *
 * Unpatched CLOCK: it follows IN every tick and CHANGED is a trigger at the
 * tick where the note changes. With a cable into CLOCK it takes IN only at
 * CLOCK's rising edges (a sample-and-hold quantiser) and CHANGED fires at
 * the edge's frame when the note changed.
 *
 * The quantiser is a C port of Braids' (Emilie Gillet, 2015, MIT;
 * engines/mod/mod_mi.c), call for call the original's output
 * (fm1-mod-mi-ref), with its scales; Braids keeps a held note through a
 * scale change until the input moves, this drops it. */
#include "kinds_int.h"

#include "mod_mi.h"

enum { P_SCALE, P_ROOT, P_RANGE, P_TRANS, P_IN, P_COUNT };
enum { O_PITCH, O_CHANGED };

static const char *const kScales[MOD_MI_SCALES] = {
  "Off", "Semitones", "Ionian", "Dorian", "Phrygian", "Lydian", "Mixolydian", "Aeolian",
  "Locrian", "BluesMaj", "BluesMin", "PentaMaj", "PentaMin", "Folk", "Japanese", "Gamelan",
  "Gypsy", "Arabian", "Flamenco", "WholeTone", "Pythagorean", "QuarterEb", "QuarterE",
  "QuarterEa", "Bhairav", "Gunakri", "Marwa", "Shree", "Purvi", "Bilawal", "Yaman", "Kafi",
  "Bhimpalasree", "Darbari", "Rageshree", "Khamaj", "Mimal", "Parameshwari", "Rangeshwari",
  "Gangeshwari", "Kameshwari", "PaKafi", "Natbhairav", "MKauns", "Bairagi", "BTodi",
  "Chandradeep", "KaushikTodi", "Jogeshwari"
};
static const char *const kRoots[12] = { "C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A",
                                        "A#", "B" };

#define MOD FM1_PARAM_MOD
static const fm1_param_t kParams[P_COUNT] = {
  { "Scale", FM1_PARAM_ENUM, 0.0f, 48.0f, 2.0f, kScales, 0, 1, MOD, FM1_UNIT_NONE, "Scale" },
  { "Root", FM1_PARAM_ENUM, 0.0f, 11.0f, 0.0f, kRoots, 0, 2, MOD, FM1_UNIT_NONE, "Root" },
  { "Range", FM1_PARAM_FLOAT, 0.0f, 5.0f, 5.0f, NULL, 0, 3, MOD, FM1_UNIT_NONE, "Range" },
  { "Trans", FM1_PARAM_FLOAT, -24.0f, 24.0f, 0.0f, NULL, 0, 4, MOD, FM1_UNIT_SEMI, "Trans" },
  { "In", FM1_PARAM_FLOAT, -1.0f, 1.0f, 0.0f, NULL, 1, 5, FM1_PARAM_INPUT, FM1_UNIT_NONE, "In" },
};
#undef MOD

static const fm1_port_t kGates[] = { { "Clock", FM1_PORT_GATE, FM1_UNIT_NONE, MOD_NONE, 0 } };
static const fm1_port_t kOuts[] = { { "Pitch", FM1_PORT_CV_BI, FM1_UNIT_SEMI, MOD_NONE, 0 },
                                    { "Chg", FM1_PORT_GATE, FM1_UNIT_NONE, MOD_NONE, 0 } };

typedef struct quantize {
  mod_mi_quantizer_t q;
  int32_t note;                /* the held result, 1/128 semitone */
  mod_trig_t changed;
  uint8_t scale, primed, reserved[2];
} quantize_t;

static size_t quantize_size(const fm1_host_t *host) {
  (void)host;
  return sizeof(quantize_t);
}

static void *quantize_create(void *mem, const fm1_host_t *host, uint32_t seed) {
  quantize_t *s = (quantize_t *)mem;
  (void)host;
  (void)seed;
  mod_mi_quantizer_init(&s->q);
  mod_mi_quantizer_configure(&s->q, 2);
  s->scale = 2;
  s->note = 0;
  mod_trig_init(&s->changed);
  s->primed = 0;
  s->reserved[0] = s->reserved[1] = 0;
  return s;
}

/* Quantises this tick's IN; fires CHANGED at `frame` when the note moved. */
static void take(quantize_t *s, const fm1_mod_io_t *io, unsigned frame) {
  const float *p = io->p;
  const float semis = p[P_IN] * 12.0f * p[P_RANGE];
  const int32_t pitch = (int32_t)mod_round(semis * 128.0f);
  const int32_t note = mod_mi_quantizer_process(&s->q, pitch, (int32_t)p[P_ROOT] * 128);
  if (s->primed && note != s->note) mod_trig_fire(&s->changed, &io->gout[O_CHANGED], frame);
  s->note = note;
  s->primed = 1;
}

static void quantize_process(void *self, const fm1_mod_io_t *io) {
  quantize_t *s = (quantize_t *)self;
  const fm1_mod_gate_t *clk = &io->gate[0];
  const unsigned scale = (unsigned)io->p[P_SCALE];
  float semis;
  unsigned e;
  if (scale != s->scale) {
    mod_mi_quantizer_configure(&s->q, scale);
    s->scale = (uint8_t)scale;
  }
  mod_trig_begin(&s->changed, &io->gout[O_CHANGED]);
  if (io->gate_connected & 1u) {
    for (e = 0; e < clk->n; ++e) {
      if (clk->ev[e].high) take(s, io, clk->ev[e].frame);
    }
  } else {
    take(s, io, 0);
  }
  semis = (float)s->note * (1.0f / 128.0f) + mod_round(io->p[P_TRANS]);
  io->out[O_PITCH] = mod_clampf(semis * (1.0f / 60.0f), -1.0f, 1.0f, 0.0f);
  mod_trig_end(&s->changed, &io->gout[O_CHANGED], &io->out[O_CHANGED]);
}

static void quantize_reset(void *self, uint32_t why) {
  quantize_t *s = (quantize_t *)self;
  if (why == FM1_MOD_RESET_PRESET) {
    mod_mi_quantizer_configure(&s->q, s->scale);
    s->primed = 0;
  }
}

const fm1_mod_kind_t fm1_mod_kind_quantize = {
  FM1_MOD_MAGIC, FM1_MOD_API_VERSION, "quantize", 0x514E5420u /* "QNT " */, "Quantize", "QNT",
  "Ported from Mutable Instruments' Braids quantizer and its scales (Emilie Gillet, MIT), "
  "byte-identical; as Phazerville's Quantermain uses it.",
  kParams, P_COUNT, 1, 2, kGates, kOuts, 0, 0,
  quantize_size, quantize_create, NULL, quantize_reset, quantize_process, NULL, NULL, NULL, 0
};
