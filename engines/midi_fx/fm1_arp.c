/* fm1_arp.c -- the arpeggiator core (fm1_arp.h; engines/midi_fx/README.md).
 *
 * After Yarns' Part (Emilie Gillet, MIT; pichenettes/eurorack 08460a6):
 * - the step loop, yarns/part.cc 366-446 (ClockArpeggiator): a rhythm step
 *   counter that runs on every step and reads one bit of a 16-step mask or a
 *   rotated Euclidean mask, and a note position that moves only on steps
 *   that play;
 * - the octave range walked as one list, turning at the ends (401-408): our
 *   OCT SPAN;
 * - gates counted in clock ticks, and a prescaler from ticks to steps
 *   (part.cc 241-260, Clock);
 * - latch and the hold pedal: released keys stay, and the next key drops
 *   them (part.cc 82-125, 159-167, 470-477; part.h 345-352);
 * - the held-key list after stmlib's NoteStack (algorithms/note_stack.h
 *   76-110 and 170-180 at pichenettes/stmlib e3bd7c9): a key pressed again
 *   moves to the newest place, and when the list is full the oldest goes.
 * The note orders follow MCL's ArpSeqTrack::render (Justin Mammarella,
 * BSD-3; jmamma/MCL 693a410, src/mcl/Drivers/Generic/Sequencer/
 * ArpSeqTrack.cpp 174-358), and RATE TRG its ARP_RATE_TRIG (122-138).
 * Seeded, step-locked random modifiers with a loop length follow Super Arp
 * (Handcrafted Media, MIT; handcraftedcc/schwung-superarp 6eefd02,
 * src/dsp/superarp.c 244-320 and 1380-1430). No upstream code is copied;
 * CREDITS.md holds their notices.
 *
 * MIT licence, like the rest of this repository.
 */
#include "fm1_arp.h"

#include <string.h>

#define H_DOWN 1u       /* the key is physically down */
#define H_PENDING 2u    /* JOIN 1: waits for the next pass */

#define S_OWED 1u       /* the note-off did not fit; it goes out next */
#define S_NEW 2u        /* started between ticks: the next tick does not count */
#define S_UNTIL_STEP 4u /* TRG with no measured step: ends at the next step */

#define ALL_KEYS 0xFFu  /* a cycle entry that plays the whole chord */

enum { SALT_PROB = 1, SALT_NOTE, SALT_JUMP, SALT_VEL, SALT_GATE, SALT_RATCHET, SALT_CHORD,
       SALT_WALK, SALT_OCT, SALT_SHUFFLE = 64 };

typedef struct { uint8_t key, vel, flags, pad; } held_t;
typedef struct { uint8_t key, flags; uint16_t left; } snd_t;
typedef struct { uint8_t idx, oct; } cyc_t;

struct fm1_arp {
  fm1_arp_stats_t stats;
  uint32_t step_count;      /* steps since the last restart */
  uint16_t p[FM1_ARP_P_COUNT];
  uint16_t ppqn;
  uint16_t st;              /* ticks into the current step */
  uint16_t step_len;        /* ticks in the current step (rate mode) */
  uint16_t trg_len;         /* measured ticks between steps (TRG); 0 unknown */
  uint16_t rstep;           /* the rhythm step */
  uint16_t rat_len;         /* the step length the ratchets divide; 0 unknown */
  uint8_t need_start, trg_seen, sustain, dirty, perm_stale;
  uint8_t heard;             /* the chord has played a step since it began */
  uint8_t n_held, n_ord, n_cyc, n_snd;
  uint8_t pos, rep, rep_oct, walk, repeat_cnt;
  uint8_t rat_n, rat_k, rat_count, rat_gate;
  cyc_t cur;
  held_t held[FM1_ARP_MAX_HELD];     /* oldest first */
  uint8_t ord[FM1_ARP_MAX_HELD];     /* the active keys in ORDER, as held[] indices */
  cyc_t cyc[FM1_ARP_MAX_CYCLE];      /* one pass of the note order */
  uint8_t perm[FM1_ARP_MAX_CYCLE];   /* SHUFFLE's order for this pass */
  uint8_t rat_key[FM1_ARP_MAX_HELD], rat_vel[FM1_ARP_MAX_HELD];
  snd_t snd[FM1_ARP_MAX_SOUNDING];   /* the ledger, oldest first */
};

typedef struct { fm1_arp_ev_t *ev; uint32_t cap, n; } out_t;

/* ---- Tables ------------------------------------------------------------------ */

