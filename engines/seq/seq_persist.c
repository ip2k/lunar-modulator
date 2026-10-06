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
 * FM-1 additions, written only outside compat mode and only when they differ
 * from the default, so a set that uses no FM-1 feature is byte-identical to
 * Movy's export:
 *   key <root 0..11> <scale>       the project key, when not C major (after link)
 *   dq <percent>                   the default quantize of new clips (after key)
 *   se <1 park|2 stop>             what the song does after its last entry (after sg)
 *   sn <scene> <name>              a scene's name, 1-6 printable characters (after se)
 *   rt <track> <0 midi|1 engine> <channel|slot>   a track's routing (after its au lines)
 * Movy ignores unknown lines, so such a set still loads there. Every
 * import reads `rt` and `key` (a set read without a `key` line is in C
 * major). Outside compat mode an import reads the rest, first resetting each to its default (a
 * set without `dq` has quantize 0, as Movy's own sets were made), and
 * reseeds the RNG (ST11); compat mode reads none of them, keeps the RNG
 * running and the default quantize as it was, as Movy's load does. `sg`
 * stays Movy's: the raw scene presses, past limits.song cut and counted.
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
  if (!s->lim.compat && (s->key_root || s->key_scale)) {
    puts_(&k, "key ");
    putu(&k, s->key_root);
    puts_(&k, " ");
    putu(&k, s->key_scale);
    puts_(&k, "\n");
  }
  if (!s->lim.compat && s->default_quant) {
    puts_(&k, "dq "); putu(&k, s->default_quant); puts_(&k, "\n");
  }
  if (s->song_len) {
    puts_(&k, "sg");
    for (i = 0; i < s->song_len; ++i) {
      puts_(&k, " ");
      putu(&k, song[i]);
    }
    puts_(&k, "\n");
  }
  if (!s->lim.compat) {
    if (s->song_end != FM1_SEQ_SONG_LOOP) {
      puts_(&k, "se "); putu(&k, s->song_end); puts_(&k, "\n");
    }
    for (slot = 0; slot < FM1_SEQ_SCENES; ++slot) {
      if (!s->scene_name[slot][0]) continue;
      puts_(&k, "sn "); putu(&k, slot); puts_(&k, " "); puts_(&k, s->scene_name[slot]);
      puts_(&k, "\n");
    }
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
/*
 * Streaming (2026-10-06, the state files' item stream: notes/2026-10-06-
 * state-files.md §6): the text arrives in pieces of any size and is read a
 * character at a time, so no line is ever held. A word is a run of
 * non-white-space (Rust's split_whitespace), numbers are read as they come
 * with Rust's integer rules (an optional '+', a '-' only for signed fields,
 * no overflow), and each line's words drive its handler as Movy's
 * persist::load does, line by line. Lists (a clip's notes, locks and trig
 * rows) are read item by item between ';' and ':'. The result is the same
 * set as reading the whole text at once, for every input: the tests feed
 * every set in pieces of every size and compare, and the line-at-a-time
 * importer this replaced (git history) was run against it on Movy's fixtures
 * and mutated sets.
 */

static int is_ws(char c) {
  return c == ' ' || c == '\t' || c == '\n' || c == '\v' || c == '\f' || c == '\r';
}

#define U8_MAX_ 255u
#define U16_MAX_ 65535u
#define U32_MAX_ 4294967295u
#define USIZE_MAX_ UINT64_MAX     /* Movy's usize: 64 bits on the Move (aarch64) */

enum { IM_TAG = 0, IM_BODY, IM_REFUSED };
enum {
  K_NONE = 0, K_OTHER, K_BPM, K_SWING, K_LINK, K_SG, K_TK, K_PM, K_PS, K_CL, K_CP, K_AU, K_LK, K_TG,
  K_RT, K_KEY, K_DQ, K_SE, K_SN
};

static void num_init(fm1_seq_num_t *x) { memset(x, 0, sizeof(*x)); }

static void num_ch(fm1_seq_num_t *x, char c) {
  unsigned d;
  if (x->n++ == 0 && (c == '+' || c == '-')) {
    x->sign = (uint8_t)c;
    return;
  }
  d = (unsigned)(c - '0');
  if (d > 9) {
    x->bad = 1;
    return;
  }
  x->digits = 1;
  if (!x->over) {
    if (x->v > (UINT64_MAX - d) / 10u) x->over = 1;
    else x->v = x->v * 10u + d;
  }
}

/* FromStr for an unsigned type whose largest value is `max`. */
static int num_u(const fm1_seq_num_t *x, uint64_t max, uint64_t *out) {
  if (x->bad || !x->digits || x->sign == '-' || x->over || x->v > max) return 0;
  *out = x->v;
  return 1;
}

/* The same for a signed type whose range is [lo, hi], lo < 0 (|lo| < 2^63). */
static int num_i(const fm1_seq_num_t *x, int64_t lo, int64_t hi, int64_t *out) {
  if (x->bad || !x->digits || x->over) return 0;
  if (x->sign == '-') {
    if (x->v > (uint64_t)(-(lo + 1)) + 1u) return 0;
    *out = -(int64_t)x->v;
  } else {
    if (x->v > (uint64_t)hi) return 0;
    *out = (int64_t)x->v;
  }
  return 1;
}

/* What an import resets once the first line has proved to be the tag. */
static void import_reset(fm1_seq_t *s) {
  unsigned t, k;
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
  s->key_root = 0;
  s->key_scale = 0;
  sq_clear_song(s);
  s->song_end = FM1_SEQ_SONG_LOOP;
  memset(s->scene_name, 0, sizeof s->scene_name);
  if (!s->lim.compat) {
    s->default_quant = 0;
    s->rng = SQ_RNG_INIT;      /* ST11: a loaded song plays the same each time */
  }
}

static unsigned key_of(const fm1_seq_import_t *im) {
  static const struct { const char *name; uint8_t key; } kKeys[] = {
    { "bpm", K_BPM }, { "swing", K_SWING }, { "link", K_LINK }, { "sg", K_SG }, { "tk", K_TK },
    { "pm", K_PM }, { "ps", K_PS }, { "cl", K_CL }, { "cp", K_CP }, { "au", K_AU }, { "lk", K_LK },
    { "tg", K_TG }, { "rt", K_RT }, { "key", K_KEY }, { "dq", K_DQ }, { "se", K_SE }, { "sn", K_SN },
  };
  size_t i;
  if (im->keylen > sizeof(im->keybuf)) return K_OTHER;
  for (i = 0; i < sizeof(kKeys) / sizeof(kKeys[0]); ++i) {
    if (strlen(kKeys[i].name) == im->keylen && memcmp(kKeys[i].name, im->keybuf, im->keylen) == 0) {
      /* Movy reads none of the FM-1 lines below rt. */
      if (im->s->lim.compat && kKeys[i].key >= K_DQ) return K_OTHER;
      return kKeys[i].key;
    }
  }
  return K_OTHER;
}

/* Whether word wi of this line is a list (notes, locks, trig rows). */
static int list_word(const fm1_seq_import_t *im) {
  return (im->key == K_CL && im->wi == 5) || ((im->key == K_LK || im->key == K_TG) && im->wi == 3);
}

/* ---- Lists: a clip's notes, locks and trig rows ---- */

static void field_end(fm1_seq_import_t *im) {
  static const uint64_t kNote[5] = { U32_MAX_, U32_MAX_, U8_MAX_, U8_MAX_, U16_MAX_ };
  static const uint64_t kLock[3] = { U8_MAX_, U16_MAX_, U8_MAX_ };
  static const uint64_t kTrig[6] = { U16_MAX_, 0, U8_MAX_, U8_MAX_, U8_MAX_, U8_MAX_ };
  const unsigned f = im->nf;
  if (im->nf < 255u) ++im->nf;
  if (f >= 6u) return;
  if (im->key == K_CL) {
    if (f < 5u) im->fok[f] = (uint8_t)num_u(&im->num, kNote[f], &im->fv[f]);
  } else if (im->key == K_LK) {
    if (f < 3u) im->fok[f] = (uint8_t)num_u(&im->num, kLock[f], &im->fv[f]);
  } else if (f == 1u) {                        /* a trig row's lane is signed */
    int64_t lane;
    im->fok[f] = (uint8_t)num_i(&im->num, -32768, 32767, &lane);
    im->fv[f] = (uint64_t)lane;
  } else {
    im->fok[f] = (uint8_t)num_u(&im->num, kTrig[f], &im->fv[f]);
  }
}

static void item_end(fm1_seq_import_t *im) {
  fm1_seq_t *s = im->s;
  const unsigned nf = im->nf;
  const uint64_t *v = im->fv;
  const uint8_t *ok = im->fok;
  if (im->key == K_CL) {
    uint64_t step;
    if (nf < 4u || !ok[0] || !ok[1] || !ok[2] || !ok[3]) return;
    step = nf >= 5u && ok[4] ? v[4] : (uint16_t)((v[0] + SQ_TPS / 2u) / SQ_TPS);
    sq_clip_add_raw(s, im->clip, (uint16_t)step, (uint32_t)v[0], v[1] < 1 ? 1u : (uint32_t)v[1],
                    (uint8_t)(v[2] > 127 ? 127 : v[2]), (uint8_t)(v[3] < 1 ? 1 : (v[3] > 127 ? 127 : v[3])));
  } else if (im->key == K_LK) {
    /* Movy parses the value as a u8 and keeps min(127): widening
     * fm1_seq_val_t needs a format of its own, not a wider bound here. */
    if (nf != 3u || !ok[0] || !ok[1] || !ok[2]) return;
    sq_clip_set_lock(s, im->clip, (uint8_t)(v[0] & 7), (uint16_t)v[1],
                     (fm1_seq_val_t)(v[2] > FM1_SEQ_VAL_MAX ? FM1_SEQ_VAL_MAX : v[2]));
  } else {
    const int64_t lane = (int64_t)v[1];
    uint8_t l;
    if (nf != 6u || !ok[0] || !ok[1] || !ok[2] || !ok[3] || !ok[4] || !ok[5]) return;
    l = lane >= 0 && lane < 128 ? (uint8_t)lane : SQ_NONE;
    sq_clip_edit_trig(s, im->clip, (uint16_t)v[0], (uint16_t)v[0], l, SQ_TRIG_PROB,
                      (uint8_t)(v[2] > 100 ? 100 : v[2]), 0);
    sq_clip_edit_trig(s, im->clip, (uint16_t)v[0], (uint16_t)v[0], l, SQ_TRIG_COND,
                      (uint8_t)(v[3] < 1 ? 1 : v[3]), (uint8_t)(v[4] < 1 ? 1 : v[4]));
    sq_clip_edit_trig(s, im->clip, (uint16_t)v[0], (uint16_t)v[0], l, SQ_TRIG_INV, v[5] != 0, 0);
  }
}

static void item_begin(fm1_seq_import_t *im) {
  im->nf = 0;
  memset(im->fok, 0, sizeof(im->fok));
  num_init(&im->num);
}

/* ---- Words ---- */

static void word_begin(fm1_seq_import_t *im) {
  im->in_word = 1;
  im->wi = im->words;
  if (im->words < 255u) ++im->words;
  if (im->wi == 0) {
    im->keylen = 0;
    return;
  }
  num_init(&im->num);
  im->text_n = 0;
  if (!im->dead && im->ok_list && list_word(im)) item_begin(im);
}

static void word_char(fm1_seq_import_t *im, char c) {
  if (im->wi == 0) {
    if (im->keylen < sizeof(im->keybuf)) im->keybuf[im->keylen] = c;
    if (im->keylen <= sizeof(im->keybuf)) ++im->keylen;
    return;
  }
  if (im->dead) return;
  switch (im->key) {
    case K_CL: case K_LK: case K_TG:
      if (list_word(im)) {
        if (!im->ok_list) return;
        if (c == ':') { field_end(im); num_init(&im->num); }
        else if (c == ';') { field_end(im); item_end(im); item_begin(im); }
        else num_ch(&im->num, c);
        return;
      }
      break;
    case K_AU:
      if (im->wi == 4) {
        if (im->ok_list && im->text_n < FM1_SEQ_LABEL_MAX - 1u) {
          sq_track_t *tr = &sq_tracks(im->s)[im->lv[0]];
          tr->label[im->lv[1]][im->text_n++] = c;
          tr->label[im->lv[1]][im->text_n] = '\0';
        }
        return;
      }
      break;
    case K_SN:
      if (im->wi == 2) {
        if (im->text_n < FM1_SEQ_SCENE_NAME_MAX) im->text[im->text_n] = c;
        if (im->text_n < 255u) ++im->text_n;
        return;
      }
      break;
    case K_NONE: case K_OTHER:
      return;
    default:
      break;
  }
  num_ch(&im->num, c);
}

/* The word just read as an unsigned value into lv[i]; a failure ends the
 * line's handler, as a failed word_u ends Movy's. */
static int word_u(fm1_seq_import_t *im, unsigned i, uint64_t max) {
  if (!num_u(&im->num, max, &im->lv[i])) {
    im->dead = 1;
    return 0;
  }
  return 1;
}

static void word_end(fm1_seq_import_t *im) {
  fm1_seq_t *s = im->s;
  const unsigned wi = im->wi;
  uint64_t a;
  im->in_word = 0;
  if (wi == 0) {
    im->key = (uint8_t)key_of(im);
    if (im->key == K_SG) s->song_len = 0;
    return;
  }
  if (im->dead) return;
  switch (im->key) {
    case K_BPM:
      if (wi == 1 && num_u(&im->num, U32_MAX_, &a)) sq_set_bpm(s, (uint32_t)a);
      break;
    case K_SWING:
      if (wi == 1 && num_u(&im->num, U32_MAX_, &a)) s->swing_pct = (uint32_t)(a < 50 ? 50 : (a > 80 ? 80 : a));
      break;
    case K_LINK:
      if (wi == 1 && num_u(&im->num, U8_MAX_, &a)) s->link_enabled = a != 0;
      break;
    case K_SG:
      if (num_u(&im->num, U8_MAX_, &a) && a < FM1_SEQ_SLOTS) {
        if (s->song_len < s->lim.song) sq_song(s)[s->song_len++] = (uint8_t)a;
        else ++s->stats.refused;
      }
      break;
    case K_TK:
      /* Every token that parses, then exactly three of them. */
      if (num_u(&im->num, USIZE_MAX_, &a)) {
        if (im->n_tk < 3u) im->lv[im->n_tk] = a;
        if (im->n_tk < 255u) ++im->n_tk;
      }
      break;
    case K_PM: case K_PS:
      if (wi == 1) {
        word_u(im, 0, USIZE_MAX_);
      } else if (wi == 2 && word_u(im, 1, U8_MAX_) && im->lv[0] < s->n_tracks && im->lv[1] < 128) {
        if (im->key == K_PM) sq_set_pad_mute(s, (unsigned)im->lv[0], (uint8_t)im->lv[1], 1);
        else sq_tracks(s)[im->lv[0]].pad_solo = (uint8_t)im->lv[1];
      }
      break;
    case K_CL:
      if (wi <= 4) {
        static const uint64_t kMax[4] = { USIZE_MAX_, USIZE_MAX_, U16_MAX_, U16_MAX_ };
        if (!word_u(im, wi - 1u, kMax[wi - 1u]) || wi < 4) break;
        if (im->lv[0] >= s->n_tracks || im->lv[1] >= 8) { im->dead = 1; break; }
        im->clip = (uint16_t)sq_clip_no((unsigned)im->lv[0], (unsigned)im->lv[1]);
        sq_clip_reset(s, im->clip);
        im->ok_list = 1;
      } else if (wi == 5 && im->ok_list) {
        field_end(im);
        item_end(im);
      }
      break;
    case K_LK: case K_TG:
      if (wi <= 2) {
        if (!word_u(im, wi - 1u, USIZE_MAX_) || wi < 2) break;
        if (im->lv[0] >= s->n_tracks || im->lv[1] >= 8) { im->dead = 1; break; }
        im->clip = (uint16_t)sq_clip_no((unsigned)im->lv[0], (unsigned)im->lv[1]);
        im->ok_list = 1;
      } else if (wi == 3 && im->ok_list) {
        field_end(im);
        item_end(im);
      }
      break;
    case K_CP:
      if (wi <= 4) {
        static const uint64_t kMax[4] = { USIZE_MAX_, USIZE_MAX_, U8_MAX_, U8_MAX_ };
        word_u(im, wi - 1u, kMax[wi - 1u]);
      } else if (wi == 5) {
        int64_t tr;
        if (num_i(&im->num, -128, 127, &tr)) {
          im->lv[4] = (uint64_t)tr;
          im->ok_list = 1;                       /* the five words cp needs are in */
        } else {
          im->dead = 1;
        }
      } else if (wi == 6) {
        if (!num_u(&im->num, U8_MAX_, &im->lv[5])) im->lv[5] = 0;
      }
      break;
    case K_AU:
      if (wi <= 3) {
        static const uint64_t kMax[3] = { USIZE_MAX_, USIZE_MAX_, U8_MAX_ };
        if (!word_u(im, wi - 1u, kMax[wi - 1u]) || wi < 3) break;
        if (im->lv[0] >= s->n_tracks || im->lv[1] >= 8) { im->dead = 1; break; }
        {
          sq_track_t *tr = &sq_tracks(s)[im->lv[0]];
          tr->lanes_assigned |= (uint8_t)(1u << im->lv[1]);
          tr->base[im->lv[1]] = (fm1_seq_val_t)im->lv[2];
          tr->label[im->lv[1]][0] = '\0';
        }
        im->ok_list = 1;                         /* word 4, if any, is its label */
      }
      break;
    case K_RT:
      if (wi <= 3) {
        static const uint64_t kMax[3] = { USIZE_MAX_, U8_MAX_, U8_MAX_ };
        if (!word_u(im, wi - 1u, kMax[wi - 1u]) || wi < 3) break;
        if (im->lv[0] < s->n_tracks &&
            !fm1_seq_set_route(s, (uint8_t)im->lv[0], (uint8_t)im->lv[1], (uint8_t)im->lv[2])) {
          ++s->stats.refused;
        }
      }
      break;
    case K_KEY:
      if (wi == 1) {
        word_u(im, 0, U8_MAX_);
      } else if (wi == 2 && word_u(im, 1, U8_MAX_)) {
        fm1_seq_set_key(s, (unsigned)im->lv[0], (unsigned)im->lv[1]);
      }
      break;
    case K_DQ:
      if (wi == 1 && num_u(&im->num, U8_MAX_, &a)) s->default_quant = (uint8_t)(a > 100 ? 100 : a);
      break;
    case K_SE:
      if (wi == 1 && num_u(&im->num, U8_MAX_, &a) && a <= FM1_SEQ_SONG_STOP) s->song_end = (uint8_t)a;
      break;
    case K_SN:
      if (wi == 1) {
        if (!word_u(im, 0, U8_MAX_) || im->lv[0] >= FM1_SEQ_SCENES) im->dead = 1;
      } else if (wi == 2) {
        sq_scene_set_name(s, (unsigned)im->lv[0], im->text,
                          im->text_n < FM1_SEQ_SCENE_NAME_MAX ? im->text_n : FM1_SEQ_SCENE_NAME_MAX);
      }
      break;
    default:
      break;
  }
}

static void line_end(fm1_seq_import_t *im) {
  fm1_seq_t *s = im->s;
  if (!im->dead) {
    if (im->key == K_TK) {
      if (im->n_tk == 3u && im->lv[0] < s->n_tracks) {
        sq_tracks(s)[im->lv[0]].active = (uint8_t)(im->lv[1] < 7 ? im->lv[1] : 7);
        sq_tracks(s)[im->lv[0]].muted = im->lv[2] != 0;
      }
    } else if (im->key == K_CL && im->ok_list) {
      /* The saved window wins over what the notes extended. */
      sq_clip_t *c = &sq_clips(s)[im->clip];
      c->loop_start = (uint8_t)(im->lv[3] < SQ_MAX_STEPS - 1u ? im->lv[3] : SQ_MAX_STEPS - 1u);
      {
        const uint64_t max = SQ_MAX_STEPS - c->loop_start;
        c->length_steps = (uint16_t)(im->lv[2] < 1 ? 1 : (im->lv[2] > max ? max : im->lv[2]));
      }
      sq_clip_invalidate(s, im->clip);
    } else if (im->key == K_CP && im->ok_list) {
      const uint64_t a = im->lv[0], b = im->lv[1], sn = im->lv[2], sd = im->lv[3];
      const int64_t tr = (int64_t)im->lv[4];
      const uint64_t q = im->words > 6u ? im->lv[5] : 0u;
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
  }
  im->key = K_NONE;
  im->words = 0;
  im->wi = 0;
  im->dead = 0;
  im->ok_list = 0;
  im->n_tk = 0;
}

/* ---- The tag line, and the calls ---- */

void fm1_seq_import_begin(fm1_seq_import_t *im, fm1_seq_t *s) {
  memset(im, 0, sizeof(*im));
  im->s = s;
  im->state = IM_TAG;
}

static void tag_char(fm1_seq_import_t *im, char c) {
  if (c == '\n') {
    if (im->tag == 5u) {
      import_reset(im->s);
      im->state = IM_BODY;
    } else {
      im->state = IM_REFUSED;
    }
    return;
  }
  if (is_ws(c)) {
    if (im->tag != 0u && im->tag != 5u) im->tag = 0xFFu;   /* white space inside the tag */
    return;
  }
  if (im->tag < 5u && c == "movy1"[im->tag]) ++im->tag;
  else im->tag = 0xFFu;
}

int fm1_seq_import_feed(fm1_seq_import_t *im, const char *txt, size_t len) {
  size_t i;
  for (i = 0; i < len && im->state != IM_REFUSED; ++i) {
    const char c = txt[i];
    if (im->state == IM_TAG) {
      tag_char(im, c);
      continue;
    }
    if (c == '\n') {
      if (im->in_word) word_end(im);
      line_end(im);
    } else if (is_ws(c)) {
      if (im->in_word) word_end(im);
    } else {
      if (!im->in_word) word_begin(im);
      word_char(im, c);
    }
  }
  return im->state != IM_REFUSED;
}

int fm1_seq_import_end(fm1_seq_import_t *im) {
  fm1_seq_t *s = im->s;
  unsigned t, k;
  if (im->state == IM_TAG) {
    if (im->tag != 5u) return 0;
    import_reset(s);
    im->state = IM_BODY;
  } else if (im->state != IM_BODY) {
    return 0;
  } else {
    if (im->in_word) word_end(im);
    line_end(im);
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
  im->state = IM_REFUSED;     /* spent */
  return 1;
}

int fm1_seq_import_movy1(fm1_seq_t *s, const char *txt, size_t len) {
  fm1_seq_import_t im;
  fm1_seq_import_begin(&im, s);
  fm1_seq_import_feed(&im, txt, len);
  return fm1_seq_import_end(&im);
}
