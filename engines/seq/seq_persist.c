/* seq_persist.c -- the `movy1` set format, export and import (R14).
 *
 * Derived from Movy's seq-core persist.rs (commit 9190e79, MIT, Copyright (c)
 * 2026 megadake). Byte-identical output for any set this core can hold, line
 * order and trailing spaces included; numbers are parsed with Rust's integer
 * rules (an optional '+', a '-' only for signed fields, no overflow).
 *
 * What a fixed-size core cannot hold is dropped on import and so missing
 * from a re-export: notes and locks past the pools or caps, locks and trig
 * rows on steps past 255 (inert in Movy: no playhead reaches them), lane
 * labels past FM1_SEQ_LABEL_MAX - 1 bytes, ticks and gates past 65,535, and
 * tracks past limits.tracks.
 *
 * FM-1 addition, written only outside compat mode and only when a track's
 * routing differs from the default (MIDI channel track+1):
 *   rt <track> <0 midi|1 engine> <channel|slot>
 * Movy ignores unknown lines, so such a set still loads there.
 */
#include "seq_int.h"

/* ---- Export ------------------------------------------------------------- */

typedef struct {
  char *buf;
  size_t cap, len;
} sink_t;

static void put(sink_t *k, const char *s, size_t n) {
  size_t i;
  for (i = 0; i < n; ++i) {
    if (k->len + 1 < k->cap) k->buf[k->len] = s[i];
    ++k->len;
  }
}

static void puts_(sink_t *k, const char *s) { put(k, s, strlen(s)); }

static void putu(sink_t *k, uint64_t v) {
  char tmp[24];
  size_t n = 0;
  do {
    tmp[sizeof(tmp) - 1 - n++] = (char)('0' + v % 10u);
    v /= 10u;
  } while (v);
  put(k, tmp + sizeof(tmp) - n, n);
}

static void puti(sink_t *k, int64_t v) {
  if (v < 0) {
    put(k, "-", 1);
    putu(k, (uint64_t)(-(v + 1)) + 1u);
  } else {
    putu(k, (uint64_t)v);
  }
}

