/* arp_tool.c -- fm1-arp: runs the arpeggiator core alone, for tests.
 *
 *   fm1-arp --list
 *   fm1-arp [--script FILE] [--block N] [--cap N] [--ppqn N] [--fill BYTE]
 *           [--end FRAME] [--log FILE]
 *
 * Reads a timed script (FILE, or stdin), plays it through fm1_arp in blocks
 * of N frames (64 by default) with an output buffer of --cap events (64),
 * and writes one JSON line per output event with its absolute frame, then a
 * summary line. Note-offs that a small --cap deferred past the end go out in
 * empty calls after it, one block apart. --fill sets the instance memory to BYTE before create.
 * --list prints the parameters, the enum names, the rates and both rhythm
 * tables as JSON.
 *
 * Script lines ('#' starts a comment):
 *   @FRAME on KEY VEL [seq]    @FRAME off KEY [seq]    @FRAME sus 0|1
 *   @FRAME step                @FRAME reset            @FRAME flush
 *   @FRAME panic               @FRAME set NAME VALUE   @FRAME stop
 *   @FRAME run POS             @FRAME halt
 *   clock START NUM DEN COUNT  ticks at START + floor(i * NUM / DEN), i < COUNT
 * NAME is a parameter name (fm1-arp --list); VALUE is a number or, for
 * mode, order, oct_mode and rate, a name. `seq` marks a note the
 * sequencer's (FM1_MIDI_SRC_SEQ), which `stop` (FM1_ARP_EV_STOP) lets go.
 * `run POS` says the host's sequencer runs from FRAME, its first tick there
 * or later being tick POS from its Start (fm1_arp_process_at: the steps
 * lock to that grid), and `halt` that it stopped; a block is cut at their
 * frames. Events keep script order at one frame and come before a tick at
 * the same frame, as fm1_arp_process() takes them. A note out of the
 * sequencer's keys has "seq": 1 in its line. MIT licence.
 */
#include "fm1_arp.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct { uint32_t frame, seq; fm1_arp_ev_t ev; } sev_t;
typedef struct { uint32_t frame; int running; uint64_t pos; } run_t;   /* run, halt */

static run_t g_run[256];
static size_t g_nrun;

static sev_t *g_ev;
static size_t g_nev, g_capev;
static uint32_t *g_tick;
static size_t g_ntick, g_captick;

static void usage(void) {
  fputs("usage: fm1-arp --list\n"
        "       fm1-arp [--script FILE] [--block N] [--cap N] [--ppqn N] [--fill BYTE]\n"
        "               [--end FRAME] [--log FILE]\n", stderr);
}

static void die(const char *msg, unsigned line) {
  fprintf(stderr, "fm1-arp: %s (line %u)\n", msg, line);
  exit(2);
}

static void add_ev(uint32_t frame, uint8_t kind, uint8_t a, uint16_t b) {
  if (g_nev == g_capev) {
    g_capev = g_capev ? 2 * g_capev : 256;
    g_ev = (sev_t *)realloc(g_ev, g_capev * sizeof *g_ev);
    if (!g_ev) die("out of memory", 0);
  }
  g_ev[g_nev].frame = frame;
  g_ev[g_nev].seq = (uint32_t)g_nev;
  g_ev[g_nev].ev.frame = 0;
  g_ev[g_nev].ev.kind = kind;
  g_ev[g_nev].ev.a = a;
  g_ev[g_nev].ev.b = b;
  ++g_nev;
}

static void add_tick(uint32_t frame) {
  if (g_ntick == g_captick) {
    g_captick = g_captick ? 2 * g_captick : 1024;
    g_tick = (uint32_t *)realloc(g_tick, g_captick * sizeof *g_tick);
    if (!g_tick) die("out of memory", 0);
  }
  g_tick[g_ntick++] = frame;
}

static int cmp_ev(const void *x, const void *y) {
  const sev_t *a = (const sev_t *)x, *b = (const sev_t *)y;
  if (a->frame != b->frame) return a->frame < b->frame ? -1 : 1;
  return a->seq < b->seq ? -1 : a->seq > b->seq;
}

static int cmp_run(const void *x, const void *y) {
  const run_t *a = (const run_t *)x, *b = (const run_t *)y;
  return a->frame < b->frame ? -1 : a->frame > b->frame;
}

static int cmp_u32(const void *x, const void *y) {
  const uint32_t a = *(const uint32_t *)x, b = *(const uint32_t *)y;
  return a < b ? -1 : a > b;
}

