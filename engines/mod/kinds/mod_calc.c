/* kinds/mod_calc.c -- the Calc module kind (docs/16 §3.6): arithmetic on two
 * signals.
 *
 * OUT = clamp(Amount x op(A, B) + Offset), INV = -OUT. A and B are bare
 * signal inputs (a cable at 100 % passes its source). The ops:
 *   Sum A + B        Diff A - B        Mult A x B        Min, Max
 *   Mean (A + B)/2   Abs |A|           Rect max(A, 0)    Neg -A
 *   Fade A to B by Fade (0: A, 1: B)
 *   Log, Root, Square: A through the matrix's sign-preserving LOG, ROOT and
 *     SQUARE curves (33-point tables, no libm)
 *   Slope  A's rate of change: 1.0 is a change of 10 per second (0.1 in
 *     10 ms), measured tick to tick.
 * Snap rounds Offset to whole semitones (1/60, the SEMI unit), so Calc can
 * transpose a pitch in tune.
 *
 * Our own code, MIT. After Mutable Instruments' Kinks and Links (analog,
 * no code), the disting mk4's A-1 to A-5 (closed; ideas only), Phazerville's
 * Calculate applet (Jason Justian, MIT) and Music Thing Modular's Workshop
 * System Computer card 107 Scintillator (Matt Allison, MIT); no code taken
 * from any of them. */
#include "kinds_int.h"

enum { P_OP, P_AMOUNT, P_OFFSET, P_SNAP, P_FADE, P_A, P_B, P_COUNT };
enum { O_OUT, O_INV };
enum { OP_SUM, OP_DIFF, OP_MULT, OP_MIN, OP_MAX, OP_MEAN, OP_ABS, OP_RECT, OP_NEG, OP_FADE,
       OP_LOG, OP_ROOT, OP_SQUARE, OP_SLOPE, OP_COUNT };

static const char *const kOps[OP_COUNT] = { "Sum", "Diff", "Mult", "Min", "Max", "Mean", "Abs",
                                            "Rect", "Neg", "Fade", "Log", "Root", "Square",
                                            "Slope" };
static const char *const kSnap[] = { "Off", "Semi" };

#define MOD FM1_PARAM_MOD
#define IN FM1_PARAM_INPUT
static const fm1_param_t kParams[P_COUNT] = {
  { "Op", FM1_PARAM_ENUM, 0.0f, 13.0f, 0.0f, kOps, 0, 1, MOD, FM1_UNIT_NONE, "Op" },
  { "Amount", FM1_PARAM_FLOAT, -1.0f, 1.0f, 1.0f, NULL, 0, 2, MOD, FM1_UNIT_NONE, "Amt" },
  { "Offset", FM1_PARAM_FLOAT, -1.0f, 1.0f, 0.0f, NULL, 0, 3, MOD, FM1_UNIT_NONE, "Ofs" },
  { "Snap", FM1_PARAM_ENUM, 0.0f, 1.0f, 0.0f, kSnap, 0, 4, 0, FM1_UNIT_NONE, "Snap" },
  { "Fade", FM1_PARAM_FLOAT, 0.0f, 1.0f, 0.5f, NULL, 1, 5, MOD, FM1_UNIT_NONE, "Fade" },
  { "A", FM1_PARAM_FLOAT, -1.0f, 1.0f, 0.0f, NULL, 1, 6, IN, FM1_UNIT_NONE, "A" },
  { "B", FM1_PARAM_FLOAT, -1.0f, 1.0f, 0.0f, NULL, 1, 7, IN, FM1_UNIT_NONE, "B" },
};
#undef MOD
#undef IN

static const fm1_port_t kOuts[] = { { "Out", FM1_PORT_CV_BI, FM1_UNIT_NONE, MOD_NONE, 0 },
                                    { "Inv", FM1_PORT_CV_BI, FM1_UNIT_NONE, MOD_NONE, 0 } };

typedef struct calc {
  float prev_a;                /* Slope: A at the last tick */
  float per_tick;              /* Slope's scale: ticks per 0.1 s */
  uint8_t primed, reserved[3];
} calc_t;

static size_t calc_size(const fm1_host_t *host) {
  (void)host;
  return sizeof(calc_t);
}

static void *calc_create(void *mem, const fm1_host_t *host, uint32_t seed) {
  calc_t *s = (calc_t *)mem;
  (void)seed;
  s->prev_a = 0.0f;
  s->per_tick = 0.1f / kind_tick_s(kind_rate(host));
  s->primed = 0;
  s->reserved[0] = s->reserved[1] = s->reserved[2] = 0;
  return s;
}

static float maxf(float a, float b) { return a > b ? a : b; }
static float minf(float a, float b) { return a < b ? a : b; }

static void calc_process(void *self, const fm1_mod_io_t *io) {
  calc_t *s = (calc_t *)self;
  const float *p = io->p;
  const float a = p[P_A], b = p[P_B];
  float r = 0.0f, ofs = p[P_OFFSET];
  switch ((unsigned)p[P_OP]) {
    case OP_SUM: r = a + b; break;
    case OP_DIFF: r = a - b; break;
    case OP_MULT: r = a * b; break;
    case OP_MIN: r = minf(a, b); break;
    case OP_MAX: r = maxf(a, b); break;
    case OP_MEAN: r = (a + b) * 0.5f; break;
    case OP_ABS: r = a < 0.0f ? -a : a; break;
    case OP_RECT: r = maxf(a, 0.0f); break;
    case OP_NEG: r = -a; break;
    case OP_FADE: r = a + (b - a) * p[P_FADE]; break;
    case OP_LOG: r = fm1_mod_curve(FM1_MOD_CURVE_LOG, a); break;
    case OP_ROOT: r = fm1_mod_curve(FM1_MOD_CURVE_ROOT, a); break;
    case OP_SQUARE: r = fm1_mod_curve(FM1_MOD_CURVE_SQUARE, a); break;
    case OP_SLOPE: r = s->primed ? (a - s->prev_a) * s->per_tick : 0.0f; break;
    default: break;
  }
  s->prev_a = a;
  s->primed = 1;
  if (p[P_SNAP] >= 0.5f) ofs = mod_round(ofs * 60.0f) * (1.0f / 60.0f);
  r = mod_clampf(p[P_AMOUNT] * r + ofs, -1.0f, 1.0f, 0.0f);
  io->out[O_OUT] = r;
  io->out[O_INV] = -r;
}

static void calc_reset(void *self, uint32_t why) {
  calc_t *s = (calc_t *)self;
  if (why == FM1_MOD_RESET_PRESET) s->primed = 0;
}

const fm1_mod_kind_t fm1_mod_kind_calc = {
  FM1_MOD_MAGIC, FM1_MOD_API_VERSION, "calc", 0x434C4320u /* "CLC " */, "Calc", "CLC",
  "Our own. After Mutable Instruments' Kinks and Links (analog), Phazerville's Calculate "
  "(Jason Justian, MIT) and Music Thing Modular Workshop System Computer card 107 (Matt "
  "Allison, MIT); no code taken.",
  kParams, P_COUNT, 0, 2, NULL, kOuts, 0, 0,
  calc_size, calc_create, NULL, calc_reset, calc_process, NULL, NULL, NULL, 0
};