static const fm1_arp_param_info_t kInfo[FM1_ARP_P_COUNT] = {
  {"mode", 0, FM1_ARP_MODE_COUNT - 1, FM1_ARP_MODE_UP},
  {"order", 0, FM1_ARP_ORDER_COUNT - 1, FM1_ARP_ORDER_PITCH},
  {"octaves", 1, FM1_ARP_MAX_OCTAVES, 1},
  {"oct_mode", 0, FM1_ARP_OCT_COUNT - 1, FM1_ARP_OCT_SPAN},
  {"rate", 0, FM1_ARP_RATE_COUNT - 1, 4},
  {"gate", 1, 200, 50},
  {"swing", 50, 80, 50},
  {"pattern", 0, 22, 0},
  {"euclid_len", 0, 32, 0},
  {"euclid_fill", 0, 32, 0},
  {"euclid_rotate", 0, 31, 0},
  {"latch", 0, 1, 0},
  {"join", 0, 1, 0},
  {"sync", 0, 1, 1},
  {"repeat", 1, 8, 1},
  {"ratchet", 1, 4, 1},
  {"ratchet_prob", 0, 100, 100},
  {"prob", 0, 100, 100},
  {"chord_prob", 0, 100, 0},
  {"oct_jump", 0, 100, 0},
  {"velocity", 0, 127, 0},
  {"vel_spread", 0, 127, 0},
  {"gate_spread", 0, 100, 0},
  {"loop", 0, 64, 0},
  {"seed", 0, 65535, 0},
};

static const char *const kModeNames[FM1_ARP_MODE_COUNT] = {
  "up", "down", "up-down", "down-up", "up&down", "down&up", "converge", "diverge",
  "conv-div", "thumb-up", "thumb-down", "pinky-up", "pinky-down", "up-top-oct",
  "down-low-oct", "up-alt-oct", "down-alt-oct", "crawl", "random", "shuffle", "walk", "chord",
};
static const char *const kOrderNames[FM1_ARP_ORDER_COUNT] = {"pitch", "played", "reverse"};
static const char *const kOctNames[FM1_ARP_OCT_COUNT] = {"span", "up", "down", "up-down", "random"};

/* Step lengths in ticks at 96 PPQN, all multiples of 4 so that 24 PPQN works. */
static const uint16_t kRateTicks96[FM1_ARP_RATE_COUNT] = {
  0, 8, 12, 16, 24, 32, 36, 48, 64, 72, 96, 128, 144, 192, 256, 288, 384,
};
static const char *const kRateNames[FM1_ARP_RATE_COUNT] = {
  "trg", "1/32t", "1/32", "1/16t", "1/16", "1/8t", "1/16d", "1/8", "1/4t", "1/8d", "1/4",
  "1/2t", "1/4d", "1/2", "1/1t", "1/2d", "1/1",
};

const fm1_arp_param_info_t *fm1_arp_param_info(unsigned id) {
  return id < FM1_ARP_P_COUNT ? &kInfo[id] : NULL;
}
const char *fm1_arp_mode_name(unsigned m) { return m < FM1_ARP_MODE_COUNT ? kModeNames[m] : NULL; }
const char *fm1_arp_order_name(unsigned o) { return o < FM1_ARP_ORDER_COUNT ? kOrderNames[o] : NULL; }
const char *fm1_arp_oct_mode_name(unsigned o) { return o < FM1_ARP_OCT_COUNT ? kOctNames[o] : NULL; }
const char *fm1_arp_rate_name(unsigned r) { return r < FM1_ARP_RATE_COUNT ? kRateNames[r] : NULL; }
uint16_t fm1_arp_rate_ticks96(unsigned r) { return r < FM1_ARP_RATE_COUNT ? kRateTicks96[r] : 0u; }

/* ---- Randomness ----------------------------------------------------------------
 * Counter-based: a draw is a pure function of (seed, salt, step), so a step's
 * draws repeat whenever its step index does (LOOP), and no draw depends on
 * how many came before it. A splitmix64 finalizer spreads the counter; the
 * output is one xorshift64* round, fm1_seq's generator (docs/13 R7). */
static uint32_t rnd(const fm1_arp_t *a, uint32_t step, uint32_t salt) {
  uint64_t x = ((uint64_t)a->p[FM1_ARP_P_SEED] << 48) ^ ((uint64_t)(salt & 0xFFFFu) << 32) ^ step;
  x += 0x9E3779B97F4A7C15ull;
  x = (x ^ (x >> 30)) * 0xBF58476D1CE4E5B9ull;
  x = (x ^ (x >> 27)) * 0x94D049BB133111EBull;
  x ^= x >> 31;
  if (!x) x = 0x9E3779B97F4A7C15ull;
  x ^= x >> 12;
  x ^= x << 25;
  x ^= x >> 27;
  return (uint32_t)((x * 0x2545F4914F6CDD1Dull) >> 32);
}

static int chance(const fm1_arp_t *a, unsigned pct, uint32_t mstep, uint32_t salt) {
  if (pct >= 100u) return 1;
  if (pct == 0u) return 0;
  return rnd(a, mstep, salt) % 100u < pct;
}

static int spread(const fm1_arp_t *a, unsigned amount, uint32_t mstep, uint32_t salt) {
  if (!amount) return 0;
  return (int)(rnd(a, mstep, salt) % (2u * amount + 1u)) - (int)amount;
}

/* ---- The ledger: every note-on sent has one note-off to come ------------------ */

static void put(out_t *o, uint16_t frame, uint8_t kind, uint8_t key, uint8_t vel) {
  fm1_arp_ev_t *e = &o->ev[o->n++];
  e->frame = frame;
  e->kind = kind;
  e->a = key;
  e->b = vel;
}

