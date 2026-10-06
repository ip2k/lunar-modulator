/* kinds/mod_bounce.c -- the Bounce module kind (docs/16 §3.1): a bouncing
 * ball, after Mutable Instruments' Peaks.
 *
 * Each rising edge at TRIG (normalled to the note trigger) drops the ball
 * from Height with Velocity (bipolar: a throw up or down); it falls with
 * Gravity and loses energy at each bounce by Bounce (0: dead, 1: elastic).
 * OUT is its height, 0..1. HIT (ours) is a trigger at each bounce on the
 * floor whose rebound would rise above 1 % of full height, so the rattle at
 * the end and the ball at rest make none.
 *
 * The ball is a C port of Peaks' BouncingBall (Emilie Gillet, 2013, MIT;
 * engines/mod/mod_mi.c), sample for sample the original's output
 * (fm1-mod-mi-ref). It steps once per sample at 48 kHz, Peaks' rate, so each
 * tick runs the 48 kHz samples that fall inside it (about 35): a trigger at
 * frame F starts the sample floor(F x 48,000 / rate), and OUT is the ball's
 * height after the tick's last sample. The knobs are Peaks' four pots,
 * Gravity turned round so that up is heavier: a fall from full height takes
 * about 0.97 s at 0 and 5.3 ms at 1 (fm1-mod-kinds-test). Light and
 * elastic, the ball never quite settles: Peaks' integer rebound adds a
 * little energy at low speed, so it keeps bouncing a few percent high and
 * HIT keeps firing, as on the original. */
#include "kinds_int.h"

#include "mod_mi.h"

enum { P_GRAVITY, P_BOUNCE, P_HEIGHT, P_VELOCITY, P_COUNT };
enum { O_OUT, O_HIT };

#define MOD FM1_PARAM_MOD
static const fm1_param_t kParams[P_COUNT] = {
  { "Gravity", FM1_PARAM_FLOAT, 0.0f, 1.0f, 0.5f, NULL, 0, 1, MOD, FM1_UNIT_NONE, "Grav" },
  { "Bounce", FM1_PARAM_FLOAT, 0.0f, 1.0f, 0.8f, NULL, 0, 2, MOD, FM1_UNIT_NONE, "Bounce" },
  { "Height", FM1_PARAM_FLOAT, 0.0f, 1.0f, 1.0f, NULL, 0, 3, MOD, FM1_UNIT_NONE, "Height" },
  { "Velocity", FM1_PARAM_FLOAT, -1.0f, 1.0f, 0.0f, NULL, 0, 4, MOD, FM1_UNIT_NONE, "Vel" },
};
#undef MOD

static const fm1_port_t kGates[] = { { "Trig", FM1_PORT_GATE, FM1_UNIT_NONE, FM1_MOD_SRC_TRIG, 0 } };
static const fm1_port_t kOuts[] = { { "Out", FM1_PORT_CV_UNI, FM1_UNIT_NONE, MOD_NONE, 0 },
                                    { "Hit", FM1_PORT_GATE, FM1_UNIT_NONE, MOD_NONE, 0 } };

/* HIT: a rebound that would rise above 1 % of full height, v^2 / 2g >
 * 2^30 / 100, so v^2 > g x 21,474,836. */
#define HIT_K 21474836ll

typedef struct bounce {
  mod_mi_bounce_t ball;
  uint32_t fs;
  int16_t out;
  mod_trig_t hit;
  uint8_t pending, reserved;
} bounce_t;

static size_t bounce_size(const fm1_host_t *host) {
  (void)host;
  return sizeof(bounce_t);
}

static void *bounce_create(void *mem, const fm1_host_t *host, uint32_t seed) {
  bounce_t *s = (bounce_t *)mem;
  (void)seed;
  mod_mi_bounce_init(&s->ball);
  s->fs = kind_rate(host);
  s->out = 0;
  mod_trig_init(&s->hit);
  s->pending = s->reserved = 0;
  return s;
}

static void bounce_process(void *self, const fm1_mod_io_t *io) {
  bounce_t *s = (bounce_t *)self;
  const uint64_t t0 = kind_t0(io), t1 = t0 + FM1_MOD_TICK;
  const uint32_t r = MOD_MI_BALL_RATE;
  const uint64_t n0 = kind_native(t0, r, s->fs), n1 = kind_native(t1, r, s->fs);
  const fm1_mod_gate_t *trig = &io->gate[0];
  uint64_t rise[FM1_MOD_EDGES + 1u], a;
  unsigned n_rise = 0, e, next = 0;
  uint16_t k[4];
  k[0] = kind_u16(1.0f - io->p[P_GRAVITY]);   /* Peaks' pot: up is lighter */
  k[1] = kind_u16(io->p[P_BOUNCE]);
  k[2] = kind_u16(io->p[P_HEIGHT]);
  k[3] = (uint16_t)kind_int(mod_clampf(io->p[P_VELOCITY], -1.0f, 1.0f, 0.0f) * 32767.0f + 32768.0f,
                            0, 65535);
  mod_mi_bounce_configure(&s->ball, k);
  mod_trig_begin(&s->hit, &io->gout[O_HIT]);
  if (s->pending) rise[n_rise++] = n0;
  s->pending = 0;
  for (e = 0; e < trig->n; ++e) {
    if (!trig->ev[e].high) continue;
    a = kind_native(t0 + trig->ev[e].frame, r, s->fs);
    if (a >= n1) s->pending = 1;
    else if (n_rise < FM1_MOD_EDGES + 1u) rise[n_rise++] = a;
  }
  for (a = n0; a < n1; ++a) {
    int rising = 0, floor;
    while (next < n_rise && rise[next] <= a) {
      rising = 1;
      ++next;
    }
    s->out = mod_mi_bounce_sample(&s->ball, rising, &floor);
    if (floor && s->ball.velocity > 0 &&
        (int64_t)s->ball.velocity * s->ball.velocity > (int64_t)s->ball.gravity * HIT_K) {
      mod_trig_fire(&s->hit, &io->gout[O_HIT], kind_after_native(a, r, s->fs, t0));
    }
  }
  io->out[O_OUT] = (float)s->out * (1.0f / 32767.0f);
  mod_trig_end(&s->hit, &io->gout[O_HIT], &io->out[O_HIT]);
}

static void bounce_reset(void *self, uint32_t why) {
  bounce_t *s = (bounce_t *)self;
  if (why == FM1_MOD_RESET_PRESET) {
    s->ball.velocity = 0;
    s->ball.position = 0;
    s->out = 0;
    s->pending = 0;
  }
}

const fm1_mod_kind_t fm1_mod_kind_bounce = {
  FM1_MOD_MAGIC, FM1_MOD_API_VERSION, "bounce", 0x424E4320u /* "BNC " */, "Bounce", "BNC",
  "Ported from Mutable Instruments' Peaks bouncing ball (Emilie Gillet, MIT), byte-identical "
  "at its 48 kHz rate; the HIT output is ours.",
  kParams, P_COUNT, 1, 2, kGates, kOuts, 0, 0, 0,
  bounce_size, bounce_create, NULL, bounce_reset, bounce_process, NULL, NULL, NULL
};