static int param_id(const char *name) {
  unsigned i;
  for (i = 0; i < FM1_ARP_P_COUNT; ++i) {
    if (!strcmp(fm1_arp_param_info(i)->name, name)) return (int)i;
  }
  return -1;
}

static int enum_value(unsigned id, const char *v) {
  unsigned i;
  const char *(*fn)(unsigned) = NULL;
  char *end;
  long n = strtol(v, &end, 0);
  if (*v && !*end) return (int)n;
  switch (id) {
    case FM1_ARP_P_MODE: fn = fm1_arp_mode_name; break;
    case FM1_ARP_P_ORDER: fn = fm1_arp_order_name; break;
    case FM1_ARP_P_OCT_MODE: fn = fm1_arp_oct_mode_name; break;
    case FM1_ARP_P_RATE: fn = fm1_arp_rate_name; break;
    default: return -1;
  }
  for (i = 0; fn(i); ++i) {
    if (!strcmp(fn(i), v)) return (int)i;
  }
  return -1;
}

static void parse(FILE *f) {
  char line[512];
  unsigned ln = 0;
  while (fgets(line, sizeof line, f)) {
    char *hash = strchr(line, '#');
    char w[5][64];
    int n;
    ++ln;
    if (hash) *hash = 0;
    n = sscanf(line, "%63s %63s %63s %63s %63s", w[0], w[1], w[2], w[3], w[4]);
    if (n <= 0) continue;
    if (!strcmp(w[0], "clock")) {
      unsigned long start, num, den, count, i;
      if (n != 5) die("clock START NUM DEN COUNT", ln);
      start = strtoul(w[1], NULL, 0);
      num = strtoul(w[2], NULL, 0);
      den = strtoul(w[3], NULL, 0);
      count = strtoul(w[4], NULL, 0);
      if (!den) die("clock DEN is 0", ln);
      for (i = 0; i < count; ++i) {
        add_tick((uint32_t)(start + (unsigned long long)i * num / den));
      }
    } else if (w[0][0] == '@') {
      const uint32_t frame = (uint32_t)strtoul(w[0] + 1, NULL, 0);
      if (n < 2) die("@FRAME VERB", ln);
      if (!strcmp(w[1], "on")) {
        const int seq = n == 5 && !strcmp(w[4], "seq");
        if (n != 4 && !seq) die("on KEY VEL [seq]", ln);
        add_ev(frame, FM1_ARP_EV_NOTE_ON, (uint8_t)atoi(w[2]),
               (uint16_t)(seq ? FM1_MIDI_EV_B(atoi(w[3]), FM1_MIDI_SRC_SEQ) : atoi(w[3])));
      } else if (!strcmp(w[1], "off")) {
        const int seq = n == 4 && !strcmp(w[3], "seq");
        if (n != 3 && !seq) die("off KEY [seq]", ln);
        add_ev(frame, FM1_ARP_EV_NOTE_OFF, (uint8_t)atoi(w[2]),
               (uint16_t)(seq ? FM1_MIDI_EV_B(0, FM1_MIDI_SRC_SEQ) : 0));
      } else if (!strcmp(w[1], "stop")) {
        add_ev(frame, FM1_ARP_EV_STOP, 0, 0);
      } else if (!strcmp(w[1], "run") || !strcmp(w[1], "halt")) {
        const int run = !strcmp(w[1], "run");
        if (run ? n != 3 : n != 2) die("run POS, or halt", ln);
        if (g_nrun == sizeof g_run / sizeof g_run[0]) die("too many run and halt lines", ln);
        g_run[g_nrun].frame = frame;
        g_run[g_nrun].running = run;
        g_run[g_nrun].pos = run ? strtoull(w[2], NULL, 0) : 0u;
        ++g_nrun;
      } else if (!strcmp(w[1], "sus")) {
        if (n != 3) die("sus 0|1", ln);
        add_ev(frame, FM1_ARP_EV_SUSTAIN, 0, (uint16_t)atoi(w[2]));
      } else if (!strcmp(w[1], "step")) {
        add_ev(frame, FM1_ARP_EV_STEP, 0, 0);
      } else if (!strcmp(w[1], "reset")) {
        add_ev(frame, FM1_ARP_EV_RESET, 0, 0);
      } else if (!strcmp(w[1], "flush")) {
        add_ev(frame, FM1_ARP_EV_FLUSH, 0, 0);
      } else if (!strcmp(w[1], "panic")) {
        add_ev(frame, FM1_ARP_EV_PANIC, 0, 0);
      } else if (!strcmp(w[1], "set")) {
        int id, v;
        if (n != 4) die("set NAME VALUE", ln);
        id = param_id(w[2]);
        if (id < 0) die("unknown parameter", ln);
        v = enum_value((unsigned)id, w[3]);
        if (v < 0) die("bad value", ln);
        add_ev(frame, FM1_ARP_EV_PARAM, (uint8_t)id, (uint16_t)v);
      } else {
        die("unknown verb", ln);
      }
    } else {
      die("a line starts with @FRAME or clock", ln);
    }
  }
}