static void snd_remove(fm1_arp_t *a, unsigned i) {
  memmove(&a->snd[i], &a->snd[i + 1u], (size_t)(a->n_snd - i - 1u) * sizeof a->snd[0]);
  --a->n_snd;
}

/* 1: the note-off went out and the entry is gone; 0: it is owed. */
static int end_note(fm1_arp_t *a, unsigned i, uint16_t frame, out_t *o) {
  if (o->n < o->cap) {
    put(o, frame, FM1_ARP_EV_NOTE_OFF, a->snd[i].key, 0);
    snd_remove(a, i);
    return 1;
  }
  if (!(a->snd[i].flags & S_OWED)) {
    a->snd[i].flags |= S_OWED;
    ++a->stats.deferred_offs;
  }
  return 0;
}

static void flush_owed(fm1_arp_t *a, uint16_t frame, out_t *o) {
  unsigned i = 0;
  while (i < a->n_snd) {
    if (!(a->snd[i].flags & S_OWED)) ++i;
    else if (!end_note(a, i, frame, o)) return;
  }
}

/* Ends every note, or only those with one of `only` flags. */
static void end_all(fm1_arp_t *a, uint16_t frame, out_t *o, uint8_t only) {
  unsigned i = 0;
  while (i < a->n_snd) {
    if (only && !(a->snd[i].flags & only)) ++i;
    else if (!end_note(a, i, frame, o)) ++i;
  }
}

static void start_note(fm1_arp_t *a, uint8_t key, uint8_t vel, uint16_t left, uint8_t flags,
                       uint16_t frame, out_t *o) {
  unsigned i = 0;
  while (i < a->n_snd) {          /* the same key sounds: end it first */
    if (a->snd[i].key != key) {
      ++i;
    } else if (!end_note(a, i, frame, o)) {
      ++a->stats.dropped_ons;
      return;
    }
  }
  if (a->n_snd >= FM1_ARP_MAX_SOUNDING) {
    if (!end_note(a, 0, frame, o)) {
      ++a->stats.dropped_ons;
      return;
    }
    ++a->stats.stolen;
  }
  if (o->n >= o->cap) {
    ++a->stats.dropped_ons;
    return;
  }
  put(o, frame, FM1_ARP_EV_NOTE_ON, key, vel);
  a->snd[a->n_snd].key = key;
  a->snd[a->n_snd].flags = flags;
  a->snd[a->n_snd].left = left;
  ++a->n_snd;
}

/* One tick of every running gate. A note started at a tick ends `left` ticks
 * later, before that tick's step; one started between ticks starts counting
 * at the next tick. */
static void tick_gates(fm1_arp_t *a, uint16_t frame, out_t *o) {
  unsigned i;
  for (i = 0; i < a->n_snd; ++i) {
    snd_t *s = &a->snd[i];
    if (s->flags & S_NEW) s->flags &= (uint8_t)~S_NEW;
    else if (!(s->flags & (S_OWED | S_UNTIL_STEP)) && s->left) --s->left;
  }
  i = 0;
  while (i < a->n_snd) {
    const snd_t *s = &a->snd[i];
    if ((s->flags & (S_OWED | S_UNTIL_STEP)) || s->left) ++i;
    else if (!end_note(a, i, frame, o)) ++i;
  }
}

/* ---- The chord ---------------------------------------------------------------- */

static unsigned n_active(const fm1_arp_t *a) {
  unsigned i, n = 0;
  for (i = 0; i < a->n_held; ++i) n += !(a->held[i].flags & H_PENDING);
  return n;
}

static void held_remove(fm1_arp_t *a, unsigned i) {
  memmove(&a->held[i], &a->held[i + 1u], (size_t)(a->n_held - i - 1u) * sizeof a->held[0]);
  --a->n_held;
  a->dirty = 1;
}

static void drop_released(fm1_arp_t *a) {
  unsigned i = 0;
  while (i < a->n_held) {
    if (a->held[i].flags & H_DOWN) ++i;
    else held_remove(a, i);
  }
}

static void activate_pending(fm1_arp_t *a) {
  unsigned i;
  for (i = 0; i < a->n_held; ++i) {
    if (a->held[i].flags & H_PENDING) {
      a->held[i].flags &= (uint8_t)~H_PENDING;
      a->dirty = 1;
    }
  }
}

static void restart_position(fm1_arp_t *a) {
  a->heard = 0;
  a->pos = 0;
  a->rep = 0;
  a->walk = 0;
  a->repeat_cnt = 0;
  a->perm_stale = 1;
}

/* After keys leave: pending keys play at once if nothing else is left, and
 * an empty chord cancels the step's remaining ratchets. */
static void settle(fm1_arp_t *a) {
  if (!n_active(a)) {
    activate_pending(a);
    if (!n_active(a)) a->rat_n = 0;
  }
}

/* The pattern restarts: the next tick (or, in TRG, the next STEP) is step 0.
 * TRG's measured step length survives; RESET clears it too. */