size_t fm1_seq_export_movy1(const fm1_seq_t *s, char *buf, size_t cap) {
  sink_t k;
  unsigned t, lane, slot, i;
  const uint8_t *song = sq_csong(s);
  k.buf = buf;
  k.cap = buf ? cap : 0;
  k.len = 0;
  puts_(&k, "movy1\nbpm ");
  putu(&k, s->bpm_x100);
  puts_(&k, "\nswing ");
  putu(&k, s->swing_pct);
  puts_(&k, "\nlink ");
  putu(&k, s->link_enabled ? 1u : 0u);
  puts_(&k, "\n");
  if (s->song_len) {
    puts_(&k, "sg");
    for (i = 0; i < s->song_len; ++i) {
      puts_(&k, " ");
      putu(&k, song[i]);
    }
    puts_(&k, "\n");
  }
  for (t = 0; t < s->n_tracks; ++t) {
    const sq_track_t *tr = &sq_ctracks(s)[t];
    const uint8_t *pm = sq_cpmutes(s, t);
    puts_(&k, "tk "); putu(&k, t);
    puts_(&k, " "); putu(&k, tr->active);
    puts_(&k, " "); putu(&k, tr->muted ? 1u : 0u);
    puts_(&k, "\n");
    for (i = 0; i < tr->n_pad_mutes; ++i) {
      puts_(&k, "pm "); putu(&k, t); puts_(&k, " "); putu(&k, pm[i]); puts_(&k, "\n");
    }
    if (tr->pad_solo != SQ_NONE) {
      puts_(&k, "ps "); putu(&k, t); puts_(&k, " "); putu(&k, tr->pad_solo); puts_(&k, "\n");
    }
    for (lane = 0; lane < FM1_SEQ_LANES; ++lane) {
      if (!(tr->lanes_assigned & (1u << lane))) continue;
      puts_(&k, "au "); putu(&k, t);
      puts_(&k, " "); putu(&k, lane);
      puts_(&k, " "); putu(&k, tr->base[lane]);
      puts_(&k, " "); puts_(&k, tr->label[lane]);
      puts_(&k, "\n");
    }
    if (!s->lim.compat &&
        !(tr->route_kind == FM1_SEQ_ROUTE_MIDI && tr->route_index == (uint8_t)(t % 16u + 1u))) {
      puts_(&k, "rt "); putu(&k, t);
      puts_(&k, " "); putu(&k, tr->route_kind);
      puts_(&k, " "); putu(&k, tr->route_index);
      puts_(&k, "\n");
    }
    for (slot = 0; slot < FM1_SEQ_SLOTS; ++slot) {
      const sq_clip_t *c = sq_cclip(s, t, slot);
      if (sq_exists(c)) {
        const sq_note_t *n = &sq_cnotes(s)[c->seg[SQ_K_NOTES].off];
        puts_(&k, "cl "); putu(&k, t);
        puts_(&k, " "); putu(&k, slot);
        puts_(&k, " "); putu(&k, c->length_steps);
        puts_(&k, " "); putu(&k, c->loop_start);
        puts_(&k, " ");
        for (i = 0; i < c->seg[SQ_K_NOTES].len; ++i) {
          if (i) puts_(&k, ";");
          putu(&k, n[i].tick); puts_(&k, ":");
          putu(&k, n[i].gate); puts_(&k, ":");
          putu(&k, n[i].pitch); puts_(&k, ":");
          putu(&k, n[i].vel); puts_(&k, ":");
          putu(&k, SQ_NSTEP(&n[i]));
        }
        puts_(&k, "\ncp "); putu(&k, t);
        puts_(&k, " "); putu(&k, slot);
        puts_(&k, " "); putu(&k, c->scale_num);
        puts_(&k, " "); putu(&k, c->scale_den);
        puts_(&k, " "); puti(&k, c->transpose);
        puts_(&k, " "); putu(&k, c->quant);
        puts_(&k, "\n");
      }
      if (c->seg[SQ_K_LOCKS].len) {
        const sq_lock_t *l = &sq_clocks(s)[c->seg[SQ_K_LOCKS].off];
        puts_(&k, "lk "); putu(&k, t); puts_(&k, " "); putu(&k, slot); puts_(&k, " ");
        for (i = 0; i < c->seg[SQ_K_LOCKS].len; ++i) {
          if (i) puts_(&k, ";");
          putu(&k, l[i].lane); puts_(&k, ":");
          putu(&k, l[i].step); puts_(&k, ":");
          putu(&k, l[i].val);
        }
        puts_(&k, "\n");
      }
      if (c->seg[SQ_K_TRIGS].len) {
        const sq_trig_t *g = &sq_ctrigs(s)[c->seg[SQ_K_TRIGS].off];
        puts_(&k, "tg "); putu(&k, t); puts_(&k, " "); putu(&k, slot); puts_(&k, " ");
        for (i = 0; i < c->seg[SQ_K_TRIGS].len; ++i) {
          if (i) puts_(&k, ";");
          putu(&k, g[i].step); puts_(&k, ":");
          puti(&k, g[i].lane == SQ_NONE ? -1 : (int64_t)g[i].lane); puts_(&k, ":");
          putu(&k, g[i].prob_inv & 0x7Fu); puts_(&k, ":");
          putu(&k, g[i].a); puts_(&k, ":");
          putu(&k, g[i].b); puts_(&k, ":");
          putu(&k, g[i].prob_inv >> 7);
        }
        puts_(&k, "\n");
      }
    }
  }
  if (k.cap) k.buf[k.len < k.cap ? k.len : k.cap - 1] = '\0';
  return k.len;
}

/* ---- Import ------------------------------------------------------------- */

typedef struct {
  const char *p;
  size_t n;
} tok_t;

