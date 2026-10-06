/* mp_sah.c -- sample-and-hold and track-and-hold (fm1_mp.h). The CHANCE
 * source of the 2026-10-01 options note (§5) is this plus the LFO's random
 * shapes; DaisySP's SampleHold (Electrosmith, Paul Batchelor, MIT) has the
 * same two modes. Written from the behaviour, not from that code. */
#include "mp_int.h"

void fm1_mp_sah_init(fm1_mp_sah_t *h) {
  h->held = 0.0f;
  h->mode = FM1_MP_SAH_SAMPLE;
  h->gate = 0;
  h->pad_[0] = h->pad_[1] = 0;
}

void fm1_mp_sah_set_mode(fm1_mp_sah_t *h, int mode) {
  h->mode = (uint8_t)((mode >= 0 && mode < FM1_MP_SAH_MODE_COUNT) ? mode : FM1_MP_SAH_SAMPLE);
}

static void step(fm1_mp_sah_t *h, float in, int gate) {
  const int take = h->mode == FM1_MP_SAH_TRACK ? gate : (gate && !h->gate);
  if (take && mp_finite(in)) h->held = in;
  h->gate = (uint8_t)gate;
}

float fm1_mp_sah_process(fm1_mp_sah_t *h, float in, int gate) {
  step(h, in, gate != 0);
  return h->held;
}

float fm1_mp_sah_value(const fm1_mp_sah_t *h) {
  return h->held;
}