static void restart_clock(fm1_arp_t *a) {
  a->need_start = 1;
  a->step_count = 0;
  a->rstep = 0;
  a->rat_n = 0;
  restart_position(a);
}

static void key_on(fm1_arp_t *a, uint8_t key, uint8_t vel) {
  unsigned i, empty;
  if (a->p[FM1_ARP_P_LATCH] && !a->sustain) drop_released(a);  /* Yarns: a new key drops the latched */
  empty = !n_active(a);
  for (i = 0; i < a->n_held; ++i) {
    if (a->held[i].key == key) {
      held_remove(a, i);
      break;
    }
  }
  if (a->n_held >= FM1_ARP_MAX_HELD) held_remove(a, 0);
  if (!n_active(a)) empty = 1;
  a->held[a->n_held].key = key;
  a->held[a->n_held].vel = vel;
  /* JOIN 1: a key waits for the next pass once the chord is playing; keys
   * that arrive before its first step (one chord, pressed together) join. */
  a->held[a->n_held].flags =
      (uint8_t)(H_DOWN | (a->p[FM1_ARP_P_JOIN] && !empty && a->heard ? H_PENDING : 0u));
  a->held[a->n_held].pad = 0;
  ++a->n_held;
  a->dirty = 1;
  if (empty) {
    restart_position(a);
    if (a->p[FM1_ARP_P_SYNC]) restart_clock(a);
  }
}

static void key_off(fm1_arp_t *a, uint8_t key) {
  unsigned i;
  for (i = 0; i < a->n_held; ++i) {
    if (a->held[i].key != key) continue;
    if (a->p[FM1_ARP_P_LATCH] || a->sustain) a->held[i].flags &= (uint8_t)~H_DOWN;
    else held_remove(a, i);
    break;
  }
  settle(a);
}

static void set_sustain(fm1_arp_t *a, unsigned on) {
  a->sustain = (uint8_t)(on != 0);
  if (!on && !a->p[FM1_ARP_P_LATCH]) {
    drop_released(a);
    settle(a);
  }
}

/* ---- One pass of the note order --------------------------------------------- */

static unsigned is_lift_mode(unsigned m) {
  return m >= FM1_ARP_MODE_UP_TOP_OCT && m <= FM1_ARP_MODE_DOWN_ALT_OCT;
}

/* The index sequence of mode `m` over a list of `n` entries (n >= 1). */
static unsigned order_indices(unsigned m, unsigned n, uint8_t *s) {
  unsigned c = 0, i, j;
  switch (m) {
    case FM1_ARP_MODE_DOWN:
      for (i = n; i-- > 0;) s[c++] = (uint8_t)i;
      break;
    case FM1_ARP_MODE_UP_DOWN:
      for (i = 0; i < n; ++i) s[c++] = (uint8_t)i;
      for (i = n - 1u; i-- > 1u;) s[c++] = (uint8_t)i;
      break;
    case FM1_ARP_MODE_DOWN_UP:
      for (i = n; i-- > 0;) s[c++] = (uint8_t)i;
      for (i = 1; i + 1u < n; ++i) s[c++] = (uint8_t)i;
      break;
    case FM1_ARP_MODE_UP_N_DOWN:
      for (i = 0; i < n; ++i) s[c++] = (uint8_t)i;
      for (i = n; i-- > 0;) s[c++] = (uint8_t)i;
      break;
    case FM1_ARP_MODE_DOWN_N_UP:
      for (i = n; i-- > 0;) s[c++] = (uint8_t)i;
      for (i = 0; i < n; ++i) s[c++] = (uint8_t)i;
      break;
    case FM1_ARP_MODE_CONVERGE:
    case FM1_ARP_MODE_DIVERGE:
    case FM1_ARP_MODE_CONV_DIV:
      for (j = 0; j < n; ++j) s[c++] = (uint8_t)((j & 1u) ? n - 1u - j / 2u : j / 2u);
      if (m == FM1_ARP_MODE_DIVERGE) {
        for (i = 0; i < n / 2u; ++i) {
          const uint8_t t = s[i];
          s[i] = s[n - 1u - i];
          s[n - 1u - i] = t;
        }
      } else if (m == FM1_ARP_MODE_CONV_DIV) {
        for (j = n - 1u; j-- > 1u;) s[c++] = s[j];  /* back out, ends once */
      }
      break;
    case FM1_ARP_MODE_THUMB_UP:
      if (n == 1u) s[c++] = 0;
      for (i = 1; i < n; ++i) { s[c++] = 0; s[c++] = (uint8_t)i; }
      break;
    case FM1_ARP_MODE_THUMB_DOWN:
      if (n == 1u) s[c++] = 0;
      for (i = n; i-- > 1u;) { s[c++] = 0; s[c++] = (uint8_t)i; }
      break;
    case FM1_ARP_MODE_PINKY_UP:
      if (n == 1u) s[c++] = 0;
      for (i = 0; i + 1u < n; ++i) { s[c++] = (uint8_t)i; s[c++] = (uint8_t)(n - 1u); }
      break;
    case FM1_ARP_MODE_PINKY_DOWN:
      if (n == 1u) s[c++] = 0;
      for (i = n - 1u; i-- > 0;) { s[c++] = (uint8_t)i; s[c++] = (uint8_t)(n - 1u); }
      break;
    case FM1_ARP_MODE_CRAWL:
      for (i = 0; i < n; ++i) {
        s[c++] = (uint8_t)i;
        if (i + 2u < n) s[c++] = (uint8_t)(i + 2u);
      }
      break;
    default:  /* UP, and the list that RANDOM, SHUFFLE and WALK draw from */
      for (i = 0; i < n; ++i) s[c++] = (uint8_t)i;
      break;
  }
  return c;
}

