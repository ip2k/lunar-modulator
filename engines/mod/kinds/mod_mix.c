/* kinds/mod_mix.c -- the Mix module kind (docs/16 §3.6): four signals with
 * gains, summed.
 *
 * SUM = clamp(Gain1 x IN1 + ... + Gain4 x IN4 + Offset), AVG the same sum
 * divided by the number of inputs with a cable (Offset added after; with
 * none, AVG is Offset), INV = -SUM. Gains run -2..2 (+-200 %), so Mix is
 * also an attenuverter, an amplifier and an offset. The IN inputs are bare
 * signal inputs: a cable at 100 % passes its source.
 *
 * Our own code, MIT. After Mutable Instruments' Links and Shades (analog),
 * the disting EX's Matrix Mixer (closed; idea only) and Phazerville's
 * AttenuateOffset and Combin8 applets (MIT); no code taken. */
#include "kinds_int.h"

enum { P_GAIN1, P_GAIN2, P_GAIN3, P_GAIN4, P_OFFSET, P_IN1, P_IN2, P_IN3, P_IN4, P_COUNT };
enum { O_SUM, O_AVG, O_INV };

#define MOD FM1_PARAM_MOD
#define IN FM1_PARAM_INPUT
static const fm1_param_t kParams[P_COUNT] = {
  { "Gain1", FM1_PARAM_FLOAT, -2.0f, 2.0f, 1.0f, NULL, 0, 1, MOD, FM1_UNIT_NONE, "Gain1" },
  { "Gain2", FM1_PARAM_FLOAT, -2.0f, 2.0f, 1.0f, NULL, 0, 2, MOD, FM1_UNIT_NONE, "Gain2" },
  { "Gain3", FM1_PARAM_FLOAT, -2.0f, 2.0f, 1.0f, NULL, 0, 3, MOD, FM1_UNIT_NONE, "Gain3" },
  { "Gain4", FM1_PARAM_FLOAT, -2.0f, 2.0f, 1.0f, NULL, 0, 4, MOD, FM1_UNIT_NONE, "Gain4" },
  { "Offset", FM1_PARAM_FLOAT, -1.0f, 1.0f, 0.0f, NULL, 1, 5, MOD, FM1_UNIT_NONE, "Ofs" },
  { "In1", FM1_PARAM_FLOAT, -1.0f, 1.0f, 0.0f, NULL, 1, 6, IN, FM1_UNIT_NONE, "In1" },
  { "In2", FM1_PARAM_FLOAT, -1.0f, 1.0f, 0.0f, NULL, 1, 7, IN, FM1_UNIT_NONE, "In2" },
  { "In3", FM1_PARAM_FLOAT, -1.0f, 1.0f, 0.0f, NULL, 1, 8, IN, FM1_UNIT_NONE, "In3" },
  { "In4", FM1_PARAM_FLOAT, -1.0f, 1.0f, 0.0f, NULL, 1, 9, IN, FM1_UNIT_NONE, "In4" },
};
#undef MOD
#undef IN

static const fm1_port_t kOuts[] = { { "Sum", FM1_PORT_CV_BI, FM1_UNIT_NONE, MOD_NONE, 0 },
                                    { "Avg", FM1_PORT_CV_BI, FM1_UNIT_NONE, MOD_NONE, 0 },
                                    { "Inv", FM1_PORT_CV_BI, FM1_UNIT_NONE, MOD_NONE, 0 } };

typedef struct mix {
  uint32_t reserved;
} mix_t;

static size_t mix_size(const fm1_host_t *host) {
  (void)host;
  return sizeof(mix_t);
}

static void *mix_create(void *mem, const fm1_host_t *host, uint32_t seed) {
  mix_t *s = (mix_t *)mem;
  (void)host;
  (void)seed;
  s->reserved = 0;
  return s;
}

static void mix_process(void *self, const fm1_mod_io_t *io) {
  const float *p = io->p;
  float sum = 0.0f;
  unsigned i, n = 0;
  (void)self;
  for (i = 0; i < 4u; ++i) {
    sum = sum + p[P_GAIN1 + i] * p[P_IN1 + i];
    n += (io->routed >> (P_IN1 + i)) & 1u;
  }
  io->out[O_SUM] = mod_clampf(sum + p[P_OFFSET], -1.0f, 1.0f, 0.0f);
  io->out[O_AVG] = mod_clampf((n ? sum / (float)n : 0.0f) + p[P_OFFSET], -1.0f, 1.0f, 0.0f);
  io->out[O_INV] = -io->out[O_SUM];
}

const fm1_mod_kind_t fm1_mod_kind_mix = {
  FM1_MOD_MAGIC, FM1_MOD_API_VERSION, "mix", 0x4D495820u /* "MIX " */, "Mix", "MIX",
  "Our own. After Mutable Instruments' Links and Shades (analog) and Phazerville's "
  "AttenuateOffset and Combin8 (MIT); no code taken.",
  kParams, P_COUNT, 0, 3, NULL, kOuts, 0, 0,
  mix_size, mix_create, NULL, NULL, mix_process, NULL, NULL, NULL, 0
};
