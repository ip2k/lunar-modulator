/* mp_tool.c -- fm1-mod, the desktop test tool for the modulation primitives
 * (engines/mod/README.md). Desktop only: it reads a script of commands, runs
 * them on instances in a static pool, and prints one JSON object per line for
 * every command that reports something. tests/test_engines_mod.py drives it.
 *
 *   fm1-mod [--fill BYTE] SCRIPT|-     run a script (- for stdin)
 *   fm1-mod --sizes                    the size of every primitive's struct
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "fm1_mp.h"

#define MAX_INST 64
#define MAX_RENDER 1000000

enum { K_NONE, K_LFO, K_ENV, K_SLEW, K_SAH, K_TURING, K_CLKDIV };

typedef struct {
  char name[32];
  int kind;
  union {
    fm1_mp_lfo_t lfo;
    fm1_mp_env_t env;
    fm1_mp_slew_t slew;
    fm1_mp_sah_t sah;
    fm1_mp_turing_t turing;
    fm1_mp_clkdiv_t clkdiv;
  } u;
} inst_t;

static inst_t pool[MAX_INST];
static int fill_byte = 0;
static float rate = FM1_MP_DEFAULT_RATE;
static int line_no = 0;
static float render_buf[MAX_RENDER];
static float in_buf[MAX_RENDER];

static void die(const char *msg, const char *arg) {
  fprintf(stderr, "fm1-mod: line %d: %s%s%s\n", line_no, msg, arg ? ": " : "", arg ? arg : "");
  exit(2);
}

static void put_float(float v) {
  if (v != v || v - v != 0.0f) {
    fputs("null", stdout);
  } else {
    printf("%.9g", (double)v);
  }
}

static const char *const SHAPES[] = {"sine", "triangle", "saw_up", "saw_down", "square",
                                     "smooth", "sh", "walk", NULL};
static const char *const LFO_MODES[] = {"free", "one", "half", NULL};
static const char *const CURVES[] = {"linear", "expo", "quartic", NULL};
static const char *const LOOPS[] = {"off", "ad", "adr", NULL};
static const char *const SLEW_MODES[] = {"linear", "expo", NULL};
static const char *const SAH_MODES[] = {"sample", "track", NULL};

/* A name from the list, or any integer (to test out-of-range values). */
static int parse_enum(const char *s, const char *const *names) {
  char *end;
  long v;
  int i;
  if (!s) die("missing argument", NULL);
  for (i = 0; names[i]; ++i) {
    if (strcmp(s, names[i]) == 0) return i;
  }
  v = strtol(s, &end, 0);
  if (*end) die("unknown name", s);
  return (int)v;
}

static float parse_f(const char *s) {
  char *end;
  float v;
  if (!s) die("missing argument", NULL);
  v = strtof(s, &end);
  if (*end) die("not a number", s);
  return v;
}

static int parse_i(const char *s) {
  char *end;
  long v;
  if (!s) die("missing argument", NULL);
  v = strtol(s, &end, 0);
  if (*end) die("not an integer", s);
  return (int)v;
}

static unsigned long parse_u(const char *s) {
  char *end;
  unsigned long v;
  if (!s) die("missing argument", NULL);
  v = strtoul(s, &end, 0);
  if (*end) die("not an integer", s);
  return v;
}

static inst_t *find(const char *name) {
  int i;
  if (!name) die("missing instance name", NULL);
  for (i = 0; i < MAX_INST; ++i) {
    if (pool[i].kind != K_NONE && strcmp(pool[i].name, name) == 0) return &pool[i];
  }
  die("no such instance", name);
  return NULL;
}

static inst_t *find_kind(const char *name, int kind) {
  inst_t *x = find(name);
  if (x->kind != kind) die("wrong kind of instance for this command", name);
  return x;
}