static unsigned rep_len(const fm1_arp_t *a) {
  const unsigned n = a->p[FM1_ARP_P_OCTAVES];
  switch (a->p[FM1_ARP_P_OCT_MODE]) {
    case FM1_ARP_OCT_UP:
    case FM1_ARP_OCT_DOWN: return n;
    case FM1_ARP_OCT_UP_DOWN: return n > 1u ? 2u * n - 2u : 1u;
    default: return 1u;
  }
}

static unsigned spans_octaves(const fm1_arp_t *a) {
  return a->p[FM1_ARP_P_OCT_MODE] == FM1_ARP_OCT_SPAN || is_lift_mode(a->p[FM1_ARP_P_MODE]);
}

/* The octave the current pass adds (OCT UP, DOWN, UP_DOWN, RANDOM). */
static unsigned pass_octave(const fm1_arp_t *a) {
  const unsigned n = a->p[FM1_ARP_P_OCTAVES], r = a->rep;
  if (spans_octaves(a)) return 0;
  switch (a->p[FM1_ARP_P_OCT_MODE]) {
    case FM1_ARP_OCT_UP: return r;
    case FM1_ARP_OCT_DOWN: return n - 1u - r;
    case FM1_ARP_OCT_UP_DOWN: return r < n ? r : 2u * n - 2u - r;
    case FM1_ARP_OCT_RANDOM: return a->rep_oct;
    default: return 0;
  }
}

static void rebuild(fm1_arp_t *a) {
  const unsigned mode = a->p[FM1_ARP_P_MODE], octs = a->p[FM1_ARP_P_OCTAVES];
  unsigned i, j, n = 0;
  a->dirty = 0;
  a->perm_stale = 1;
  a->repeat_cnt = 0;
  for (i = 0; i < a->n_held; ++i) {
    if (!(a->held[i].flags & H_PENDING)) a->ord[n++] = (uint8_t)i;
  }
  if (a->p[FM1_ARP_P_ORDER] == FM1_ARP_ORDER_PITCH) {        /* insertion sort by key */
    for (i = 1; i < n; ++i) {
      const uint8_t t = a->ord[i];
      for (j = i; j > 0 && a->held[a->ord[j - 1u]].key > a->held[t].key; --j) a->ord[j] = a->ord[j - 1u];
      a->ord[j] = t;
    }
  } else if (a->p[FM1_ARP_P_ORDER] == FM1_ARP_ORDER_REVERSE) {
    for (i = 0; i < n / 2u; ++i) {
      const uint8_t t = a->ord[i];
      a->ord[i] = a->ord[n - 1u - i];
      a->ord[n - 1u - i] = t;
    }
  }
  a->n_ord = (uint8_t)n;
  a->n_cyc = 0;
  if (n == 0) return;
  if (mode == FM1_ARP_MODE_CHORD) {
    const unsigned c = spans_octaves(a) ? octs : 1u;
    for (i = 0; i < c; ++i) {
      a->cyc[i].idx = ALL_KEYS;
      a->cyc[i].oct = (uint8_t)i;
    }
    a->n_cyc = (uint8_t)c;
  } else if (is_lift_mode(mode)) {
    /* MCL: the one-octave pass, then a copy per extra octave in which only
     * the last note (UPP, DOWNP) or every other note (UP2, DOWN2) is lifted. */
    const unsigned up = mode == FM1_ARP_MODE_UP_TOP_OCT || mode == FM1_ARP_MODE_UP_ALT_OCT;
    const unsigned top = mode == FM1_ARP_MODE_UP_TOP_OCT || mode == FM1_ARP_MODE_DOWN_LOW_OCT;
    unsigned c = 0, o;
    for (o = 0; o < octs; ++o) {
      for (i = 0; i < n; ++i) {
        const unsigned lift = top ? i == n - 1u : !(i & 1u);
        a->cyc[c].idx = a->ord[up ? i : n - 1u - i];
        a->cyc[c].oct = (uint8_t)(o && lift ? o : 0u);
        ++c;
      }
    }
    a->n_cyc = (uint8_t)c;
  } else {
    uint8_t seq[FM1_ARP_MAX_CYCLE];
    const unsigned m = spans_octaves(a) ? n * octs : n;
    const unsigned c = order_indices(mode, m, seq);
    for (i = 0; i < c; ++i) {
      a->cyc[i].idx = a->ord[seq[i] % n];
      a->cyc[i].oct = (uint8_t)(seq[i] / n);
    }
    a->n_cyc = (uint8_t)c;
  }
  if (a->pos >= a->n_cyc) a->pos = 0;
  if (a->walk >= a->n_cyc) a->walk = (uint8_t)(a->n_cyc - 1u);
  a->rep = (uint8_t)(a->rep % rep_len(a));
  if (a->rep_oct >= octs) a->rep_oct = 0;
}