static int is_ws(char c) {
  return c == ' ' || c == '\t' || c == '\n' || c == '\v' || c == '\f' || c == '\r';
}

/* Rust's FromStr for an unsigned integer type whose largest value is `max`:
 * an optional '+', at least one digit, nothing else, and no overflow (a
 * '-', even on "-0", is an error). */
static int parse_u(tok_t t, uint64_t max, uint64_t *out) {
  size_t i = 0;
  uint64_t v = 0;
  if (t.n == 0) return 0;
  if (t.p[0] == '+') {
    i = 1;
    if (t.n == 1) return 0;
  }
  for (; i < t.n; ++i) {
    const unsigned d = (unsigned)(t.p[i] - '0');
    if (d > 9) return 0;
    if (v > max / 10u || (v == max / 10u && d > max % 10u)) return 0;
    v = v * 10u + d;
  }
  *out = v;
  return 1;
}

/* The same for a signed type whose range is [lo, hi], lo < 0. */
static int parse_i(tok_t t, int64_t lo, int64_t hi, int64_t *out) {
  uint64_t m;
  int neg = 0;
  if (t.n > 0 && (t.p[0] == '-' || t.p[0] == '+')) {
    neg = t.p[0] == '-';
    ++t.p;
    --t.n;
    if (t.n == 0 || t.p[0] == '+' || t.p[0] == '-') return 0;
  }
  if (!parse_u(t, neg ? (uint64_t)(-(lo + 1)) + 1u : (uint64_t)hi, &m)) return 0;
  *out = neg ? -(int64_t)m : (int64_t)m;
  return 1;
}

#define U8_MAX_ 255u
#define U16_MAX_ 65535u
#define U32_MAX_ 4294967295u
#define USIZE_MAX_ UINT64_MAX     /* Movy's usize: 64 bits on the Move (aarch64) */

/* split_whitespace over one line. */
typedef struct {
  const char *p, *end;
} words_t;

static int word(words_t *w, tok_t *t) {
  while (w->p < w->end && is_ws(*w->p)) ++w->p;
  if (w->p >= w->end) return 0;
  t->p = w->p;
  while (w->p < w->end && !is_ws(*w->p)) ++w->p;
  t->n = (size_t)(w->p - t->p);
  return 1;
}

static int word_u(words_t *w, uint64_t max, uint64_t *v) {
  tok_t t;
  return word(w, &t) && parse_u(t, max, v);
}

/* Splits t at the next `sep`, like str::split. Returns 0 when exhausted. */
static int split_next(tok_t *rest, char sep, int *done, tok_t *part) {
  size_t i = 0;
  if (*done) return 0;
  while (i < rest->n && rest->p[i] != sep) ++i;
  part->p = rest->p;
  part->n = i;
  if (i < rest->n) {
    rest->p += i + 1;
    rest->n -= i + 1;
  } else {
    *done = 1;
  }
  return 1;
}