static inst_t *create(const char *name, int kind) {
  int i;
  if (!name || strlen(name) >= sizeof pool[0].name) die("bad instance name", name);
  for (i = 0; i < MAX_INST; ++i) {
    if (pool[i].kind != K_NONE && strcmp(pool[i].name, name) == 0) die("name in use", name);
  }
  for (i = 0; i < MAX_INST; ++i) {
    if (pool[i].kind == K_NONE) {
      memset(&pool[i].u, fill_byte, sizeof pool[i].u);
      strcpy(pool[i].name, name);
      pool[i].kind = kind;
      return &pool[i];
    }
  }
  die("too many instances", name);
  return NULL;
}

static float value_of(inst_t *x) {
  switch (x->kind) {
    case K_LFO: return fm1_mp_lfo_value(&x->u.lfo);
    case K_ENV: return fm1_mp_env_value(&x->u.env);
    case K_SLEW: return fm1_mp_slew_value(&x->u.slew);
    case K_SAH: return fm1_mp_sah_value(&x->u.sah);
    case K_TURING: return fm1_mp_turing_value(&x->u.turing);
    default: die("no value for this kind", x->name); return 0.0f;
  }
}

static void print_v(float v) {
  fputs("{\"v\":", stdout);
  put_float(v);
  fputs("}\n", stdout);
}

static void print_r(const float *v, unsigned long n) {
  unsigned long i;
  fputs("{\"r\":[", stdout);
  for (i = 0; i < n; ++i) {
    if (i) putchar(',');
    put_float(v[i]);
  }
  fputs("]}\n", stdout);
}

static void print_state(inst_t *x) {
  switch (x->kind) {
    case K_LFO: {
      const fm1_mp_lfo_t *l = &x->u.lfo;
      printf("{\"phase\":%lu,\"inc\":%lu,\"inc_frac\":%lu,\"wraps\":%lu,\"done\":%d,\"owed\":%d,\"hz\":",
             (unsigned long)l->phase, (unsigned long)l->inc, (unsigned long)l->inc_frac,
             (unsigned long)l->wraps, l->done,
             l->owed);
      put_float(l->hz);
      fputs(",\"v\":", stdout);
      put_float(fm1_mp_lfo_value(l));
      fputs("}\n", stdout);
      break;
    }
    case K_ENV: {
      const fm1_mp_env_t *e = &x->u.env;
      printf("{\"seg\":%d,\"phase\":%lu,\"done\":%d,\"gate\":%d,\"segments\":%d,\"inc0\":%lu,\"v\":",
             e->seg, (unsigned long)e->phase, fm1_mp_env_done(e), e->gate, e->num_segments,
             (unsigned long)e->inc[0]);
      put_float(fm1_mp_env_value(e));
      fputs("}\n", stdout);
      break;
    }
    case K_TURING:
      printf("{\"bits\":%lu,\"gate\":%d,\"length\":%d}\n",
             (unsigned long)fm1_mp_turing_bits(&x->u.turing), fm1_mp_turing_gate(&x->u.turing),
             x->u.turing.length);
      break;
    case K_CLKDIV:
      printf("{\"phase\":%lu,\"period\":%lu,\"mul\":%lu}\n",
             (unsigned long)fm1_mp_clkdiv_phase(&x->u.clkdiv), (unsigned long)x->u.clkdiv.period,
             (unsigned long)x->u.clkdiv.mul);
      break;
    default: print_v(value_of(x)); break;
  }
}

#define ARG(i) (argc > (i) ? argv[i] : NULL)