static void print_list(void) {
  unsigned i, len, fill;
  printf("{\"size\": %u, \"params\": [", (unsigned)fm1_arp_size());
  for (i = 0; i < FM1_ARP_P_COUNT; ++i) {
    const fm1_arp_param_info_t *p = fm1_arp_param_info(i);
    printf("%s{\"id\": %u, \"name\": \"%s\", \"min\": %u, \"max\": %u, \"def\": %u}", i ? ", " : "",
           i, p->name, p->min, p->max, p->def);
  }
  printf("], \"modes\": [");
  for (i = 0; fm1_arp_mode_name(i); ++i) printf("%s\"%s\"", i ? ", " : "", fm1_arp_mode_name(i));
  printf("], \"orders\": [");
  for (i = 0; fm1_arp_order_name(i); ++i) printf("%s\"%s\"", i ? ", " : "", fm1_arp_order_name(i));
  printf("], \"oct_modes\": [");
  for (i = 0; fm1_arp_oct_mode_name(i); ++i) printf("%s\"%s\"", i ? ", " : "", fm1_arp_oct_mode_name(i));
  printf("], \"rates\": [");
  for (i = 0; fm1_arp_rate_name(i); ++i) {
    printf("%s{\"name\": \"%s\", \"ticks96\": %u}", i ? ", " : "", fm1_arp_rate_name(i),
           fm1_arp_rate_ticks96(i));
  }
  printf("], \"patterns\": [");
  for (i = 0; i <= 22u; ++i) printf("%s%u", i ? ", " : "", fm1_arp_pattern_mask(i));
  printf("], \"euclid\": [");
  for (len = 1; len <= 32u; ++len) {
    printf("%s[", len > 1u ? ", " : "");
    for (fill = 0; fill < 32u; ++fill) printf("%s%lu", fill ? ", " : "", (unsigned long)fm1_arp_euclid_mask(len, fill));
    printf("]");
  }
  printf("]}\n");
}