static void load_clip(fm1_seq_t *s, words_t *w) {
  uint64_t t, slot, len, lstart;
  tok_t notes;
  unsigned clip;
  sq_clip_t *c;
  if (!word_u(w, USIZE_MAX_, &t) || !word_u(w, USIZE_MAX_, &slot) ||
      !word_u(w, U16_MAX_, &len) || !word_u(w, U16_MAX_, &lstart)) return;
  if (t >= s->n_tracks || slot >= 8) return;
  clip = sq_clip_no((unsigned)t, (unsigned)slot);
  sq_clip_reset(s, clip);
  if (word(w, &notes)) {
    int done = 0;
    tok_t note;
    while (split_next(&notes, ';', &done, &note)) {
      tok_t f[6];
      int nf = 0, fd = 0;
      uint64_t tick, gate, pitch, vel, step;
      while (nf < 6 && split_next(&note, ':', &fd, &f[nf])) ++nf;
      if (!fd) {
        tok_t extra;
        while (split_next(&note, ':', &fd, &extra)) ++nf;
      }
      if (nf < 4) continue;
      if (!parse_u(f[0], U32_MAX_, &tick) || !parse_u(f[1], U32_MAX_, &gate) ||
          !parse_u(f[2], U8_MAX_, &pitch) || !parse_u(f[3], U8_MAX_, &vel)) continue;
      if (nf < 5 || !parse_u(f[4], U16_MAX_, &step)) {
        step = (uint16_t)((tick + SQ_TPS / 2u) / SQ_TPS);
      }
      sq_clip_add_raw(s, clip, (uint16_t)step, (uint32_t)tick, gate < 1 ? 1u : (uint32_t)gate,
                      (uint8_t)(pitch > 127 ? 127 : pitch), (uint8_t)(vel < 1 ? 1 : (vel > 127 ? 127 : vel)));
    }
  }
  /* The saved window wins over what the notes extended. */
  c = &sq_clips(s)[clip];
  c->loop_start = (uint8_t)(lstart < SQ_MAX_STEPS - 1u ? lstart : SQ_MAX_STEPS - 1u);
  {
    const uint64_t max = SQ_MAX_STEPS - c->loop_start;
    c->length_steps = (uint16_t)(len < 1 ? 1 : (len > max ? max : len));
  }
  sq_clip_invalidate(s, clip);
}

static void load_locks(fm1_seq_t *s, words_t *w) {
  uint64_t t, slot;
  tok_t list, item;
  int done = 0;
  if (!word_u(w, USIZE_MAX_, &t) || !word_u(w, USIZE_MAX_, &slot)) return;
  if (t >= s->n_tracks || slot >= 8) return;
  if (!word(w, &list)) return;
  while (split_next(&list, ';', &done, &item)) {
    tok_t f[3], extra;
    int nf = 0, fd = 0;
    uint64_t lane, step, val;
    while (nf < 3 && split_next(&item, ':', &fd, &f[nf])) ++nf;
    if (!fd && split_next(&item, ':', &fd, &extra)) continue;   /* more than 3 fields */
    if (nf != 3) continue;
    /* Movy parses the value as a u8 and keeps min(127): widening
     * fm1_seq_val_t needs a format of its own, not a wider bound here. */
    if (!parse_u(f[0], U8_MAX_, &lane) || !parse_u(f[1], U16_MAX_, &step) ||
        !parse_u(f[2], U8_MAX_, &val)) continue;
    sq_clip_set_lock(s, sq_clip_no((unsigned)t, (unsigned)slot), (uint8_t)(lane & 7), (uint16_t)step,
                     (fm1_seq_val_t)(val > FM1_SEQ_VAL_MAX ? FM1_SEQ_VAL_MAX : val));
  }
}

static void load_trigs(fm1_seq_t *s, words_t *w) {
  uint64_t t, slot;
  tok_t list, item;
  int done = 0;
  if (!word_u(w, USIZE_MAX_, &t) || !word_u(w, USIZE_MAX_, &slot)) return;
  if (t >= s->n_tracks || slot >= 8) return;
  if (!word(w, &list)) return;
  while (split_next(&list, ';', &done, &item)) {
    tok_t f[6], extra;
    int nf = 0, fd = 0;
    uint64_t step, prob, a, b, inv;
    int64_t lane;
    unsigned clip;
    uint8_t l;
    while (nf < 6 && split_next(&item, ':', &fd, &f[nf])) ++nf;
    if (!fd && split_next(&item, ':', &fd, &extra)) continue;
    if (nf != 6) continue;
    if (!parse_u(f[0], U16_MAX_, &step) || !parse_i(f[1], -32768, 32767, &lane) ||
        !parse_u(f[2], U8_MAX_, &prob) || !parse_u(f[3], U8_MAX_, &a) ||
        !parse_u(f[4], U8_MAX_, &b) || !parse_u(f[5], U8_MAX_, &inv)) continue;
    clip = sq_clip_no((unsigned)t, (unsigned)slot);
    l = lane >= 0 && lane < 128 ? (uint8_t)lane : SQ_NONE;
    sq_clip_edit_trig(s, clip, (uint16_t)step, (uint16_t)step, l, SQ_TRIG_PROB,
                      (uint8_t)(prob > 100 ? 100 : prob), 0);
    sq_clip_edit_trig(s, clip, (uint16_t)step, (uint16_t)step, l, SQ_TRIG_COND,
                      (uint8_t)(a < 1 ? 1 : a), (uint8_t)(b < 1 ? 1 : b));
    sq_clip_edit_trig(s, clip, (uint16_t)step, (uint16_t)step, l, SQ_TRIG_INV, inv != 0, 0);
  }
}

