/* meta_number_test.c -- fm1-meta-number-test: the metadata export's float
 * writer (state/fm1_meta.c, f32_text) on float32 values: every exponent's
 * edges, the values knobs reach, and random bit patterns. Prints one line a
 * value, its bits in hex and the text written; tests/test_engine_metadata.py
 * holds each line to tests/state_canon.py's number(), the canonical layout's
 * reference (the shortest decimal that reads back to the float32, in
 * ECMAScript's format). MIT licence. */
#include "../state/fm1_meta.c"

static uint32_t rng_state = 0x2545F491u;

static uint32_t next(void) {
  rng_state ^= rng_state << 13;
  rng_state ^= rng_state >> 17;
  rng_state ^= rng_state << 5;
  return rng_state;
}

static void show(uint32_t bits) {
  float v;
  char text[40];
  memcpy(&v, &bits, sizeof(v));
  if (v != v || v - v != 0.0f) return;            /* never written */
  f32_text(v, text);
  printf("%08x %s\n", (unsigned)bits, text);
}

int main(int argc, char **argv) {
  const unsigned n = argc > 1 ? (unsigned)atoi(argv[1]) : 20000u;
  unsigned i, e;
  for (e = 0; e < 255u; ++e) {                     /* each exponent's ends, both signs */
    const uint32_t lo = e << 23, hi = lo | 0x7FFFFFu;
    show(lo);
    show(lo + 1u);
    show(hi);
    show(lo | 0x80000000u);
    show(hi | 0x80000000u);
  }
  for (i = 0; i <= 1000u; ++i) {                   /* a knob's hundredths over common ranges */
    const float u = (float)i / 1000.0f;
    float v[4];
    uint32_t b;
    v[0] = u;
    v[1] = -24.0f + 48.0f * u;
    v[2] = 20.0f * (float)(1u << (i % 10u)) * u;
    v[3] = 0.03f + 3.97f * u;
    for (e = 0; e < 4u; ++e) {
      memcpy(&b, &v[e], sizeof(b));
      show(b);
    }
  }
  for (i = 0; i < n; ++i) show(next());
  return 0;
}