int main(int argc, char **argv) {
  const char *script = NULL, *log = NULL;
  unsigned long block = 64, cap = 64, ppqn = 96, fill = 0, end = 0;
  int have_end = 0, i;
  FILE *in, *out;
  void *mem;
  fm1_arp_t *arp;
  fm1_arp_ev_t *ibuf, *obuf;
  uint16_t *tbuf;
  size_t ie = 0, it = 0, ir = 0;
  uint32_t start;
  int running = 0;
  uint64_t pos = 0;   /* while running: the next tick's place on the grid */
  fm1_arp_stats_t st;
  unsigned long long n_on = 0, n_off = 0;

  for (i = 1; i < argc; i += 2) {
    const char *a = argv[i];
    const char *v = i + 1 < argc ? argv[i + 1] : NULL;
    if (!strcmp(a, "--list")) { print_list(); return 0; }
    if (!v) { usage(); return 2; }
    if (!strcmp(a, "--script")) script = v;
    else if (!strcmp(a, "--log")) log = v;
    else if (!strcmp(a, "--block")) block = strtoul(v, NULL, 0);
    else if (!strcmp(a, "--cap")) cap = strtoul(v, NULL, 0);
    else if (!strcmp(a, "--ppqn")) ppqn = strtoul(v, NULL, 0);
    else if (!strcmp(a, "--fill")) fill = strtoul(v, NULL, 0);
    else if (!strcmp(a, "--end")) { end = strtoul(v, NULL, 0); have_end = 1; }
    else { usage(); return 2; }
  }
  if (block < 1 || block > 65535u) { fputs("fm1-arp: --block is 1..65535\n", stderr); return 2; }

  in = script && strcmp(script, "-") ? fopen(script, "r") : stdin;
  if (!in) { perror(script); return 2; }
  parse(in);
  if (in != stdin) fclose(in);
  if (g_nev) qsort(g_ev, g_nev, sizeof *g_ev, cmp_ev);
  if (g_ntick) qsort(g_tick, g_ntick, sizeof *g_tick, cmp_u32);
  if (g_nrun) qsort(g_run, g_nrun, sizeof *g_run, cmp_run);   /* not stable: one a frame */
  if (!have_end) {
    if (g_nev && g_ev[g_nev - 1].frame >= end) end = g_ev[g_nev - 1].frame + 1ul;
    if (g_ntick && g_tick[g_ntick - 1] >= end) end = g_tick[g_ntick - 1] + 1ul;
  }

  out = log ? fopen(log, "w") : stdout;
  if (!out) { perror(log); return 2; }
  mem = malloc(fm1_arp_size());
  ibuf = (fm1_arp_ev_t *)malloc((g_nev ? g_nev : 1) * sizeof *ibuf);
  tbuf = (uint16_t *)malloc((g_ntick ? g_ntick : 1) * sizeof *tbuf);
  obuf = (fm1_arp_ev_t *)malloc((cap ? cap : 1) * sizeof *obuf);
  if (!mem || !ibuf || !tbuf || !obuf) die("out of memory", 0);
  memset(mem, (int)(fill & 0xFFu), fm1_arp_size());
  arp = fm1_arp_create(mem, (uint16_t)ppqn);

  for (start = 0; start < end;) {
    uint32_t stop = end - start < block ? (uint32_t)end : start + (uint32_t)block;
    uint32_t ni = 0, nt = 0, n, k;
    for (; ir < g_nrun && g_run[ir].frame <= start; ++ir) {
      running = g_run[ir].running;
      pos = g_run[ir].pos;
    }
    if (ir < g_nrun && g_run[ir].frame < stop) stop = g_run[ir].frame;   /* a block ends there */
    while (ie < g_nev && g_ev[ie].frame < stop) {
      ibuf[ni] = g_ev[ie].ev;
      ibuf[ni].frame = (uint16_t)(g_ev[ie].frame - start);
      ++ni;
      ++ie;
    }
    while (it < g_ntick && g_tick[it] < stop) {
      tbuf[nt++] = (uint16_t)(g_tick[it] - start);
      ++it;
    }
    n = fm1_arp_process_at(arp, ibuf, ni, tbuf, nt, running, pos, obuf, (uint32_t)cap);
    if (running) pos += nt;
    for (k = 0; k < n; ++k) {
      const fm1_arp_ev_t *e = &obuf[k];
      const char *seq = FM1_MIDI_EV_SRC(e->b) == FM1_MIDI_SRC_SEQ ? ", \"seq\": 1" : "";
      if (e->kind == FM1_ARP_EV_NOTE_ON) {
        fprintf(out, "{\"frame\": %lu, \"kind\": \"on\", \"key\": %u, \"vel\": %u%s}\n",
                (unsigned long)(start + e->frame), e->a, FM1_MIDI_EV_VEL(e->b), seq);
        ++n_on;
      } else {
        fprintf(out, "{\"frame\": %lu, \"kind\": \"off\", \"key\": %u%s}\n",
                (unsigned long)(start + e->frame), e->a, seq);
        ++n_off;
      }
    }
    start = stop;
  }
  /* Note-offs deferred by a small --cap go out in the calls that follow. */
  for (;;) {
    const uint32_t n = fm1_arp_process(arp, NULL, 0, NULL, 0, obuf, (uint32_t)cap);
    uint32_t k;
    if (!n) break;
    for (k = 0; k < n; ++k) {
      fprintf(out, "{\"frame\": %lu, \"kind\": \"off\", \"key\": %u%s}\n",
              (unsigned long)start, obuf[k].a,
              FM1_MIDI_EV_SRC(obuf[k].b) == FM1_MIDI_SRC_SEQ ? ", \"seq\": 1" : "");
      ++n_off;
    }
    start += (uint32_t)block;
  }
  fm1_arp_get_stats(arp, &st);
  fprintf(out, "{\"summary\": {\"end\": %lu, \"ons\": %llu, \"offs\": %llu, \"sounding\": %u, "
               "\"held\": %u, \"held_seq\": %u, \"steps\": %lu, \"dropped_ons\": %lu, \"deferred_offs\": %lu, "
               "\"stolen\": %lu, \"size\": %u}}\n",
          end, n_on, n_off, fm1_arp_sounding(arp), fm1_arp_held(arp), fm1_arp_held_seq(arp),
          (unsigned long)st.steps,
          (unsigned long)st.dropped_ons, (unsigned long)st.deferred_offs, (unsigned long)st.stolen,
          (unsigned)fm1_arp_size());
  if (out != stdout) fclose(out);
  free(mem);
  free(ibuf);
  free(tbuf);
  free(obuf);
  free(g_ev);
  free(g_tick);
  return 0;
}