static void run(int argc, char **argv) {
  const char *cmd = argv[0];
  if (strcmp(cmd, "rate") == 0) {
    rate = parse_f(ARG(1));
  } else if (strcmp(cmd, "lfo") == 0) {
    inst_t *x = create(ARG(1), K_LFO);
    fm1_mp_lfo_init(&x->u.lfo, rate, argc > 2 ? (uint32_t)parse_u(argv[2]) : 0u);
  } else if (strcmp(cmd, "env") == 0) {
    fm1_mp_env_init(&create(ARG(1), K_ENV)->u.env, rate);
  } else if (strcmp(cmd, "slew") == 0) {
    fm1_mp_slew_init(&create(ARG(1), K_SLEW)->u.slew, rate);
  } else if (strcmp(cmd, "sah") == 0) {
    fm1_mp_sah_init(&create(ARG(1), K_SAH)->u.sah);
  } else if (strcmp(cmd, "turing") == 0) {
    inst_t *x = create(ARG(1), K_TURING);
    fm1_mp_turing_init(&x->u.turing, argc > 2 ? (uint32_t)parse_u(argv[2]) : 0u);
  } else if (strcmp(cmd, "clkdiv") == 0) {
    inst_t *x = create(ARG(1), K_CLKDIV);
    fm1_mp_clkdiv_init(&x->u.clkdiv, (uint32_t)parse_u(ARG(2)), (uint32_t)parse_u(ARG(3)),
                       (uint32_t)parse_u(ARG(4)));
  } else if (strcmp(cmd, "shape") == 0) {
    fm1_mp_lfo_set_shape(&find_kind(ARG(1), K_LFO)->u.lfo, parse_enum(ARG(2), SHAPES));
  } else if (strcmp(cmd, "mode") == 0) {
    inst_t *x = find(ARG(1));
    if (x->kind == K_LFO) fm1_mp_lfo_set_mode(&x->u.lfo, parse_enum(ARG(2), LFO_MODES));
    else if (x->kind == K_SLEW) fm1_mp_slew_set_mode(&x->u.slew, parse_enum(ARG(2), SLEW_MODES));
    else if (x->kind == K_SAH) fm1_mp_sah_set_mode(&x->u.sah, parse_enum(ARG(2), SAH_MODES));
    else die("no mode for this kind", x->name);
  } else if (strcmp(cmd, "hz") == 0) {
    fm1_mp_lfo_set_rate(&find_kind(ARG(1), K_LFO)->u.lfo, parse_f(ARG(2)),
                        argc > 3 ? parse_f(argv[3]) : 1.0f);
  } else if (strcmp(cmd, "pw") == 0) {
    fm1_mp_lfo_set_pulse_width(&find_kind(ARG(1), K_LFO)->u.lfo, parse_f(ARG(2)));
  } else if (strcmp(cmd, "walk") == 0) {
    fm1_mp_lfo_set_walk(&find_kind(ARG(1), K_LFO)->u.lfo, parse_f(ARG(2)));
  } else if (strcmp(cmd, "start") == 0) {
    fm1_mp_lfo_set_start_phase(&find_kind(ARG(1), K_LFO)->u.lfo, parse_f(ARG(2)));
  } else if (strcmp(cmd, "seed") == 0) {
    fm1_mp_lfo_seed(&find_kind(ARG(1), K_LFO)->u.lfo, (uint32_t)parse_u(ARG(2)));
  } else if (strcmp(cmd, "sync") == 0) {
    fm1_mp_lfo_sync(&find_kind(ARG(1), K_LFO)->u.lfo, (uint32_t)parse_u(ARG(2)));
  } else if (strcmp(cmd, "reset") == 0) {
    inst_t *x = find(ARG(1));
    if (x->kind == K_LFO) fm1_mp_lfo_reset(&x->u.lfo);
    else if (x->kind == K_CLKDIV) fm1_mp_clkdiv_reset(&x->u.clkdiv);
    else if (x->kind == K_SLEW) fm1_mp_slew_reset(&x->u.slew, parse_f(ARG(2)));
    else die("no reset for this kind", x->name);
  } else if (strcmp(cmd, "adsr") == 0) {
    fm1_mp_env_set_adsr(&find_kind(ARG(1), K_ENV)->u.env, parse_f(ARG(2)), parse_f(ARG(3)),
                        parse_f(ARG(4)), parse_f(ARG(5)), parse_enum(ARG(6), CURVES),
                        parse_enum(ARG(7), LOOPS));
  } else if (strcmp(cmd, "ad") == 0) {
    fm1_mp_env_set_ad(&find_kind(ARG(1), K_ENV)->u.env, parse_f(ARG(2)), parse_f(ARG(3)),
                      parse_enum(ARG(4), CURVES), (int)parse_u(ARG(5)));
  } else if (strcmp(cmd, "config") == 0) {
    fm1_mp_env_configure(&find_kind(ARG(1), K_ENV)->u.env, parse_i(ARG(2)),
                         parse_i(ARG(3)),
                         parse_i(ARG(4)),
                         parse_i(ARG(5)));
  } else if (strcmp(cmd, "segment") == 0) {
    fm1_mp_env_set_segment(&find_kind(ARG(1), K_ENV)->u.env, parse_i(ARG(2)),
                           parse_f(ARG(3)), parse_f(ARG(4)), parse_enum(ARG(5), CURVES));
  } else if (strcmp(cmd, "startlevel") == 0) {
    fm1_mp_env_set_start_level(&find_kind(ARG(1), K_ENV)->u.env, parse_f(ARG(2)));
  } else if (strcmp(cmd, "hard") == 0) {
    fm1_mp_env_set_hard_reset(&find_kind(ARG(1), K_ENV)->u.env, (int)parse_u(ARG(2)));
  } else if (strcmp(cmd, "gate") == 0) {
    fm1_mp_env_gate(&find_kind(ARG(1), K_ENV)->u.env, (int)parse_u(ARG(2)));
  } else if (strcmp(cmd, "trigger") == 0) {
    fm1_mp_env_trigger(&find_kind(ARG(1), K_ENV)->u.env);
  } else if (strcmp(cmd, "knob") == 0) {
    print_v(fm1_mp_env_time_from_knob(parse_f(ARG(1))));
  } else if (strcmp(cmd, "times") == 0) {
    fm1_mp_slew_set_times(&find_kind(ARG(1), K_SLEW)->u.slew, parse_f(ARG(2)), parse_f(ARG(3)));
  } else if (strcmp(cmd, "length") == 0) {
    fm1_mp_turing_set_length(&find_kind(ARG(1), K_TURING)->u.turing, parse_i(ARG(2)));
  } else if (strcmp(cmd, "flip") == 0) {
    fm1_mp_turing_set_flip(&find_kind(ARG(1), K_TURING)->u.turing, parse_f(ARG(2)));
  } else if (strcmp(cmd, "proc") == 0) {
    /* proc NAME N [IN]: LFO and envelope advance N samples; the slew holds IN
     * for N samples. Prints the value. */
    inst_t *x = find(ARG(1));
    const uint32_t n = (uint32_t)parse_u(ARG(2));
    if (x->kind == K_LFO) print_v(fm1_mp_lfo_process(&x->u.lfo, n));
    else if (x->kind == K_ENV) print_v(fm1_mp_env_process(&x->u.env, n));
    else if (x->kind == K_SLEW) print_v(fm1_mp_slew_process(&x->u.slew, parse_f(ARG(3)), n));
    else die("no proc for this kind", x->name);
  } else if (strcmp(cmd, "render") == 0) {
    /* render NAME N [IN...]: per-sample values; for the slew, IN values are
     * repeated cyclically over the N samples (none: hold the target). */
    inst_t *x = find(ARG(1));
    const unsigned long n = parse_u(ARG(2));
    if (n > MAX_RENDER) die("render too long", ARG(2));
    if (x->kind == K_LFO) {
      fm1_mp_lfo_render(&x->u.lfo, render_buf, (uint32_t)n);
    } else if (x->kind == K_ENV) {
      fm1_mp_env_render(&x->u.env, render_buf, (uint32_t)n);
    } else if (x->kind == K_SLEW) {
      unsigned long i;
      const int k = argc - 3;
      for (i = 0; k > 0 && i < n; ++i) in_buf[i] = parse_f(argv[3 + (int)(i % (unsigned long)k)]);
      fm1_mp_slew_render(&x->u.slew, k > 0 ? in_buf : NULL, render_buf, (uint32_t)n);
    } else {
      die("no render for this kind", x->name);
    }
    print_r(render_buf, n);
  } else if (strcmp(cmd, "step") == 0) {
    fm1_mp_sah_t *h = &find_kind(ARG(1), K_SAH)->u.sah;
    print_v(fm1_mp_sah_process(h, parse_f(ARG(2)), (int)parse_u(ARG(3))));
  } else if (strcmp(cmd, "clock") == 0) {
    /* clock NAME [K]: K Turing clocks (values) or K clkdiv ticks (pulses). */
    inst_t *x = find(ARG(1));
    const unsigned long k = argc > 2 ? parse_u(argv[2]) : 1ul;
    unsigned long i;
    if (k > MAX_RENDER) die("too many clocks", ARG(2));
    if (x->kind == K_TURING) {
      for (i = 0; i < k; ++i) render_buf[i] = fm1_mp_turing_clock(&x->u.turing);
      print_r(render_buf, k);
    } else if (x->kind == K_CLKDIV) {
      fputs("{\"p\":[", stdout);
      for (i = 0; i < k; ++i) printf(i ? ",%lu" : "%lu", (unsigned long)fm1_mp_clkdiv_tick(&x->u.clkdiv));
      fputs("]}\n", stdout);
    } else {
      die("no clock for this kind", x->name);
    }
  } else if (strcmp(cmd, "advance") == 0) {
    fm1_mp_clkdiv_t *c = &find_kind(ARG(1), K_CLKDIV)->u.clkdiv;
    printf("{\"n\":%lu}\n", (unsigned long)fm1_mp_clkdiv_advance(c, (uint32_t)parse_u(ARG(2))));
  } else if (strcmp(cmd, "value") == 0) {
    print_v(value_of(find(ARG(1))));
  } else if (strcmp(cmd, "state") == 0) {
    print_state(find(ARG(1)));
  } else {
    die("unknown command", cmd);
  }
}