static void make_perm(fm1_arp_t *a, uint32_t mstep) {
  unsigned i;
  for (i = 0; i < a->n_cyc; ++i) a->perm[i] = (uint8_t)i;
  for (i = a->n_cyc; i-- > 1u;) {     /* Fisher-Yates */
    const unsigned j = rnd(a, mstep, SALT_SHUFFLE + i) % (i + 1u);
    const uint8_t t = a->perm[i];
    a->perm[i] = a->perm[j];
    a->perm[j] = t;
  }
  a->perm_stale = 0;
}

static void pick(fm1_arp_t *a, uint32_t mstep) {
  const unsigned mode = a->p[FM1_ARP_P_MODE];
  if (a->pos == 0) {
    const unsigned octs = a->p[FM1_ARP_P_OCTAVES];
    a->rep_oct = (uint8_t)(a->p[FM1_ARP_P_OCT_MODE] == FM1_ARP_OCT_RANDOM && octs > 1u
                           ? rnd(a, mstep, SALT_OCT) % octs : 0u);
  }
  if (mode == FM1_ARP_MODE_SHUFFLE && (a->pos == 0 || a->perm_stale)) make_perm(a, mstep);
  switch (mode) {
    case FM1_ARP_MODE_RANDOM: a->cur = a->cyc[rnd(a, mstep, SALT_NOTE) % a->n_cyc]; break;
    case FM1_ARP_MODE_SHUFFLE: a->cur = a->cyc[a->perm[a->pos]]; break;
    case FM1_ARP_MODE_WALK: a->cur = a->cyc[a->walk]; break;
    default: a->cur = a->cyc[a->pos]; break;
  }
}

static void move(fm1_arp_t *a, uint32_t mstep) {
  if (++a->repeat_cnt < a->p[FM1_ARP_P_REPEAT]) return;
  a->repeat_cnt = 0;
  if (a->p[FM1_ARP_P_MODE] == FM1_ARP_MODE_WALK) {
    const unsigned n = a->n_cyc;
    if (n <= 1u) a->walk = 0;
    else if (a->walk == 0) a->walk = 1;
    else if (a->walk >= n - 1u) a->walk = (uint8_t)(n - 2u);
    else a->walk = (uint8_t)((rnd(a, mstep, SALT_WALK) & 1u) ? a->walk + 1u : a->walk - 1u);
  }
  if (++a->pos >= a->n_cyc) {      /* the pass is over */
    a->pos = 0;
    a->rep = (uint8_t)((a->rep + 1u) % rep_len(a));
    if (a->p[FM1_ARP_P_JOIN]) activate_pending(a);
  }
}

/* ---- Steps -------------------------------------------------------------------- */

static void play_sub(fm1_arp_t *a, unsigned k, uint16_t frame, out_t *o, unsigned in_tick) {
  uint16_t left = 0;
  uint8_t flags = in_tick ? 0u : S_NEW;
  unsigned i;
  if (a->rat_len) {
    const uint32_t p0 = (uint32_t)k * a->rat_len / a->rat_n;
    const uint32_t p1 = (uint32_t)(k + 1u) * a->rat_len / a->rat_n;
    uint32_t g = (p1 - p0) * a->rat_gate / 100u;
    if (g < 1u) g = 1u;
    if (g > 0xFFFFu) g = 0xFFFFu;
    left = (uint16_t)g;
  } else {
    flags |= S_UNTIL_STEP;
  }
  for (i = 0; i < a->rat_count; ++i) start_note(a, a->rat_key[i], a->rat_vel[i], left, flags, frame, o);
}

static void add_key(fm1_arp_t *a, const held_t *h, unsigned oct, int vel_off) {
  int key = h->key + 12 * (int)oct;
  int vel = a->p[FM1_ARP_P_VELOCITY] ? a->p[FM1_ARP_P_VELOCITY] : h->vel;
  while (key > 127) key -= 12;    /* Yarns: fold down by octaves */
  vel += vel_off;
  if (vel < 1) vel = 1;
  if (vel > 127) vel = 127;
  a->rat_key[a->rat_count] = (uint8_t)key;
  a->rat_vel[a->rat_count] = (uint8_t)vel;
  ++a->rat_count;
}