static int line_is(tok_t t, const char *name) {
  return t.n == strlen(name) && memcmp(t.p, name, t.n) == 0;
}

int fm1_seq_import_movy1(fm1_seq_t *s, const char *txt, size_t len) {
  const char *p = txt, *end = txt + len, *eol;
  unsigned t, k;
  /* The first line, trimmed, must be the tag. */
  eol = p;
  while (eol < end && *eol != '\n') ++eol;
  {
    const char *a = p, *b = eol;
    while (a < b && is_ws(*a)) ++a;
    while (b > a && is_ws(b[-1])) --b;
    if ((size_t)(b - a) != 5 || memcmp(a, "movy1", 5) != 0) return 0;
  }
  p = eol < end ? eol + 1 : end;
  for (t = 0; t < s->n_tracks; ++t) {
    sq_track_t *tr = &sq_tracks(s)[t];
    for (k = 0; k < FM1_SEQ_SLOTS; ++k) sq_clip_clear(s, sq_clip_no(t, k));
    tr->active = 0;
    tr->muted = 0;
    tr->n_pad_mutes = 0;
    tr->pad_solo = SQ_NONE;
    tr->playing = SQ_NONE;
    tr->queued = SQ_NONE;
    tr->pending_stop = 0;
    tr->pending_select = SQ_NONE;
    tr->lanes_assigned = 0;
    memset(tr->base, 0, sizeof(tr->base));
    memset(tr->label, 0, sizeof(tr->label));
    tr->route_kind = FM1_SEQ_ROUTE_MIDI;
    tr->route_index = (uint8_t)(t % 16u + 1u);
  }
  s->link_enabled = 0;
  sq_clear_song(s);
  while (p < end) {
    words_t w;
    tok_t key;
    uint64_t a, b, c;
    eol = p;
    while (eol < end && *eol != '\n') ++eol;
    w.p = p;
    w.end = eol;
    p = eol < end ? eol + 1 : end;
    if (!word(&w, &key)) continue;
    if (line_is(key, "bpm")) {
      if (word_u(&w, U32_MAX_, &a)) sq_set_bpm(s, (uint32_t)a);
    } else if (line_is(key, "swing")) {
      if (word_u(&w, U32_MAX_, &a)) s->swing_pct = (uint32_t)(a < 50 ? 50 : (a > 80 ? 80 : a));
    } else if (line_is(key, "link")) {
      if (word_u(&w, U8_MAX_, &a)) s->link_enabled = a != 0;
    } else if (line_is(key, "sg")) {
      tok_t x;
      s->song_len = 0;
      while (word(&w, &x)) {
        if (parse_u(x, U8_MAX_, &a) && a < FM1_SEQ_SLOTS) {
          if (s->song_len < s->lim.song) sq_song(s)[s->song_len++] = (uint8_t)a;
          else ++s->stats.refused;
        }
      }
    } else if (line_is(key, "tk")) {
      /* Every token that parses, then exactly three of them. */
      uint64_t v[3];
      int n = 0;
      tok_t x;
      while (word(&w, &x)) {
        if (parse_u(x, USIZE_MAX_, &a)) {
          if (n < 3) v[n] = a;
          ++n;
        }
      }
      if (n == 3 && v[0] < s->n_tracks) {
        sq_tracks(s)[v[0]].active = (uint8_t)(v[1] < 7 ? v[1] : 7);
        sq_tracks(s)[v[0]].muted = v[2] != 0;
      }
    } else if (line_is(key, "pm")) {
      if (word_u(&w, USIZE_MAX_, &a) && word_u(&w, U8_MAX_, &b) && a < s->n_tracks && b < 128) {
        sq_set_pad_mute(s, (unsigned)a, (uint8_t)b, 1);
      }
    } else if (line_is(key, "ps")) {
      if (word_u(&w, USIZE_MAX_, &a) && word_u(&w, U8_MAX_, &b) && a < s->n_tracks && b < 128) {
        sq_tracks(s)[a].pad_solo = (uint8_t)b;
      }
    } else if (line_is(key, "cl")) {
      load_clip(s, &w);
    } else if (line_is(key, "cp")) {
      uint64_t sn, sd, q = 0;
      int64_t tr;
      tok_t x;
      if (word_u(&w, USIZE_MAX_, &a) && word_u(&w, USIZE_MAX_, &b) &&
          word_u(&w, U8_MAX_, &sn) && word_u(&w, U8_MAX_, &sd) &&
          word(&w, &x) && parse_i(x, -128, 127, &tr)) {
        if (!word_u(&w, U8_MAX_, &q)) q = 0;
        if (a < s->n_tracks && b < 8) {
          sq_clip_t *cl = sq_clip(s, (unsigned)a, (unsigned)b);
          cl->scale_num = (uint8_t)(sn < 1 ? 1 : sn);
          cl->scale_den = (uint8_t)(sd < 1 ? 1 : sd);
          sq_scale_limit(s, &cl->scale_num, &cl->scale_den);   /* D8 */
          cl->transpose = (int8_t)(tr < -36 ? -36 : (tr > 36 ? 36 : tr));
          cl->quant = (uint8_t)(q > 100 ? 100 : q);
          sq_clip_invalidate(s, sq_clip_no((unsigned)a, (unsigned)b));
        }
      }
    } else if (line_is(key, "au")) {
      tok_t label;
      if (word_u(&w, USIZE_MAX_, &a) && word_u(&w, USIZE_MAX_, &b) &&
          word_u(&w, U8_MAX_, &c) && a < s->n_tracks && b < 8) {
        sq_track_t *tr = &sq_tracks(s)[a];
        size_t m = 0;
        tr->lanes_assigned |= (uint8_t)(1u << b);
        tr->base[b] = (fm1_seq_val_t)c;
        if (word(&w, &label)) {
          m = label.n < FM1_SEQ_LABEL_MAX - 1u ? label.n : FM1_SEQ_LABEL_MAX - 1u;
          memcpy(tr->label[b], label.p, m);
        }
        tr->label[b][m] = '\0';
      }
    } else if (line_is(key, "lk")) {
      load_locks(s, &w);
    } else if (line_is(key, "tg")) {
      load_trigs(s, &w);
    } else if (line_is(key, "rt")) {
      if (word_u(&w, USIZE_MAX_, &a) && word_u(&w, U8_MAX_, &b) &&
          word_u(&w, U8_MAX_, &c) && a < s->n_tracks) {
        if (!fm1_seq_set_route(s, (uint8_t)a, (uint8_t)b, (uint8_t)c)) ++s->stats.refused;
      }
    }
  }
  /* A selected empty slot falls back to the track's lowest real clip. */
  for (t = 0; t < s->n_tracks; ++t) {
    sq_track_t *tr = &sq_tracks(s)[t];
    if (!sq_exists(sq_clip(s, t, tr->active))) {
      for (k = 0; k < FM1_SEQ_SLOTS; ++k) {
        if (sq_exists(sq_clip(s, t, k))) {
          tr->active = (uint8_t)k;
          break;
        }
      }
    }
  }
  sq_reseed_empty_clips(s);
  sq_invalidate_all(s);
  return 1;
}