static void sizes(void) {
  printf("{\"lfo\":%lu,\"env\":%lu,\"slew\":%lu,\"sah\":%lu,\"turing\":%lu,\"clkdiv\":%lu,"
         "\"rng\":%lu}\n",
         (unsigned long)sizeof(fm1_mp_lfo_t), (unsigned long)sizeof(fm1_mp_env_t),
         (unsigned long)sizeof(fm1_mp_slew_t), (unsigned long)sizeof(fm1_mp_sah_t),
         (unsigned long)sizeof(fm1_mp_turing_t), (unsigned long)sizeof(fm1_mp_clkdiv_t),
         (unsigned long)sizeof(fm1_mp_rng_t));
}

int main(int argc, char **argv) {
  static char line[1 << 16];
  const char *path = NULL;
  FILE *f;
  int i;
  for (i = 1; i < argc; ++i) {
    if (strcmp(argv[i], "--sizes") == 0) {
      sizes();
      return 0;
    } else if (strcmp(argv[i], "--fill") == 0 && i + 1 < argc) {
      fill_byte = (int)strtol(argv[++i], NULL, 0) & 0xFF;
    } else if (!path) {
      path = argv[i];
    } else {
      fprintf(stderr, "usage: fm1-mod [--fill BYTE] SCRIPT|-  |  fm1-mod --sizes\n");
      return 2;
    }
  }
  if (!path) {
    fprintf(stderr, "usage: fm1-mod [--fill BYTE] SCRIPT|-  |  fm1-mod --sizes\n");
    return 2;
  }
  f = strcmp(path, "-") == 0 ? stdin : fopen(path, "r");
  if (!f) {
    perror(path);
    return 2;
  }
  while (fgets(line, sizeof line, f)) {
    char *args[64];
    int n = 0;
    char *tok, *hash = strchr(line, '#');
    ++line_no;
    if (hash) *hash = 0;
    for (tok = strtok(line, " \t\r\n"); tok && n < 64; tok = strtok(NULL, " \t\r\n")) args[n++] = tok;
    if (n) run(n, args);
  }
  if (f != stdin) fclose(f);
  return 0;
}