static void play_step(fm1_arp_t *a, uint32_t mstep, uint16_t len, uint16_t frame, out_t *o,
                      unsigned in_tick) {
  unsigned oct = a->cur.oct + pass_octave(a), r, i;
  int g, vel_off;
  if (chance(a, a->p[FM1_ARP_P_OCT_JUMP], mstep, SALT_JUMP)) ++oct;
  vel_off = spread(a, a->p[FM1_ARP_P_VEL_SPREAD], mstep, SALT_VEL);
  a->rat_count = 0;
  if (a->cur.idx == ALL_KEYS || chance(a, a->p[FM1_ARP_P_CHORD_PROB], mstep, SALT_CHORD)) {
    for (i = 0; i < a->n_ord; ++i) add_key(a, &a->held[a->ord[i]], oct, vel_off);
  } else {
    add_key(a, &a->held[a->cur.idx], oct, vel_off);
  }
  g = (int)a->p[FM1_ARP_P_GATE] + spread(a, a->p[FM1_ARP_P_GATE_SPREAD], mstep, SALT_GATE);
  if (g < 1) g = 1;
  if (g > 200) g = 200;
  r = a->p[FM1_ARP_P_RATCHET];
  if (r > 1u && !chance(a, a->p[FM1_ARP_P_RATCHET_PROB], mstep, SALT_RATCHET)) r = 1;
  if (r > len) r = len ? len : 1u;  /* each ratchet needs a tick of its own */
  a->rat_gate = (uint8_t)g;
  a->rat_len = len;
  a->rat_n = (uint8_t)r;
  a->rat_k = 1;
  play_sub(a, 0, frame, o, in_tick);
}

static unsigned rhythm_hit(fm1_arp_t *a) {
  const unsigned elen = a->p[FM1_ARP_P_EUCLID_LEN];
  const unsigned len = elen ? elen : 16u;
  const unsigned s = a->rstep % len;
  unsigned bit;
  uint32_t mask;
  if (elen) {
    mask = fm1_arp_euclid_mask(elen, a->p[FM1_ARP_P_EUCLID_FILL]);
    bit = (s + a->p[FM1_ARP_P_EUCLID_ROTATE]) % len;
  } else {
    mask = fm1_arp_pattern_mask(a->p[FM1_ARP_P_PATTERN]);
    bit = s;
  }
  a->rstep = (uint16_t)(s + 1u >= len ? 0u : s + 1u);
  return (mask >> bit) & 1u;
}

/* A step starts: at a tick (rate mode, in_tick 1) or at a STEP event (TRG). */
static void begin_step(fm1_arp_t *a, uint16_t frame, out_t *o, unsigned in_tick) {
  const unsigned loop = a->p[FM1_ARP_P_LOOP];
  uint32_t mstep;
  uint16_t len;
  end_all(a, frame, o, S_UNTIL_STEP);   /* also after a switch away from TRG */
  if (a->p[FM1_ARP_P_RATE] == FM1_ARP_RATE_TRG) {
    if (a->trg_seen && a->st) a->trg_len = a->st;
    a->trg_seen = 1;
    len = a->trg_len;
  } else {
    const unsigned base = (unsigned)kRateTicks96[a->p[FM1_ARP_P_RATE]] * a->ppqn / 96u;
    const unsigned d = (a->p[FM1_ARP_P_SWING] - 50u) * base / 60u;   /* docs/13 R6 */
    len = (uint16_t)((a->step_count & 1u) ? base - d : base + d);
    a->step_len = len;
    a->need_start = 0;
  }
  a->st = 0;
  a->rat_n = 0;
  if (loop && a->step_count && a->step_count % loop == 0u) {   /* a new pass too */
    restart_position(a);
    a->heard = 1;
    a->rstep = 0;
    if (a->p[FM1_ARP_P_JOIN]) activate_pending(a);
  }
  mstep = loop ? a->step_count % loop : a->step_count;
  if (a->dirty) rebuild(a);
  if (rhythm_hit(a) && a->n_cyc) {
    if (a->repeat_cnt == 0) pick(a, mstep);
    a->heard = 1;
    if (chance(a, a->p[FM1_ARP_P_PROB], mstep, SALT_PROB)) play_step(a, mstep, len, frame, o, in_tick);
    move(a, mstep);
  }
  ++a->step_count;
  ++a->stats.steps;
}

static void ratchet_due(fm1_arp_t *a, uint16_t frame, out_t *o) {
  if (a->rat_k < a->rat_n && a->st == (uint32_t)a->rat_k * a->rat_len / a->rat_n) {
    play_sub(a, a->rat_k, frame, o, 1);
    ++a->rat_k;
  }
}

/* A tick; `gated`: its gates already ran, for a STEP at its frame. */
static void on_tick(fm1_arp_t *a, uint16_t frame, out_t *o, unsigned gated) {
  flush_owed(a, frame, o);
  if (!gated) tick_gates(a, frame, o);
  if (a->p[FM1_ARP_P_RATE] != FM1_ARP_RATE_TRG && (a->need_start || a->st >= a->step_len)) {
    begin_step(a, frame, o, 1);
  } else {
    ratchet_due(a, frame, o);
  }
  if (a->st < 0xFFFFu) ++a->st;
}

/* ---- Parameters ---------------------------------------------------------------- */

void fm1_arp_set_param(fm1_arp_t *a, unsigned id, int value) {
  const fm1_arp_param_info_t *in = fm1_arp_param_info(id);
  uint16_t v, old;
  if (!a || !in) return;
  v = value < (int)in->min ? in->min : value > (int)in->max ? in->max : (uint16_t)value;
  old = a->p[id];
  a->p[id] = v;
  if (old == v) return;
  switch (id) {
    case FM1_ARP_P_MODE:
    case FM1_ARP_P_ORDER:
    case FM1_ARP_P_OCTAVES:
    case FM1_ARP_P_OCT_MODE:
      a->dirty = 1;
      break;
    case FM1_ARP_P_RATE:
      if ((old == FM1_ARP_RATE_TRG) != (v == FM1_ARP_RATE_TRG)) {
        a->need_start = 1;
        a->trg_seen = 0;
        a->trg_len = 0;
        a->rat_n = 0;
      }
      break;
    case FM1_ARP_P_LATCH:
      if (!v && !a->sustain) {
        drop_released(a);
        settle(a);
      }
      break;
    case FM1_ARP_P_JOIN:
      if (!v) activate_pending(a);
      break;
    default:
      break;
  }
}

int fm1_arp_get_param(const fm1_arp_t *a, unsigned id) {
  return a && id < FM1_ARP_P_COUNT ? a->p[id] : 0;
}

/* ---- Instance ------------------------------------------------------------------ */

size_t fm1_arp_size(void) { return sizeof(fm1_arp_t); }

fm1_arp_t *fm1_arp_create(void *mem, uint16_t ppqn) {
  fm1_arp_t *a = (fm1_arp_t *)mem;
  unsigned i;
  if (!a) return NULL;
  memset(a, 0, sizeof *a);
  a->ppqn = (ppqn == 24u || ppqn == 48u) ? ppqn : 96u;
  for (i = 0; i < FM1_ARP_P_COUNT; ++i) a->p[i] = kInfo[i].def;
  a->need_start = 1;
  a->perm_stale = 1;
  return a;
}

/* An input event; `gated`: a tick at its frame has run its gates (a STEP
 * there then starts its notes as a tick's step does). */
static void handle(fm1_arp_t *a, const fm1_arp_ev_t *e, out_t *o, unsigned gated) {
  flush_owed(a, e->frame, o);
  switch (e->kind) {
    case FM1_ARP_EV_NOTE_ON:
      if (e->a > 127u) break;
      if (e->b == 0u) key_off(a, e->a);
      else key_on(a, e->a, (uint8_t)(e->b > 127u ? 127u : e->b));
      break;
    case FM1_ARP_EV_NOTE_OFF:
      key_off(a, e->a);
      break;
    case FM1_ARP_EV_SUSTAIN:
      set_sustain(a, e->b);
      break;
    case FM1_ARP_EV_STEP:
      if (a->p[FM1_ARP_P_RATE] == FM1_ARP_RATE_TRG) begin_step(a, e->frame, o, gated);
      break;
    case FM1_ARP_EV_RESET:
      restart_clock(a);
      a->st = 0;
      a->trg_seen = 0;
      a->trg_len = 0;
      break;
    case FM1_ARP_EV_FLUSH:
      end_all(a, e->frame, o, 0);
      a->rat_n = 0;
      break;
    case FM1_ARP_EV_PANIC:
      end_all(a, e->frame, o, 0);
      a->n_held = 0;
      a->dirty = 1;
      a->rat_n = 0;
      break;
    case FM1_ARP_EV_PARAM:
      fm1_arp_set_param(a, e->a, e->b);
      break;
    default:
      break;
  }
}

uint32_t fm1_arp_process(fm1_arp_t *a, const fm1_arp_ev_t *in, uint32_t n_in,
                         const uint16_t *ticks, uint32_t n_ticks,
                         fm1_arp_ev_t *out, uint32_t cap) {
  out_t o;
  uint32_t i = 0, j = 0;
  unsigned gated = 0;   /* the next tick's gates have run */
  if (!a) return 0;
  if (!in) n_in = 0;
  if (!ticks) n_ticks = 0;
  o.ev = out;
  o.cap = out ? cap : 0u;
  o.n = 0;
  flush_owed(a, 0, &o);
  while (i < n_in || j < n_ticks) {
    if (i < n_in && (j >= n_ticks || in[i].frame <= ticks[j])) {
      /* A STEP on a tick's frame (TRG): that tick's gates first, so the
       * notes they end go before the step's, as at a rate's step. */
      if (in[i].kind == FM1_ARP_EV_STEP && a->p[FM1_ARP_P_RATE] == FM1_ARP_RATE_TRG && !gated &&
          j < n_ticks && in[i].frame == ticks[j]) {
        flush_owed(a, ticks[j], &o);
        tick_gates(a, ticks[j], &o);
        gated = 1;
      }
      handle(a, &in[i++], &o, gated);
    } else {
      on_tick(a, ticks[j++], &o, gated);
      gated = 0;
    }
  }
  return o.n;
}

unsigned fm1_arp_sounding(const fm1_arp_t *a) { return a ? a->n_snd : 0u; }
unsigned fm1_arp_held(const fm1_arp_t *a) { return a ? a->n_held : 0u; }

void fm1_arp_get_stats(const fm1_arp_t *a, fm1_arp_stats_t *st) {
  if (a && st) *st = a->stats;
}
